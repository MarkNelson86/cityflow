# CityFlow local dashboard — step-by-step guide

Prepared for the completed Snowflake validation phase, 14 October 2026.

## What this phase delivers

Build and validate a local interactive dashboard for the retained January–March
2025 DuckDB snapshot. The supplied package contains the app, read-only SQL queries,
13 dashboard tests, an automated data checker, a GitHub dashboard workflow and
design documentation. You install these additions into the existing repository.

The interface has two views:

1. **Activity:** inclusive pickup-date filters, daily counts, a trailing seven-day
   mean, selected-day rates and monthly cohort/percentile statistics.
2. **Directed route:** origin/destination/month controls populated from the full
   route mart, zero-trip months, eligible sample sizes and guarded adjacent-month
   comparisons. Unmapped/outside-city routes are available explicitly.

The next phase after this one is **cloud connection and public hosting**. Your
Snowflake resources stay removed during this local phase. Maps, forecasting,
additional data and public deployment are separate future work.

| Session | Work | Approximate time | Gate |
| --- | --- | --- | --- |
| A | Branch, install package, prepare dashboard environment | 20–40 min | Clean install and dependency check |
| B | Build fixture, run tests, review fixture in browser | 30–60 min | 19 base tests + 13 dashboard tests; known fixture answers |
| C | Check retained real warehouse and review real interface | 30–60 min | Monthly known answers and sampled route checks pass |
| D | Save evidence, update docs, commit and merge | 30–60 min | Green existing CI and dashboard workflow; reviewed PR |

Time estimates assume the existing pipeline and retained real DuckDB database are
available. Rebuilding a missing local warehouse or resolving a dependency issue
adds time. This package has been tested here on reconstructed dbt-built fixture
data on Python 3.12.14 with DuckDB 1.4.1; your Python 3.11 environment and full
11-million-record warehouse are verified by the commands below on your Mac.

## Where you work

Every step below identifies its surface. **Terminal A** is your usual project
terminal. **Terminal B** is a second terminal tab used while A is occupied by the
running app. **Browser** means the local page at `http://127.0.0.1:8501`.
**Editor** means your local file editor. No step in this phase uses Snowsight.

Copy command contents without a leading `$` prompt. Run commands from the project
root unless a step says otherwise. When Streamlit is running, Terminal A will not
return a shell prompt until you stop it with Ctrl+C. Do not paste shell commands
into the running server. Use Terminal B or stop A's server first.

`.venv`, `.venv-snowflake` and the new `.venv-dashboard` are sibling directories in
the project root. The existing `.venv` runs ingestion/dbt/base CI. Explicit
`.venv-dashboard/bin/python` commands run the app and app tests. You do not activate
the dashboard environment or nest it inside another environment.

## Session A — prepare the branch and app

### 1. Confirm the Snowflake changes are committed and merged — Terminal A

```bash
cd ~/Desktop/projects/cityflow
git status --short
git branch --show-current
```

The first command should show no pending changes. If Snowflake work is still
uncommitted or its PR is unmerged, finish the previous guide's commit/PR step first.
Do not hide those changes with a stash to proceed. If there is an existing PR for
the current branch, these commands inspect it:

```bash
gh pr view
gh pr checks
```

Once Snowflake is merged, prepare the new branch:

```bash
git switch main
git pull --ff-only
test -f docs/snowflake_results/summary.md
test -f scripts/export_analytics.py
git switch -c feat/dashboard
source .venv/bin/activate
python --version
which dbt
```

The two `test` commands succeed silently. If a file is absent on main, check the
Snowflake merge before continuing. Python should be your existing 3.11 environment;
`which dbt` should end in `cityflow/.venv/bin/dbt`. This matters because the base CI
script finds `dbt` through your terminal's PATH.

If `feat/dashboard` already exists from an interrupted start, inspect it before
continuing and use `git switch feat/dashboard` instead of creating it again.

### 2. Download and unpack the package — Terminal A

Download `cityflow_dashboard.zip` from this conversation into `~/Downloads`.
If your browser adds a suffix, rename the downloaded ZIP to that exact name.
Then run:

```bash
.venv/bin/python -m zipfile -e ~/Downloads/cityflow_dashboard.zip ~/Downloads
ls ~/Downloads/cityflow_dashboard
```

Expected folder contents: `GUIDE.md`, `install.py`, `manifest.json`, and `files/`.
You can read the standalone guide or `GUIDE.md`; they contain the same instructions.

### 3. Check and install the additive files — Terminal A

```bash
.venv/bin/python ~/Downloads/cityflow_dashboard/install.py --repo "$PWD" --check
.venv/bin/python ~/Downloads/cityflow_dashboard/install.py --repo "$PWD"
git status --short
```

The preflight validates all package hashes and destinations before copying any
files. It refuses to overwrite an existing different file. If it reports a
conflict, inspect the named file; do not overwrite it blindly. Matching files are
safe to retain on a repeat install.

You should see additions under `dashboard/`, `.streamlit/`, `scripts/`, `docs/`,
`.github/workflows/`, and `requirements-dashboard.txt`. Existing dbt models,
Snowflake SQL, README figure and source files are not replaced.

### 4. Ignore the app environment and runtime outputs — Terminal A

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
path = Path('.gitignore')
text = path.read_text() if path.exists() else ''
lines = set(text.splitlines())
needed = [p for p in ('.venv-dashboard/', 'reports/', '.streamlit/secrets.toml', '__pycache__/', '*.py[cod]', '.pytest_cache/') if p not in lines]
if needed:
    path.write_text(text.rstrip() + '\n\n# Local dashboard environment and runtime files\n' + '\n'.join(needed) + '\n')
print('Dashboard ignore rules are present.')
PY
```

The supplied `.streamlit/config.toml` is public app configuration and belongs in
Git. No credentials or secrets are needed for this phase.

### 5. Create the dashboard environment and match DuckDB — Terminal A

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

### 6. Build a fresh fixture with the established pipeline — Terminal A

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

### 7. Run the dashboard tests and fixture data checker — Terminal A

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

### 8. Start the fixture app — Terminal A

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

### 9. Open and inspect the fixture — Terminal B, then Browser

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

### 10. Stop the fixture server — Terminal A

Press **Ctrl+C** in Terminal A. Wait for the shell prompt. Closing the browser tab
alone does not stop Streamlit. You can leave the browser tab open for the real run.

## Session C — validate and inspect the retained real warehouse

### 11. Select the real database and run read-only checks — Terminal A

```bash
export CITYFLOW_DASHBOARD_DATABASE="$PWD/data/warehouse/cityflow.duckdb"
export CITYFLOW_DASHBOARD_DATASET='real'
test -f "$CITYFLOW_DASHBOARD_DATABASE"
.venv-dashboard/bin/python scripts/check_dashboard.py \
  --dataset real \
  --database "$CITYFLOW_DASHBOARD_DATABASE" \
  --report reports/dashboard/real_validation.json \
  --write-summary docs/dashboard_results/summary.md
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
the summary template with actual data/environment results. It refuses to overwrite
an existing summary. On a repeat, omit `--write-summary`, retain your manual notes,
and review the new JSON separately.

If the retained real database is elsewhere, replace only
`CITYFLOW_DASHBOARD_DATABASE` with its actual path. Never select the fixture path
while leaving the dataset label as `real`; the checker and app reject that mismatch.
Do not use fixture threshold **2** when rebuilding real models.

If the database is absent or stale, see troubleshooting below before proceeding.
You do not need to recreate the deleted Snowflake objects.

### 12. Launch and inspect the real app — Terminal A, then Browser

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

## Session D — evidence, docs and Git

### 13. Stop the app and retain small validation evidence — Terminal A

Press Ctrl+C and wait for the shell prompt. Then run:

```bash
mkdir -p docs/dashboard_results
cp reports/dashboard/fixture_validation.json docs/dashboard_results/
cp reports/dashboard/real_validation.json docs/dashboard_results/
cp reports/dashboard/dashboard_environment.txt docs/dashboard_results/
open -a TextEdit docs/dashboard_results/summary.md
```

The summary is already generated by step 11. In the editor, replace its test-count
placeholder with the **actual dashboard test result**, record the browser review
date/time/timezone, and mark each manual review row Pass only if you performed it.
Describe any unresolved issue instead of marking it passed. Save the file.

Full pytest/dbt logs, JUnit XML, databases and large route exports stay under ignored
reports/data directories. Small JSON evidence, environment versions and the results
summary are enough for this phase. There is no required screenshot or external login.

### 14. Update README and roadmap — Terminal A, then Editor

This command adds a local-dashboard section and changes Next milestones while
preserving the existing figure and reproduction sections. Review its diff afterward.

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import re
path = Path('README.md')
text = path.read_text()
section = '''## Local dashboard

The local Streamlit dashboard supports pickup-date activity exploration and directed-route
month comparisons using the validated DuckDB snapshot. It preserves eligible cohorts,
zero-trip months, sample thresholds and undefined growth from zero. See the
[dashboard guide](docs/dashboard_guide.md), [design](docs/dashboard_design.md), and
[validation results](docs/dashboard_results/summary.md).

Run from the repository root after installing the dashboard environment:

CODE_FENCEbash
.venv-dashboard/bin/python -m streamlit run dashboard/app.py
CODE_FENCE

Open http://127.0.0.1:8501. Stop the server with Ctrl+C in its terminal.

'''.replace('CODE_FENCE', chr(96) * 3)
if '## Local dashboard' not in text:
    anchor = '## Next milestones'
    if anchor in text:
        text = text.replace(anchor, section + anchor, 1)
    else:
        text = text.rstrip() + '\n\n' + section
next_block = '''## Next milestones

1. Cloud connection and hosting: connect the validated dashboard to the accepted
   cloud environment and deploy it with tested configuration, refresh and cost behavior.

See [the remaining roadmap](docs/remaining_roadmap.md). Local dashboard validation
and Snowflake parity are complete. The dedicated Snowflake resources were removed
after validation; cloud infrastructure will be rebuilt when needed for hosting.

'''
if '## Next milestones' in text:
    text = re.sub(r'^## Next milestones\n.*?(?=^## |\Z)', next_block,
                  text, count=1, flags=re.M | re.S)
else:
    text += next_block
path.write_text(text.rstrip() + '\n')
print('README dashboard section and next milestone updated; review the diff.')
PY
open -a TextEdit docs/remaining_roadmap.md
```

In the roadmap editor, mark **Local interactive dashboard complete** and **Cloud
connection and hosting next**. Keep Snowflake marked complete and its resources
removed. Replace the forward-looking dashboard phase text with this completion note:

```markdown
## Local dashboard phase — complete

The local dashboard provides date-filtered activity and directed-route monthly
exploration from the retained DuckDB snapshot. Fixture controls and metric boundaries
are tested; real activity and sampled route outputs reconcile with validated aggregates.
See [dashboard results](dashboard_results/summary.md) and
[dashboard design](dashboard_design.md).

## Cloud connection and hosting — next

Rebuild the dedicated cloud environment when needed, add a cloud data adapter,
and deploy the validated dashboard. Test access, secret handling, refresh behavior,
availability and warehouse costs before calling the hosted product complete.
```

Update the corresponding table rows too. Keep existing estimates and any other
roadmap work that is still relevant. Save the file, then review:

```bash
git diff -- README.md docs/remaining_roadmap.md
git diff --check
```

The original local commands and README figure should remain in the diff's context,
with no deletion of those sections. Only label this phase complete after the earlier
gates pass. A local dashboard is not yet a publicly hosted application.

### 15. Stage and review the intended additions — Terminal A

```bash
git status --short
git add .gitignore README.md docs/remaining_roadmap.md \
  requirements-dashboard.txt .streamlit/config.toml dashboard \
  scripts/check_dashboard.py docs/dashboard_design.md docs/dashboard_guide.md \
  docs/dashboard_results .github/workflows/dashboard.yml
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git status --short
```

Expected staged files are app code/tests, the dashboard requirements/config/workflow,
README/roadmap/design/guide and small evidence. No `.venv*`, `.duckdb`, raw Parquet,
full route exports, credentials or unrelated changes should be staged. Do not use
`git add .` to sweep runtime outputs into the commit.

The GitHub dashboard workflow will repeat the established fixture pipeline and the
13 app tests in isolated environments. No real TLC download or Snowflake login is
required on GitHub. If you changed app/query code after the earlier checks, rerun
step 7 and affected real checks before committing; documentation-only edits do not
require another full data build.

### 16. Commit, push and create a reviewable PR — Terminal A

```bash
git commit -m "Add validated local CityFlow dashboard"
git push -u origin feat/dashboard
cat > /tmp/cityflow_dashboard_pr_body.md <<'BODY'
Adds a local Streamlit dashboard for date-filtered taxi activity and directed-route
month comparisons from the existing DuckDB warehouse. The interface preserves
calendar zeroes, independent duration/fare cohorts, route sample thresholds and
undefined percentage growth from zero. Selected downloads contain aggregates.

Validation: the established 19-case Python suite and eight-model/33-test dbt fixture
pipeline pass; 13 additional dashboard checks exercise queries and Streamlit controls.
The full retained snapshot passes known monthly answers, date-range reconciliation
and declared independent route samples. Browser results and environment versions are
recorded in docs/dashboard_results. Full Snowflake parity evidence remains separate.

Snowflake test resources remain removed. Cloud connection and public hosting are next.
BODY
gh pr create --draft --base main --head feat/dashboard \
  --title "Add validated local CityFlow dashboard" \
  --body-file /tmp/cityflow_dashboard_pr_body.md
gh pr checks --watch
gh pr view --web
```

Use the PR description only if those validations actually passed. Inspect both the
existing CI and **Dashboard checks** results. Review changed files in GitHub.
If a check fails, inspect its log and fix the issue before marking the PR ready.

After review and green checks, the merge commands are:

```bash
gh pr ready
gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
git status --short
```

Expected final worktree status: no pending changes. Retain the small validation
evidence, local warehouse and source data. Proceed to the separate cloud
connection/hosting phase only after this local dashboard is accepted.

## Stop for the night and resume tomorrow

Stop the app with Ctrl+C in its terminal. No Snowflake action is needed. Keep the
Git branch and local data. For a normal next-day real-data start:

```bash
cd ~/Desktop/projects/cityflow
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
