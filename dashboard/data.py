"""Parameterized, read-only queries against the validated local warehouse."""
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from scripts.export_analytics import require_ready

EXPECTED = {
    'real': {'raw_records': 11198026, 'observed_records': 11198001,
             'daily_rows': 90, 'route_rows': 133377, 'comparison_rows': 133377,
             'minimum_metric_records': 30},
    'fixture': {'raw_records': 13, 'observed_records': 12,
                'daily_rows': 90, 'route_rows': 12, 'comparison_rows': 12,
                'minimum_metric_records': 2},
}
START, END = date(2025, 1, 1), date(2025, 3, 31)


class DashboardDataError(ValueError):
    """The selected data cannot support the dashboard's analytical contract."""


class Warehouse:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise DashboardDataError('Database file not found. Set CITYFLOW_DASHBOARD_DATABASE '
                                     'to your existing DuckDB warehouse or built CI fixture.')

    def query(self, sql, parameters=None):
        # A fresh connection is closed after every query; no persistent writer/lock.
        with duckdb.connect(str(self.path), read_only=True,
                            config={'threads': 2, 'memory_limit': '2GB'}) as con:
            return con.execute(sql, parameters or []).fetchdf()

    def validate(self, dataset):
        if dataset not in EXPECTED:
            raise DashboardDataError('CITYFLOW_DASHBOARD_DATASET must be real or fixture.')
        with duckdb.connect(str(self.path), read_only=True,
                            config={'threads': 2, 'memory_limit': '2GB'}) as con:
            observed = require_ready(con)
            actual = {
                'raw_records': con.execute('SELECT COUNT(*) FROM raw.trips').fetchone()[0],
                'observed_records': observed,
                'daily_rows': con.execute('SELECT COUNT(*) FROM analytics.mart_daily_activity').fetchone()[0],
                'route_rows': con.execute('SELECT COUNT(*) FROM analytics.mart_route_monthly').fetchone()[0],
                'comparison_rows': con.execute('SELECT COUNT(*) FROM analytics.mart_route_month_comparison').fetchone()[0],
            }
            thresholds = con.execute('SELECT DISTINCT minimum_metric_records '
                                     'FROM analytics.mart_route_monthly').fetchall()
            if len(thresholds) != 1:
                raise DashboardDataError('Route cohort thresholds are inconsistent.')
            actual['minimum_metric_records'] = thresholds[0][0]
            if actual != EXPECTED[dataset]:
                raise DashboardDataError(f'{dataset} dataset contract mismatch: {actual}. '
                                         'Check the database, dataset label and dbt threshold.')
            bounds = con.execute('SELECT MIN(date_day), MAX(date_day) '
                                 'FROM analytics.mart_daily_activity').fetchone()
            if bounds != (START, END):
                raise DashboardDataError('Expected the complete January–March 2025 calendar.')
        return actual

    def daily(self, start=START, end=END):
        self.validate_dates(start, end)
        # Calculate the trailing window on the full calendar before filtering.
        return self.query('''
            WITH series AS (
                SELECT date_day, trip_count,
                    CASE WHEN COUNT(trip_count) OVER w = 7
                         THEN AVG(trip_count) OVER w END AS trailing_7_day_mean
                FROM analytics.mart_daily_activity
                WINDOW w AS (ORDER BY date_day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
            )
            SELECT * FROM series WHERE date_day BETWEEN ? AND ? ORDER BY date_day
        ''', [start, end])

    @staticmethod
    def validate_dates(start, end):
        if not START <= start <= end <= END:
            raise DashboardDataError('Choose an ordered date range within January–March 2025.')

    def monthly_activity(self, start=START, end=END):
        self.validate_dates(start, end)
        # Percentiles come from individual eligible fact records, never averaged medians.
        return self.query('''
            WITH calendar AS (
                SELECT month_start, COUNT(*) AS selected_calendar_days
                FROM analytics.dim_dates WHERE date_day BETWEEN ? AND ? GROUP BY 1
            ), activity AS (
                SELECT DATE_TRUNC('month', pickup_date)::DATE AS month_start,
                    COUNT(*) AS trip_count,
                    COUNT(*) FILTER (WHERE is_duration_eligible) AS duration_records,
                    COUNT(*) FILTER (WHERE is_fare_eligible) AS fare_records,
                    MEDIAN(duration_minutes) FILTER (WHERE is_duration_eligible) AS median_duration_minutes,
                    QUANTILE_CONT(duration_minutes, 0.9) FILTER (WHERE is_duration_eligible) AS p90_duration_minutes,
                    MEDIAN(fare_amount) FILTER (WHERE is_fare_eligible) AS median_fare_usd
                FROM analytics.fact_trips
                WHERE is_observed_trip AND pickup_date BETWEEN ? AND ? GROUP BY 1
            )
            SELECT c.month_start, c.selected_calendar_days,
                COALESCE(a.trip_count, 0) AS trip_count,
                COALESCE(a.trip_count, 0) * 1.0 / c.selected_calendar_days AS trips_per_calendar_day,
                COALESCE(a.duration_records, 0) AS duration_records,
                COALESCE(a.fare_records, 0) AS fare_records,
                a.median_duration_minutes, a.p90_duration_minutes, a.median_fare_usd
            FROM calendar c LEFT JOIN activity a USING (month_start) ORDER BY month_start
        ''', [start, end, start, end])

    def routes(self, geographic_only=True):
        return self.query('''
            SELECT DISTINCT route_key, pickup_zone_name, dropoff_zone_name,
                pickup_borough, dropoff_borough, is_geographic_route
            FROM analytics.mart_route_monthly
            WHERE (NOT ? OR is_geographic_route) ORDER BY route_key
        ''', [geographic_only])

    def route_months(self, route_key):
        # Bound values also make arbitrary user-provided route strings harmless.
        return self.query('''
            SELECT * FROM analytics.mart_route_month_comparison
            WHERE route_key = ? ORDER BY month_start
        ''', [route_key])

    def independent_route(self, route_key):
        return self.query('''
            WITH months AS (
                SELECT month_start, COUNT(*) AS calendar_days FROM analytics.dim_dates GROUP BY 1
            ), counts AS (
                SELECT DATE_TRUNC('month', pickup_date)::DATE AS month_start,
                    COUNT(*) AS trip_count,
                    COUNT(*) FILTER (WHERE is_duration_eligible) AS duration_records,
                    COUNT(*) FILTER (WHERE is_fare_eligible) AS fare_records,
                    MEDIAN(duration_minutes) FILTER (WHERE is_duration_eligible) AS median_duration_minutes,
                    MEDIAN(fare_amount) FILTER (WHERE is_fare_eligible) AS median_fare_usd
                FROM analytics.fact_trips WHERE is_observed_trip
                    AND COALESCE(pickup_zone_id::VARCHAR, 'NULL') || '->' ||
                        COALESCE(dropoff_zone_id::VARCHAR, 'NULL') = ? GROUP BY 1
            )
            SELECT m.month_start, COALESCE(c.trip_count, 0) AS trip_count,
                COALESCE(c.duration_records, 0) AS duration_records,
                COALESCE(c.fare_records, 0) AS fare_records,
                c.median_duration_minutes, c.median_fare_usd
            FROM months m LEFT JOIN counts c USING (month_start) ORDER BY 1
        ''', [route_key])


def safe_route_table(frame):
    """Only expose route percentiles/medians for sufficient eligible cohorts."""
    result = frame.copy()
    for field in ('median_duration_minutes', 'p90_duration_minutes'):
        result.loc[~result['duration_sample_sufficient'].fillna(False), field] = float('nan')
    result.loc[~result['fare_sample_sufficient'].fillna(False), 'median_fare_usd'] = float('nan')
    return result


def number(value, decimals=0, prefix=''):
    if pd.isna(value):
        return '—'
    return prefix + f'{value:,.{decimals}f}'


def comparison_note(row):
    if pd.isna(row['previous_month_start']):
        return 'No previous month within this snapshot.'
    if row['previous_trip_count'] == 0:
        return 'Percentage change is undefined because the previous month had zero trips.'
    return 'Compared with the previous calendar month; trips/day accounts for month length.'
