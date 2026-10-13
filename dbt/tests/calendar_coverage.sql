select count(*) as calendar_rows
from {{ ref('dim_dates') }}
having count(*) <> 90
    or min(date_day) <> date '2025-01-01'
    or max(date_day) <> date '2025-03-31'
