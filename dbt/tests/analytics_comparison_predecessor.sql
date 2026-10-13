{{ config(tags=['analytics']) }}
select route_month_key from {{ ref('mart_route_month_comparison') }}
where (month_start = date '2025-01-01' and previous_month_start is not null)
   or (month_start > date '2025-01-01' and
       previous_month_start is distinct from cast(month_start - interval '1 month' as date))
   or (previous_trip_count = 0 and trip_count_change_pct is not null)
   or ((not duration_sample_sufficient or not coalesce(previous_duration_sample_sufficient, false))
       and median_duration_change_minutes is not null)
   or ((not fare_sample_sufficient or not coalesce(previous_fare_sample_sufficient, false))
       and median_fare_change_usd is not null)
