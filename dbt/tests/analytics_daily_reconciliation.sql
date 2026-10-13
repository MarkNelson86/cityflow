{{ config(tags=['analytics']) }}
with expected as (
    select count(*) as trips,
           count(*) filter (where is_duration_eligible) as durations,
           count(*) filter (where is_fare_eligible) as fares
    from {{ ref('fact_trips') }} where is_observed_trip
), actual as (
    select count(*) as calendar_rows, min(date_day) as first_day, max(date_day) as last_day,
           sum(trip_count) as trips,
           sum(duration_records) as durations, sum(fare_records) as fares
    from {{ ref('mart_daily_activity') }}
)
select a.*, e.trips as expected_trips from actual a cross join expected e
where a.calendar_rows <> 90 or a.first_day <> date '2025-01-01'
   or a.last_day <> date '2025-03-31' or a.trips is distinct from e.trips
   or a.durations is distinct from e.durations or a.fares is distinct from e.fares
