"""Fixture and committed-snapshot tests; no network or cloud credentials required."""
import copy
import json
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from cloud_dashboard.backend import frames, make_payload, read_snapshot, snapshot_digest, validate
from scripts.publish_dashboard import compare, local_data

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixture_database():
    path = Path(os.environ.get('CITYFLOW_DASHBOARD_FIXTURE_DB',
                               ROOT / 'reports/ci-hosting-fixture/work/pipeline_fixture.duckdb'))
    if not path.is_file():
        pytest.fail('Build the CI fixture and set CITYFLOW_DASHBOARD_FIXTURE_DB first.')
    return path


@pytest.fixture
def payload(fixture_database):
    return make_payload(local_data(fixture_database, 'fixture'))


def test_every_published_fixture_cell_matches(payload, fixture_database):
    assert compare(frames(payload), fixture_database, 'fixture')
    assert validate(frames(payload))['published_route_month_rows'] == 12


def test_publish_suppresses_metrics_before_download(payload):
    data = frames(payload)
    row = data['routes'].loc[(data['routes'].route_key == '999->2') &
                            (data['routes'].month_start.dt.month == 1)].iloc[0]
    assert row.duration_records == 1
    assert str(row.median_duration_minutes) == 'nan'


def test_reject_incomplete_calendar(payload):
    payload['tables']['daily'].pop()
    with pytest.raises(ValueError):
        frames(payload)


def test_reject_unsuppressed_metric(payload):
    for row in payload['tables']['routes']:
        if not row['duration_sample_sufficient']:
            row['median_duration_minutes'] = 123
            break
    with pytest.raises(ValueError, match='suppressed'):
        frames(payload)


def test_reject_wrong_dataset_label(payload):
    payload['tables']['metadata'][0]['dataset'] = 'real'
    with pytest.raises(ValueError):
        frames(payload)


def test_zero_previous_month_remains_undefined(payload):
    data = frames(payload)
    row = data['routes'].loc[(data['routes'].route_key == '1->2') &
                            (data['routes'].month_start.dt.month == 3)].iloc[0]
    assert row.previous_trip_count == 0
    assert str(row.trips_per_day_change_pct) == 'nan'


def test_app_period_route_and_unknown_cohort(payload, tmp_path, monkeypatch):
    import cloud_dashboard.backend as backend
    path = tmp_path / 'public_snapshot.json'
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(backend, 'SNAPSHOT', path)
    monkeypatch.setenv('CITYFLOW_HOSTING_BACKEND', 'snapshot')
    app = AppTest.from_file(str(ROOT / 'cloud_dashboard/app.py')).run(timeout=30)
    assert not app.exception and not app.error
    assert app.metric[0].value == '12'
    app.selectbox(key='activity_period').set_value('February 2025').run()
    assert app.metric[0].value == '3'
    app.sidebar.radio(key='view').set_value('Directed route').run()
    app.selectbox(key='route').set_value('1->2').run()
    assert any('undefined' in c.value for c in app.caption)
    app.checkbox(key='include_other').set_value(True).run()
    app.selectbox(key='route').set_value('999->2').run()
    from datetime import date
    app.selectbox(key='route_month').set_value(date(2025, 1, 1)).run()
    assert app.metric[2].value == '—'
    assert not app.exception


def test_missing_snapshot_has_safe_error(tmp_path, monkeypatch):
    import cloud_dashboard.backend as backend
    monkeypatch.setattr(backend, 'SNAPSHOT', tmp_path / 'missing.json')
    monkeypatch.setenv('CITYFLOW_HOSTING_BACKEND', 'snapshot')
    app = AppTest.from_file(str(ROOT / 'cloud_dashboard/app.py')).run(timeout=30)
    assert not app.exception
    assert 'unavailable' in app.error[0].value


def test_committed_public_snapshot_matches_deployment_report():
    snapshot = ROOT / 'cloud_dashboard/public_snapshot.json'
    report = json.loads((ROOT / 'docs/hosting_results/published_parity.json').read_text())
    counts = validate(read_snapshot(snapshot))
    assert counts['dataset'] == 'real'
    assert counts == report['counts']
    assert snapshot_digest(snapshot) == report['snapshot_sha256']
    assert snapshot.stat().st_size == report['snapshot_bytes']
