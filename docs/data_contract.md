# Cityflow v0.1 data contract

## Purpose and scope
Analyze recorded NYC yellow-taxi trips for January–March 2025 by pickup time,
origin zone and destination zone. Describe observed taxi activity, travel-time
distributions and recorded charges. These data do not measure all urban travel,
unmet demand or causal effects of congestion pricing.

## Grains and identities
- Raw trips: one physical record in one downloaded source file.
- Proposed fact_trips: one preserved source record, including quality flags.
- dim_zones: one row per LocationID in the taxi-zone lookup.
- dim_dates: one row per calendar day in the analysis quarter.
- Ingestion registry: one active source version per dataset/month, with hash,
  byte size, schema, row count and successful load status.
- No published unique trip key is assumed. Proposed internal identity:
  source-file SHA-256 plus stable physical row ordinal. Verify the loader's
  ordinal behavior before implementing this key. A hash of trip attributes
  alone is insufficient because identical-looking records can be distinct.
- Re-loading the same source version must not add rows. If a month's source
  bytes change, require explicit partition replacement and preserve provenance.

## Time and metrics
- Treat timestamps as source-local NYC wall-clock values; do not assume UTC.
  Retain the original values. Daylight-saving ambiguities remain a limitation.
- Analysis window: pickup >= 2025-01-01 and pickup < 2025-04-01.
  Preserve and separately count out-of-window records.
- Observed trip count: source records in the window with non-null pickup time.
- Duration minutes: (dropoff - pickup) in seconds / 60.
- Travel-time cohort: in-window records with both timestamps and
  0 < duration <= 180 minutes. This is an initial analytical threshold;
  report exclusions and later check sensitivity to the upper bound.
- Fare metrics: recorded fare_amount, in USD; summarize non-null nonnegative
  values among in-window records and report excluded negative/missing values.
- Total-charge metrics: total_amount, separately labeled; it is not the same
  as fare_amount and excludes unrecorded cash tips.
- Trip distance: reported miles. Preserve and flag null/nonpositive values.
- Route: ordered pair of pickup and dropoff zone IDs; origin/destination joins
  use two aliases of dim_zones. Unknown zones remain explicitly labeled.
- Compare daily rates as well as monthly counts because month lengths differ.
- Missing source partitions must not appear as zero observed trips.

## Validation policy
- Fail loading on unreadable files or missing required columns.
- Retain unexpected additional columns; record full schemas and review drift.
- Required columns: tpep_pickup_datetime, tpep_dropoff_datetime,
  PULocationID, DOLocationID, trip_distance, fare_amount, total_amount.
- Record nulls, timestamp anomalies, negative amounts and lookup mismatches;
  do not silently discard records or apply one validity rule to every metric.
- Test zone-key uniqueness and non-nullness before joins.
- Reconcile raw rows, fact rows and cohort exclusions before publishing results.

## Release goal
Python + DuckDB + dbt SQL, small synthetic fixture, tests, GitHub Actions,
documented analyses and measured real-data performance. A bounded Snowflake
deployment follows the reproducible local workflow.
