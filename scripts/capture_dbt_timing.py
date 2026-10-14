"""Preserve the latest dbt run artifact and distinguish node times from wall time."""
import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'dbt/target/run_results.json')
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'reports/performance/dbt_analytics')
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    if data.get('args', {}).get('which') != 'build':
        raise SystemExit('Latest artifact is not a dbt build; capture immediately after the build')
    results = data['results']
    if not results or any(row['status'] not in ('success', 'pass') for row in results):
        raise SystemExit('Capture requires a successful build with model/test results')
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit('Output directory is not empty; choose a new run directory')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.input, args.output_dir / 'run_results.json')
    rows = [{'unique_id': row['unique_id'], 'status': row['status'],
             'execution_seconds': row['execution_time'], 'thread': row['thread_id']}
            for row in results]
    with (args.output_dir / 'node_timings.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    models = sum(row['unique_id'].startswith('model.') for row in results)
    tests = sum(row['unique_id'].startswith('test.') for row in results)
    text = (f'# dbt build timing\n\n'
            f"dbt version: {data['metadata']['dbt_version']}. "
            f"Artifact generated: {data['metadata']['generated_at']}.\n\n"
            f"Successful models: {models}; passed tests: {tests}.\n\n"
            f"dbt-reported elapsed time: {data['elapsed_time']:.3f} seconds.\n\n"
            'This is one build measurement, not a multi-run benchmark. The artifact elapsed '
            'time is not the full shell-command duration including startup. Node execution '
            'times can overlap across threads; do not add them to estimate wall time. '
            'Keep build cost separate from the cost of reading saved marts.\n')
    (args.output_dir / 'summary.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
