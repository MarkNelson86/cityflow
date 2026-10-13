-- A view: rename fields and compute derived values without removing records.
with renamed as (
    select
        trip_id, source_month, source_sha256, source_row_number,
        tpep_pickup_datetime as pickup_time,
        tpep_dropoff_datetime as dropoff_time,
        PULocationID as pickup_zone_id,
        DOLocationID as dropoff_zone_id,
        trip_distance as distance_miles,
        fare_amount, total_amount
    from {{ source('cityflow_raw', 'trips') }}
), derived as (
    select *,
        cast(pickup_time as date) as pickup_date,
        epoch(dropoff_time - pickup_time) / 60.0 as duration_minutes,
        coalesce(
            pickup_time >= timestamp '2025-01-01'
            and pickup_time < timestamp '2025-04-01', false
        ) as is_observed_trip
    from renamed
)
select *,
    coalesce(is_observed_trip and isfinite(duration_minutes)
             and duration_minutes > 0 and duration_minutes <= 180, false)
        as is_duration_eligible,
    coalesce(is_observed_trip and isfinite(fare_amount) and fare_amount >= 0, false)
        as is_fare_eligible,
    coalesce(is_observed_trip and isfinite(total_amount) and total_amount >= 0, false)
        as is_total_eligible,
    coalesce(is_observed_trip and isfinite(distance_miles) and distance_miles > 0, false)
        as is_distance_eligible
from derived
