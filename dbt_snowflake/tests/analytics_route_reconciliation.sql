{{ config(tags=['analytics']) }}
with expected as (
    select cast(date_trunc('month', pickup_date) as date) as month_start,
           count(*) as trips,
           count(case when is_duration_eligible then 1 end) as durations,
           count(case when is_fare_eligible then 1 end) as fares
    from {{ ref('fact_trips') }} where is_observed_trip group by 1
), actual as (
    select month_start, sum(trip_count) as trips,
           sum(duration_records) as durations, sum(fare_records) as fares
    from {{ ref('mart_route_monthly') }} group by 1
)
select coalesce(a.month_start, e.month_start) as month_start
from actual a full outer join expected e using (month_start)
where a.trips is distinct from coalesce(e.trips, 0)
   or a.durations is distinct from coalesce(e.durations, 0)
   or a.fares is distinct from coalesce(e.fares, 0)
