{{ config(tags=['analytics']) }}
select route_key, count(*) as month_rows
from {{ ref('mart_route_monthly') }} group by route_key
having count(*) <> 3 or count(distinct month_start) <> 3
   or min(month_start) <> date '2025-01-01' or max(month_start) <> date '2025-03-01'
   or count(*) filter (where month_start not in (date '2025-01-01', date '2025-02-01', date '2025-03-01')) > 0
