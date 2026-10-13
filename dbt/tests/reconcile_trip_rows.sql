-- Any returned row signals a missing partition or unexpected loss/multiplication.
with registry as (
    select source_month, row_count
    from {{ source('cityflow_meta', 'loaded_sources') }}
    where source_kind = 'trips'
), raw_counts as (
    select source_month, count(*) as raw_rows
    from {{ source('cityflow_raw', 'trips') }} group by 1
), fact_counts as (
    select source_month, count(*) as fact_rows
    from {{ ref('fact_trips') }} group by 1
)
select coalesce(m.source_month, r.source_month, f.source_month) as source_month,
       m.row_count, r.raw_rows, f.fact_rows
from registry m
full outer join raw_counts r on m.source_month = r.source_month
full outer join fact_counts f on coalesce(m.source_month, r.source_month) = f.source_month
where m.row_count is null
   or m.row_count <> coalesce(r.raw_rows, 0)
   or m.row_count <> coalesce(f.fact_rows, 0)
