"""Generate an isolated Snowflake project from the current local dbt project."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def adapt(sql):
    sql = sql.replace('epoch(dropoff_time - pickup_time) / 60.0',
                      "datediff(microsecond, pickup_time, dropoff_time) / 60000000.0::float")
    sql = re.sub(r'isfinite\((\w+)\)',
                 r"(\1 not in ('NaN'::float, 'inf'::float, '-inf'::float))", sql)
    sql = re.sub(r'count\(\*\)\s+filter\s*\(where\s+([^\n]+)\)',
                 r'count(case when \1 then 1 end)', sql, flags=re.I)
    sql = re.sub(r'median\((\w+)\)\s+filter\s*\(where\s+(\w+)\)',
                 r'median(case when \2 then \1 end)', sql, flags=re.I)
    sql = re.sub(r'quantile_cont\((\w+),\s*0\.9\)\s+filter\s*\(where\s+(\w+)\)',
                 r'percentile_cont(0.9) within group (order by case when \2 then \1 end)', sql)
    sql = sql.replace('bool_and(', 'booland_agg(')
    sql = sql.replace('g.trip_count * 1.0 / g.calendar_days', 'g.trip_count::float / g.calendar_days')
    sql = sql.replace('100.0 *', '100.0::float *')
    sql = sql.replace('over by_route', 'over (partition by route_key order by month_start)')
    sql = re.sub(r'\n\s*window by_route as \(partition by route_key order by month_start\)', '', sql)
    sql = sql.replace("cast(month_start - interval '1 month' as date)",
                      "dateadd(month, -1, month_start)::date")
    sql = sql.replace("m.month_start::varchar", "to_char(m.month_start, 'YYYY-MM-DD')")
    sql = sql.replace('median_duration_minutes > p90_duration_minutes\n',
                      'median_duration_minutes > p90_duration_minutes + 1e-9\n')
    sql = sql.replace("with expected(source_month) as (\n    values ('2025-01'), ('2025-02'), ('2025-03')\n)",
                      "with expected as (\n    select column1::varchar as source_month from values ('2025-01'), ('2025-02'), ('2025-03')\n)")
    return sql


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('dbt'))
    p.add_argument('--output', type=Path, default=Path('dbt_snowflake'))
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit('Output already exists; review it or use a new --output path.')
    shutil.copytree(a.source, a.output, ignore=shutil.ignore_patterns(
        'target', 'logs', 'dbt_packages', '*profiles*', '__pycache__'))
    hashes = {}
    for src in a.source.rglob('*.sql'):
        rel = src.relative_to(a.source)
        if any(part in ('target', 'logs', 'dbt_packages') for part in rel.parts):
            continue
        hashes[str(rel)] = hashlib.sha256(src.read_bytes()).hexdigest()
        dst = a.output / rel
        if dst.exists():
            dst.write_text(adapt(src.read_text()))
    (a.output / 'models/marts/dim_dates.sql').write_text("""with dates as (
    select dateadd(day, row_number() over (order by seq4()) - 1, date '2025-01-01')::date as date_day
    from table(generator(rowcount => 90))
)
select date_day, date_trunc('month', date_day)::date as month_start,
    year(date_day)::integer as year_number, month(date_day)::integer as month_number,
    dayofweekiso(date_day)::integer as weekday_number from dates
""")
    # All generated models use the one dedicated ANALYTICS schema, never a shared schema.
    (a.output / 'macros/generate_schema_name.sql').write_text("""{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema }}
{%- endmacro %}
""")
    for src in a.output.rglob('*.sql'):
        if re.search(r'generate_series|\bisfinite\(|\bepoch\(|\bquantile_cont\(|\bbool_and\(|\bfilter\s*\(|over by_route|\bwindow by_route', src.read_text(), re.I):
            raise SystemExit(f'Unconverted dialect expression in {src}; inspect before cloud execution.')
    (a.output / 'migration_sources.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print('Generated', a.output, '; inspect its diff against dbt before running.')


if __name__ == '__main__':
    main()
