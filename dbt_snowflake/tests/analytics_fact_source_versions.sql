{{ config(tags=['analytics']) }}
-- Count reconciliation alone cannot detect a same-size source replacement.
select f.source_month, f.source_sha256, count(*) as mismatched_records
from {{ ref('fact_trips') }} f
left join {{ source('cityflow_meta', 'loaded_sources') }} m
    on m.source_kind = 'trips' and f.source_month = m.source_month
where m.partition_key is null or f.source_sha256 is distinct from m.source_sha256
group by f.source_month, f.source_sha256
