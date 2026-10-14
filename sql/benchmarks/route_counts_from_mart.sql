-- Same question and output grain as route_counts_from_fact.sql.
-- Aggregation has already happened during the dbt build: filter the saved rows.
-- Zero months and non-geographic routes are retained in the mart but excluded here.
select month_start, route_key, trip_count
from analytics.mart_route_monthly
where snapshot_complete and is_geographic_route and trip_count > 0
order by month_start, route_key
