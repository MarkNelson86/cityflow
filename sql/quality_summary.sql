-- File partition summaries. Metric cohorts use the pickup-time analysis window.
select
    source_month,
    count(*) as raw_records,
    count(*) filter (where is_observed_trip) as observed_trip_records,
    count(*) filter (where not is_observed_trip) as outside_or_missing_pickup,
    count(*) filter (where is_duration_eligible) as duration_cohort,
    count(*) filter (where is_fare_eligible) as fare_cohort,
    count(*) filter (where is_total_eligible) as total_charge_cohort,
    count(*) filter (where not pickup_zone_found) as unmapped_pickup_records,
    count(*) filter (where not dropoff_zone_found) as unmapped_dropoff_records,
    median(duration_minutes) filter (where is_duration_eligible) as median_duration_minutes,
    median(fare_amount) filter (where is_fare_eligible) as median_fare_usd
from analytics.fact_trips
group by source_month
order by source_month
