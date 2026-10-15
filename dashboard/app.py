"""Run with python -m streamlit run dashboard/app.py from the repository root."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data import START, END, Warehouse, comparison_note, number, safe_route_table

st.set_page_config(page_title='CityFlow | NYC taxi activity', page_icon='🚕', layout='wide')


@st.cache_data(show_spinner=False, max_entries=16)
def load_context(path, signature, dataset):
    return Warehouse(path).validate(dataset)


@st.cache_data(show_spinner=False, max_entries=32)
def load_daily(path, signature, start, end):
    return Warehouse(path).daily(start, end)


@st.cache_data(show_spinner=False, max_entries=32)
def load_monthly(path, signature, start, end):
    return Warehouse(path).monthly_activity(start, end)


@st.cache_data(show_spinner=False, max_entries=16)
def load_routes(path, signature, geographic_only):
    return Warehouse(path).routes(geographic_only)


@st.cache_data(show_spinner=False, max_entries=64)
def load_route(path, signature, route_key):
    return Warehouse(path).route_months(route_key)


def activity(path, signature):
    st.header('Activity across time')
    st.caption('Choose pickup dates. Monthly statistics use only the selected days.')
    dates = st.date_input('Pickup date range', value=(START, END),
                          min_value=START, max_value=END, key='activity_dates')
    if len(dates) != 2:
        st.info('Choose both a start date and an end date.')
        return
    start, end = dates
    with st.spinner('Reading activity…'):
        daily = load_daily(path, signature, start, end)
        monthly = load_monthly(path, signature, start, end)
    total = int(daily['trip_count'].sum())
    cols = st.columns(4)
    cols[0].metric('Observed trips', number(total))
    cols[1].metric('Trips / selected calendar day', number(total / len(daily), 1))
    cols[2].metric('Eligible duration records', number(monthly['duration_records'].sum()))
    cols[3].metric('Eligible fare records', number(monthly['fare_records'].sum()))
    chart = daily.rename(columns={'trip_count': 'Recorded trips',
                                  'trailing_7_day_mean': 'Trailing 7-day mean'})
    fig = px.line(chart, x='date_day', y=['Recorded trips', 'Trailing 7-day mean'],
                  color_discrete_sequence=['#147D92', '#E89638'],
                  labels={'date_day': 'Pickup date', 'value': 'Trips', 'variable': ''})
    fig.update_layout(legend=dict(orientation='h', y=1.12), margin=dict(t=45, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption('The trailing mean needs seven complete calendar days. Filtering retains '
               'earlier days in that window; the first six days of the snapshot have no mean.')
    st.subheader('Monthly activity within selected dates')
    st.dataframe(monthly, hide_index=True, use_container_width=True)
    st.caption('Medians and p90 are recomputed from individual eligible trip records. '
               'Partial months use selected calendar days, including days with zero trips.')
    st.download_button('Download selected activity', monthly.to_csv(index=False).encode(),
                       file_name='cityflow_selected_activity.csv', mime='text/csv')


def route_view(path, signature, threshold):
    st.header('Compare a directed route')
    st.caption('Route metrics use whole pickup months. Origin → destination is directional.')
    all_routes = st.checkbox('Include unmapped and outside-city routes', key='include_other')
    catalog = load_routes(path, signature, not all_routes).copy()
    catalog['origin'] = catalog.route_key.str.split('->').str[0]
    catalog['destination'] = catalog.route_key.str.split('->').str[1]
    if catalog.empty:
        st.info('No routes match this category.')
        return
    origins = catalog.drop_duplicates('origin').set_index('origin')
    origin = st.selectbox('Origin', origins.index.tolist(), key='origin',
                          format_func=lambda k: f'{k} · {origins.loc[k, "pickup_zone_name"]} '
                                                f'({origins.loc[k, "pickup_borough"]})')
    destinations = catalog[catalog.origin == origin].set_index('destination')
    destination = st.selectbox('Destination', destinations.index.tolist(), key='destination',
                               format_func=lambda k: f'{k} · {destinations.loc[k, "dropoff_zone_name"]} '
                                                     f'({destinations.loc[k, "dropoff_borough"]})')
    route_key = origin + '->' + destination
    rows = load_route(path, signature, route_key)
    if rows.empty:
        st.info('No observations of this route anywhere in the snapshot.')
        return
    selected = st.selectbox('Comparison month', rows.month_start.dt.date.tolist(),
                            index=len(rows)-1, format_func=lambda d: d.strftime('%B %Y'),
                            key='route_month')
    row = rows.loc[rows.month_start.dt.date == selected].iloc[0]
    safe = safe_route_table(rows)
    current = safe.loc[safe.month_start.dt.date == selected].iloc[0]
    cols = st.columns(4)
    cols[0].metric('Observed trips', number(row.trip_count))
    cols[1].metric('Trips / calendar day', number(row.trips_per_calendar_day, 2))
    cols[2].metric('Median duration (min)', number(current.median_duration_minutes, 2))
    cols[3].metric('Median fare (USD)', number(current.median_fare_usd, 2, '$'))
    st.caption(f'Duration cohort: {int(row.duration_records):,} · Fare cohort: '
               f'{int(row.fare_records):,} · Route metric threshold: {threshold:,}')
    if not row.duration_sample_sufficient or not row.fare_sample_sufficient:
        st.info('A dash means the eligible cohort is below the route threshold. '
                'Duration and fare eligibility are assessed independently.')
    st.caption(comparison_note(row))
    delta_cols = st.columns(3)
    delta_cols[0].metric('Trips/day change (%)', number(row.trips_per_day_change_pct, 2))
    delta_cols[1].metric('Median duration change (min)', number(row.median_duration_change_minutes, 2))
    delta_cols[2].metric('Median fare change (USD)', number(row.median_fare_change_usd, 2, '$'))
    st.plotly_chart(px.bar(safe, x='month_start', y='trip_count',
                          labels={'month_start': 'Pickup month', 'trip_count': 'Recorded trips'},
                          color_discrete_sequence=['#147D92']), use_container_width=True)
    columns = ['month_start', 'trip_count', 'trips_per_calendar_day', 'duration_records',
               'fare_records', 'median_duration_minutes', 'p90_duration_minutes',
               'median_fare_usd', 'volume_rank']
    st.dataframe(safe[columns], hide_index=True, use_container_width=True)
    st.download_button('Download this route', safe[columns].to_csv(index=False).encode(),
                       file_name='cityflow_selected_route.csv', mime='text/csv')
    st.caption('Only routes observed somewhere in the snapshot appear in the selector. '
               'Their missing months become zero only for a complete validated snapshot. '
               'Volume ranks are monthly dense ranks among geographic routes with positive trips.')


def main():
    st.title('CityFlow')
    st.markdown('NYC yellow-taxi activity · January–March 2025')
    dataset = os.environ.get('CITYFLOW_DASHBOARD_DATASET', 'real')
    path = str(Path(os.environ.get('CITYFLOW_DASHBOARD_DATABASE',
                                   ROOT / 'data/warehouse/cityflow.duckdb')).expanduser().resolve())
    try:
        stat = Path(path).stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        with st.spinner('Checking the selected snapshot…'):
            context = load_context(path, signature, dataset)
        if dataset == 'fixture':
            st.warning('SYNTHETIC FIXTURE — 13 raw records / 12 observed trips. Not real NYC results.')
        else:
            st.caption('Validated local snapshot · 11,198,001 observed trips · 90 calendar days')
        view = st.sidebar.radio('Explore', ['Activity', 'Directed route'], key='view')
        st.sidebar.caption('DuckDB · local read-only data')
        if view == 'Activity':
            activity(path, signature)
        else:
            route_view(path, signature, context['minimum_metric_records'])
    except Exception as exc:
        st.error('Dashboard data could not be loaded.')
        st.write(str(exc))
        st.info('Check the database path and dataset label. If the warehouse is locked, '
                'stop ingestion/dbt writers before opening the dashboard. See docs/dashboard_design.md.')
        return
    with st.expander('Definitions and interpretation'):
        st.markdown('Trips are observed source records with pickup dates inside the quarter. '
                    'Duration eligibility requires a finite duration greater than zero and at most '
                    '180 minutes. Fare eligibility requires a finite nonnegative fare. '
                    'Patterns are descriptive; trip mix, payment categories and source coverage '
                    'affect comparisons. These values are not travel-time forecasts. '
                    'Source-local wall-clock durations retain daylight-saving ambiguity.')


if __name__ == '__main__':
    main()
