{{ config(tags=['analytics']) }}

-- One row per calendar day. The fact table's flags define each denominator.
with observed as (
    select * from {{ ref('fact_trips') }} where is_observed_trip
), daily as (
    select
        pickup_date,
        count(*) as trip_count,
        count(case when is_duration_eligible then 1 end) as duration_records,
        count(case when is_fare_eligible then 1 end) as fare_records,
        count(case when is_total_eligible then 1 end) as total_charge_records,
        median(case when is_duration_eligible then duration_minutes end) as median_duration_minutes,
        percentile_cont(0.9) within group (order by case when is_duration_eligible then duration_minutes end) as p90_duration_minutes,
        median(case when is_fare_eligible then fare_amount end) as median_fare_usd
    from observed
    group by pickup_date
), coverage as (
    select {{ cityflow_snapshot_complete() }} as snapshot_complete
)
select
    d.date_day, d.month_start, d.weekday_number, c.snapshot_complete,
    -- Only a complete snapshot warrants interpreting absent activity as zero.
    case when c.snapshot_complete then coalesce(a.trip_count, 0) end as trip_count,
    case when c.snapshot_complete then coalesce(a.duration_records, 0) end as duration_records,
    case when c.snapshot_complete then coalesce(a.fare_records, 0) end as fare_records,
    case when c.snapshot_complete then coalesce(a.total_charge_records, 0) end as total_charge_records,
    case when c.snapshot_complete then a.median_duration_minutes end as median_duration_minutes,
    case when c.snapshot_complete then a.p90_duration_minutes end as p90_duration_minutes,
    case when c.snapshot_complete then a.median_fare_usd end as median_fare_usd
from {{ ref('dim_dates') }} d
cross join coverage c
left join daily a on d.date_day = a.pickup_date
