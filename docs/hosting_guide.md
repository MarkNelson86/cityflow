# CityFlow final phase: cloud connection and public hosting

## Outcome and scope

You have completed the local pipeline, analytical marts, Snowflake reconciliation,
and local interactive dashboard. This is the final planned implementation phase:

1. Recreate the dedicated real Snowflake snapshot and reconcile it again.
2. Create a dedicated key-pair service user with read-only access to four small serving tables.
3. Test the cloud dashboard locally and from Streamlit Community Cloud.
4. Publish a validated aggregate snapshot, remove live credentials, and clean up Snowflake.
5. Add the public app URL, evidence and final project status to GitHub.

**Recommended final state:** a public hosted dashboard that needs no Snowflake
credentials or compute; a preserved, tested Snowflake connection implementation;
and the original local DuckDB project. The hosted data is a frozen snapshot,
not a continuously refreshed feed. This remains useful after your trial expires.
Streamlit Community Cloud is the hosting platform, not an AWS deployment.
Its free hosting can hibernate; this is a portfolio app, not a production SLA.

The public app is a separate entrypoint, `cloud_dashboard/app.py`. It shows
whole-month activity and up to 100 geographic plus five non-geographic directed
routes, selected by quarter volume. It includes at most 315 route/month records.
The existing local dashboard retains arbitrary date filters and the full route
catalog. Public monthly medians are never combined into a quarter-wide median.

All application code, SQL, and tests are included in the repository. A fresh clone
does not include TLC source files, DuckDB databases, private Snowflake profiles,
or credentials; this guide gives commands to create each local prerequisite.
Snowflake execution and hosted deployment still require your own account.

To run only the committed public snapshot locally, without following the
Snowflake steps, use this short path from the repository root:

```bash
python3.11 -m venv .venv-dashboard
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt
CITYFLOW_HOSTING_BACKEND=snapshot .venv-dashboard/bin/python -m streamlit run cloud_dashboard/app.py
```

Open `http://localhost:8501` and stop with Control+C. No Snowflake account,
database, source files, or credentials are needed for snapshot mode.

Allow roughly 4–6 hours across several sessions; data downloads, uploads and
provider setup can add time. The commands create separate `.venv`,
`.venv-snowflake`, and `.venv-dashboard` environments in the repository root.

## Where each instruction runs

| Label | Where | What happens there |
| --- | --- | --- |
| Terminal A | Mac terminal, repository root | Git, installs, tests, exports, local app server |
| Terminal B | Second Mac terminal tab | Health checks and opening the local app while A runs it |
| Snowsight | Your Snowflake browser account, SQL workspace | Resource creation, serving tables, grants, pause/cleanup |
| Streamlit Cloud | `https://share.streamlit.io` | GitHub connection, hosted app creation, settings/secrets |
| Editor | TextEdit or your code editor | Review SQL, private secrets, README and evidence |

Run command blocks in order. Do not type shell commands into Snowsight or a
terminal occupied by the Streamlit server. Stop that server with **Control+C**
before returning to Terminal A commands. Shell variables belong to one tab and
disappear when you close it. SQL `USE ROLE` changes the worksheet's active role;
the scripts explicitly switch roles where necessary.

All Git commands use **`git checkout`**, compatible with your older Git.
Commands below do not include the `$` prompt; paste only their contents.

## Session A — prepare the branch and verify the code

### 1. Clone the repository and install the base environment — Terminal A

From the directory where you keep projects, run:

~~~bash
git clone https://github.com/MarkNelson86/cityflow.git
cd cityflow
git checkout -b feat/cloud-hosting
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
mkdir -p reports/hosting
python scripts/run_ci_checks.py --output-dir reports/ci-hosting-fixture
~~~

Expected: no broken requirements; 19 Python tests, 8 dbt models and 33 dbt tests
pass; the fixture database is created under
`reports/ci-hosting-fixture/work/pipeline_fixture.duckdb`. If you already have a
clone, use this instead of the first three commands above (replace the path if
your project directory is elsewhere). Confirm `git status` shows no uncommitted
work before switching to `main`; if it does, stop and preserve that work first:

~~~bash
cd /path/to/cityflow
git status --short --branch
git checkout main
git pull --ff-only
git checkout -b feat/cloud-hosting
~~~

Continue with `python3.11 -m venv .venv`. If the branch already exists, use
`git checkout feat/cloud-hosting` instead of creating it again.

### 2. Confirm the project files are already in the clone — Terminal A

~~~bash
for file in docs/dashboard_results/summary.md scripts/export_analytics.py scripts/snowflake_snapshot.py dashboard/app.py cloud_dashboard/app.py cloud_dashboard/public_snapshot.json dbt_snowflake/dbt_project.yml sql/snowflake/hosting_setup.sql; do
  if test -f "$file"; then
    echo "FOUND: $file"
  else
    echo "MISSING: $file"
  fi
done
~~~

All must say FOUND. There is no ZIP package or install script: these files are
tracked in Git. The real-data files, local database, and private profile are
created in later steps.

### 3. Install the Snowflake and dashboard environments — Terminal A

The base environment from Step 1 runs the local pipeline and builds the fixture.
Create two additional environments for the Snowflake adapter/loader and dashboard:

~~~bash
mkdir -p reports/hosting
.venv/bin/python -m venv .venv-snowflake
.venv-snowflake/bin/python -m pip install -r requirements.txt
.venv-snowflake/bin/python -m pip install dbt-snowflake==1.12.2 snowflake-connector-python==3.18.1
.venv-snowflake/bin/python -m pip check
.venv/bin/python -m venv .venv-dashboard
.venv/bin/python -c "import duckdb; print('duckdb==' + duckdb.__version__)" > reports/hosting/duckdb-constraint.txt
.venv-dashboard/bin/python -m pip install -r requirements-dashboard.txt -c reports/hosting/duckdb-constraint.txt
.venv-dashboard/bin/python -m pip install -r cloud_dashboard/requirements.txt
.venv-dashboard/bin/python -m pip check
.venv-dashboard/bin/python -m pip freeze > reports/hosting/environment.txt
git check-ignore .venv-snowflake/ .venv-dashboard/ reports/ .streamlit/secrets.toml
~~~

Expected: both pip check commands report no broken requirements, and the final
command lists all four ignored paths. The dashboard and Snowflake dependencies
stay in separate virtual environments. The DuckDB constraint matches the version
installed in the base environment.

### 4. Run the hosting fixture checks — Terminal A

Step 1 already built the synthetic DuckDB fixture and ran the base test suite.
Point the hosting checks at that fixture:

~~~bash
export CITYFLOW_DASHBOARD_FIXTURE_DB="$PWD/reports/ci-hosting-fixture/work/pipeline_fixture.duckdb"
.venv-dashboard/bin/python -m pytest cloud_dashboard/checks.py -q --junitxml=reports/hosting/pytest.xml
~~~

Expected: eight hosting checks pass. No Snowflake connection occurs in these tests.

### 5. Check that the shared Streamlit config is host-compatible — Terminal A

The committed config contains no server address override, so it works for both
local launches and Streamlit Community Cloud. Local launch commands below bind
to loopback explicitly. Confirm the config has no fixed address:

~~~bash
.venv/bin/python -c "from pathlib import Path; lines=Path('.streamlit/config.toml').read_text().splitlines(); print('Address override found' if any(x.strip().startswith('address =') for x in lines) else 'OK: no address override')"
~~~

Expected: OK: no address override. Do not edit the committed config for this step.

## Session B — rebuild the dedicated cloud snapshot

### 6. Confirm trial/billing and absence of old project objects — Snowsight

Log in to the intended Snowflake account. Check its trial expiry, remaining
credits and billing state before recreating resources. The previous phase removed
the project objects; do not assume they were retained.

Open your SQL workspace and create a new SQL file named `cityflow_hosting.sql`.
Choose ACCOUNTADMIN or run the first line explicitly. Select/run this block:

```sql
USE ROLE ACCOUNTADMIN;
SHOW DATABASES LIKE 'CITYFLOW_%';
SHOW WAREHOUSES LIKE 'CITYFLOW_%';
SHOW RESOURCE MONITORS LIKE 'CITYFLOW_%';
SHOW ROLES LIKE 'CITYFLOW_%';
SHOW USERS LIKE 'CITYFLOW_APP_USER';
```

Expected: no dedicated project objects remain. `_` is a LIKE wildcard, so inspect
names and do not treat unrelated matches as this project's objects. If dedicated
objects do exist, inspect their state before creation; do not drop them to make
an error go away. The scripts deliberately use CREATE, not CREATE OR REPLACE.

Get your private connection values using:

```sql
SELECT CURRENT_USER() AS SQL_USERNAME,
       CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS CONNECTION_ACCOUNT;
```

### 7. Create a private dbt profile and enter your login values — Terminal A

The committed profile is a template. Copy it into the ignored reports directory;
the template reads account, username and password from environment variables. Use
the same account and username you confirmed in Snowsight. Keep the password out
of files and never print it.

~~~bash
mkdir -p reports/snowflake/profiles
cp sql/snowflake/profiles.example.yml reports/snowflake/profiles/profiles.yml
chmod 600 reports/snowflake/profiles/profiles.yml
export CITYFLOW_SF_ACCOUNT='YOUR_ORGANIZATION-YOUR_ACCOUNT'
export CITYFLOW_SF_USER='YOUR_SQL_USERNAME'
export CITYFLOW_SF_DATABASE='CITYFLOW_REAL'
printf 'Snowflake password: '
read -s CITYFLOW_SF_PASSWORD
printf '\n'
export CITYFLOW_SF_PASSWORD
~~~

Replace the first three values with yours. CITYFLOW_REAL is the literal project
database name. The profile uses Snowflake username/password authentication, which
also matches the Python loader. The password stays in this terminal session's
environment; the hosted app uses a separate service key later.

Check that the private profile exists and is ignored:

~~~bash
test -s reports/snowflake/profiles/profiles.yml && echo 'Private dbt profile created'
git check-ignore reports/snowflake/profiles/profiles.yml
~~~

The second command must print the profile path.

### 8. Recreate the real database and controlled loading warehouse — Snowsight

Copy the private rendered SQL into `cityflow_hosting.sql`. Run statements or
short blocks individually with **Command+Return**, checking success each time:

1. ACCOUNTADMIN: create the five-credit monthly monitor and X-Small warehouse.
2. ACCOUNTADMIN: create/grant the project role and create the real database.
3. ACCOUNTADMIN: transfer database ownership to CITYFLOW_ROLE.
4. CITYFLOW_ROLE: create RAW, META and ANALYTICS schemas.
5. ACCOUNTADMIN: run the final SHOW checks.

This rebuild does not create CITYFLOW_FIXTURE. Fixture regression tests already
ran locally; the earlier completed Snowflake phase tested fixture parity.
Expected warehouse settings: X-Small, Standard, auto-suspend 60 seconds,
auto-resume TRUE, query acceleration FALSE, timeout 600 seconds, assigned monitor.
The grant to your human user is intentional; no SYSADMIN inheritance is added.

### 9. Verify the human connection and export fresh inputs — Terminal A

The Snowflake export reads the full local real DuckDB warehouse. A fresh clone
does not have that ignored database. If it is missing, first follow the
“Rebuild the real local warehouse” section in `docs/dashboard_guide.md`, which
downloads the three TLC source files and builds the warehouse. Before continuing,
confirm the database exists and is nonempty:

```bash
test -s data/warehouse/cityflow.duckdb && echo 'Real local warehouse found'
```

This step is required before creating Snowflake resources; the committed public
aggregate snapshot alone cannot supply the raw projection for migration.

```bash
.venv-snowflake/bin/dbt debug --project-dir dbt_snowflake --profiles-dir reports/snowflake/profiles
.venv/bin/python scripts/snowflake_snapshot.py export \
  --dataset real \
  --database data/warehouse/cityflow.duckdb \
  --output data/snowflake_exports/hosting-real
```

Expected: connection OK, then a fresh raw export. Use a new empty output directory
if `hosting-real` exists. Do not overwrite the previous Snowflake evidence.
The new export reads the retained local warehouse; it does not download source
data again or rebuild the local pipeline.

### 10. Load, build and reconcile all real marts — Terminal A

```bash
.venv-snowflake/bin/python scripts/snowflake_snapshot.py load \
  --dataset real \
  --input data/snowflake_exports/hosting-real \
  --report reports/hosting/real_load.json

.venv-snowflake/bin/dbt build \
  --project-dir dbt_snowflake \
  --profiles-dir reports/snowflake/profiles \
  --vars '{analytics_min_records: 30}'

.venv-snowflake/bin/python scripts/snowflake_snapshot.py parity \
  --dataset real \
  --database data/warehouse/cityflow.duckdb \
  --report reports/hosting/real_parity.json

cat reports/hosting/real_parity.json
```

Run each command only after the preceding command succeeds. Expected:
11,198,026 raw rows; eight models and 33 tests pass; all three marts reconcile
with `all_equal: true`; 90/133,377/133,377 mart rows. The real threshold is 30.

Save the build result:

```bash
mkdir -p reports/hosting/dbt_artifacts
cp dbt_snowflake/target/run_results.json reports/hosting/dbt_artifacts/
```

The loader is one-shot. If a load fails after creating tables, it will refuse
another load into those schemas. Inspect the error and partial state; do not
append data or rerun the entire setup blindly. If authentication returns the
SAML identity-provider error, verify that the private dbt profile still uses
`authenticator: snowflake` and that `CITYFLOW_SF_PASSWORD` is exported in the
same terminal session before retrying.

## Session C — serving tables, key pair and cloud-to-local verification

### 11. Generate a dedicated service key — Terminal A

This creates a private unencrypted PKCS8 RSA key protected by filesystem
permissions. It is a service credential, not your human password. Never commit it.

```bash
umask 077
mkdir -p reports/hosting/keys
if test -f reports/hosting/keys/app_key.p8; then
  echo "Key already exists; retaining it."
else
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out reports/hosting/keys/app_key.p8
fi
openssl pkey -in reports/hosting/keys/app_key.p8 -pubout -out reports/hosting/keys/app_key.pub
chmod 600 reports/hosting/keys/app_key.p8
git check-ignore reports/hosting/keys/app_key.p8
```

Expected: the private path is ignored. Do not regenerate the private key after
assigning its public key in Snowflake; they must remain a matching pair.

Render the second SQL file with the public key body:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
body = ''.join(line.strip() for line in Path('reports/hosting/keys/app_key.pub').read_text().splitlines()
               if not line.startswith('-----'))
text = Path('sql/snowflake/hosting_setup.sql').read_text().replace('YOUR_PUBLIC_KEY_BODY', body)
Path('reports/hosting/serving.private.sql').write_text(text)
print('Created ignored reports/hosting/serving.private.sql')
PY
open -a TextEdit reports/hosting/serving.private.sql
```

### 12. Create serving tables and the app identity — Snowsight

Copy the rendered SQL into your worksheet below the completed rebuild block.
Select/run only the new statements, in order, one CREATE at a time:

1. **Block A, CITYFLOW_ROLE:** create SERVING and its four tables. Monthly
   statistics are computed once from eligible facts; public requests never scan facts.
2. **Block B, ACCOUNTADMIN:** create CITYFLOW_APP_MONITOR, CITYFLOW_APP_WH,
   CITYFLOW_APP_ROLE and CITYFLOW_APP_USER with the generated public key.
3. **Block C, CITYFLOW_ROLE:** grant only serving-schema usage and four table reads.
4. **Block D, ACCOUNTADMIN:** inspect grants and warehouse/monitor settings.

The app user has TYPE=SERVICE and authenticates with its key pair. It receives
no human password or ACCOUNTADMIN/CITYFLOW_ROLE grant. Do not add a grant to fix
an error until its cause is understood.

Expected app warehouse: X-Small, timeout 60 seconds, auto-suspend 60 seconds,
auto-resume TRUE, query acceleration FALSE, one-credit daily monitor. The loading
warehouse retains its separate five-credit monthly monitor. Monitors are not
exact spending/dollar caps and do not cover all storage/service costs.

### 13. Create private app secrets and export the validated public subset — Terminal A

```bash
.venv-dashboard/bin/python scripts/publish_dashboard.py credentials \
  --key reports/hosting/keys/app_key.p8

.venv-dashboard/bin/python scripts/publish_dashboard.py export \
  --database data/warehouse/cityflow.duckdb \
  --snapshot cloud_dashboard/public_snapshot.json \
  --report reports/hosting/published_parity.json

cat reports/hosting/published_parity.json
```

The credentials command uses your account environment variable and writes ignored
`.streamlit/secrets.toml` with mode 600. It refuses an existing secrets file;
inspect/retain existing credentials rather than overwriting them blindly.

Expected export result: `all_equal: true`, `raw_access_denied: true`, 90 daily
rows, three monthly rows and at most 105 selected routes/315 route-month rows.
Query IDs, a SHA256 hash and file size are recorded. Every published cell and
the serialized roundtrip must match local analytics. This is separate from the
full three-mart parity in step 10.

**Publication decision already defined by this guide:** commit this bounded,
suppressed aggregate JSON for the public demo. Do not commit individual trips,
full route exports, raw Parquet or credentials. The snapshot contains no account
or personal user identifier. Exact published route counts come from your report,
not a hard-coded assumption that all 105 candidates exist.

### 14. Test live mode locally — Terminal A, then Terminal B and Browser

Terminal A:

```bash
export CITYFLOW_HOSTING_BACKEND='snowflake'
.venv-dashboard/bin/python -m streamlit run cloud_dashboard/app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Terminal A stays occupied. In Terminal B:

```bash
curl --fail http://127.0.0.1:8501/_stcore/health
open http://127.0.0.1:8501
```

Expected health response: `ok`. In the browser confirm the label says Snowflake
serving tables and no synthetic-fixture banner appears. Check:

- Full quarter: 11,198,001 observed trips and 90 calendar days.
- January/February/March counts: 3,475,234 / 3,577,542 / 4,145,225.
- Monthly medians/p90/cohorts agree with your earlier validated results.
- A selected route has three months, explicit duration/fare cohorts and threshold 30.
- January has no predecessor; insufficient metrics show a dash; a zero predecessor
  leaves percentage change undefined if such a route is present in the selected subset.
- Route downloads contain only selected aggregates and suppress insufficient metrics.

Record any scenario absent from the selected real routes as “not present in
published selection”; fixture tests cover those cases. Do not mark it as a manual
real-data observation you did not make. Stop the server with Control+C in A.

### 15. Test the credential-free snapshot locally — Terminal A

```bash
.venv-dashboard/bin/python scripts/publish_dashboard.py check \
  --database data/warehouse/cityflow.duckdb \
  --snapshot cloud_dashboard/public_snapshot.json \
  --report reports/hosting/snapshot_check.json

export CITYFLOW_HOSTING_BACKEND='snapshot'
.venv-dashboard/bin/python -m streamlit run cloud_dashboard/app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Open the same browser URL from B. Repeat the activity/route/download checks.
Expected label: **Published Snowflake aggregate snapshot · no live database
connection**. Results must agree with live mode. Stop the server with Control+C.

## Session D — commit, host, verify remotely

### 16. Prepare and merge the implementation PR — Terminal A

Review files and check that no private credentials are tracked:

```bash
git status --short
git diff --check
git ls-files .streamlit/secrets.toml reports/hosting/keys/app_key.p8
```

The final command must print nothing. Stage specific paths:

```bash
git add .gitignore .streamlit/config.toml cloud_dashboard scripts/publish_dashboard.py \
  sql/snowflake/hosting_rebuild.sql sql/snowflake/hosting_setup.sql sql/snowflake/hosting_cleanup.sql \
  docs/hosting_design.md docs/hosting_guide.md .github/workflows/hosting.yml
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
```

Confirm the public JSON is included and private files are absent. Read the staged
diff before committing. Keep the original dashboard files and SQL templates.

```bash
git commit -m "Add bounded Snowflake serving and public dashboard deployment"
git push -u origin feat/cloud-hosting
cat > reports/hosting/implementation_pr.md <<'EOF'
## Changes
- Add a dedicated key-pair service identity and four bounded serving tables.
- Add a public whole-month dashboard and a validated aggregate snapshot.
- Preserve the full local dashboard and add deployment/pause/cleanup instructions.

## Validation
- Existing local CI and eight hosting fixture checks passed.
- Rebuilt Snowflake real marts passed dbt and complete DuckDB parity.
- Every published cell and serialized roundtrip matched local analytics.
- Service-user raw access was denied; local live and snapshot modes were reviewed.
- Remote hosting validation and final cleanup follow after this implementation merge.
EOF
gh pr create --base main --head feat/cloud-hosting \
  --title "Add public dashboard deployment" --body-file reports/hosting/implementation_pr.md
gh pr checks --watch
```

Use these claims only after those checks actually passed. Review the PR and all
CI results. If your normal process permits your own merge:

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
```

If GitHub CLI is unavailable, push with Git, create/review/merge the same PR on
GitHub, then run the final two local commands. This implementation merge does
not claim the hosted phase is already complete; the evidence PR comes afterward.

### 17. Create the hosted app — Streamlit Cloud

Go to `https://share.streamlit.io`, sign in and connect the GitHub account that
owns CityFlow. Review the requested GitHub repository permissions. Use the
existing repository; do not upload your local database.

1. Click **Create app** and choose deployment from your GitHub repository.
2. Repository: your CityFlow GitHub repository.
3. Branch: **main**.
4. Main file path: **cloud_dashboard/app.py**.
5. Custom subdomain: try a memorable available name such as `cityflow-mark`.
6. Open **Advanced settings** and choose **Python 3.11**, matching your Mac.
7. Initially leave **Secrets empty**. Deploy.

The app-directory `cloud_dashboard/requirements.txt` is intentionally beside
the entrypoint, so Community Cloud selects the hosting dependencies rather than
the root pipeline requirements. Streamlit currently supports selecting Python
in Advanced settings; check the actual available versions when deploying.

Expected: a public `https://...streamlit.app` URL, showing snapshot mode and real
results. A failed build is diagnosed in the owner-only deployment logs. Do not
paste entire logs publicly if they contain identifiers or credentials.

### 18. Prove the hosted Snowflake connection — Editor, then Streamlit Cloud

Keep the warehouses available just for this bounded check. In Terminal A:

```bash
open -a TextEdit .streamlit/secrets.toml
```

Copy the contents, including `backend = "snowflake"` and the `[snowflake]`
section. In the hosted app's **Settings → Secrets** (or **Advanced settings →
Secrets**, depending on the current UI), paste and save the private TOML.
This is the host's private secrets store, not an app input widget or Git file.
Reboot the app from its management menu if it does not restart automatically.

Open its URL and confirm the Snowflake label appears. Repeat full-quarter,
monthly, route and download checks. Live mode reads/caches the bounded serving
tables, not your full facts. It can repeat queries on restart/process changes,
so do not leave it in this mode unattended.

In Snowsight, verify actual hosted reads were executed:

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CITYFLOW_WH;
USE DATABASE CITYFLOW_REAL;
SELECT QUERY_ID, START_TIME, QUERY_TYPE, EXECUTION_STATUS, TOTAL_ELAPSED_TIME,
       BYTES_SCANNED, ROWS_PRODUCED, WAREHOUSE_NAME, QUERY_TAG
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(RESULT_LIMIT=>10000))
WHERE QUERY_TAG='cityflow_hosting'
ORDER BY START_TIME;
```

Match query timestamps to the hosted check and warehouse CITYFLOW_APP_WH. The
tag also includes the earlier local service reads. Visibility depends on your
role; query history is not scoped to CITYFLOW_REAL simply because it is current.
Export the filtered evidence to ignored `reports/hosting/query_history.csv`.
Record the hosted check's timestamps and query IDs in the final summary.

### 19. Switch the host to its final snapshot mode — Streamlit Cloud

Replace the ENTIRE hosted Secrets contents with:

```toml
backend = "snapshot"
```

Save and reboot. This removes the account identifier/private key from the host,
rather than merely setting a mode while leaving unused credentials there.
Open the app in a private/incognito browser window, where you are not signed in.
Confirm it is publicly accessible, the snapshot label appears and all controls
and downloads still work. If the app is private, use its sharing/settings controls
to make this portfolio app public. No personal/source records are published.

Copy the final URL. Close your local app server if it is still running.

## Session E — usage evidence, cleanup and final project documentation

### 20. Record usage and remove Snowflake resources — Snowsight

First save filtered query history and inspect Usage for both CITYFLOW_WH and
CITYFLOW_APP_WH. Record start/end/timezone, credits by warehouse, other services
shown separately, checked-at time and provisional/final reporting status. Usage
can be delayed; a zero displayed immediately is not proof of zero consumption.
Do not combine account-wide totals with warehouse-only totals as if identical.

Disable the service identity now that the host is proven in snapshot mode:

```sql
USE ROLE ACCOUNTADMIN;
ALTER USER CITYFLOW_APP_USER SET DISABLED=TRUE;
SHOW WAREHOUSES LIKE 'CITYFLOW_%';
```

If either warehouse is STARTED, suspend that warehouse individually:

```sql
ALTER WAREHOUSE CITYFLOW_APP_WH SUSPEND;
```

```sql
ALTER WAREHOUSE CITYFLOW_WH SUSPEND;
```

Then prevent automatic resume:

```sql
ALTER WAREHOUSE CITYFLOW_APP_WH SET AUTO_RESUME=FALSE;
ALTER WAREHOUSE CITYFLOW_WH SET AUTO_RESUME=FALSE;
```

Check the public snapshot app again. It should still work after the service user
is disabled. After evidence is saved, the recommended final cleanup is below.
Run EACH statement separately; the role switches are required:

```sql
USE ROLE CITYFLOW_ROLE;
DROP DATABASE CITYFLOW_REAL;
```

```sql
USE ROLE ACCOUNTADMIN;
DROP USER CITYFLOW_APP_USER;
DROP ROLE CITYFLOW_APP_ROLE;
DROP WAREHOUSE CITYFLOW_APP_WH;
DROP RESOURCE MONITOR CITYFLOW_APP_MONITOR;
DROP WAREHOUSE CITYFLOW_WH;
DROP RESOURCE MONITOR CITYFLOW_MONITOR;
DROP ROLE CITYFLOW_ROLE;
```

Verify no dedicated objects remain:

```sql
SHOW DATABASES LIKE 'CITYFLOW_%';
SHOW WAREHOUSES LIKE 'CITYFLOW_%';
SHOW RESOURCE MONITORS LIKE 'CITYFLOW_%';
SHOW ROLES LIKE 'CITYFLOW_%';
SHOW USERS LIKE 'CITYFLOW_APP_USER';
```

Inspect names in any results. CITYFLOW_FIXTURE was not recreated in this phase.
Dropping objects stops their active use but does not erase already accrued usage
or all retained-storage charges immediately. Keep the monitor/billing evidence
honest about reporting lag and storage retention. Keep local DuckDB and sources.

### 21. Save concise evidence and write the final summary — Terminal A and Editor

Create a documentation branch after the implementation has merged:

```bash
git checkout main
git pull --ff-only
git checkout -b docs/hosting-results
mkdir -p docs/hosting_results
cp reports/hosting/real_parity.json docs/hosting_results/
cp reports/hosting/published_parity.json docs/hosting_results/
cp reports/hosting/snapshot_check.json docs/hosting_results/
cp reports/hosting/environment.txt docs/hosting_results/
```

Inspect the CSV first and copy only the query-history fields from step 18. Query
IDs are useful; personal/account identifiers and login logs are not:

```bash
cp reports/hosting/query_history.csv docs/hosting_results/
```

Create the summary once. Change the URL in the first export command:

```bash
export CITYFLOW_PUBLIC_URL='https://YOUR-SUBDOMAIN.streamlit.app'
.venv-dashboard/bin/python - <<'PY'
import json, os
from pathlib import Path
r = json.loads(Path('reports/hosting/published_parity.json').read_text())
c = r['counts']
p = Path('docs/hosting_results/summary.md')
if p.exists():
    raise SystemExit('Summary exists; edit it instead of overwriting.')
text = f'''# CityFlow public deployment

- Public URL: {os.environ['CITYFLOW_PUBLIC_URL']}
- Final hosted mode: published Snowflake aggregate snapshot; no live database credentials.
- Source snapshot: January–March 2025 NYC yellow taxis.
- Observed records: {c['observed_records']:,}.
- Published daily/monthly rows: {c['daily_rows']} / {c['monthly_rows']}.
- Published selected routes / route-month rows: {c['published_routes']} / {c['published_route_month_rows']}.
- Route cohort threshold: {c['minimum_metric_records']}.
- Published-cell parity: all_equal true; raw access denied true.
- Snapshot SHA256: {r['snapshot_sha256']}.
- Full three-mart parity: see real_parity.json.
- Actual hosting fixture test result: [fill from pytest output].
- Hosted Python version: [record configured version].
- Hosted live connection checked: [date/time/timezone; query IDs].
- Hosted snapshot/incognito/control/download checks: [actual results and date/time/timezone].
- Coverage limitation: whole months, up to 100 geographic and five non-geographic routes selected by quarter volume.
- Local dashboard: retained with arbitrary date ranges and full route catalog.

## Usage and cleanup

- Usage window: [start/end/timezone].
- CITYFLOW_WH credits: [reported amount].
- CITYFLOW_APP_WH credits: [reported amount].
- Storage/other service usage: [separate figures, or none shown].
- Source and checked at: [Snowsight Usage; date/time/timezone].
- Reporting status and limitations: [provisional/final; lag, exclusions, retained storage].
- Hosted credentials removed: [date/time/timezone].
- Snowflake resources removed: [actual objects and date/time/timezone].
- Last checked: [date/time/timezone; app still works after cleanup].
- Local DuckDB and source data: retained.
- No account/personal user identifiers or private credentials are included here.
'''
p.write_text(text)
print('Created', p)
PY
open -a TextEdit docs/hosting_results/summary.md
```

Replace every bracketed placeholder with actual results. Eight tests passed only
if your pytest output says so. No screenshot is required. Keep full dbt manifests,
tracebacks and build logs in ignored reports. Do not publish billing screenshots.

### 22. Add the public link and finish the roadmap — Editor

```bash
open -a TextEdit README.md
```

Add a short section near the existing dashboard section. Use your actual URL:

```markdown
## Public dashboard

[Open CityFlow](https://YOUR-SUBDOMAIN.streamlit.app)

The public app serves a validated Snowflake aggregate snapshot for January–March
2025, with whole-month activity and selected directed routes. A dedicated key-pair
service identity was tested from the hosted app before switching to credential-free
snapshot mode and removing the dedicated Snowflake resources. The full local
dashboard retains arbitrary date filters and the complete route catalog.

See [deployment design](hosting_design.md),
[deployment results](hosting_results/summary.md), and
[deployment guide](hosting_guide.md).
```

Keep all existing local reproduction commands, Snowflake/dashboard evidence
links and figures. Update the roadmap's cloud connection/public hosting milestone
to **complete** only after the remote checks and cleanup actually pass. Note that
the planned portfolio build is complete; ongoing maintenance is the next activity.
Do not describe the app as live-refreshing or hosted on AWS.

### 23. Commit and merge final evidence — Terminal A

```bash
git diff --check
git diff -- README.md docs/hosting_results/summary.md
git add README.md docs/hosting_results
git diff --cached --stat
git diff --cached --check
git commit -m "Record hosted dashboard validation and final cleanup"
git push -u origin docs/hosting-results
cat > reports/hosting/results_pr.md <<'EOF'
## Final deployment evidence
- Add the public portfolio dashboard URL.
- Record real/full parity, published-subset parity, remote live and snapshot checks.
- Record warehouse usage, reporting limitations and actual final cleanup.
- Mark the planned implementation phases complete; retain local reproduction and figures.
EOF
gh pr create --base main --head docs/hosting-results \
  --title "Document completed CityFlow deployment" --body-file reports/hosting/results_pr.md
gh pr checks --watch
```

Review and merge after CI passes:

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git status --short --branch
```

Open the public URL once more after the main-branch update. The Streamlit host
updates from the repository; private mode settings remain `backend = "snapshot"`.
If your roadmap is in a separate tracked file, stage its actual path in the same
evidence PR rather than leaving that update uncommitted.

## Pausing partway through

Stop local app servers with Control+C. Before closing Snowsight, as ACCOUNTADMIN,
SHOW warehouses, suspend whichever is running, and set AUTO_RESUME=FALSE for
each warehouse that exists. If the public app already exists, use snapshot mode
and remove the hosted Snowflake credentials before leaving it unattended.
Private local variables can be cleared:

```bash
unset CITYFLOW_SF_PASSWORD
unset CITYFLOW_HOSTING_BACKEND
```

To resume a cloud session, restore private environment variables from step 7;
enable AUTO_RESUME for the dedicated warehouses that still exist. If you disabled
the service user for a temporary pause, enable it only for the next bounded live
check (`ALTER USER CITYFLOW_APP_USER SET DISABLED=FALSE` as ACCOUNTADMIN).
If final DROP cleanup already ran, cloud testing requires a deliberate rebuild;
the published snapshot does not. Do not rerun CREATE blocks against existing objects.

## After completion: normal local startup

The public app is available through its URL without your Mac being on. To run
its frozen public version locally:

```bash
cd ~/Desktop/projects/cityflow
export CITYFLOW_HOSTING_BACKEND='snapshot'
.venv-dashboard/bin/python -m streamlit run cloud_dashboard/app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

For the original full local dashboard, use its previous quick-start commands
and `dashboard/app.py`. Deleted Snowflake resources are not needed for either
local mode. Keep private keys ignored; after final cleanup they no longer provide
access to the dropped user. Do not reuse a published/compromised key.

## Troubleshooting

- **Git switch unsupported:** this guide uses checkout exclusively. `git branch`
  lists branches; `git checkout -b NAME` creates and selects one.
- **Silent file checks:** `test -f` normally prints nothing. The prerequisite
  block here prints FOUND/MISSING explicitly.
- **Local app port occupied:** stop your previous server. Inspect with
  `lsof -nP -iTCP:8501 -sTCP:LISTEN`; do not kill an unrelated process. You can
  launch with `--server.port 8502` and open `http://127.0.0.1:8502` instead.
- **Service JWT/auth failure:** confirm the correct account, matching generated
  public/private key, service user name and current Mac clock. The human password
  profile is unrelated to service key-pair authentication. Do not loosen grants.
- **Raw access check unexpectedly succeeds:** stop before publication. Inspect
  service role and PUBLIC grants; no raw access is intended.
- **Snapshot parity failure:** retain the reports and inspect mismatched columns.
  Do not loosen tolerances, fill nulls with zero or publish despite the failure.
- **Hosted dependencies wrong:** confirm entrypoint `cloud_dashboard/app.py` and
  adjacent `cloud_dashboard/requirements.txt`, with Python 3.11 selected. Check
  owner logs; do not change root pipeline dependencies to fix hosting.
- **Host still says Snowflake after switching:** replace the entire Secrets
  contents with the one-line snapshot setting, save and reboot. Verify in incognito.
- **A sleeping host needs waking:** use its wake control and wait for startup.
  This does not require recreating Snowflake in snapshot mode.
- **Quota/monitor suspension:** inspect actual usage before changing a budget;
  do not remove the monitor to complete a run. Snapshot mode remains usable.
- **Report/snapshot already exists:** helpers refuse to overwrite evidence. For
  a deliberate new export use a new snapshot/report path, compare it, then review
  an explicit replacement; do not blindly erase the previous published result.

## Official references checked for this guide

- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Dependencies and entrypoint-directory precedence: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- Secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- App management/hibernation: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Snowflake key pairs: https://docs.snowflake.com/en/user-guide/key-pair-auth
- Service users: https://docs.snowflake.com/en/sql-reference/sql/create-user
- Monitor limits: https://docs.snowflake.com/en/user-guide/resource-monitors

Provider UI labels and supported Python versions can change. The tested local
package does not substitute for your real cloud execution and remote checks.
