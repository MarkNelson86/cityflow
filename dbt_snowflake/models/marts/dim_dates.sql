with dates as (
    select dateadd(day, row_number() over (order by seq4()) - 1, date '2025-01-01')::date as date_day
    from table(generator(rowcount => 90))
)
select date_day, date_trunc('month', date_day)::date as month_start,
    year(date_day)::integer as year_number, month(date_day)::integer as month_number,
    dayofweekiso(date_day)::integer as weekday_number from dates
