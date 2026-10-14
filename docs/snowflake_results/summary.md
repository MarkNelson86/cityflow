# CityFlow Snowflake Validation

## Environment

- Snowflake region: AWS_US_EAST_2
- Snowflake edition: Enterprise
- Python: 3.11.4
- dbt Core: 1.12.5
- dbt Snowflake adapter: 1.12.2
- Warehouse: `CITYFLOW_WH`, X-Small, Standard
- Warehouse settings: auto-suspend after 60 seconds; auto-resume enabled; query acceleration disabled; statement timeout 600 seconds
- Resource monitor: `CITYFLOW_MONITOR`, 5-credit monthly quota; suspend at 80%; suspend immediately at 100%

No Snowflake account or user identifiers are included in this summary.

## Fixture validation

- Local fixture CI: 19 Python tests passed; 8 dbt models and 33 dbt tests passed.
- Fixture data: 13 raw trip rows; 12 observed trips.
- Fixture mart rows: 90 daily activity; 12 route-month; 12 route-month comparison.
- Snowflake fixture build: 8 models and 33 data tests passed.
- DuckDB-to-Snowflake fixture parity: all marts matched. `all_equal: true`

## Full-data validation

- Raw trips loaded: 11,198,026.
- Observed trips: 11,198,001. The difference is expected: not every raw trip is in the analytical observation window.
- Route cohort threshold: 30.
- Snowflake build: 8 models and 33 data tests passed; 41/41 dbt build steps passed.
- DuckDB-to-Snowflake parity: `all_equal: true`; no mismatches.
- Mart row counts:
  - `mart_daily_activity`: 90
  - `mart_route_monthly`: 133,377
  - `mart_route_month_comparison`: 133,377

### Independent monthly checks

| Month | Observed trips | Duration records | Fare records | Median duration (min) | P90 duration (min) | Median fare (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-01 | 3,475,234 | 3,471,806 | 3,331,116 | 11.70 | 27.5166667 | 12.80 |
| 2025-02 | 3,577,542 | 3,571,077 | 3,394,887 | 12.2166667 | 27.8333333 | 13.50 |
| 2025-03 | 4,145,225 | 4,121,371 | 3,936,501 | 12.5166667 | 29.2666667 | 14.10 |

The monthly observed-trip counts sum to 11,198,001.

## Selected query evidence

Elapsed time and bytes scanned are from the project-tagged Snowsight query-history export. Query Profile spill observations remain to be recorded.

| Operation | Query ID | Elapsed (ms) | Bytes scanned | Rows returned/produced |
| --- | --- | ---: | ---: | ---: |
| Observed-trip count | `01c7bb5c-0308-fe66-0011-d6c20001b632` | 955 | 605,984,256 | 1 |
| Monthly metrics | `01c7bb5c-0308-fe97-0011-d6c20001a692` | 1,585 | 615,909,888 | 3 |
| Daily mart parity read | `01c7bb56-0308-fe97-0011-d6c20001a62a` | 816 | 32,768 | 90 |
| Route-month mart parity read | `01c7bb56-0308-fe97-0011-d6c20001a62e` | 649 | 11,932,672 | 133,377 |
| Route-month comparison parity read | `01c7bb56-0308-fe66-0011-d6c20001b5b6` | 687 | 16,437,248 | 133,377 |

- Query Profile spill observations:
  - COPY load (`01c7bb34-0308-fe97-0011-d6c20001a0ea`): 529.65 MB spilled to local storage.
  - `fact_trips` model (`01c7bb39-0308-fe97-0011-d6c20001a496`): spill metrics not reported in Query Profile.
  - `mart_route_monthly` model (`01c7bb39-0308-fe66-0011-d6c20001b46a`): 377.21 MB spilled to local storage.
- Query-history export: `reports/snowflake/query_history.csv`

## Usage and cost evidence

- Usage window: 2026-10-13 23:08 to 2026-10-14 14:08 PDT
- `CITYFLOW_WH` credits reported: 0.25
- Storage or other service usage shown separately: `COMPUTE_WH`, 0.46 credits; `CLOUD_SERVICES_ONLY`, 0.00 credits
- Source and checked at: Snowsight Usage page; 2026-10-14 14:42 PDT
- Status: provisional
- Exclusions or limitations: The 0.25 credits are attributed to `CITYFLOW_WH`. The page also shows 0.46 credits for `COMPUTE_WH`; its association with this project is unverified and it is excluded from the `CITYFLOW_WH` figure. Usage reporting may be delayed.

## Resource state and cleanup

- Last checked: 2026-10-14 15:25 PDT
- `CITYFLOW_WH`, `CITYFLOW_FIXTURE`, `CITYFLOW_REAL`, `CITYFLOW_ROLE`, and `CITYFLOW_MONITOR`: removed; post-cleanup checks showed no active matches
- Paused or deleted resources and when: All five dedicated Snowflake objects were removed; confirmed by 2026-10-14 15:19 PDT
- Local DuckDB project and source data: retained
