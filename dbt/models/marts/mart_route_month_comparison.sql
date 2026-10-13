{{ config(tags=['analytics']) }}

-- The complete route-month grid makes LAG mean previous calendar month.
with previous as (
    select *,
        lag(month_start) over by_route as previous_month_start,
        lag(trip_count) over by_route as previous_trip_count,
        lag(trips_per_calendar_day) over by_route as previous_trips_per_calendar_day,
        lag(median_duration_minutes) over by_route as previous_median_duration_minutes,
        lag(median_fare_usd) over by_route as previous_median_fare_usd,
        lag(duration_sample_sufficient) over by_route as previous_duration_sample_sufficient,
        lag(fare_sample_sufficient) over by_route as previous_fare_sample_sufficient
    from {{ ref('mart_route_monthly') }}
    window by_route as (partition by route_key order by month_start)
)
select *,
    trip_count - previous_trip_count as trip_count_change,
    100.0 * (trip_count - previous_trip_count) / nullif(previous_trip_count, 0)
        as trip_count_change_pct,
    trips_per_calendar_day - previous_trips_per_calendar_day as trips_per_day_change,
    100.0 * (trips_per_calendar_day - previous_trips_per_calendar_day)
        / nullif(previous_trips_per_calendar_day, 0) as trips_per_day_change_pct,
    case when duration_sample_sufficient and previous_duration_sample_sufficient
         then median_duration_minutes - previous_median_duration_minutes end
        as median_duration_change_minutes,
    case when fare_sample_sufficient and previous_fare_sample_sufficient
         then median_fare_usd - previous_median_fare_usd end as median_fare_change_usd
from previous
