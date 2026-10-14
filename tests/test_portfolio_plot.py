"""Check the plot's calendar, denominators and full-window smoothing contract."""
import csv
import json

import pytest

from scripts.plot_portfolio import DAYS, MONTHS, load_inputs


def inputs(tmp_path):
    daily = tmp_path / 'daily.csv'
    monthly = tmp_path / 'monthly.csv'
    metadata = tmp_path / 'metadata.json'
    daily_rows = [{'date_day': str(day), 'trip_count': index + 1, 'snapshot_complete': 'True'}
                  for index, day in enumerate(DAYS)]
    monthly_rows = []
    for month, count_days in MONTHS:
        count = sum(index + 1 for index, day in enumerate(DAYS) if day.month == month.month)
        monthly_rows.append({'month_start': str(month), 'trip_count': count,
                             'calendar_days': count_days, 'trips_per_calendar_day': count / count_days})
    write(daily, daily_rows)
    write(monthly, monthly_rows)
    metadata.write_text(json.dumps({'label': 'Synthetic test fixture', 'observed_records': 4095}))
    return daily, monthly, metadata, daily_rows, monthly_rows


def write(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_complete_calendar_reconciliation_and_trailing_mean(tmp_path):
    daily, monthly, metadata, _, _ = inputs(tmp_path)
    data = load_inputs(daily, monthly, metadata)
    assert data['observed_records'] == 4095
    assert data['rolling'][:6] == [None] * 6
    assert data['rolling'][6] == 4 and data['rolling'][-1] == 87
    assert data['monthly_rates'] == [16, 45.5, 75]


def test_missing_day_and_incomplete_coverage_are_not_silently_zeroed(tmp_path):
    daily, monthly, metadata, rows, _ = inputs(tmp_path)
    write(daily, rows[1:])
    with pytest.raises(ValueError, match='exactly once'):
        load_inputs(daily, monthly, metadata)
    rows[0]['snapshot_complete'] = 'False'
    write(daily, rows)
    with pytest.raises(ValueError, match='incomplete source coverage'):
        load_inputs(daily, monthly, metadata)


def test_mismatched_monthly_counts_and_export_total_are_rejected(tmp_path):
    daily, monthly, metadata, _, rows = inputs(tmp_path)
    rows[0]['trip_count'] += 1
    write(monthly, rows)
    with pytest.raises(ValueError, match='do not reconcile'):
        load_inputs(daily, monthly, metadata)
    rows[0]['trip_count'] -= 1
    write(monthly, rows)
    metadata.write_text(json.dumps({'label': 'Synthetic test fixture', 'observed_records': 4096}))
    with pytest.raises(ValueError, match='totals do not reconcile'):
        load_inputs(daily, monthly, metadata)
