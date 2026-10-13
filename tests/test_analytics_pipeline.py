"""Check boundary dates, zero months, rank ties, quantiles and missing coverage."""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from scripts.ingest_sources import ingest

ROOT = Path(__file__).resolve().parents[1]


def test_analytics_calendars_cohorts_and_comparisons(tmp_path):
    raw, db = tmp_path / 'raw', tmp_path / 'fixture_analytics.duckdb'
    subprocess.run([sys.executable, str(ROOT / 'scripts/make_analytics_demo.py'),
                    '--output-dir', str(raw)], check=True, capture_output=True)
    config = json.loads((ROOT / 'config/demo_sources.json').read_text())
    ingest(db, raw, config)
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

    def run_dbt(command, *selection):
        run = subprocess.run([dbt, command, '--project-dir', str(project),
                              '--profiles-dir', str(profiles),
                              '--vars', '{analytics_min_records: 2}', *selection],
                             cwd=tmp_path, capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + '\n' + run.stderr

    run_dbt('build')
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute('SELECT count(*), sum(trip_count) '
                           'FROM analytics.mart_daily_activity').fetchone() == (90, 12)
        assert con.execute('SELECT count(*) FROM analytics.mart_route_monthly').fetchone() == (12,)
        jan = con.execute("SELECT trip_count, median_duration_minutes, p90_duration_minutes "
                          "FROM analytics.mart_route_monthly WHERE route_key='1->2' "
                          "AND month_start=date '2025-01-01'").fetchone()
        assert jan == pytest.approx((3, 20, 28))
        assert con.execute("SELECT trip_count, median_duration_minutes, volume_rank "
                           "FROM analytics.mart_route_monthly WHERE route_key='1->2' "
                           "AND month_start=date '2025-02-01'").fetchone() == (0, None, None)
        march = con.execute("SELECT previous_trip_count, trip_count_change, "
                            "trip_count_change_pct, median_duration_change_minutes "
                            "FROM analytics.mart_route_month_comparison WHERE route_key='1->2' "
                            "AND month_start=date '2025-03-01'").fetchone()
        assert march == (0, 2, None, None)
        assert con.execute("SELECT trip_count FROM analytics.mart_daily_activity "
                           "WHERE date_day=date '2025-01-31'").fetchone() == (1,)
        assert con.execute("SELECT trip_count, median_duration_minutes "
                           "FROM analytics.mart_daily_activity "
                           "WHERE date_day=date '2025-01-01'").fetchone() == (0, None)
        assert con.execute("SELECT trips_per_calendar_day FROM analytics.mart_route_monthly "
                           "WHERE route_key='2->1' AND month_start=date '2025-02-01'").fetchone()[0] == pytest.approx(2 / 28)
        assert con.execute("SELECT volume_rank FROM analytics.mart_route_monthly "
                           "WHERE route_key='999->2' AND month_start=date '2025-01-01'").fetchone() == (None,)
        # Both NYC routes have two March records, so they share dense rank 1.
        assert con.execute("SELECT volume_rank FROM analytics.mart_route_monthly "
                           "WHERE route_key='1->2' AND month_start=date '2025-03-01'").fetchone() == (1,)
        assert con.execute("SELECT volume_rank FROM analytics.mart_route_monthly "
                           "WHERE route_key='2->1' AND month_start=date '2025-03-01'").fetchone() == (1,)
        change = con.execute("SELECT trip_count_change, trips_per_day_change_pct, "
                             "median_duration_change_minutes FROM analytics.mart_route_month_comparison "
                             "WHERE route_key='2->1' AND month_start=date '2025-03-01'").fetchone()
        assert change == pytest.approx((0, -9.6774193548, 20))
    out = tmp_path / 'exports'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/export_analytics.py'),
                             '--database', str(db), '--output-dir', str(out),
                             '--label', 'Synthetic analytics fixture'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with (out / 'monthly_activity.csv').open() as stream:
        monthly = list(csv.DictReader(stream))
    assert [int(r['trip_count']) for r in monthly] == [5, 3, 4]
    assert float(monthly[0]['median_duration_minutes']) == 15
    # A missing partition must not be reinterpreted as zero observed activity.
    with duckdb.connect(str(db)) as con:
        con.execute("DELETE FROM meta.loaded_sources WHERE source_month='2025-02'")
    run_dbt('run', '--select', 'tag:analytics')
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute('SELECT count(*) FROM analytics.mart_daily_activity '
                           'WHERE NOT snapshot_complete AND trip_count IS NULL').fetchone() == (90,)
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/export_analytics.py'),
                             '--database', str(db), '--output-dir', str(tmp_path / 'blocked')],
                            capture_output=True, text=True)
    assert result.returncode != 0 and 'Incomplete snapshot' in result.stderr
    assert not (tmp_path / 'blocked').exists()
