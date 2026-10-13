"""Export analytical CSVs and a compact Markdown report from built dbt models."""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def require_ready(con):
    versions = con.execute('''
        SELECT source_month FROM meta.loaded_sources WHERE source_kind = 'trips'
    ''').fetchall()
    if sorted(r[0] for r in versions) != ['2025-01', '2025-02', '2025-03']:
        raise ValueError('Incomplete snapshot: all three source partitions are required')
    stale = con.execute('''
        SELECT count(*) FROM analytics.fact_trips f
        LEFT JOIN meta.loaded_sources m
            ON m.source_kind = 'trips' AND f.source_month = m.source_month
        WHERE m.partition_key IS NULL OR f.source_sha256 IS DISTINCT FROM m.source_sha256
    ''').fetchone()[0]
    if stale:
        raise ValueError('Fact table has stale source versions; rebuild upstream dbt models')
    for table in ('mart_daily_activity', 'mart_route_monthly', 'mart_route_month_comparison'):
        incomplete = con.execute(f'SELECT count(*) FROM analytics.{table} '
                                 'WHERE snapshot_complete IS DISTINCT FROM true').fetchone()[0]
        if incomplete:
            raise ValueError('Analytical models reflect incomplete coverage; rebuild them')
    expected = con.execute('SELECT count(*) FROM analytics.fact_trips WHERE is_observed_trip').fetchone()[0]
    daily = con.execute('SELECT count(*), coalesce(sum(trip_count), 0) '
                        'FROM analytics.mart_daily_activity').fetchone()
    routes = con.execute('SELECT coalesce(sum(trip_count), 0) '
                         'FROM analytics.mart_route_monthly').fetchone()[0]
    if daily != (90, expected) or routes != expected:
        raise ValueError('Analytical totals do not reconcile; build and test the models')
    return expected


def export_query(con, query, path):
    result = con.execute(query)
    columns = [r[0] for r in result.description]
    records = result.fetchall()
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(records)
    return [dict(zip(columns, r)) for r in records]


def fmt(value):
    if value is None:
        return '—'
    if isinstance(value, float):
        return f'{value:,.2f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(records, fields):
    return '\n'.join([
        '| ' + ' | '.join(label for _, label in fields) + ' |',
        '| ' + ' | '.join('---' for _ in fields) + ' |',
        *['| ' + ' | '.join(fmt(r[key]) for key, _ in fields) + ' |' for r in records],
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/warehouse/cityflow.duckdb')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/analytics')
    parser.add_argument('--label', default='NYC TLC yellow-taxi snapshot, January–March 2025')
    args = parser.parse_args()
    with duckdb.connect(str(args.database), read_only=True) as con:
        observed = require_ready(con)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {}
        for name, order in [('mart_daily_activity', 'date_day'),
                            ('mart_route_monthly', 'month_start, route_key'),
                            ('mart_route_month_comparison', 'month_start, route_key')]:
            data = export_query(con, f'SELECT * FROM analytics.{name} ORDER BY {order}',
                                args.output_dir / (name + '.csv'))
            print(name, len(data), 'rows')
            if name == 'mart_daily_activity':
                outputs['daily'] = data
        for name in ('monthly_activity', 'top_routes', 'route_comparison_highlights'):
            outputs[name] = export_query(con, (ROOT / f'sql/analytics/{name}.sql').read_text(),
                                         args.output_dir / (name + '.csv'))
        sources = con.execute('''
            SELECT partition_key, source_sha256, row_count, source_url
            FROM meta.loaded_sources ORDER BY partition_key
        ''').fetchall()
        minimum = con.execute('SELECT DISTINCT minimum_metric_records '
                              'FROM analytics.mart_route_monthly').fetchall()
        metadata = {
            'label': args.label,
            'exported_at_utc': datetime.now(timezone.utc).isoformat(),
            'duckdb_version': duckdb.__version__,
            'observed_records': observed,
            'minimum_metric_records': [r[0] for r in minimum],
            'sources': [dict(zip(('partition', 'sha256', 'rows', 'source_url'), r)) for r in sources],
        }
        (args.output_dir / 'run_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        monthly = table(outputs['monthly_activity'], [
            ('month_start', 'Pickup month'), ('calendar_days', 'Days'),
            ('trip_count', 'Recorded trips'), ('trips_per_calendar_day', 'Trips/day'),
            ('duration_records', 'Duration cohort'), ('fare_records', 'Fare cohort'),
            ('median_duration_minutes', 'Median min'), ('p90_duration_minutes', 'P90 min'),
            ('median_fare_usd', 'Median fare USD'),
        ])
        routes = table(outputs['top_routes'], [
            ('month_start', 'Month'), ('pickup_zone_name', 'Pickup'),
            ('dropoff_zone_name', 'Dropoff'), ('trip_count', 'Recorded trips'),
            ('median_duration_minutes', 'Median min'), ('p90_duration_minutes', 'P90 min'),
        ])
        changes = table(outputs['route_comparison_highlights'], [
            ('month_start', 'Month'), ('pickup_zone_name', 'Pickup'),
            ('dropoff_zone_name', 'Dropoff'), ('median_duration_change_minutes', 'Median change min'),
            ('trips_per_day_change_pct', 'Trips/day change %'),
        ])
        peak = max(outputs['daily'], key=lambda r: r['trip_count'])
        text = f'''# Cityflow analytical results

Dataset: {args.label}. Exported: {metadata['exported_at_utc']}.
The three analytical models reconcile to **{observed:,} in-window source records**.
The calendar includes 90 days. Peak recorded activity: **{peak['date_day']}**, with **{peak['trip_count']:,} records**.

## Monthly activity

{monthly}

## Most recorded geographic routes

{routes}

## Adjacent-month duration changes

{changes}

## Interpretation

All month labels use actual pickup dates, not source-file months. The rate denominator
is every calendar day in the month (31, 28, 31). Percentiles are recomputed from
eligible trip records; they are not averages of daily or route medians.

Route highlights require matched pickup/dropoff zones in NYC's five boroughs.
Unknown and outside-city routes remain in the complete analytical aggregates.
Volume ranks use recorded counts, with ties sharing a dense rank.

Route metrics in the highlight tables are suppressed below the configured cohort
threshold, shown in `run_metadata.json`. Duration comparisons require adequate
duration cohorts in both adjacent months. A blank comparison table means no route
met the requirements. Percentage change from zero is undefined and remains blank.

These are descriptive recorded taxi patterns. They do not establish changes in
all urban travel, causal congestion effects, or a travel-time forecast. Payment
categories and trip mix can affect comparisons. Wall-clock duration ambiguities
around daylight-saving changes remain part of the source limitations.

See `docs/analytics_design.md` for grains, definitions and validation.
'''
        (args.output_dir / 'overview.md').write_text(text)
        print('Observed records:', observed)
        print('Monthly counts:', [(r['month_start'], r['trip_count']) for r in outputs['monthly_activity']])
        print('Report:', args.output_dir / 'overview.md')


if __name__ == '__main__':
    main()
