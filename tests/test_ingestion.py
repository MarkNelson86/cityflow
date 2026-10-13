"""Exercise actual file loading and database state, using temporary fixtures."""
import json

import duckdb
import pytest

from scripts.ingest_sources import ingest


CONFIG = {
    "months": ["2025-01", "2025-02", "2025-03"],
    "trip_url_template": "https://example.test/yellow_{month}.parquet",
    "zones_url": "https://example.test/zones.csv",
}


def write_trips(path, vendor="1", extra=False, omit_fare=False, rows=2):
    with duckdb.connect() as con:
        fare = "" if omit_fare else ", 10.5::DOUBLE AS fare_amount"
        more = ", 'retained' AS new_column" if extra else ""
        con.execute(f"""
            COPY (SELECT
                timestamp '2025-01-15 12:00:00' AS tpep_pickup_datetime,
                timestamp '2025-01-15 12:20:00' AS tpep_dropoff_datetime,
                1::INTEGER AS PULocationID, 2::INTEGER AS DOLocationID,
                3.0::DOUBLE AS trip_distance,
                12.5::DOUBLE AS total_amount,
                {vendor} AS VendorID {fare} {more}
                FROM range({rows})) TO ? (FORMAT PARQUET)
        """, [str(path)])


@pytest.fixture
def files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_trips(raw / "yellow_tripdata_2025-01.parquet")
    (raw / "taxi_zone_lookup.csv").write_text(
        "LocationID,Borough,Zone,service_zone\n"
        "1,Manhattan,First,Yellow\n2,Brooklyn,Second,Boro\n"
    )
    return tmp_path / "warehouse.duckdb", raw


def query(db, sql):
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql).fetchall()


def test_rerun_skips_and_preserves_identical_looking_records(files):
    db, raw = files
    first = ingest(db, raw, CONFIG, ["2025-01"])
    ids = query(db, "SELECT trip_id, source_row_number FROM raw.trips ORDER BY 2")
    second = ingest(db, raw, CONFIG, ["2025-01"])
    assert [r["action"] for r in first] == ["loaded", "loaded"]
    assert [r["action"] for r in second] == ["skipped", "skipped"]
    assert len(ids) == 2 and ids[0][0] != ids[1][0]
    assert ids == query(db, "SELECT trip_id, source_row_number FROM raw.trips ORDER BY 2")
    assert query(db, "SELECT count(*) FROM meta.load_history") == [(2,)]


def test_changed_file_refused_then_explicitly_replaced(files):
    db, raw = files
    ingest(db, raw, CONFIG, ["2025-01"])
    write_trips(raw / "yellow_tripdata_2025-01.parquet", rows=3)
    with pytest.raises(ValueError, match="source bytes changed"):
        ingest(db, raw, CONFIG, ["2025-01"])
    assert query(db, "SELECT count(*) FROM raw.trips") == [(2,)]
    results = ingest(db, raw, CONFIG, ["2025-01"], replace_changed=True)
    assert results[0]["action"] == "replaced"
    assert query(db, "SELECT count(*) FROM raw.trips") == [(3,)]
    assert query(db, "SELECT row_count FROM meta.loaded_sources WHERE source_kind='trips'") == [(3,)]
    assert query(db, "SELECT count(*) FROM meta.load_history") == [(3,)]


def test_insert_failure_after_delete_rolls_back_previous_partition(files):
    db, raw = files
    ingest(db, raw, CONFIG, ["2025-01"])
    before = query(db, "SELECT * FROM raw.trips ORDER BY source_row_number")
    registry = query(db, "SELECT * FROM meta.loaded_sources ORDER BY partition_key")
    # VendorID was INTEGER in the existing table. Incoming malformed text
    # reaches INSERT after DELETE, where strict conversion must fail.
    write_trips(raw / "yellow_tripdata_2025-01.parquet", vendor="'not-an-integer'")
    with pytest.raises(duckdb.ConversionException):
        ingest(db, raw, CONFIG, ["2025-01"], replace_changed=True)
    assert query(db, "SELECT * FROM raw.trips ORDER BY source_row_number") == before
    assert query(db, "SELECT * FROM meta.loaded_sources ORDER BY partition_key") == registry
    assert query(db, "SELECT count(*) FROM meta.load_history") == [(2,)]


def test_missing_required_column_rejected(files):
    db, raw = files
    write_trips(raw / "yellow_tripdata_2025-01.parquet", omit_fare=True)
    with pytest.raises(ValueError, match="missing columns"):
        ingest(db, raw, CONFIG, ["2025-01"])
    assert query(db, "SELECT count(*) FROM meta.loaded_sources") == [(0,)]


def test_extra_column_retained_and_other_partition_preserved(files):
    db, raw = files
    ingest(db, raw, CONFIG, ["2025-01"])
    jan = query(db, "SELECT trip_id FROM raw.trips ORDER BY trip_id")
    write_trips(raw / "yellow_tripdata_2025-02.parquet", extra=True)
    ingest(db, raw, CONFIG, ["2025-02"])
    assert query(db, "SELECT trip_id FROM raw.trips WHERE source_month='2025-01' ORDER BY trip_id") == jan
    assert query(db, "SELECT count(*) FROM raw.trips WHERE new_column='retained'") == [(2,)]
    assert query(db, "SELECT count(*) FROM raw.trips WHERE new_column IS NULL") == [(2,)]
    schema = query(db, "SELECT source_schema FROM meta.loaded_sources WHERE source_month='2025-02'")[0][0]
    assert "new_column" in {r["column"] for r in json.loads(schema)}


def test_duplicate_zone_keys_rejected_without_partial_zone_replacement(files):
    db, raw = files
    ingest(db, raw, CONFIG, ["2025-01"])
    before = query(db, "SELECT * FROM raw.zones ORDER BY LocationID")
    (raw / "taxi_zone_lookup.csv").write_text(
        "LocationID,Borough,Zone,service_zone\n"
        "1,M,First,Y\n1,M,Duplicate,Y\n"
    )
    with pytest.raises(ValueError, match="Zone IDs"):
        ingest(db, raw, CONFIG, ["2025-01"], replace_changed=True)
    assert query(db, "SELECT * FROM raw.zones ORDER BY LocationID") == before


def test_registered_row_loss_blocks_skip(files):
    db, raw = files
    ingest(db, raw, CONFIG, ["2025-01"])
    with duckdb.connect(str(db)) as con:
        con.execute("DELETE FROM raw.trips WHERE source_row_number=0")
    with pytest.raises(ValueError, match="investigate database integrity"):
        ingest(db, raw, CONFIG, ["2025-01"])
