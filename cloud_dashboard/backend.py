"""Read four fixed serving tables; never run viewer-supplied SQL."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'cloud_dashboard/public_snapshot.json'
TABLES = ('metadata', 'daily', 'monthly', 'routes')
ROUTE_FIELDS = ('route_key', 'month_start', 'pickup_zone_name', 'dropoff_zone_name',
                'pickup_borough', 'dropoff_borough', 'is_geographic_route', 'trip_count',
                'calendar_days', 'trips_per_calendar_day', 'duration_records', 'fare_records',
                'minimum_metric_records', 'duration_sample_sufficient', 'fare_sample_sufficient',
                'median_duration_minutes', 'p90_duration_minutes', 'median_fare_usd',
                'volume_rank', 'previous_month_start', 'previous_trip_count',
                'trips_per_day_change_pct', 'median_duration_change_minutes', 'median_fare_change_usd')


def frames(payload):
    if payload.get('format_version') != 1 or set(payload.get('tables', {})) != set(TABLES):
        raise ValueError('Invalid public snapshot format.')
    result = {name: pd.DataFrame(payload['tables'][name]) for name in TABLES}
    for frame in result.values():
        frame.columns = frame.columns.str.lower()
        for column in ('date_day', 'month_start', 'previous_month_start'):
            if column in frame:
                frame[column] = pd.to_datetime(frame[column])
    validate(result)
    return result


def validate(data):
    meta, daily, monthly, routes = (data[name] for name in TABLES)
    if len(meta) != 1:
        raise ValueError('Expected one metadata record.')
    row = meta.iloc[0]
    fixture = row.dataset == 'fixture'
    if row.dataset not in ('fixture', 'real'):
        raise ValueError('Unknown dataset.')
    expected = (13, 12, 2, 12) if fixture else (11198026, 11198001, 30, 133377)
    if tuple(int(row[k]) for k in ('raw_records', 'observed_records',
                                  'minimum_metric_records', 'full_route_month_rows')) != expected:
        raise ValueError('Frozen dataset counts/threshold do not match.')
    if len(daily) != 90 or daily.date_day.nunique() != 90:
        raise ValueError('The complete 90-day daily calendar is required.')
    if list(daily.sort_values('date_day').date_day) != list(pd.date_range('2025-01-01', '2025-03-31')):
        raise ValueError('Daily dates must cover the frozen quarter exactly.')
    if daily.trip_count.isna().any() or (daily.trip_count < 0).any():
        raise ValueError('Daily counts must be nonnegative and complete.')
    expected_counts = [5, 3, 4] if fixture else [3475234, 3577542, 4145225]
    if len(monthly) != 3 or monthly.month_start.duplicated().any():
        raise ValueError('Expected three distinct whole-month records.')
    ordered = monthly.sort_values('month_start')
    if list(ordered.month_start) != list(pd.date_range('2025-01-01', periods=3, freq='MS')):
        raise ValueError('Monthly dates do not cover the frozen quarter.')
    if ordered.trip_count.astype(int).tolist() != expected_counts:
        raise ValueError('Monthly observation counts do not match.')
    if int(daily.trip_count.sum()) != expected[1] or int(monthly.trip_count.sum()) != expected[1]:
        raise ValueError('Daily and monthly totals do not reconcile.')
    if len(routes) > 315 or routes.route_key.nunique() > 105:
        raise ValueError('Public route subset exceeds its publishing limit.')
    if routes.empty or routes.duplicated(['route_key', 'month_start']).any():
        raise ValueError('Invalid route/month keys.')
    if not (routes.groupby('route_key').size() == 3).all():
        raise ValueError('Each published route needs all three months.')
    for _, group in routes.groupby('route_key'):
        if set(group.month_start) != set(ordered.month_start):
            raise ValueError('Route calendar mismatch.')
    if not (routes.minimum_metric_records == expected[2]).all():
        raise ValueError('Route metric threshold mismatch.')
    for flag, cohort, fields in (
        ('duration_sample_sufficient', 'duration_records', ('median_duration_minutes', 'p90_duration_minutes')),
        ('fare_sample_sufficient', 'fare_records', ('median_fare_usd',))):
        if not (routes[flag].astype(bool) == (routes[cohort] >= expected[2])).all():
            raise ValueError('Eligible-cohort flag mismatch.')
        if routes.loc[~routes[flag].astype(bool), list(fields)].notna().any().any():
            raise ValueError('Insufficient-cohort metrics must be suppressed before publishing.')
    for column in ('trips_per_day_change_pct', 'median_duration_change_minutes', 'median_fare_change_usd'):
        if routes.loc[routes.previous_month_start.isna(), column].notna().any():
            raise ValueError('January must have no predecessor change.')
    if routes.loc[routes.previous_trip_count.eq(0), 'trips_per_day_change_pct'].notna().any():
        raise ValueError('Percentage change from zero must remain undefined.')
    return {'dataset': row.dataset, 'observed_records': expected[1], 'daily_rows': len(daily),
            'monthly_rows': len(monthly), 'published_routes': routes.route_key.nunique(),
            'published_route_month_rows': len(routes), 'minimum_metric_records': expected[2]}


def read_snapshot(path=SNAPSHOT):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError('Public snapshot is unexpectedly large.')
    return frames(json.loads(path.read_text()))


def connect(settings):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(settings['private_key_pem'].encode(), password=None)
    private_key = key.private_bytes(serialization.Encoding.DER,
                                   serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return snowflake.connector.connect(account=settings['account'], user='CITYFLOW_APP_USER',
        private_key=private_key, authenticator='SNOWFLAKE_JWT', role='CITYFLOW_APP_ROLE',
        warehouse='CITYFLOW_APP_WH', database='CITYFLOW_REAL', schema='SERVING',
        login_timeout=30, network_timeout=60, client_session_keep_alive=False,
        session_parameters={'TIMEZONE': 'UTC', 'QUERY_TAG': 'cityflow_hosting',
                            'STATEMENT_TIMEOUT_IN_SECONDS': 60})


def read_cloud(settings, check_privileges=False):
    tables, ids = {}, []
    with connect(settings) as con:
        with con.cursor() as cur:
            cur.execute('USE SECONDARY ROLES NONE')
            for name in TABLES:
                cur.execute('SELECT * FROM CITYFLOW_REAL.SERVING.APP_' + name.upper())
                ids.append(cur.sfqid)
                columns = [x[0].lower() for x in cur.description]
                rows = cur.fetchmany(1000)
                if cur.fetchone() is not None:
                    raise ValueError('Serving table exceeds its intended row limit.')
                tables[name] = pd.DataFrame(rows, columns=columns)
            if check_privileges:
                try:
                    cur.execute('SELECT TRIP_ID FROM CITYFLOW_REAL.RAW.TRIPS LIMIT 0')
                except snowflake_error_types() as exc:
                    if getattr(exc, 'errno', None) not in (2003, 3001):
                        raise
                    ids.append(cur.sfqid)
                else:
                    raise ValueError('Service role unexpectedly has access to RAW trips.')
    payload = make_payload(tables)
    return frames(payload), ids


def snowflake_error_types():
    from snowflake.connector.errors import ProgrammingError
    return ProgrammingError


def make_payload(data):
    return {'format_version': 1, 'tables': {
        name: json.loads(data[name].to_json(orient='records', date_format='iso', double_precision=15))
        for name in TABLES}}


def snapshot_digest(path=SNAPSHOT):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
