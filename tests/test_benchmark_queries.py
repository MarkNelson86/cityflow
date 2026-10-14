"""The performance comparison must answer exactly the same count question."""
from datetime import date
from pathlib import Path

import duckdb
import pytest

from scripts.benchmark_queries import benchmark, verify_equivalent

ROOT = Path(__file__).resolve().parents[1]


def test_equivalent_route_counts_and_rotating_samples():
    with duckdb.connect() as con:
        con.execute('create schema analytics')
        con.execute('''
            create table analytics.fact_trips as
            select * from (values
                (date '2025-01-31', 1, 2, true, true, true, 'Manhattan', 'Brooklyn'),
                (date '2025-01-31', 1, 2, true, true, true, 'Manhattan', 'Brooklyn'),
                (date '2025-03-01', 2, 1, true, true, true, 'Brooklyn', 'Manhattan'),
                (date '2025-02-01', 999, 2, true, false, true, 'Unmapped', 'Brooklyn'),
                (date '2024-12-31', 1, 2, false, true, true, 'Manhattan', 'Brooklyn')
            ) as fixture(pickup_date, pickup_zone_id, dropoff_zone_id,
                is_observed_trip, pickup_zone_found, dropoff_zone_found,
                pickup_borough, dropoff_borough)
        ''')
        con.execute('''
            create table analytics.mart_route_monthly as
            select * from (values
                (date '2025-01-01', '1->2', 2, true, true),
                (date '2025-02-01', '1->2', 0, true, true),
                (date '2025-03-01', '2->1', 1, true, true),
                (date '2025-02-01', '999->2', 1, true, false)
            ) as fixture(month_start, route_key, trip_count,
                         snapshot_complete, is_geographic_route)
        ''')
        names = ('route_counts_from_fact', 'route_counts_from_mart')
        queries = {name: (ROOT / f'sql/benchmarks/{name}.sql').read_text() for name in names}
        assert con.execute(queries[names[0]]).fetchall() == [
            (date(2025, 1, 1), '1->2', 2), (date(2025, 3, 1), '2->1', 1)]
        samples, summaries = benchmark(con, queries, repeats=3)
        assert len(samples) == 6 and len(summaries) == 2
        assert [row['query'] for row in samples[:4]] == [names[0], names[1], names[1], names[0]]
        assert all(row['returned_rows'] == 2 and row['seconds'] >= 0 for row in samples)
        assert summaries[0]['result_sha256'] == summaries[1]['result_sha256']
        con.execute("update analytics.mart_route_monthly set trip_count=3 where route_key='1->2' and trip_count>0")
        with pytest.raises(ValueError, match='route counts differ'):
            benchmark(con, queries, repeats=3)


def test_equal_grand_totals_do_not_hide_shifted_route_counts():
    # Total 3 on both sides is insufficient: the route/date keys must also agree.
    with pytest.raises(ValueError, match='route counts differ'):
        verify_equivalent([(date(2025, 1, 1), '1->2', 3)],
                          [(date(2025, 1, 1), '2->1', 3)])
