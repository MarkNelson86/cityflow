# Remaining Cityflow phases

All three extensions below are accepted project work. Deliver each as a reviewed
branch/PR with concrete validation, and reuse the existing definitions and evidence.

| Phase | Focused time estimate | Deliverables | Completion gate |
| --- | --- | --- | --- |
| Portfolio presentation | 3–5 hours | Reproducible activity figure, clearer README, architecture/metric documentation | Real inputs reconcile; image/links reviewed; CI green; PR merged |
| Bounded Snowflake extension | 6–10 hours | Isolated cloud environment, staged inputs, warehouse-compatible dbt transforms, reconciliation and cleanup evidence | Fixture parity first, real-snapshot parity, recorded configuration/query evidence and suspended/cleaned resources | complete; CI green; PR merged |
| Local interactive dashboard | 6–10 hours | Date/month and directed-route exploration, activity/metric charts, cohort-aware comparisons | Filtered outputs reconcile with validated aggregates; zero/missing/under-threshold states are correctly displayed | complete; CI green; PR merged |
| Cloud connection and hosting | Additional 4–8 hours | Dashboard connected to the accepted cloud environment and deployed on an agreed host | Access/configuration, secrets handling, refresh and cost behavior tested |

## Portfolio phase

Lead the repository with its question, actual dataset, an interpretable plot,
measured results and the shortest reproducible path. Explain engineering choices
through their evidence: preserved provenance, independent metric cohorts, calendar
grids, replacement-safe ingestion, tests and equivalently benchmarked reads.

Keep completed local functionality distinct from the upcoming cloud and dashboard
milestones. The static README figure will later become the dashboard's activity
view; the same exports and definitions will support both.

## Snowflake phase - complete

Start with the generated analytical fixture in an isolated environment. Configure
authentication, a small warehouse, access roles, staging and suspension/budget
controls before loading the real snapshot. Current account/trial/authentication
conditions will be verified when preparing that phase; no paid commitment is
assumed here.

Reuse the sources' version identities and the analytical contracts, then adapt
warehouse-specific SQL through appropriate dbt macros or isolated model variants.
DuckDB expressions such as interval-to-epoch duration calculations, boolean
aggregates, FILTER aggregates and `quantile_cont` need a deliberate dialect review.
Pointing a new profile at Snowflake alone is not sufficient.

Require matching fixture known answers before the bounded full load. Then
reconcile observed/source/cohort counts, route-month keys, zero months and
percentiles within documented numeric tolerances. Record cloud-specific timings
without treating them as a direct cross-machine DuckDB performance comparison.
Keep the local pipeline runnable, record credentials only through the chosen
secret mechanism and finish with suspended/cleaned resources.

## Dashboard phase - complete

The local dashboard provides date-filtered activity and directed-route monthly
exploration from the retained DuckDB snapshot. Fixture controls and metric boundaries
are tested; real activity and sampled route outputs reconcile with validated aggregates.
See [dashboard results](dashboard_results/summary.md) and
[dashboard design](dashboard_design.md).

## Cloud connection and hosting — next

Rebuild the dedicated cloud environment when needed, add a cloud data adapter,
and deploy the validated dashboard. Test access, secret handling, refresh behavior,
availability and warehouse costs before calling the hosted product complete.
