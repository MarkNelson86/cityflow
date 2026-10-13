# CityFlow: Urban Mobility Analytics

A SQL analytics warehouse for recorded NYC yellow-taxi trips, built with
Python, DuckDB and dbt Core.

## Status
Initial setup and source audit. Warehouse ingestion and analytical models
are under development.

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
dbt run --project-dir dbt --profiles-dir dbt --select setup_check
```

## Data
January–March 2025 yellow-taxi Parquet files and taxi-zone lookup from
[NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
Large source files and local databases are excluded from Git.
See [the data contract](docs/data_contract.md) for grains and metric definitions.

## Roadmap
Source audit -> manifest-backed ingestion -> dbt models -> quality tests
-> analytical SQL -> fixture/CI/release -> optional bounded Snowflake run.
