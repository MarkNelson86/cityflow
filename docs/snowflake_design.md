# Bounded Snowflake migration

The cloud run rebuilds the eight models from raw inputs. It does not upload the
finished marts and call that a warehouse migration. DuckDB remains the reproducible
local path and GitHub CI environment.

Inputs are a projection of the versioned DuckDB raw snapshot: all trip rows,
the eleven fields consumed by staging, the five zone fields, and the current
source registry. Other raw source columns and historical ingestion events remain
local. Export hashes identify the projected Parquet bytes; original SHA-256 fields
continue to identify the TLC source versions. Hashes are provenance identifiers,
not a proof that a cloud table is byte-identical to its source file.

A Python generator makes a separate `dbt_snowflake` project from the current
`dbt` tree. Inspect and commit the generated SQL. It handles the established
Cityflow dialect expressions and refuses known remaining DuckDB syntax; it is
not a general SQL transpiler. Future local model changes require a new generation
and parity run. `migration_sources.json` records the source SQL hashes.

Pickup/dropoff times stay TIMESTAMP_NTZ with microsecond precision, representing
the source wall clock. Registry load times are explicitly normalized to UTC.
Durations use DATEDIFF(microsecond)/60000000.0::FLOAT. Rate and percentage
divisions also use FLOAT operands to avoid Snowflake fixed-point scale rounding. ISO weekdays and formatted route
month keys are session independent. Filtered counts use COUNT(CASE WHEN ...),
which returns zero for empty eligible groups. Percentiles use exact continuous
interpolation, not approximate percentiles. The 1e-9 invariant tolerance is kept.

Fixtures and the real snapshot use separate databases. The loader validates
local export hashes, COPY status, total table counts, and counts grouped by source
month and source hash. It refuses existing raw tables instead of appending or
silently replacing data. A failed partial load requires inspection and deliberate
reset of that dedicated database before retrying; this is a one-shot migration,
not an incremental ingestion service.

Parity compares every row and column of all three marts after sorting by their
unique keys. Nulls, counts, booleans, dates and keys must match exactly; floating
metrics use abs=1e-9 and rel=1e-12 tolerance. Real parity covers 90 daily rows and
133,377 rows in each route mart, including empty routes, suppression flags,
rankings and adjacent-month differences. Existing dbt tests separately verify
unique keys, source coverage, raw-to-fact reconciliation and metric invariants.

No always-on dashboard, Snowpipe, task, dynamic table or other serverless service
is introduced. A five-credit monitor is a chosen compute threshold, not a dollar
budget or a guaranteed hard cap. Storage and some services are outside it;
threshold enforcement can lag. Cost depends on account terms and region. Export
usage evidence before deleting dedicated objects. Pausing a warehouse retains
billable storage. Final cleanup removes project objects; retained/time-travel data
may remain until the platform's retention periods expire.

Cloud credentials never enter GitHub. Browser authentication is interactive.
Existing GitHub fixture CI remains local; actual Snowflake execution and parity
are manual evidence, not a claimed cloud CI job.
