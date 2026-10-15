# CityFlow local dashboard — step-by-step guide

Prepared for the completed Snowflake validation phase, 14 October 2026.

## What this phase delivers

Build and validate a local interactive dashboard for the January–March 2025
DuckDB snapshot. The dashboard code, tests, workflow, and documentation are already
included in this repository; there is no ZIP package to install.

The interface has two views:

1. **Activity:** inclusive pickup-date filters, daily counts, a trailing seven-day
   mean, selected-day rates and monthly cohort/percentile statistics.
2. **Directed route:** origin/destination/month controls populated from the full
   route mart, zero-trip months, eligible sample sizes and guarded adjacent-month
   comparisons. Unmapped/outside-city routes are available explicitly.

This guide reproduces the completed local-dashboard checks from a repository
clone. The separate [hosting guide](hosting_guide.md) covers rebuilding the
dedicated Snowflake environment and deploying the public snapshot.

| Session | Work | Approximate time | Gate |
| --- | --- | --- | --- |
| A | Clone repository and prepare dashboard environment | 20–40 min | Clean install and dependency check |
| B | Build fixture, run tests, review fixture in browser | 30–60 min | 19 base tests + 13 dashboard tests; known fixture answers |
| C | Rebuild or check the real warehouse and review the interface | 30–60 min | Monthly known answers and sampled route checks pass |
| D | Optional: repeat checks and inspect generated evidence | 15–30 min | Reports are written under ignored `reports/` |

Time estimates assume the project dependencies install successfully. A fresh
clone does not contain the ignored raw TLC files or the full local DuckDB database;
the real-data section below provides the download and rebuild commands.

## Where you work

Every step below identifies its surface. **Terminal A** is your usual project
terminal. **Terminal B** is a second terminal tab used while A is occupied by the
running app. **Browser** means the local page at `http://127.0.0.1:8501`.
**Editor** means your local file editor. No step in this phase uses Snowsight.

Copy command contents without a leading `$` prompt. Run commands from the project
root unless a step says otherwise. When Streamlit is running, Terminal A will not
return a shell prompt until you stop it with Ctrl+C. Do not paste shell commands
into the running server. Use Terminal B or stop A's server first.

`.venv` and `.venv-dashboard` are separate directories in the project root. The
first runs ingestion/dbt/base CI. Explicit `.venv-dashboard/bin/python` commands
run the app and app tests. You do not nest one environment inside another.

## Run the committed public snapshot (no Snowflake)

This quick start runs the published aggregate snapshot in `cloud_dashboard/`.
It does not need source data, a DuckDB database, a Snowflake account, or
credentials. Run from the repository root on macOS/Linux:

```bash
python3.11 -m venv .venv-dashboard
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt
CITYFLOW_HOSTING_BACKEND=snapshot .venv-dashboard/bin/python -m streamlit run cloud_dashboard/app.py
```

Open `http://localhost:8501`. Stop the app with **Control+C** in the terminal.
The app should show “Published Snowflake aggregate snapshot · no live database
connection.” This committed snapshot contains 11,198,001 observed trips from
January–March 2025. The environment directory is ignored by Git.

## Session A — prepare a local dashboard environment

### 1. Clone the repository and install the project environment — Terminal A

Run from the directory where you keep projects. If you already cloned the
repository, omit `git clone` and `cd cityflow`, then run the remaining commands
from the repository root.

```bash
git clone https://github.com/MarkNelson86/cityflow.git
cd cityflow
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Expected: `No broken requirements found.` The repository already contains the
dashboard app, checks, Streamlit configuration, and CI workflow. No installer
ZIP or prior checkout is required.

### 2. Confirm local-only files are ignored — Terminal A

```bash
git check-ignore .venv-dashboard/ reports/ .streamlit/secrets.toml
```

These paths should be ignored. The public `.streamlit/config.toml` stays in Git;
credentials are unnecessary for the local dashboard.

### 3. Create the dashboard environment and match DuckDB — Terminal A

```bash
.venv/bin/python -m venv .venv-dashboard
mkdir -p reports/dashboard
.venv/bin/python -c "import duckdb; print('duckdb==' + duckdb.__version__)" > reports/dashboard/duckdb-constraint.txt
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt -c reports/dashboard/duckdb-constraint.txt
.venv-dashboard/bin/python -m pip check
```

Expected final result: `No broken requirements found.` Matching the existing
DuckDB version avoids opening the retained warehouse with an arbitrarily different
library version. Streamlit/Plotly and their key numerical dependencies use tested
pins rather than an unbounded upgrade to the latest release.

Record the app environment:

```bash
.venv-dashboard/bin/python -m pip freeze > reports/dashboard/dashboard_environment.txt
.venv-dashboard/bin/python - <<'PY'
import duckdb, streamlit, pandas, plotly, sys
print('Python:', sys.version.split()[0])
print('DuckDB:', duckdb.__version__)
print('Streamlit:', streamlit.__version__)
print('pandas:', pandas.__version__)
print('Plotly:', plotly.__version__)
PY
git check-ignore .venv-dashboard/ reports/dashboard/
```

The last command should print both ignored paths. Do not install these app
dependencies into `.venv-snowflake`.

## Session B — prove the synthetic dashboard first

### 4. Build a fresh fixture with the established pipeline — Terminal A

Check that no ingestion/dbt process is currently writing the real warehouse. This
step creates its own isolated fixture database; it does not replace the real data.

```bash
source .venv/bin/activate
python scripts/run_ci_checks.py --output-dir reports/ci-dashboard-fixture
```

Expected: **19 Python tests**, **8 dbt models and 33 dbt tests**, followed by
`CI contract passed`. The fixture exports contain 12 observed records with monthly
counts **5 / 3 / 4**, and 90 / 12 / 12 rows in the three marts.

If the output directory already contains a prior run, the script refuses to
overwrite it. On a repeat, use `reports/ci-dashboard-fixture-repeat` as the output
directory and update the fixture path in the following exports to that directory.
Do not delete previous evidence merely to rerun the command.

### 5. Run the dashboard tests and fixture data checker — Terminal A

```bash
export CITYFLOW_DASHBOARD_FIXTURE_DB="$PWD/reports/ci-dashboard-fixture/work/pipeline_fixture.duckdb"
.venv-dashboard/bin/python -m pytest dashboard/checks.py -q --junitxml=reports/dashboard/pytest.xml
.venv-dashboard/bin/python scripts/check_dashboard.py \
  --dataset fixture \
  --database "$CITYFLOW_DASHBOARD_FIXTURE_DB" \
  --report reports/dashboard/fixture_validation.json
```

Expected: **13 dashboard tests passed**, then `Dashboard validation passed` and
`"all_checks_passed": true`. These are additional tests in the app environment.
The established 19-case suite stays in the original environment. The checker
verifies known monthly counts/cohorts/percentiles, a partial date window and
independent fact-level route samples. It does not assert full new cross-engine
parity; that evidence belongs to the completed Snowflake phase.

### 6. Start the fixture app — Terminal A

```bash
export CITYFLOW_DASHBOARD_DATABASE="$CITYFLOW_DASHBOARD_FIXTURE_DB"
export CITYFLOW_DASHBOARD_DATASET='fixture'
.venv-dashboard/bin/python -m streamlit run dashboard/app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

Leave Terminal A running. The displayed URL should be `http://127.0.0.1:8501`.
The loopback address keeps this development server on your own computer.

### 7. Open and inspect the fixture — Terminal B, then Browser

Open a second terminal tab. Run:

```bash
cd ~/Desktop/projects/cityflow
curl --fail http://127.0.0.1:8501/_stcore/health
open http://127.0.0.1:8501
```

The health request returns `ok`. It confirms the server is reachable; the data
checker and browser review confirm the data is actually usable.

In the browser, perform these checks in order:

| View / action | Expected result |
| --- | --- |
| Initial Activity view, full quarter | Visible **SYNTHETIC FIXTURE** warning; observed trips **12**; monthly counts **5, 3, 4** |
| Set both activity date endpoints to 15 January 2025 | **2** trips; one selected calendar day; median duration **20** and p90 **28** |
| Restore full quarter, switch Explore to Directed route | Origin and destination selectors appear; no arbitrary date range controls for monthly routes |
| Origin `1 · First`, destination `2 · Second`, February | Trips **0**; median duration/fare shown as dashes |
| Same route, March | Trips **2**, median duration **30**, median fare **$15**; percentage growth from prior zero is explicitly undefined |
| Same route, January | Median duration **20**, p90 **28**, median fare **$10**; no predecessor month in the snapshot |
| Check “Include unmapped and outside-city routes”; choose origin `999`, destination `2`, January | Trips **1**; duration/fare metrics suppressed under threshold **2** |
| Choose origin `2`, destination `1`, March | Median duration change **20** minutes; trips/day change approximately **-9.68%** |
| Download selected activity / selected route | Small CSV downloads contain the selected aggregates; no raw trips |

The route chart shows zero months; the interface never describes missing/incomplete
source coverage as confirmed zero. The automated tests separately prove the
incomplete/stale-data refusal. Route metrics are suppressed independently for
duration and fare, using their own eligible cohort sizes.

### 8. Stop the fixture server — Terminal A

Press **Ctrl+C** in Terminal A. Wait for the shell prompt. Closing the browser tab
alone does not stop Streamlit. You can leave the browser tab open for the real run.

## Session C — rebuild or inspect the real warehouse

### 9. Rebuild the real local warehouse if it is missing — Terminal A

A fresh clone has no TLC source files or real DuckDB database because both are
ignored by Git. Skip this step if `data/warehouse/cityflow.duckdb` already exists
and contains the validated real snapshot. Otherwise download the three source
partitions and zone lookup, then build the local warehouse:

```bash
mkdir -p data/raw
for month in 2025-01 2025-02 2025-03; do
  curl -fL "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_${month}.parquet" \
    -o "data/raw/yellow_tripdata_${month}.parquet"
done
curl -fL https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv \
  -o data/raw/taxi_zone_lookup.csv
source .venv/bin/activate
python scripts/ingest_sources.py
dbt build --project-dir dbt --profiles-dir dbt --vars '{analytics_min_records: 30}'
python scripts/export_analytics.py --output-dir reports/dashboard/local_rebuild
```

Expected: source rows reconcile to 11,198,026; dbt reports eight models and 33
data tests passed; the analytics export succeeds with the threshold set to 30.
The public snapshot quick start above does not require this full-data download.

### 10. Select the real database and run read-only checks — Terminal A

```bash
export CITYFLOW_DASHBOARD_DATABASE="$PWD/data/warehouse/cityflow.duckdb"
export CITYFLOW_DASHBOARD_DATASET='real'
test -f "$CITYFLOW_DASHBOARD_DATABASE"
.venv-dashboard/bin/python scripts/check_dashboard.py \
  --dataset real \
  --database "$CITYFLOW_DASHBOARD_DATABASE" \
  --report reports/dashboard/real_validation.json
```

Expected report counts:

| Item | Expected |
| --- | ---: |
| Raw records | 11,198,026 |
| Observed records | 11,198,001 |
| Daily mart rows | 90 |
| Route-month mart rows | 133,377 |
| Comparison mart rows | 133,377 |
| Route threshold | 30 |
| January / February / March observed records | 3,475,234 / 3,577,542 / 4,145,225 |

The checker also validates the monthly eligible cohort counts, median duration,
p90 duration and median fare against the earlier established values. It writes
the new report only under ignored reports/. The repository already contains the
completed summary; do not overwrite it when reproducing the check.

If the retained real database is elsewhere, replace only
`CITYFLOW_DASHBOARD_DATABASE` with its actual path. Never select the fixture path
while leaving the dataset label as `real`; the checker and app reject that mismatch.
Do not use fixture threshold **2** when rebuilding real models.

If the database is absent or stale, see troubleshooting below before proceeding.
You do not need to recreate the deleted Snowflake objects.

### 11. Launch and inspect the real app — Terminal A, then Browser

```bash
.venv-dashboard/bin/python -m streamlit run dashboard/app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

In Terminal B, reopen or refresh the local page:

```bash
open http://127.0.0.1:8501
```

Perform the following real-data checks:

1. Confirm the fixture warning is gone and full-quarter observed trips are
   **11,198,001**. The first load may take longer while the app validates the
   warehouse and computes the eligible monthly percentiles.
2. Inspect the monthly table: counts and percentile values should match the
   Snowflake results summary. The Activity chart should cover 90 calendar days.
3. Filter Activity to **1–31 January 2025**. Observed trips should be **3,475,234**
   and the selected calendar-day denominator should be **31**. The displayed rate
   rounds to approximately **112,104.3 trips/day**.
4. Change the range to **15 January–14 February**. Compare its observed count with
   `partial_window.observed_records` in `reports/dashboard/real_validation.json`.
   The two selected month portions contain **31 total calendar days**.
5. Switch to Directed route. Try both directions for a zone pair when both routes
   exist. Choose February and March; check that route counts, rates and cohort
   sizes update together. The visible route threshold must be **30**.
6. Enable unmapped/outside-city routes and inspect one. It stays distinguishable
   through its ID/name/borough labels; it does not receive a geographic volume rank.
7. Download a selected activity CSV and a selected route CSV; open them and confirm
   they match the displayed selection. A route download has only its three monthly
   rows, not the full 133,377-row mart.

Counts are observed source records, not unique people or a complete measure of all
urban mobility. Activity date filters do not change the whole-month route view.
The underlying route mart contains medians even for small cohorts, so the app
specifically masks them before displaying or downloading the selected route.

## After running the dashboard

Stop Streamlit with Control+C in the terminal running the app. Fresh test reports,
logs, fixture databases and environment freezes are written under reports/, which
is ignored by Git. The committed dashboard results already describe the completed
validation; running this guide does not require editing README.md, the roadmap, or
those committed result files.

If you change project code and want to contribute the change, create a branch from
the current main branch, rerun the relevant tests, and review your actual diff
before opening a pull request. Use git checkout commands for branch operations:

~~~bash
git status --short
git checkout main
git pull --ff-only
git checkout -b feat/dashboard-update
~~~

## Stop for the night and resume tomorrow

Stop the app with Ctrl+C in its terminal. No Snowflake action is needed. Keep the
Git branch and local data. For a normal next-day real-data start:

```bash
export CITYFLOW_DASHBOARD_DATABASE="$PWD/data/warehouse/cityflow.duckdb"
export CITYFLOW_DASHBOARD_DATASET='real'
.venv-dashboard/bin/python -m streamlit run dashboard/app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

In another terminal tab, run `open http://127.0.0.1:8501`. No environment activation
is required for that explicit app interpreter. To resume fixture review instead,
export the fixture database path and `CITYFLOW_DASHBOARD_DATASET='fixture'` before
the same launch command. Environment exports do not persist in a new terminal.

## Troubleshooting commands

### The server is running but the page will not open

In Terminal B:

```bash
curl --fail http://127.0.0.1:8501/_stcore/health
lsof -nP -iTCP:8501 -sTCP:LISTEN
```

If port 8501 belongs to an earlier app you started, stop that app in its original
terminal. Alternatively use `--server.port 8502` and open `http://127.0.0.1:8502`.
Do not kill unrelated processes to free the port.

### A module is missing or the wrong environment is active

```bash
.venv-dashboard/bin/python -m pip check
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt -c reports/dashboard/duckdb-constraint.txt
```

For existing ingestion/dbt/base CI, run `source .venv/bin/activate` and confirm
`which dbt`. App commands always use `.venv-dashboard/bin/python` explicitly.

### The database is locked

Stop app/ingestion/dbt processes you started before trying again. In Terminal B:

```bash
lsof data/warehouse/cityflow.duckdb
```

The app is read-only, but an active external writer can prevent another process
opening the file. Stop the app before source/model rebuilds, then restart it.

### The real warehouse is missing, stale or built at the wrong threshold

With the app stopped, use the original environment. If the original Parquet files
and taxi zone lookup are still present under `data/raw/`, rebuild locally:

```bash
source .venv/bin/activate
python scripts/ingest_sources.py
dbt build --project-dir dbt --profiles-dir dbt --vars '{analytics_min_records: 30}'
python scripts/export_analytics.py --output-dir reports/dashboard/local_rebuild
```

The ingestion command retains version tracking and skips unchanged sources. If it
reports changed bytes, investigate the source change instead of adding a replacement
flag casually. Then repeat the real checker (omit `--write-summary` if it already
exists). Do not rebuild against a Snowflake profile or pass the fixture threshold.

### A dashboard test cannot find its fixture

Re-export the fixture path in the terminal running pytest:

```bash
export CITYFLOW_DASHBOARD_FIXTURE_DB="$PWD/reports/ci-dashboard-fixture/work/pipeline_fixture.duckdb"
test -f "$CITYFLOW_DASHBOARD_FIXTURE_DB"
.venv-dashboard/bin/python -m pytest dashboard/checks.py -q
```

Use the `-repeat` directory if that is where you built the fixture. A new terminal
does not inherit exports from another terminal tab.

## Technical references

- [Streamlit: run an app](https://docs.streamlit.io/develop/concepts/architecture/run-your-app)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
- [Streamlit configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
- [DuckDB Python DB API](https://duckdb.org/docs/stable/clients/python/dbapi.html)
- [DuckDB concurrency](https://duckdb.org/docs/stable/connect/concurrency.html)

The package pins Streamlit 1.50.0 and Plotly 6.3.0 as tested dependencies. These are
not claims about the latest releases. The app only reads the established models;
analytical contracts and interpretation limits remain in docs/analytics_design.md.
