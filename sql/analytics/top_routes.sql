-- Exactly up to ten rows per month; volume_rank retains the meaning of ties.
select month_start, route_key, pickup_zone_name, dropoff_zone_name,
       trip_count, trips_per_calendar_day, duration_records, fare_records,
       volume_rank, minimum_metric_records,
       duration_sample_sufficient, fare_sample_sufficient,
       case when duration_sample_sufficient then median_duration_minutes end as median_duration_minutes,
       case when duration_sample_sufficient then p90_duration_minutes end as p90_duration_minutes,
       case when fare_sample_sufficient then median_fare_usd end as median_fare_usd,
       row_number() over (partition by month_start order by trip_count desc, route_key) as display_order
from analytics.mart_route_monthly
where is_geographic_route and trip_count > 0
qualify display_order <= 10
order by month_start, display_order
