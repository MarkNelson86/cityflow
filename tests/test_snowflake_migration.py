"""Local migration checks; cloud execution remains a separate manual gate."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_filtered_count_with_nested_predicate():
    m = module('prepare_snowflake_project')
    assert m.adapt("count(*) filter (where x not in ('a', 'b')) > 0") == "count(case when x not in ('a', 'b') then 1 end) > 0"


def test_exact_percentile_and_named_window():
    m = module('prepare_snowflake_project')
    text = "quantile_cont(duration_minutes, 0.9) filter (where is_duration_eligible) as p90\nlag(trip_count) over by_route\nwindow by_route as (partition by route_key order by month_start)"
    result = m.adapt(text)
    assert 'percentile_cont(0.9) within group (order by case when is_duration_eligible then duration_minutes end)' in result
    assert 'lag(trip_count) over (partition by route_key order by month_start)' in result
    assert 'window by_route' not in result
    assert '60000000.0::float' in m.adapt('epoch(dropoff_time - pickup_time) / 60.0')
    assert m.adapt('g.trip_count * 1.0 / g.calendar_days') == 'g.trip_count::float / g.calendar_days'
    assert m.adapt('100.0 * x / y') == '100.0::float * x / y'


def test_parity_counts_nulls_and_roundoff():
    m = module('snowflake_snapshot')
    assert m.equal(49.81666666666667,49.81666666666666,True)
    assert not m.equal(49.8,49.81,True)
    assert m.equal(None,None)
    assert not m.equal(None,0)
    assert not m.equal(100,101)


def test_export_preserves_microseconds_and_registry(tmp_path):
    import argparse
    import duckdb
    m = module('snowflake_snapshot')
    db = tmp_path / 'fixture.duckdb'
    with duckdb.connect(str(db)) as c:
        c.execute('create schema raw'); c.execute('create schema meta')
        c.execute("""create table raw.trips as select 'id' as trip_id, '2025-01' as source_month,
            'sha' as source_sha256, 1::bigint as source_row_number,
            timestamp '2025-01-01 10:00:00.123456' as tpep_pickup_datetime,
            timestamp '2025-01-01 10:00:30.123456' as tpep_dropoff_datetime,
            1 as PULocationID, 2 as DOLocationID, 1.2::double as trip_distance,
            3.4::double as fare_amount, 4.5::double as total_amount""")
        c.execute("""create table raw.zones as select 1 as LocationID, 'Manhattan' as Borough,
            'Zone' as Zone, 'yellow' as service_zone, 'sha' as source_sha256""")
        c.execute("""create table meta.loaded_sources as select 'yellow:2025-01' as partition_key,
            'trips' as source_kind, '2025-01' as source_month, 'file' as source_file,
            'url' as source_url, 'sha' as source_sha256, 123 as source_bytes,
            '[]'::json as source_schema, 1 as row_count, current_timestamp as loaded_at""")
    out = tmp_path / 'export'
    m.export(argparse.Namespace(database=db,output=out,dataset='fixture'))
    with duckdb.connect() as c:
        row = c.execute('select TPEP_PICKUP_DATETIME, SOURCE_ROW_NUMBER from read_parquet(?)', [str(out/'raw_trips.parquet')]).fetchone()
    assert row[0].microsecond == 123456
    assert row[1] == 1
    import json
    data = json.loads((out/'manifest.json').read_text())
    assert data['trip_partitions'] == [['2025-01','sha',1]]
    assert all(x['rows'] == 1 for x in data['tables'])
