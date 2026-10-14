"""Keep floating-point noise acceptable while still detecting real inversions."""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def test_metric_invariant_tolerates_rounding_but_rejects_real_inversion():
    template = (ROOT / 'dbt/tests/analytics_metric_invariants.sql').read_text()
    query = template.replace("{{ config(tags=['analytics']) }}", '')
    query = query.replace("{{ ref('mart_daily_activity') }}", 'daily')
    query = query.replace("{{ ref('mart_route_monthly') }}", 'routes')
    with duckdb.connect() as con:
        # Same numeric pattern as the real two-record failure: aggregation methods
        # may differ in their last floating-point bit for a repeated duration.
        median, p90 = con.execute('''
            select median(seconds / 60.0), quantile_cont(seconds / 60.0, 0.9)
            from (values (2989), (2989)) as samples(seconds)
        ''').fetchone()
        assert abs(median - p90) < 1e-9
        con.execute('''
            create table daily (
                date_day date, snapshot_complete boolean, trip_count bigint,
                duration_records bigint, fare_records bigint,
                median_duration_minutes double, p90_duration_minutes double,
                median_fare_usd double
            )
        ''')
        con.execute('''
            create table routes as
            select 'rounding:2025-01-01'::varchar as route_month_key,
                   true as snapshot_complete, 2::bigint as trip_count,
                   2::bigint as duration_records, 1::bigint as fare_records,
                   ?::double as median_duration_minutes, ?::double as p90_duration_minutes,
                   84.2::double as median_fare_usd
        ''', [median, p90])
        # Explicitly force one last-bit difference, even if a future engine fixes it.
        con.execute('update routes set p90_duration_minutes = median_duration_minutes - 1e-14')
        assert con.execute(query).fetchall() == []
        con.execute('update routes set p90_duration_minutes = median_duration_minutes - 0.1')
        rows = con.execute(query).fetchall()
        assert len(rows) == 1 and rows[0][1] == 'rounding:2025-01-01'
