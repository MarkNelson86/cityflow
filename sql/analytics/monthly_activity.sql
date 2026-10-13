-- Recompute percentiles from eligible trip records; do not average medians.
with months as (
    select month_start, count(*) as calendar_days from analytics.dim_dates group by 1
), totals as (
    select cast(date_trunc('month', pickup_date) as date) as month_start,
        count(*) as trip_count,
        count(*) filter (where is_duration_eligible) as duration_records,
        count(*) filter (where is_fare_eligible) as fare_records,
        median(duration_minutes) filter (where is_duration_eligible) as median_duration_minutes,
        quantile_cont(duration_minutes, 0.9) filter (where is_duration_eligible) as p90_duration_minutes,
        median(fare_amount) filter (where is_fare_eligible) as median_fare_usd
    from analytics.fact_trips where is_observed_trip group by 1
)
select m.month_start, m.calendar_days,
       coalesce(t.trip_count, 0) as trip_count,
       coalesce(t.trip_count, 0) * 1.0 / m.calendar_days as trips_per_calendar_day,
       coalesce(t.duration_records, 0) as duration_records,
       coalesce(t.fare_records, 0) as fare_records,
       t.median_duration_minutes, t.p90_duration_minutes, t.median_fare_usd
from months m left join totals t using (month_start) order by m.month_start
