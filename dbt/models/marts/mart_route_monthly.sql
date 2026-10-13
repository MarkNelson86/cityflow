{{ config(tags=['analytics']) }}
{% set minimum = var('analytics_min_records', 30) | int %}
{% if minimum < 1 %}{{ exceptions.raise_compiler_error('analytics_min_records must be positive') }}{% endif %}

-- Route = ordered origin/destination IDs. Explicit text preserves null IDs.
with observed as (
    select *,
        coalesce(pickup_zone_id::varchar, 'NULL') || '->' ||
        coalesce(dropoff_zone_id::varchar, 'NULL') as route_key,
        cast(date_trunc('month', pickup_date) as date) as month_start,
        pickup_zone_found and dropoff_zone_found
        and pickup_borough in ('Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island')
        and dropoff_borough in ('Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island')
            as is_geographic_route
    from {{ ref('fact_trips') }}
    where is_observed_trip
), routes as (
    select distinct route_key, pickup_zone_id, dropoff_zone_id,
        pickup_zone_name, dropoff_zone_name, pickup_borough, dropoff_borough,
        is_geographic_route
    from observed
), months as (
    select month_start, count(*) as calendar_days
    from {{ ref('dim_dates') }} group by month_start
), monthly as (
    select route_key, month_start,
        count(*) as trip_count,
        count(*) filter (where is_duration_eligible) as duration_records,
        count(*) filter (where is_fare_eligible) as fare_records,
        median(duration_minutes) filter (where is_duration_eligible) as median_duration_minutes,
        quantile_cont(duration_minutes, 0.9) filter (where is_duration_eligible) as p90_duration_minutes,
        median(fare_amount) filter (where is_fare_eligible) as median_fare_usd
    from observed group by route_key, month_start
), coverage as (
    select {{ cityflow_snapshot_complete() }} as snapshot_complete
), complete_grid as (
    select
        r.*, m.month_start, m.calendar_days, c.snapshot_complete,
        r.route_key || ':' || m.month_start::varchar as route_month_key,
        case when c.snapshot_complete then coalesce(a.trip_count, 0) end as trip_count,
        case when c.snapshot_complete then coalesce(a.duration_records, 0) end as duration_records,
        case when c.snapshot_complete then coalesce(a.fare_records, 0) end as fare_records,
        case when c.snapshot_complete then a.median_duration_minutes end as median_duration_minutes,
        case when c.snapshot_complete then a.p90_duration_minutes end as p90_duration_minutes,
        case when c.snapshot_complete then a.median_fare_usd end as median_fare_usd
    from routes r cross join months m cross join coverage c
    left join monthly a on r.route_key = a.route_key and m.month_start = a.month_start
), geographic_ranks as (
    -- Non-geographic/zero-volume rows remain in the grid, without volume ranks.
    select route_key, month_start,
        dense_rank() over (partition by month_start order by trip_count desc) as volume_rank
    from complete_grid where is_geographic_route and trip_count > 0
)
select
    g.*, g.trip_count * 1.0 / g.calendar_days as trips_per_calendar_day,
    {{ minimum }}::integer as minimum_metric_records,
    coalesce(g.duration_records >= {{ minimum }}, false) as duration_sample_sufficient,
    coalesce(g.fare_records >= {{ minimum }}, false) as fare_sample_sufficient,
    r.volume_rank
from complete_grid g
left join geographic_ranks r on g.route_key = r.route_key and g.month_start = r.month_start
