"""Export versioned local raw inputs, load once in Snowflake, compare every mart cell.
Run from the repo root. Cloud operations use browser authentication and dedicated databases.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
from decimal import Decimal
from pathlib import Path

TABLES = {'raw.trips': ['trip_id','source_month','source_sha256','source_row_number',
    'tpep_pickup_datetime','tpep_dropoff_datetime','PULocationID','DOLocationID',
    'trip_distance','fare_amount','total_amount'], 'raw.zones': ['LocationID','Borough',
    'Zone','service_zone','source_sha256'], 'meta.loaded_sources': ['partition_key',
    'source_kind','source_month','source_file','source_url','source_sha256','source_bytes',
    'source_schema','row_count','loaded_at']}
MARTS = {'mart_daily_activity':'date_day','mart_route_monthly':'route_month_key',
         'mart_route_month_comparison':'route_month_key'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def ident(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value):
        raise ValueError('Invalid identifier')
    return value.upper()


def connect():
    import snowflake.connector

    database = os.environ['CITYFLOW_SF_DATABASE'].upper()
    if database not in ('CITYFLOW_FIXTURE', 'CITYFLOW_REAL'):
        raise SystemExit('Use CITYFLOW_FIXTURE or CITYFLOW_REAL only.')

    return snowflake.connector.connect(
        account=os.environ['CITYFLOW_SF_ACCOUNT'],
        user=os.environ['CITYFLOW_SF_USER'],
        password=os.environ['CITYFLOW_SF_PASSWORD'],
        authenticator='snowflake',
        role='CITYFLOW_ROLE',
        warehouse='CITYFLOW_WH',
        database=database,
        session_parameters={
            'TIMEZONE': 'UTC',
            'DATE_OUTPUT_FORMAT': 'YYYY-MM-DD',
            'QUERY_TAG': 'cityflow_snowflake',
            'STATEMENT_TIMEOUT_IN_SECONDS': 600,
        },
    )


def export(a):
    import duckdb
    if a.output.exists() and any(a.output.iterdir()):
        raise SystemExit('Use an empty export output directory.')
    a.output.mkdir(parents=True, exist_ok=True)
    manifest = {'dataset':a.dataset, 'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'duckdb_version':duckdb.__version__, 'tables':[]}
    with duckdb.connect(str(a.database), read_only=True) as con:
        con.execute("set timezone='UTC'")
        for table, cols in TABLES.items():
            projected = []
            for c in cols:
                expr = '"' + c + '"'
                if c == 'loaded_at': expr = f'cast({expr} as timestamp)'
                if c == 'source_schema': expr = f'cast({expr} as varchar)'
                # Explicit timestamp microseconds; retain source wall-clock semantics.
                if c.startswith('tpep_'): expr = f'cast({expr} as timestamp)'
                projected.append(expr + ' as "' + c.upper() + '"')
            query = 'select ' + ', '.join(projected) + ' from ' + table
            types = con.execute('describe ' + query).fetchall()
            columns = []
            for c, t, *_ in types:
                if t in ('VARCHAR', 'JSON'): st = 'VARCHAR'
                elif t.startswith('TIMESTAMP'): st = 'TIMESTAMP_NTZ(6)'
                elif t == 'DATE': st = 'DATE'
                elif t == 'BOOLEAN': st = 'BOOLEAN'
                elif t in ('FLOAT','DOUBLE','REAL'): st = 'FLOAT'
                elif t.startswith('DECIMAL'): st = t
                elif t in ('TINYINT','SMALLINT','INTEGER','BIGINT','HUGEINT','UTINYINT','USMALLINT','UINTEGER','UBIGINT'): st = 'NUMBER(38,0)'
                else: raise ValueError(f'Unsupported type {t} for {c}')
                columns.append([c,st])
            path = a.output / (table.replace('.', '_') + '.parquet')
            con.execute(f'copy ({query}) to {literal(path.resolve())} (format parquet, compression zstd)')
            rows = con.execute('select count(*) from ' + table).fetchone()[0]
            manifest['tables'].append({'table':table.upper(), 'file':path.name,
                'rows':rows, 'sha256':digest(path), 'columns':columns})
        manifest['trip_partitions'] = con.execute('select source_month, source_sha256, count(*) from raw.trips group by 1,2 order by 1,2').fetchall()
    (a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Exported raw projection and source registry to', a.output)


def load(a):
    manifest = json.loads((a.input / 'manifest.json').read_text())
    if manifest['dataset'] != a.dataset:
        raise SystemExit('Manifest dataset label does not match --dataset')
    required = 'CITYFLOW_FIXTURE' if a.dataset == 'fixture' else 'CITYFLOW_REAL'
    if os.environ['CITYFLOW_SF_DATABASE'].upper() != required:
        raise SystemExit('Dataset/database mismatch')
    for t in manifest['tables']:
        if digest(a.input / t['file']) != t['sha256']: raise SystemExit('Changed export file')
    with connect() as con:
        cur = con.cursor()
        existing = cur.execute("select count(*) from information_schema.tables where table_schema in ('RAW','META')").fetchone()[0]
        if existing: raise SystemExit('RAW/META already contain tables. This is a one-shot loader; inspect partial or previous load before resetting the dedicated database.')
        cur.execute('create stage RAW.SNAPSHOT_STAGE')
        report = {'dataset':a.dataset,'tables':[], 'query_ids':[]}
        for t in manifest['tables']:
            table = '.'.join(ident(x) for x in t['table'].split('.'))
            ddl = ', '.join(ident(c) + ' ' + typ for c,typ in t['columns'])
            cur.execute(f'create table {table} ({ddl})')
            path = (a.input / t['file']).resolve()
            uri = 'file://' + path.as_posix()
            put = cur.execute(f'put {literal(uri)} @RAW.SNAPSHOT_STAGE auto_compress=false overwrite=false').fetchall()
            if not put or any(str(row[6]).upper() not in ('UPLOADED','SKIPPED') for row in put):
                raise SystemExit('PUT did not succeed')
            cur.execute(f"copy into {table} from @RAW.SNAPSHOT_STAGE files=({literal(t['file'])}) file_format=(type=parquet use_logical_type=true) match_by_column_name=case_insensitive on_error=abort_statement")
            qid = cur.sfqid
            copies = cur.fetchall()
            if not copies or any(str(row[1]).upper() != 'LOADED' for row in copies):
                raise SystemExit('COPY did not fully load')
            rows = cur.execute(f'select count(*) from {table}').fetchone()[0]
            if rows != t['rows']: raise SystemExit('Loaded count mismatch')
            report['tables'].append({'table':table,'rows':rows,'export_sha256':t['sha256']})
            report['query_ids'].append(qid)
        partitions = cur.execute('select source_month, source_sha256, count(*) from RAW.TRIPS group by 1,2 order by 1,2').fetchall()
        if [list(x) for x in partitions] != manifest['trip_partitions']:
            raise SystemExit('Partition/hash count mismatch')
        report['trip_partitions_verified'] = True
        cur.execute('remove @RAW.SNAPSHOT_STAGE')
        cur.execute('drop stage RAW.SNAPSHOT_STAGE')
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('Loaded and verified:', a.report)


def equal(x, y, floating=False):
    if x is None or y is None: return x is None and y is None
    if floating:
        return math.isclose(float(x),float(y),rel_tol=1e-12,abs_tol=1e-9)
    return x == y


def parity(a):
    import duckdb
    report = {'dataset':a.dataset,'all_equal':True,'float_absolute_tolerance':1e-9,
              'float_relative_tolerance':1e-12, 'models':[]}
    required = 'CITYFLOW_FIXTURE' if a.dataset == 'fixture' else 'CITYFLOW_REAL'
    if os.environ['CITYFLOW_SF_DATABASE'].upper() != required: raise SystemExit('Dataset/database mismatch')
    with duckdb.connect(str(a.database),read_only=True) as local, connect() as cloud:
        for model,key in MARTS.items():
            desc = local.execute('describe analytics.' + model).fetchall()
            cols = [x[0] for x in desc]
            floating = [x[1] in ('FLOAT','DOUBLE','REAL') or x[1].startswith('DECIMAL') for x in desc]
            query = 'select ' + ','.join(cols) + ' from analytics.' + model + ' order by ' + key
            left = local.execute(query).fetchall()
            cur = cloud.cursor().execute(query)
            cloud_cols = [x[0].lower() for x in cur.description]
            right = cur.fetchall()
            if cloud_cols != [x.lower() for x in cols]: raise SystemExit('Column mismatch')
            mismatches = []
            if len(left) != len(right): mismatches.append({'row_counts':[len(left),len(right)]})
            for row_i,(lrow,rrow) in enumerate(zip(left,right)):
                for col_i,(x,y) in enumerate(zip(lrow,rrow)):
                    if not equal(x,y,floating[col_i]):
                        if len(mismatches)<20:
                            mismatches.append({'row':row_i,'key':str(lrow[cols.index(key)]),
                                'column':cols[col_i],'duckdb':str(x),'snowflake':str(y)})
                        report['all_equal'] = False
            if mismatches: report['all_equal'] = False
            report['models'].append({'model':model,'local_rows':len(left),
                'cloud_rows':len(right),'query_id':cur.sfqid,'mismatch_examples':mismatches})
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2) + '\n')
    if not report['all_equal']: raise SystemExit('Parity failed; see ' + str(a.report))
    print('Every mart row and column matched:', a.report)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    e = sub.add_parser('export'); e.add_argument('--database',type=Path,required=True)
    e.add_argument('--output',type=Path,required=True)
    l = sub.add_parser('load'); l.add_argument('--input',type=Path,required=True)
    l.add_argument('--report',type=Path,required=True)
    r = sub.add_parser('parity'); r.add_argument('--database',type=Path,required=True)
    r.add_argument('--report',type=Path,required=True)
    for s in (e,l,r): s.add_argument('--dataset',choices=['fixture','real'],required=True)
    a = p.parse_args()
    if hasattr(a,'report') and a.report.exists(): raise SystemExit('Report exists; choose a new report path.')
    {'export':export,'load':load,'parity':parity}[a.command](a)


if __name__ == '__main__':
    main()
