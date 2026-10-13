# Warehouse design, v0.2

## Source identity and typed storage

The logical source partition is `yellow:YYYY-MM`, or `taxi_zones` for the lookup.
`meta.loaded_sources` records the current successful version: SHA-256, byte size,
source URL, original schema, row count and warehouse load timestamp.
The timestamp is a load timestamp; it does not claim when the source was published
or downloaded. `meta.load_history` records successful activations/replacements,
including previous/new hashes. Failed attempts do not become successful history
records. Metadata history is not a backup of prior source bytes or table contents.

Each trip ID hashes the logical source partition, source hash and physical
Parquet row ordinal. This intentionally preserves identical-looking records.
The partition scope also prevents a file accidentally reused for two logical
months from producing duplicate internal IDs. It does not prove the data are
free of duplicate real-world taxi events; that question requires separate study.

`raw.trips` retains all source columns plus provenance. Seven contract fields
are explicitly cast to TIMESTAMP, INTEGER or DOUBLE. Extra columns are retained;
new columns extend the raw table, and absent extra columns are null-filled.
Incompatible conversions fail and roll back. The original Parquet files preserve
the exact input representation; keep this frozen snapshot for reproducibility.
The loader requires the original contract's seven fields and checks ordinals.
It does not promise automatic handling of arbitrary schema changes or formats.

## Transactions and reruns

- Same partition and hash: check row count and skip without inserting records.
- Different hash: stop unless `--replace-changed` is explicitly supplied.
- Replacement: stage input, delete only that month, insert replacement, reconcile
  row count and write registry/history in one DuckDB transaction.
- Failure within a partition: roll back that partition's changes and registry.
- Successes in earlier partitions remain committed if a later partition fails.
- The source hash is checked again before commit to detect concurrent file edits.
- Do not edit warehouse tables manually. The skip check detects row-count changes;
  it is not a full forensic checksum of every stored cell.

Python ingestion is incremental by source partition: loading a new month leaves
other loaded months intact. dbt's fact table is fully rebuilt for now. A full
rebuild provides a correctness reference; a later guide can optimize dbt itself
incrementally and compare outputs against this reference.

## Models and metric cohorts

- `stg_trips`: view that names fields consistently and calculates durations and
  separate eligibility flags. No source records are removed.
- `stg_zones`: view over the zone lookup.
- `dim_zones`: small table with one row per zone ID.
- `dim_dates`: complete 90-day calendar for January–March 2025.
- `fact_trips`: table with one row per source record and two zone joins.

The fact-table grain is a recorded source row, not a unique taxi ride proven by
an external event key. Quality flags distinguish observed in-window records,
positive travel times up to 180 minutes, finite nonnegative fare amounts,
finite nonnegative total charges, and finite positive distances. They are
independent cohorts: a negative fare does not automatically exclude the record
from a duration summary. Eligibility alone does not validate that the record
represents an ordinary completed paid trip; payment/rate categories can refine
that interpretation in the analytical phase.

Out-of-window dates, nulls and negative amounts are preserved. Unmatched zone IDs
are flagged and labeled `Unmapped`; legitimate lookup entries named `Unknown`
remain distinct. We do not infer why negative fare values occurred.

Timestamps remain source-local wall-clock values, so calculated durations around
daylight-saving changes can be ambiguous. The travel-time threshold is an
analytical policy, not a statement that longer trips are impossible.

`quality_summary.sql` groups by source-file month for reconciliation. Later trend
analyses should group by actual pickup date/month. Cross-boundary pickups in a
source file must not be silently reassigned just to match its filename.

## Tests

Pytest verifies file/hash reruns, preserved identical rows, guarded replacement,
rollback after deletion, required fields, schema extension, invalid zone keys,
and detection of registered row loss. It uses temporary files/databases.

dbt data tests check fact keys and non-null flags, dimension keys, calendar
coverage, the presence of the three expected source partitions and per-partition
row-count equality across registry, raw and fact. Unmatched zone IDs are measured
rather than treated as a guaranteed-source-cleanliness assertion.

The committed demo has 11 source records, 9 in-window observed records, 6 in the
duration cohort and 7 in the fare cohort. It intentionally includes identical
records, an unknown zone, null fields, negative amounts and historical dates.
