import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'config/sources.json').read_text())
REQUIRED = {
    'tpep_pickup_datetime', 'tpep_dropoff_datetime',
    'PULocationID', 'DOLocationID', 'trip_distance',
    'fare_amount', 'total_amount',
}


def fingerprint(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': digest}


def as_dict(cursor):
    names = [column[0] for column in cursor.description]
    return dict(zip(names, cursor.fetchone()))


report = {
    'observed_at_utc': datetime.now(timezone.utc).isoformat(),
    'duckdb_version': duckdb.__version__,
    'sources': [],
}
with duckdb.connect() as con:
    for month in CONFIG['months']:
        path = ROOT / 'data/raw' / f'yellow_tripdata_{month}.parquet'
        schema = con.execute(
            'describe select * from read_parquet(?)', [str(path)]
        ).fetchall()
        missing = REQUIRED - {row[0] for row in schema}
        if missing:
            raise ValueError(f'{path.name}: missing columns {sorted(missing)}')
        profile = as_dict(con.execute('''
            select
                count(*) as rows,
                min(tpep_pickup_datetime) as earliest_pickup,
                max(tpep_pickup_datetime) as latest_pickup,
                count(*) filter (
                    where tpep_pickup_datetime is null
                ) as missing_pickup,
                count(*) filter (
                    where tpep_pickup_datetime < timestamp '2025-01-01'
                       or tpep_pickup_datetime >= timestamp '2025-04-01'
                ) as outside_quarter,
                count(*) filter (
                    where tpep_dropoff_datetime <= tpep_pickup_datetime
                ) as nonpositive_duration,
                count(*) filter (where fare_amount < 0) as negative_fare,
                count(*) filter (where total_amount < 0) as negative_total,
                count(*) filter (where trip_distance <= 0) as nonpositive_distance
            from read_parquet(?)
        ''', [str(path)]))
        record = fingerprint(path)
        record.update({
            'month': month,
            'url': CONFIG['trip_url_template'].format(month=month),
            'schema': [{'column': r[0], 'type': r[1]} for r in schema],
            'profile': profile,
        })
        report['sources'].append(record)
        print(month, json.dumps(profile, default=str))

    zones = ROOT / 'data/raw/taxi_zone_lookup.csv'
    zone_profile = as_dict(con.execute('''
        select count(*) as rows,
               count(distinct LocationID) as distinct_zone_ids,
               count(*) filter (where LocationID is null) as missing_zone_ids
        from read_csv_auto(?)
    ''', [str(zones)]))
    if (zone_profile['rows'] != zone_profile['distinct_zone_ids']
            or zone_profile['missing_zone_ids']):
        raise ValueError(f'Zone keys are not unique/non-null: {zone_profile}')
    record = fingerprint(zones)
    record.update({'url': CONFIG['zones_url'], 'profile': zone_profile})
    report['sources'].append(record)
    print('zones', zone_profile)

destination = ROOT / 'reports/source_audit.json'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2, default=str) + '\n')
print('Saved:', destination)
