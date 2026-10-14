"""Run the CI contract locally or on GitHub, entirely on generated fixture data."""
import argparse
import csv
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/ci')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit('Output directory is not empty; choose a new run directory')
    output.mkdir(parents=True, exist_ok=True)

    def run(name, command, cwd=ROOT):
        print(f'\n{name}:', flush=True)
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=240)
        log = result.stdout + '\n' + result.stderr
        (output / (name + '.log')).write_text(log)
        print(log, flush=True)
        if result.returncode:
            raise SystemExit(f'{name} failed; retained log: {output / (name + ".log")}')

    run('pytest', [sys.executable, '-m', 'pytest', '-q',
                   '--junitxml', str(output / 'pytest.xml')])
    work = output / 'work'
    raw, database, project = work / 'raw', work / 'pipeline_fixture.duckdb', work / 'dbt'
    run('make_fixture', [sys.executable, str(ROOT / 'scripts/make_analytics_demo.py'),
                         '--output-dir', str(raw)])
    run('ingest_fixture', [sys.executable, str(ROOT / 'scripts/ingest_sources.py'),
                           '--config', str(ROOT / 'config/demo_sources.json'),
                           '--raw-dir', str(raw), '--database', str(database)])
    shutil.copytree(ROOT / 'dbt', project,
                    ignore=shutil.ignore_patterns('target', 'logs', 'dbt_packages'))
    profiles = work / 'profiles'
    profiles.mkdir()
    (profiles / 'profiles.yml').write_text(
        'cityflow:\n  target: ci\n  outputs:\n    ci:\n'
        '      type: duckdb\n      schema: analytics\n      threads: 2\n'
        f'      path: {json.dumps(str(database))}\n')
    dbt = shutil.which('dbt') or str(Path(sys.executable).parent / 'dbt')
    run('dbt_build', [dbt, 'build', '--project-dir', str(project),
                      '--profiles-dir', str(profiles),
                      '--vars', '{analytics_min_records: 2}'], cwd=work)
    artifacts = output / 'dbt_artifacts'
    artifacts.mkdir()
    for filename in ('manifest.json', 'run_results.json'):
        shutil.copyfile(project / 'target' / filename, artifacts / filename)
    run('export_fixture', [sys.executable, str(ROOT / 'scripts/export_analytics.py'),
                           '--database', str(database), '--output-dir', str(output / 'exports'),
                           '--label', 'Synthetic CI fixture (13 raw records)'])
    with (output / 'exports/monthly_activity.csv').open() as stream:
        counts = [int(row['trip_count']) for row in csv.DictReader(stream)]
    if counts != [5, 3, 4]:
        raise SystemExit(f'Unexpected fixture pickup-month counts: {counts}')
    tests = ET.parse(output / 'pytest.xml').getroot()
    results = json.loads((artifacts / 'run_results.json').read_text())['results']
    summary = {
        'dataset': 'Synthetic CI fixture; independent of the real warehouse',
        'pytest_cases': len(list(tests.iter('testcase'))),
        'dbt_models': sum(row['unique_id'].startswith('model.') for row in results),
        'dbt_tests': sum(row['unique_id'].startswith('test.') for row in results),
        'dbt_successful': all(row['status'] in ('pass', 'success') for row in results),
        'monthly_observed_counts': counts, 'observed_records': sum(counts),
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print('CI contract passed. Retained evidence:', output)


if __name__ == '__main__':
    main()
