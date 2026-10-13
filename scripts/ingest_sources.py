"""Load local TLC snapshots into DuckDB, once per logical source version."""
import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TRIP_TYPES = {
    "tpep_pickup_datetime": "TIMESTAMP",
    "tpep_dropoff_datetime": "TIMESTAMP",
    "PULocationID": "INTEGER",
    "DOLocationID": "INTEGER",
    "trip_distance": "DOUBLE",
    "fare_amount": "DOUBLE",
    "total_amount": "DOUBLE",
}
RESERVED = {"source_month", "source_sha256", "source_row_number", "trip_id",
            "file_row_number"}


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def fingerprint(path):
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return sha, path.stat().st_size


def initialize(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS meta")
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta.loaded_sources (
            partition_key VARCHAR PRIMARY KEY,
            source_kind VARCHAR NOT NULL,
            source_month VARCHAR,
            source_file VARCHAR NOT NULL,
            source_url VARCHAR NOT NULL,
            source_sha256 VARCHAR NOT NULL,
            source_bytes BIGINT NOT NULL,
            source_schema JSON NOT NULL,
            row_count BIGINT NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta.load_history (
            event_id VARCHAR PRIMARY KEY,
            partition_key VARCHAR NOT NULL,
            previous_sha256 VARCHAR,
            source_sha256 VARCHAR NOT NULL,
            row_count BIGINT NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
        )
    """)


def existing_count(con, kind, month):
    if kind == "trips":
        return con.execute(
            "SELECT count(*) FROM raw.trips WHERE source_month = ?", [month]
        ).fetchone()[0]
    return con.execute("SELECT count(*) FROM raw.zones").fetchone()[0]


def record_load(con, key, kind, month, path, url, sha, size, schema, rows, old_sha):
    con.execute("DELETE FROM meta.loaded_sources WHERE partition_key = ?", [key])
    con.execute("""
        INSERT INTO meta.loaded_sources (
            partition_key, source_kind, source_month, source_file,
            source_url, source_sha256, source_bytes, source_schema, row_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [key, kind, month, path.name, url, sha, size, json.dumps(schema), rows])
    con.execute("""
        INSERT INTO meta.load_history (
            event_id, partition_key, previous_sha256, source_sha256, row_count
        ) VALUES (?, ?, ?, ?, ?)
    """, [str(uuid.uuid4()), key, old_sha, sha, rows])


def load_one(con, path, url, month=None, replace_changed=False):
    kind = "trips" if month is not None else "zones"
    key = f"yellow:{month}" if month is not None else "taxi_zones"
    sha, size = fingerprint(path)
    old = con.execute("""
        SELECT source_sha256, row_count FROM meta.loaded_sources
        WHERE partition_key = ?
    """, [key]).fetchone()
    if old and old[0] == sha:
        actual = existing_count(con, kind, month)
        if actual != old[1]:
            raise ValueError(f"{key}: registered {old[1]} rows but found {actual}; "
                             "investigate database integrity before proceeding")
        return {"partition": key, "action": "skipped", "rows": actual, "sha256": sha}
    if old and not replace_changed:
        raise ValueError(f"{key}: source bytes changed. Review the new source first; "
                         "use --replace-changed to replace the active partition.")

    con.execute("BEGIN TRANSACTION")
    try:
        if kind == "trips":
            schema = con.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
            ).fetchall()
            names = {r[0] for r in schema}
            missing = set(TRIP_TYPES) - names
            if missing:
                raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
            if {n.lower() for n in names} & RESERVED:
                raise ValueError("Source collides with reserved provenance column names")
            casts = ", ".join(
                f"CAST({quote_identifier(n)} AS {t}) AS {quote_identifier(n)}"
                for n, t in TRIP_TYPES.items()
            )
            # file_row_number is the physical zero-based ordinal supplied by
            # the Parquet reader, independent of parallel output row order.
            con.execute(f"""
                CREATE OR REPLACE TEMP TABLE incoming AS
                SELECT ?::VARCHAR AS source_month,
                       ?::VARCHAR AS source_sha256,
                       file_row_number::BIGINT AS source_row_number,
                       sha256(? || ':' || file_row_number::VARCHAR) AS trip_id,
                       * EXCLUDE (file_row_number) REPLACE ({casts})
                FROM read_parquet(?, file_row_number = true)
            """, [month, sha, key + ":" + sha, str(path)])
            rows, distinct_rows, first, last = con.execute("""
                SELECT count(*), count(DISTINCT source_row_number),
                       min(source_row_number), max(source_row_number)
                FROM incoming
            """).fetchone()
            if rows != distinct_rows or (rows and (first != 0 or last != rows - 1)):
                raise ValueError("Physical source ordinals are not contiguous/unique")
            con.execute("CREATE TABLE IF NOT EXISTS raw.trips AS "
                        "SELECT * FROM incoming WHERE false")
            existing = {r[0].lower() for r in con.execute("DESCRIBE raw.trips").fetchall()}
            for name, sql_type, *_ in con.execute("DESCRIBE incoming").fetchall():
                if name.lower() not in existing:
                    con.execute(f"ALTER TABLE raw.trips ADD COLUMN "
                                f"{quote_identifier(name)} {sql_type}")
            con.execute("DELETE FROM raw.trips WHERE source_month = ?", [month])
            # BY NAME accommodates additional columns and null-fills columns
            # absent from this source. Incompatible conversions fail strictly.
            con.execute("INSERT INTO raw.trips BY NAME SELECT * FROM incoming")
        else:
            schema = con.execute(
                "DESCRIBE SELECT * FROM read_csv_auto(?, all_varchar = true)",
                [str(path)],
            ).fetchall()
            names = {r[0] for r in schema}
            required = {"LocationID", "Borough", "Zone", "service_zone"}
            if required - names:
                raise ValueError(f"Zone columns missing: {sorted(required - names)}")
            if {n.lower() for n in names} & RESERVED:
                raise ValueError("Zone source collides with provenance column names")
            con.execute("""
                CREATE OR REPLACE TEMP TABLE incoming AS
                SELECT ?::VARCHAR AS source_sha256,
                       * REPLACE (CAST(LocationID AS INTEGER) AS LocationID)
                FROM read_csv_auto(?, all_varchar = true)
            """, [sha, str(path)])
            rows, unique_keys, null_keys = con.execute("""
                SELECT count(*), count(DISTINCT LocationID),
                       count(*) FILTER (WHERE LocationID IS NULL)
                FROM incoming
            """).fetchone()
            if not rows or rows != unique_keys or null_keys:
                raise ValueError("Zone IDs must be unique/non-null and lookup nonempty")
            con.execute("CREATE OR REPLACE TABLE raw.zones AS SELECT * FROM incoming")

        if existing_count(con, kind, month) != rows:
            raise ValueError("Source-to-warehouse row reconciliation failed")
        # Protect against a local file changing while it was being read.
        if fingerprint(path) != (sha, size):
            raise ValueError("Source bytes changed during ingestion; load rolled back")
        schema_json = [{"column": r[0], "type": r[1]} for r in schema]
        record_load(con, key, kind, month, path, url, sha, size, schema_json,
                    rows, old[0] if old else None)
        con.execute("DROP TABLE incoming")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"partition": key, "action": "replaced" if old else "loaded",
            "rows": rows, "sha256": sha}


def ingest(database, raw_dir, config, months=None, replace_changed=False,
           memory_limit="2GB"):
    database, raw_dir = Path(database), Path(raw_dir)
    months = list(config["months"] if months is None else months)
    if not months or len(months) != len(set(months)):
        raise ValueError("Select a nonempty list of distinct months")
    if any(m not in config["months"] or not re.fullmatch(r"\d{4}-\d{2}", m)
           for m in months):
        raise ValueError("Months must be listed in config/sources.json")
    paths = [raw_dir / f"yellow_tripdata_{m}.parquet" for m in months]
    paths.append(raw_dir / "taxi_zone_lookup.csv")
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with duckdb.connect(str(database), config={"threads": 2,
                                               "memory_limit": memory_limit}) as con:
        con.execute("SET temp_directory = ?", [str(database.parent / "cityflow_spill")])
        initialize(con)
        for month in months:
            results.append(load_one(
                con, raw_dir / f"yellow_tripdata_{month}.parquet",
                config["trip_url_template"].format(month=month),
                month, replace_changed,
            ))
        results.append(load_one(con, raw_dir / "taxi_zone_lookup.csv",
                                config["zones_url"], replace_changed=replace_changed))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path,
                        default=ROOT / "data/warehouse/cityflow.duckdb")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--config", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--months", nargs="+")
    parser.add_argument("--replace-changed", action="store_true")
    parser.add_argument("--memory-limit", default="2GB")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    for result in ingest(args.database, args.raw_dir, config, args.months,
                         args.replace_changed, args.memory_limit):
        print(json.dumps(result))


if __name__ == "__main__":
    main()
