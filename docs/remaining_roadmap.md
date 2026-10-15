# CityFlow roadmap

## Completed

- **Portfolio presentation:** Reproducible project documentation and local validation are in place.
- **Snowflake validation:** Fixture and full-data builds passed; all three marts reconciled with DuckDB. 
  Snowflake resources were removed after evidence was saved.
- **Dashboard:** The local dashboard supports date and route exploration across the full route catalog.
- **Cloud hosting:** The public app serves a published Snowflake aggregate snapshot without live database credentials. 
  Published-cell parity passed, raw access is denied, and dedicated Snowflake resources were removed after validation.

## Possible future extensions

Incremental dbt models, broader historical coverage, forecasting, maps, and additional cloud platforms remain optional. 
Consider them when a specific user need or measured workload justifies the added complexity.
