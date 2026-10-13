"""Turn the tiny committed CSV fixtures into local source files for a demo."""
import argparse
import shutil
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/demo_raw')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as con:
        con.execute('''
            CREATE TABLE fixture AS SELECT * FROM read_csv_auto(?)
        ''', [str(ROOT / 'tests/fixtures/trips.csv')])
        for month in ('2025-01', '2025-02', '2025-03'):
            path = args.output_dir / f'yellow_tripdata_{month}.parquet'
            con.execute('''
                CREATE OR REPLACE TEMP TABLE selected_fixture AS
                SELECT * EXCLUDE (source_month) FROM fixture WHERE source_month = ?
            ''', [month])
            con.execute('COPY selected_fixture TO ? (FORMAT PARQUET)', [str(path)])
            print(path)
    shutil.copyfile(ROOT / 'tests/fixtures/zones.csv',
                    args.output_dir / 'taxi_zone_lookup.csv')


if __name__ == '__main__':
    main()
