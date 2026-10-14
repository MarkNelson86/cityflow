{{ config(tags=['analytics']) }}
with summaries as (
    select 'daily' as model, date_day::varchar as record_key, snapshot_complete,
           trip_count, duration_records, fare_records,
           median_duration_minutes, p90_duration_minutes, median_fare_usd
    from {{ ref('mart_daily_activity') }}
    union all
    select 'route_monthly', route_month_key, snapshot_complete,
           trip_count, duration_records, fare_records,
           median_duration_minutes, p90_duration_minutes, median_fare_usd
    from {{ ref('mart_route_monthly') }}
)
select * from summaries
where not snapshot_complete
   or trip_count < 0 or duration_records < 0 or fare_records < 0
   or duration_records > trip_count or fare_records > trip_count
   or (duration_records = 0 and (median_duration_minutes is not null or p90_duration_minutes is not null))
   or (duration_records > 0 and (median_duration_minutes is null or p90_duration_minutes is null))
   or (fare_records = 0 and median_fare_usd is not null)
   or (fare_records > 0 and median_fare_usd is null)
   or median_duration_minutes > p90_duration_minutes + 1e-9
   or median_duration_minutes <= 0 or p90_duration_minutes > 180
