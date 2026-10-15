"""Public whole-month dashboard; backend is controlled by deployment settings."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import plotly.express as px
import streamlit as st
from cloud_dashboard.backend import SNAPSHOT, read_cloud, read_snapshot, validate

st.set_page_config(page_title='CityFlow | NYC taxi activity', page_icon='🚕', layout='wide')


def number(value, decimals=0, prefix=''):
    return '—' if pd.isna(value) else prefix + f'{value:,.{decimals}f}'


@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)
def load_live(settings):
    return read_cloud(settings)[0]


@st.cache_data(max_entries=2, show_spinner=False)
def load_file(signature):
    return read_snapshot(SNAPSHOT)


def main():
    st.title('CityFlow')
    st.markdown('NYC yellow-taxi activity · January–March 2025')
    backend = os.environ.get('CITYFLOW_HOSTING_BACKEND')
    if not backend:
        try:
            backend = st.secrets.get('backend', 'snapshot')
        except FileNotFoundError:
            backend = 'snapshot'
    try:
        if backend == 'snapshot':
            stat = SNAPSHOT.stat()
            data = load_file((stat.st_size, stat.st_mtime_ns))
        elif backend == 'snowflake':
            data = load_live(dict(st.secrets['snowflake']))
        else:
            raise ValueError('Unknown backend setting.')
        info = validate(data)
    except Exception as exc:
        # Connector errors can embed account identifiers; show only their class publicly.
        st.error('The validated dashboard snapshot is currently unavailable.')
        st.caption(f'Error type: {type(exc).__name__}. The app owner can use the deployment guide to diagnose it.')
        return
    if info['dataset'] == 'fixture':
        st.warning('SYNTHETIC FIXTURE — 12 observed trips. Not real NYC results.')
    label = 'Snowflake serving tables · cached for up to one hour' if backend == 'snowflake' else 'Published Snowflake aggregate snapshot · no live database connection'
    st.caption(label)
    st.caption(f"{info['observed_records']:,} observed trips · 90 calendar days · "
               f"{info['published_routes']:,} selected directed routes")
    st.sidebar.caption('Whole-month activity and a bounded route selection. '
                       'The local dashboard supports arbitrary date ranges and the full route catalog.')
    view = st.sidebar.radio('Explore', ['Activity', 'Directed route'], key='view')
    monthly = data['monthly'].sort_values('month_start')
    if view == 'Activity':
        options = ['Full quarter'] + monthly.month_start.dt.strftime('%B %Y').tolist()
        selected = st.selectbox('Activity period', options, key='activity_period')
        selected_monthly = monthly if selected == 'Full quarter' else monthly.loc[
            monthly.month_start.dt.strftime('%B %Y') == selected]
        daily = data['daily'].sort_values('date_day')
        if selected != 'Full quarter':
            daily = daily.loc[daily.date_day.dt.to_period('M') == selected_monthly.iloc[0].month_start.to_period('M')]
        cols = st.columns(4)
        cols[0].metric('Observed trips', number(selected_monthly.trip_count.sum()))
        cols[1].metric('Trips / calendar day', number(selected_monthly.trip_count.sum() / len(daily), 1))
        cols[2].metric('Eligible duration records', number(selected_monthly.duration_records.sum()))
        cols[3].metric('Eligible fare records', number(selected_monthly.fare_records.sum()))
        st.plotly_chart(px.line(daily, x='date_day', y=['trip_count', 'trailing_7_day_mean'],
                               labels={'date_day': 'Pickup date', 'value': 'Trips', 'variable': ''}),
                        use_container_width=True)
        st.caption('Trailing mean is calculated on the full calendar before filtering. '
                   'The first six snapshot days have no seven-day mean.')
        st.subheader('Whole-month statistics')
        st.dataframe(selected_monthly, hide_index=True, use_container_width=True)
        st.caption('Each monthly median and p90 comes from individual eligible records. '
                   'No quarter-wide median is inferred from monthly medians.')
        download = selected_monthly
    else:
        st.header('Compare a selected directed route')
        include_other = st.checkbox('Include selected unmapped and outside-city routes', key='include_other')
        rows = data['routes'].copy()
        catalog = rows.drop_duplicates('route_key')
        if not include_other:
            catalog = catalog.loc[catalog.is_geographic_route]
        if catalog.empty:
            st.info('No routes in this category.')
            return
        lookup = catalog.set_index('route_key')
        route = st.selectbox('Directed route', catalog.route_key.tolist(), key='route',
            format_func=lambda k: f'{k} · {lookup.loc[k, "pickup_zone_name"]} → {lookup.loc[k, "dropoff_zone_name"]}')
        selected_rows = rows.loc[rows.route_key == route].sort_values('month_start')
        month = st.selectbox('Comparison month', selected_rows.month_start.dt.date.tolist(),
                             index=2, format_func=lambda d: d.strftime('%B %Y'), key='route_month')
        row = selected_rows.loc[selected_rows.month_start.dt.date == month].iloc[0]
        cols = st.columns(4)
        cols[0].metric('Observed trips', number(row.trip_count))
        cols[1].metric('Trips / calendar day', number(row.trips_per_calendar_day, 2))
        cols[2].metric('Median duration (min)', number(row.median_duration_minutes, 2))
        cols[3].metric('Median fare (USD)', number(row.median_fare_usd, 2, '$'))
        st.caption(f'Eligible duration records: {int(row.duration_records):,} · '
                   f'Eligible fare records: {int(row.fare_records):,} · Threshold: {int(row.minimum_metric_records)}')
        if not row.duration_sample_sufficient or not row.fare_sample_sufficient:
            st.info('A dash means that metric has an insufficient eligible cohort. Duration and fare are checked independently.')
        if pd.isna(row.previous_month_start):
            st.caption('No previous month within this snapshot.')
        elif row.previous_trip_count == 0:
            st.caption('Percentage change is undefined because the previous month had zero trips.')
        else:
            st.caption('Compared with the previous calendar month. Trips/day accounts for month length.')
        cols = st.columns(3)
        cols[0].metric('Trips/day change (%)', number(row.trips_per_day_change_pct, 2))
        cols[1].metric('Median duration change (min)', number(row.median_duration_change_minutes, 2))
        cols[2].metric('Median fare change (USD)', number(row.median_fare_change_usd, 2, '$'))
        st.plotly_chart(px.bar(selected_rows, x='month_start', y='trip_count',
                               labels={'month_start': 'Pickup month', 'trip_count': 'Trips'}), use_container_width=True)
        display = ['month_start', 'trip_count', 'trips_per_calendar_day', 'duration_records',
                   'fare_records', 'median_duration_minutes', 'p90_duration_minutes', 'median_fare_usd', 'volume_rank']
        st.dataframe(selected_rows[display], hide_index=True, use_container_width=True)
        st.caption('Selected by total quarter volume: up to 100 geographic routes plus up to '
                   'five non-geographic routes. Their three-month grid preserves valid zero months. '
                   'Volume rank is among all geographic routes in the original monthly mart.')
        download = selected_rows[display]
    st.download_button('Download selected aggregates', download.to_csv(index=False).encode(),
                       file_name='cityflow_selected_aggregates.csv', mime='text/csv')
    with st.expander('Data and interpretation'):
        st.markdown('NYC TLC yellow-taxi source snapshot, January–March 2025. Descriptive recorded-trip '
                    'statistics, not travel-time forecasts. Duration eligibility: finite, greater than '
                    'zero and at most 180 minutes. Fare eligibility: finite and nonnegative. '
                    'Source-local wall-clock durations retain daylight-saving ambiguity. '
                    'The public app serves aggregates only; it does not expose individual trips.')
        st.link_button('NYC TLC source data', 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page')


if __name__ == '__main__':
    main()
