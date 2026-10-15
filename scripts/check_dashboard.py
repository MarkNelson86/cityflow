"""Validate dashboard query outputs against the local analytical contract."""
import argparse
import json
import math
import sys
import time
import platform
from importlib.metadata import version
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from dashboard.data import START, END, Warehouse, safe_route_table


def same(a, b):
    if pd.isna(a) or pd.isna(b):
        return bool(pd.isna(a) and pd.isna(b))
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-9)


def validate(database, dataset):
    started = time.perf_counter()
    warehouse = Warehouse(database)
    context = warehouse.validate(dataset)
    daily = warehouse.daily()
    monthly = warehouse.monthly_activity()
    counts = monthly.trip_count.astype(int).tolist()
    expected_counts = [5, 3, 4] if dataset == 'fixture' else [3475234, 3577542, 4145225]
    if counts != expected_counts or int(daily.trip_count.sum()) != sum(counts):
        raise ValueError('Full-quarter activity does not reconcile.')
    known = {
        'fixture': {
            'duration_records': [5, 2, 4], 'fare_records': [4, 3, 4],
            'median_duration_minutes': [15, 10, 30],
            'p90_duration_minutes': [26, 14, 38.5], 'median_fare_usd': [9, 5, 14],
        },
        'real': {
            'duration_records': [3471806, 3571077, 4121371],
            'fare_records': [3331116, 3394887, 3936501],
            'median_duration_minutes': [11.7, 12.216666666666667, 12.516666666666667],
            'p90_duration_minutes': [27.516666666666667, 27.833333333333333, 29.266666666666667],
            'median_fare_usd': [12.8, 13.5, 14.1],
        },
    }
    for field, values in known[dataset].items():
        if not all(same(a, b) for a, b in zip(monthly[field], values)):
            raise ValueError(f'Monthly {field} differs from independently established answers.')
    start, end = date(2025, 1, 15), date(2025, 2, 14)
    partial = warehouse.monthly_activity(start, end)
    direct_count = warehouse.query('SELECT COUNT(*) AS n FROM analytics.fact_trips '
                                   'WHERE is_observed_trip AND pickup_date BETWEEN ? AND ?',
                                   [start, end]).iloc[0]['n']
    if int(partial.trip_count.sum()) != direct_count or int(partial.selected_calendar_days.sum()) != 31:
        raise ValueError('Date-filtered activity or calendar denominator does not reconcile.')
    keys = warehouse.query('''
        SELECT route_key FROM analytics.mart_route_monthly
        WHERE is_geographic_route GROUP BY route_key
        ORDER BY SUM(trip_count) DESC, route_key LIMIT 3
    ''').route_key.tolist()
    others = warehouse.query('''
        SELECT DISTINCT route_key FROM analytics.mart_route_monthly
        WHERE NOT is_geographic_route ORDER BY route_key LIMIT 1
    ''').route_key.tolist()
    inspected = []
    for key in keys + others:
        rows, direct = warehouse.route_months(key), warehouse.independent_route(key)
        if len(rows) != 3 or not rows.month_start.equals(direct.month_start):
            raise ValueError(f'Route calendar mismatch: {key}')
        for field in ('trip_count', 'duration_records', 'fare_records',
                      'median_duration_minutes', 'median_fare_usd'):
            if not all(same(a, b) for a, b in zip(rows[field], direct[field])):
                raise ValueError(f'Independent route mismatch: {key}, {field}')
        safe = safe_route_table(rows)
        if safe.loc[~rows.duration_sample_sufficient, 'median_duration_minutes'].notna().any():
            raise ValueError('Insufficient duration sample was displayed.')
        if safe.loc[~rows.fare_sample_sufficient, 'median_fare_usd'].notna().any():
            raise ValueError('Insufficient fare sample was displayed.')
        if rows.loc[rows.previous_trip_count == 0, 'trip_count_change_pct'].notna().any():
            raise ValueError('Percentage change from zero must remain undefined.')
        inspected.append(key)
    return {
        'dataset': dataset, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {'python': platform.python_version(),
                        **{name: version(name) for name in ('duckdb', 'streamlit', 'pandas', 'plotly')}},
        'all_checks_passed': True, 'counts': context,
        'monthly_observed_counts': counts,
        'partial_window': {'start': str(start), 'end': str(end), 'calendar_days': 31,
                           'observed_records': int(direct_count)},
        'sampled_route_keys': inspected,
        'route_checks_scope': 'Three highest-volume geographic routes (or all if fewer), '
                              'plus one non-geographic route when present; not a full new parity scan.',
        'elapsed_seconds': round(time.perf_counter() - started, 3),
        'read_only': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--dataset', choices=('real', 'fixture'), required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--write-summary', type=Path,
                        help='Create a new summary template with actual check results; refuses overwrite.')
    args = parser.parse_args()
    if args.write_summary and args.write_summary.exists():
        raise SystemExit('Summary already exists; review/edit it rather than overwriting it.')
    result = validate(args.database, args.dataset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    if args.write_summary:
        args.write_summary.parent.mkdir(parents=True, exist_ok=True)
        args.write_summary.write_text(f'''# CityFlow local dashboard results

- Dataset: {result['dataset']} January–March 2025 snapshot
- Automated checks completed (UTC): {result['checked_at_utc']}
- Automated data checks: passed
- Raw records: {result['counts']['raw_records']:,}
- Observed records: {result['counts']['observed_records']:,}
- Daily / route-month / comparison rows: {result['counts']['daily_rows']:,} / {result['counts']['route_rows']:,} / {result['counts']['comparison_rows']:,}
- Route metric threshold: {result['counts']['minimum_metric_records']}
- Monthly observed counts: {result['monthly_observed_counts']}
- Environment: {result['environment']}
- Backend: local DuckDB; read-only connections
- Snowflake resources: remain removed from the completed Snowflake phase
- Public hosting: not part of this phase
- Automated dashboard tests: [record the result from dashboard/checks.py]
- Browser checks completed at: [date/time and timezone]

## Browser review

| Check | Result |
| --- | --- |
| Fixture warning and 12 observed trips | Pending |
| Zero-trip route month displays 0 and suppressed metrics | Pending |
| Growth from zero is undefined | Pending |
| Unmapped route is selectable and under-threshold metrics are hidden | Pending |
| Full real snapshot shows 11,198,001 observed trips | Pending |
| Date range changes counts and selected-day denominator | Pending |
| Route origin/destination/month controls work | Pending |
| Selected activity and route CSV downloads work | Pending |

## Validation scope

The known monthly counts, eligible cohort sizes, medians and p90 match the previously
established answers. Date-filtered activity reconciles with fact records. Route
samples are recomputed from fact records: {result['route_checks_scope']}
The earlier full DuckDB–Snowflake parity evidence remains separate. Check timings
are development observations, not a cross-engine performance comparison.
''')
    print(json.dumps(result, indent=2))
    print('Dashboard validation passed. Report:', args.report)


if __name__ == '__main__':
    main()
