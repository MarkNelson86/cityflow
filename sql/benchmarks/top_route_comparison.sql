-- Choose the most-recorded geographic route across the quarter, breaking ties by key.
-- Output grain: its three consecutive pickup months, including any zero month.
with chosen_route as (
    select route_key
    from analytics.mart_route_monthly
    where snapshot_complete and is_geographic_route
    group by route_key
    order by sum(trip_count) desc, route_key
    limit 1
)
select comparison.month_start, comparison.route_key,
       comparison.trip_count, comparison.trips_per_calendar_day,
       comparison.previous_trip_count, comparison.trip_count_change_pct,
       comparison.duration_records, comparison.duration_sample_sufficient,
       comparison.median_duration_minutes,
       comparison.previous_median_duration_minutes,
       comparison.median_duration_change_minutes
from analytics.mart_route_month_comparison as comparison
join chosen_route as chosen on comparison.route_key = chosen.route_key
order by comparison.month_start
