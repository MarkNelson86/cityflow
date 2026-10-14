-- Question: how many recorded geographic trips used each directed route/month?
-- Input grain: one source record in fact_trips. Output grain: route × pickup month.
-- Keep exactly the same geographic and observed-record rules as the saved mart.
with observed_geographic as (
    select
        cast(date_trunc('month', pickup_date) as date) as month_start,
        pickup_zone_id::varchar || '->' || dropoff_zone_id::varchar as route_key
    from analytics.fact_trips
    where is_observed_trip
      and pickup_zone_found and dropoff_zone_found
      and pickup_borough in ('Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island')
      and dropoff_borough in ('Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island')
)
select month_start, route_key, count(*) as trip_count
from observed_geographic
group by month_start, route_key
order by month_start, route_key
