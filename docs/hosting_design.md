# CityFlow deployment design

The final planned phase proves key-pair access from a hosted Streamlit app to
Snowflake, then publishes a validated aggregate snapshot with no database
credentials. Snapshot mode is the enduring portfolio deployment; Snowflake mode
is a bounded connection exercise, not an always-on paid service.

`cloud_dashboard/app.py` is a separate public entrypoint. The existing
`dashboard/app.py` retains its full local capabilities. The public app supports
the full quarter or individual complete months. It does not calculate an
arbitrary partial-date percentile from stored monthly medians.

The four serving tables contain metadata, 90 daily rows, three monthly rows and
at most 315 route/month rows. Routes are selected by quarter trip volume:
100 geographic and five non-geographic routes, with route-key ordering to
break ties. Ranking displayed for each month remains the original all-route
geographic rank. A complete three-month grid preserves valid zero months.
Insufficient duration/fare cohorts are suppressed before export and download.

The service identity has USAGE on one X-Small app warehouse and the serving
schema, and SELECT on precisely four tables. No raw/fact read, object creation,
ownership, administrator role or human password is granted by these scripts.
Private PKCS8 key material belongs only in ignored local/hosted secrets.
The connector disables secondary roles and sets a 60-second statement timeout.

Live mode reads all four small tables and caches them for up to one hour in
each app process. This is a freshness/performance choice, not a global credit
cap: restarts and distinct processes can query again. The app warehouse has a
one-credit daily resource monitor; the loading warehouse retains its separate
five-credit monthly monitor. Resource monitors can overshoot and do not limit
all storage or serverless services. Frozen public mode creates no Snowflake
queries and can continue after its service identity/resources are deleted.

`scripts/publish_dashboard.py export` requires every published cell to match
local DuckDB analytics, with abs=1e-9 and rel=1e-12 numeric tolerance, checks
that the service user cannot read raw trips, verifies the serialized roundtrip,
and records query IDs and the public-file hash. Full marts must separately pass
the existing Snowflake parity command before creating serving tables.

Eight fixture tests cover cell parity, suppression, complete calendars, dataset
labels, undefined zero comparisons, interactive controls and safe public errors.
Actual real-data and remote-host checks remain explicit gates in the guide.
Public JSON contains selected aggregates only, never individual records, login
logs, account/user identifiers or full route exports. The previous prohibition
on committing full route exports remains; this bounded publication is explicit.

Runtime error messages expose only exception classes. Do not publish complete
connector tracebacks, credentials or screenshots with billing/personal details.

References:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://docs.snowflake.com/en/user-guide/key-pair-auth
- https://docs.snowflake.com/en/user-guide/resource-monitors
