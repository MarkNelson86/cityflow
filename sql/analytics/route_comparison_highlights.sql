-- Highlight changes only when both adjacent duration cohorts meet the threshold.
select month_start, previous_month_start, route_key, pickup_zone_name, dropoff_zone_name,
       trip_count, previous_trip_count, trips_per_calendar_day,
       previous_trips_per_calendar_day, trips_per_day_change_pct,
       duration_records, minimum_metric_records,
       median_duration_minutes, previous_median_duration_minutes,
       median_duration_change_minutes, median_fare_change_usd,
       row_number() over (
           partition by month_start order by abs(median_duration_change_minutes) desc, route_key
       ) as display_order
from analytics.mart_route_month_comparison
where is_geographic_route and median_duration_change_minutes is not null
qualify display_order <= 10
order by month_start, display_order
