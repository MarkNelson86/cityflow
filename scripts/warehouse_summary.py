"""Print current registry and export a quality summary from built dbt models."""
import argparse
import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path,
                        default=ROOT / 'data/warehouse/cityflow.duckdb')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/quality_summary.csv')
    args = parser.parse_args()
    with duckdb.connect(str(args.database), read_only=True) as con:
        print('Current successful source versions:')
        for row in con.execute('''
            SELECT partition_key, row_count, left(source_sha256, 12), loaded_at
            FROM meta.loaded_sources ORDER BY partition_key
        ''').fetchall():
            print(row)
        result = con.execute((ROOT / 'sql/quality_summary.sql').read_text())
        fields = [c[0] for c in result.description]
        rows = result.fetchall()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows(rows)
        print('\nQuality summary:')
        for row in rows:
            print(dict(zip(fields, row)))
        print('\nSaved:', args.output)


if __name__ == '__main__':
    main()
