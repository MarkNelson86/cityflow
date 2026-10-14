{% macro cityflow_snapshot_complete() %}
    -- Coverage is a property of the entire fixed snapshot, not a filename's
    -- month alone: source files can contain pickups crossing month boundaries.
    (
        select count(*) = 3
           and count(distinct source_month) = 3
           and coalesce(booland_agg(source_month in ('2025-01', '2025-02', '2025-03')), false)
        from {{ source('cityflow_meta', 'loaded_sources') }}
        where source_kind = 'trips'
    )
{% endmacro %}
