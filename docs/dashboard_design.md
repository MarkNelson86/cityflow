# CityFlow local dashboard

The local dashboard turns the validated January–March 2025 analytical snapshot
into two user tasks: inspect activity across pickup dates and compare a directed
route across adjacent months. Streamlit and Plotly provide the interface; the
existing DuckDB warehouse supplies read-only data. Snowflake validation and its
resource cleanup are complete. A cloud data adapter and public hosting follow
in a separate phase.

## Data and definitions

`dashboard/data.py` centralizes bound-parameter queries. `dashboard/app.py` handles
controls and presentation. Connections are read-only, closed after each query,
and use two threads with a 2 GB DuckDB query-memory limit. Streamlit caches small
query outputs using the database path, file size and modification time plus filter
values. Restart the app after any deliberate model/source rebuild.

The backend reuses `scripts/export_analytics.require_ready`: all source partitions
must exist; fact source versions must be current; complete calendar and route
totals must reconcile. Frozen real/fixture counts, calendar bounds, comparison row
counts and metric thresholds are also checked. A fixture cannot be labeled real.
The full database path is configured through `CITYFLOW_DASHBOARD_DATABASE` and the
dataset label through `CITYFLOW_DASHBOARD_DATASET` (`real` or `fixture`).

Activity date filtering is inclusive. Counts and eligible records use the existing
flags. The denominator is selected calendar days, including zero-trip days. A
partial month is labeled by its selected-day count. Monthly medians/p90 are queried
from individual eligible fact records, never averaged from daily/route medians.
The trailing mean uses seven full calendar days from the whole snapshot before
applying the visible date filter. It is absent for the first six snapshot days.

Directed routes use whole calendar months and their complete route-month grid.
Origin/destination controls are populated from every distinct route in the mart,
not top-ten exports. Geographic routes appear by default; unmapped and outside-city
routes are available through an explicit category control. A route never observed
anywhere in the quarter is absent from the selector, rather than asserted to be a
known zero. Known routes retain zero months after completeness checks.

Route duration/fare cohorts are independent. Median/p90 duration and median fare
are suppressed below the model's threshold (30 for real data, 2 for the fixture).
Changes require sufficient current and previous cohorts. January has no prior
month in the snapshot. Percentage growth from a zero denominator remains undefined.
Ranks apply only to geographic routes with positive monthly trips and retain ties.
Downloads contain selected aggregates, not raw records or the full route catalog.

## Validation

Run `dashboard/checks.py` explicitly with pytest in `.venv-dashboard`. Its filename
keeps Streamlit-dependent checks out of the established base CI's automatic
`test_*.py` discovery. Tests exercise real dbt-built synthetic marts, independent
known counts/quantiles, filtered-day denominators, preserved trailing windows,
threshold suppression, zero denominators, unknown IDs, read-only access, bound
parameters, dataset labels and incomplete/stale-data rejection. Streamlit AppTest
also changes the activity dates and route/category/month controls.

`scripts/check_dashboard.py` validates either dataset, checks established monthly
known answers, reconciles a partial-date window, and independently recomputes a
small declared sample of routes from fact records. It writes compact JSON evidence
without local paths/account identifiers. This is sampled dashboard verification;
the completed Snowflake phase retains its separate full mart parity evidence.

The dashboard workflow builds the established fixture first, then runs the app
checks in a separate environment with the same DuckDB version. The original local
pipeline commands and README figure continue to be supported.

## Run and stop

See [the step-by-step guide](dashboard_guide.md). The app binds to `127.0.0.1:8501`.
Stop it with Ctrl+C in the terminal that launched Streamlit. Closing only the
browser tab leaves the server running. Do not run ingestion or dbt writers against
the selected file while the app is open; stop the app, rebuild, then restart.

## Interpretation

These are recorded yellow-taxi patterns, not all urban mobility or travel forecasts.
Trip mix, payment categories and source coverage affect comparisons. Wall-clock
durations retain daylight-saving ambiguity from the source data. Maps, forecasting,
new datasets, cloud reads and public deployment are outside this phase.
