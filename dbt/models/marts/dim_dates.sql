select
    cast(day as date) as date_day,
    cast(date_trunc('month', day) as date) as month_start,
    extract(year from day)::integer as year_number,
    extract(month from day)::integer as month_number,
    extract(isodow from day)::integer as weekday_number
from generate_series(
    date '2025-01-01', date '2025-03-31', interval '1 day'
) as dates(day)
