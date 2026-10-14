-- Full table rebuild initially. One row per raw source record, including anomalies.
-- Joining the same dimension twice distinguishes origin from destination.
select
    t.*,
    origin.zone_id is not null as pickup_zone_found,
    destination.zone_id is not null as dropoff_zone_found,
    coalesce(origin.borough, 'Unmapped') as pickup_borough,
    coalesce(destination.borough, 'Unmapped') as dropoff_borough,
    coalesce(origin.zone_name, 'Unmapped') as pickup_zone_name,
    coalesce(destination.zone_name, 'Unmapped') as dropoff_zone_name
from {{ ref('stg_trips') }} t
left join {{ ref('dim_zones') }} origin on t.pickup_zone_id = origin.zone_id
left join {{ ref('dim_zones') }} destination on t.dropoff_zone_id = destination.zone_id
