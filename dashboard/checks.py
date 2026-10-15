"""Explicit dashboard tests; kept outside the existing 19-case base CI discovery."""
import os
import shutil
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.data import DashboardDataError, Warehouse, safe_route_table
from scripts.check_dashboard import validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database():
    path = Path(os.environ.get('CITYFLOW_DASHBOARD_FIXTURE_DB',
                               ROOT / 'reports/ci-dashboard-fixture/work/pipeline_fixture.duckdb'))
    if not path.is_file():
        pytest.fail('Build the existing CI fixture first; see the dashboard guide step 6.')
    return path


@pytest.fixture
def warehouse(database):
    return Warehouse(database)


def test_frozen_fixture_and_route_categories(warehouse):
    assert warehouse.validate('fixture')['observed_records'] == 12
    assert set(warehouse.routes().route_key) == {'1->2', '2->1'}
    assert set(warehouse.routes(False).route_key) == {'1->2', '2->1', '999->2', 'NULL->1'}


def test_activity_quantiles_partial_days_and_window(warehouse):
    daily = warehouse.daily()
    assert daily.trip_count.sum() == 12
    assert pd.isna(daily.trailing_7_day_mean.iloc[5])
    assert daily.trip_count.iloc[0] == 0
    monthly = warehouse.monthly_activity()
    assert monthly.trip_count.tolist() == [5, 3, 4]
    assert monthly.median_duration_minutes.tolist() == [15, 10, 30]
    selected = warehouse.monthly_activity(date(2025, 1, 15), date(2025, 1, 15)).iloc[0]
    assert selected.selected_calendar_days == 1 and selected.trip_count == 2
    assert selected.median_duration_minutes == 20 and selected.p90_duration_minutes == 28
    assert warehouse.daily(date(2025, 1, 15), date(2025, 1, 15)).iloc[0].trailing_7_day_mean == pytest.approx(2/7)
    assert warehouse.monthly_activity(date(2025, 1, 31), date(2025, 1, 31)).trip_count.tolist() == [1]


def test_zero_threshold_and_guarded_comparisons(warehouse):
    route = warehouse.route_months('1->2')
    assert route.trip_count.tolist() == [3, 0, 2]
    assert pd.isna(route.iloc[2].trip_count_change_pct)
    assert pd.isna(route.iloc[2].median_duration_change_minutes)
    unknown = safe_route_table(warehouse.route_months('999->2'))
    assert unknown.median_duration_minutes.isna().all()
    assert unknown.p90_duration_minutes.isna().all()
    assert unknown.median_fare_usd.isna().all()
    change = warehouse.route_months('2->1').iloc[2]
    assert change.median_duration_change_minutes == 20
    assert change.trips_per_day_change_pct == pytest.approx(-9.6774193548)


def test_route_values_are_parameterized(warehouse):
    assert warehouse.route_months("1->2' OR 1=1 --").empty


def test_connection_is_read_only(warehouse):
    with pytest.raises(duckdb.InvalidInputException, match='read-only'):
        warehouse.query('CREATE TABLE dashboard_must_not_write (id INTEGER)')


def test_fixture_cannot_be_mislabeled_real(warehouse):
    with pytest.raises(DashboardDataError, match='contract mismatch'):
        warehouse.validate('real')


@pytest.mark.parametrize('change', [
    "DELETE FROM meta.loaded_sources WHERE source_month='2025-02'",
    "UPDATE meta.loaded_sources SET source_sha256='stale' WHERE source_month='2025-01'",
    'UPDATE analytics.mart_daily_activity SET snapshot_complete=false',
])
def test_unready_data_blocked(database, tmp_path, change):
    copy = tmp_path / 'corrupt.duckdb'
    shutil.copyfile(database, copy)
    with duckdb.connect(str(copy)) as con:
        con.execute(change)
    with pytest.raises(ValueError):
        Warehouse(copy).validate('fixture')


def test_validation_report_independent_known_answers(database):
    result = validate(database, 'fixture')
    assert result['all_checks_passed']
    assert result['partial_window']['observed_records'] == 5


def test_streamlit_activity_route_and_categories(database, monkeypatch):
    monkeypatch.setenv('CITYFLOW_DASHBOARD_DATABASE', str(database.resolve()))
    monkeypatch.setenv('CITYFLOW_DASHBOARD_DATASET', 'fixture')
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    assert not app.exception and not app.error
    assert 'SYNTHETIC FIXTURE' in app.warning[0].value
    assert app.metric[0].value == '12'
    app.radio(key='view').set_value('Directed route').run()
    assert not app.exception and not app.error
    assert app.metric[0].value == '2' and app.metric[2].value == '30.00'
    assert any('previous month had zero trips' in c.value for c in app.caption)
    app.selectbox(key='route_month').set_value(date(2025, 2, 1)).run()
    assert app.metric[0].value == '0' and app.metric[2].value == '—'
    app.checkbox(key='include_other').set_value(True).run()
    app.selectbox(key='origin').set_value('999').run()
    app.selectbox(key='route_month').set_value(date(2025, 1, 1)).run()
    assert not app.error and not app.exception
    assert app.metric[0].value == '1' and app.metric[2].value == '—'


def test_streamlit_activity_date_filter(database, monkeypatch):
    monkeypatch.setenv('CITYFLOW_DASHBOARD_DATABASE', str(database.resolve()))
    monkeypatch.setenv('CITYFLOW_DASHBOARD_DATASET', 'fixture')
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    app.date_input(key='activity_dates').set_value((date(2025, 1, 15), date(2025, 1, 15))).run()
    assert not app.error and not app.exception
    assert app.metric[0].value == '2'


def test_streamlit_missing_database_explained(tmp_path, monkeypatch):
    monkeypatch.setenv('CITYFLOW_DASHBOARD_DATABASE', str(tmp_path / 'missing.duckdb'))
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30).run()
    assert not app.exception
    assert app.error[0].value == 'Dashboard data could not be loaded.'
