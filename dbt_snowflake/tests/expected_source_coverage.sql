with expected as (
    select column1::varchar as source_month from values ('2025-01'), ('2025-02'), ('2025-03')
), active as (
    select source_month
    from {{ source('cityflow_meta', 'loaded_sources') }}
    where source_kind = 'trips'
)
select coalesce(e.source_month, a.source_month) as source_month
from expected e full outer join active a using (source_month)
where e.source_month is null or a.source_month is null
