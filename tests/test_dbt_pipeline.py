"""A tiny end-to-end demonstration verifies SQL cohorts and joins."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

from scripts.ingest_sources import ingest

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_pipeline_preserves_rows_and_builds_correct_cohorts(tmp_path):
    raw = tmp_path / 'raw'
    db = tmp_path / 'fixture.duckdb'
    subprocess.run([sys.executable, str(ROOT / 'scripts/make_demo_sources.py'),
                    '--output-dir', str(raw)], check=True, capture_output=True)
    config = json.loads((ROOT / 'config/demo_sources.json').read_text())
    ingest(db, raw, config)
    rerun = ingest(db, raw, config)
    assert all(r['action'] == 'skipped' for r in rerun)
    project = tmp_path / 'dbt'
    shutil.copytree(ROOT / 'dbt', project,
                    ignore=shutil.ignore_patterns('target', 'logs', 'dbt_packages'))
    profiles = tmp_path / 'profiles'
    profiles.mkdir()
    (profiles / 'profiles.yml').write_text(
        'cityflow:\n  target: fixture\n  outputs:\n    fixture:\n'
        '      type: duckdb\n      schema: analytics\n      threads: 2\n'
        f'      path: {json.dumps(str(db))}\n'
    )
    dbt = shutil.which('dbt') or str(Path(sys.executable).parent / 'dbt')
    run = subprocess.run([dbt, 'build', '--project-dir', str(project),
                          '--profiles-dir', str(profiles)], cwd=tmp_path,
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + '\n' + run.stderr
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute('''
            SELECT count(*), count(*) FILTER (WHERE is_observed_trip),
                   count(*) FILTER (WHERE is_duration_eligible),
                   count(*) FILTER (WHERE is_fare_eligible),
                   count(*) FILTER (WHERE NOT pickup_zone_found)
            FROM analytics.fact_trips
        ''').fetchone() == (11, 9, 6, 7, 1)
        assert con.execute('SELECT count(*) FROM analytics.dim_dates').fetchone() == (90,)
        assert con.execute('SELECT count(*) FROM analytics.dim_zones').fetchone() == (2,)
