# CityFlow: Urban Mobility Analytics

A SQL analytics warehouse for recorded NYC yellow-taxi trips, built with
Python, DuckDB and dbt Core.

## Status
Transactional ingestion and first dbt models are implemented and validated
on the frozen three-month source snapshot. Analytical queries are next.

## Planned analyses
- Trip activity by date, hour, pickup zone and destination zone.
- Route travel-time distributions and recorded fares.
- Month comparisons with explicit coverage and quality reporting.

## Local setup
Requires Python 3.11, Git and internet access for the real-data download.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p data/warehouse
dbt debug --project-dir dbt --profiles-dir dbt
python -m pytest -q
python scripts/make_demo_sources.py
python scripts/ingest_sources.py --config config/demo_sources.json --raw-dir data/demo_raw --database data/warehouse/cityflow_demo.duckdb
dbt build --project-dir dbt --profiles-dir dbt/demo_profiles
python scripts/warehouse_summary.py --database data/warehouse/cityflow_demo.duckdb --output reports/demo_quality_summary.csv
```

## Data
January–March 2025 yellow-taxi Parquet files and taxi-zone lookup from
[NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
Large source files and local databases are excluded from Git.
See [the data contract](docs/data_contract.md) for grains and metric definitions.

## Roadmap
Source audit -> manifest-backed ingestion -> dbt models -> quality tests
-> analytical SQL -> fixture/CI/release -> optional bounded Snowflake run.

## Warehouse design
See [warehouse design](docs/warehouse_design.md), [source audit](docs/source_audit_2025q1.json), and [quality summary](docs/quality_summary_2025q1.csv).
