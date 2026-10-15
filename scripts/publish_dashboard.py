"""Prepare private credentials, export bounded cloud data, or verify a public snapshot."""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud_dashboard.backend import (ROUTE_FIELDS, TABLES, make_payload, read_cloud,
                                     read_snapshot, snapshot_digest, validate)


def local_data(database, dataset):
    from dashboard.data import Warehouse, safe_route_table
    warehouse = Warehouse(database)
    context = warehouse.validate(dataset)
    totals = warehouse.query('SELECT route_key, is_geographic_route, SUM(trip_count) AS quarter_trips '
                             'FROM analytics.mart_route_monthly GROUP BY 1, 2')
    totals = totals.sort_values(['quarter_trips', 'route_key'], ascending=[False, True])
    keys = []
    for geographic, limit in ((True, 100), (False, 5)):
        keys.extend(totals.loc[totals.is_geographic_route == geographic].head(limit).route_key)
    rows = warehouse.query('SELECT * FROM analytics.mart_route_month_comparison')
    rows = safe_route_table(rows.loc[rows.route_key.isin(keys)])
    import pandas as pd
    meta = pd.DataFrame([{'dataset': dataset, 'raw_records': context['raw_records'],
                          'observed_records': context['observed_records'],
                          'minimum_metric_records': context['minimum_metric_records'],
                          'full_route_month_rows': context['route_rows']}])
    return {'metadata': meta, 'daily': warehouse.daily(), 'monthly': warehouse.monthly_activity(),
            'routes': rows[list(ROUTE_FIELDS)]}


def compare(data, database, dataset):
    import pandas as pd
    local = local_data(database, dataset)
    for name in TABLES:
        keys = {'metadata': ['dataset'], 'daily': ['date_day'], 'monthly': ['month_start'],
                'routes': ['route_key', 'month_start']}[name]
        left, right = data[name], local[name]
        if set(left.columns) != set(right.columns):
            raise ValueError('Column mismatch in ' + name)
        columns = sorted(left.columns)
        left = left.sort_values(keys)[columns].reset_index(drop=True)
        right = right.sort_values(keys)[columns].reset_index(drop=True)
        for frame in (left, right):
            for column in ('date_day', 'month_start', 'previous_month_start'):
                if column in frame:
                    frame[column] = pd.to_datetime(frame[column]).astype('datetime64[ns]')
        left, right = left.convert_dtypes(), right.convert_dtypes()
        pd.testing.assert_frame_equal(left, right, check_dtype=False, check_exact=False,
                                      atol=1e-9, rtol=1e-12)
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    creds = sub.add_parser('credentials')
    creds.add_argument('--key', type=Path, required=True)
    creds.add_argument('--output', type=Path, default=ROOT / '.streamlit/secrets.toml')
    for command in ('export', 'check', 'fixture'):
        s = sub.add_parser(command)
        s.add_argument('--database', type=Path, required=True)
        s.add_argument('--snapshot', type=Path, default=ROOT / 'cloud_dashboard/public_snapshot.json')
        s.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    if a.command == 'credentials':
        if a.output.exists():
            raise SystemExit('Secrets file already exists. Keep it; review before replacing.')
        account = os.environ['CITYFLOW_SF_ACCOUNT']
        key = a.key.read_text().strip()
        if 'BEGIN PRIVATE KEY' not in key:
            raise SystemExit('Expected the generated unencrypted PKCS8 private key.')
        a.output.parent.mkdir(parents=True, exist_ok=True)
        content = 'backend = "snowflake"\n\n[snowflake]\naccount = ' + json.dumps(account)
        content += '\nprivate_key_pem = """\n' + key + '\n"""\n'
        fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        print('Private credentials written; contents were not printed.')
        return
    if a.report.exists():
        raise SystemExit('Report exists. Choose another report path.')
    ids = []
    if a.command in ('export', 'fixture'):
        if a.snapshot.exists():
            raise SystemExit('Snapshot exists. Choose a new path; do not overwrite reviewed data.')
        if a.command == 'export':
            import tomllib
            settings = tomllib.loads((ROOT / '.streamlit/secrets.toml').read_text())['snowflake']
            data, ids = read_cloud(settings, check_privileges=True)
            dataset = 'real'
        else:
            data, dataset = local_data(a.database, 'fixture'), 'fixture'
        compare(data, a.database, dataset)
        payload = make_payload(data)
        # Roundtrip the exact bytes intended for public hosting before writing.
        from cloud_dashboard.backend import frames
        roundtrip = frames(payload)
        compare(roundtrip, a.database, dataset)
        a.snapshot.parent.mkdir(parents=True, exist_ok=True)
        a.snapshot.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    else:
        data = read_snapshot(a.snapshot)
        dataset = data['metadata'].iloc[0].dataset
        compare(data, a.database, dataset)
    data = read_snapshot(a.snapshot)
    report = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'all_equal': True, 'scope': 'Every published cell across four bounded serving tables; '
              'not a new full-mart parity check.', 'counts': validate(data), 'query_ids': ids,
              'raw_access_denied': True if a.command == 'export' else None,
              'snapshot_sha256': snapshot_digest(a.snapshot), 'snapshot_bytes': a.snapshot.stat().st_size}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('Every published cell matched local analytics. Report:', a.report)


if __name__ == '__main__':
    main()
