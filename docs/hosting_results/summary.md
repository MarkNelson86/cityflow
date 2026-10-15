# CityFlow public deployment

- Public URL: https://cityflow-mark.streamlit.app/
- Final hosted mode: published Snowflake aggregate snapshot; no live database credentials.
- Source snapshot: January–March 2025 NYC yellow taxis.
- Observed records: 11,198,001.
- Published daily/monthly rows: 90 / 3.
- Published selected routes / route-month rows: 105 / 315.
- Route cohort threshold: 30.
- Published-cell parity: `all_equal: true`; raw access denied: true.
- Snapshot SHA256: `e9d2e136b0653f9805fe503e1b32869d227e3268545ea72b0916f4c453713952`.
- Full three-mart parity: see `real_parity.json`.
- Actual hosting fixture test result: 8 hosting fixture checks passed.
- Hosted Python version: Python 3.11.
- Hosted live connection checked: 2026-10-14, 20:38–20:40 PDT.
  - Query IDs:
    - `01c7bcfa-0308-fe97-0011-d6c20001f7ae`
    - `01c7bcfa-0309-01fa-0011-d6c2000224ea`
    - `01c7bcfa-0308-fe97-0011-d6c20001f7b2`
    - `01c7bcfa-0309-01fa-0011-d6c2000224ee`
    - `01c7bcfa-0309-01fa-0011-d6c2000224f2`
    - `01c7bcfc-0309-01fa-0011-d6c2000224fe`
    - `01c7bcfc-0309-01fa-0011-d6c200022502`
    - `01c7bcfc-0308-fe97-0011-d6c20001f7ba`
    - `01c7bcfc-0308-fe97-0011-d6c20001f7be`
    - `01c7bcfc-0308-fe97-0011-d6c20001f7c2`
- Hosted snapshot/incognito/control/download checks: Passed on 2026-10-14 at 22:00 PDT; public page opened without sign-in, snapshot label displayed, Activity and Directed route controls responded, and downloads succeeded in both views.
- Coverage limitation: whole months; up to 100 geographic and five non-geographic routes selected by quarter volume.
- Local dashboard: retained with arbitrary date ranges and full route catalog.

## Usage and cleanup

- Usage window: 2026-10-14 through 2026-10-14 (PDT).
- `CITYFLOW_WH` credits: 0.3.
- `CITYFLOW_APP_WH` credits: 0.00 as displayed at 2026-10-14 21:14 PDT.
- Other compute: `COMPUTE_WH`, 0.9 credits; not confirmed as project usage. Cloud services: 0.0 credits.
- Storage shown: `CITYFLOW_REAL` 1.1 GB; `SNOWFLAKE` 1.2 MB; stages 34.3 kB; `CITYFLOW_FIXTURE` 23.5 kB.
- Data transfer: no results for the selected date range. Other categories: none shown.
- Source and checked at: Snowsight Admin > Cost management > Consumption; 2026-10-14 21:14 PDT.
- Reporting status and limitations: Provisional; usage may be delayed. Recheck the same date range after 72 hours. The `CITYFLOW_APP_WH` zero is the displayed value at check time.
- Hosted credentials removed: Streamlit Cloud secrets contain only `backend = "snapshot"`; Snowflake connection credentials have been removed. Verified at 2026-10-14 22:06 PDT.
- Snowflake resources removed: `CITYFLOW_REAL`, `CITYFLOW_APP_USER`, `CITYFLOW_APP_ROLE`, `CITYFLOW_APP_WH`, `CITYFLOW_APP_MONITOR`, `CITYFLOW_WH`, `CITYFLOW_MONITOR`, and `CITYFLOW_ROLE`. `CITYFLOW_FIXTURE` was not recreated in this phase.
- Verified at: 2026-10-14 22:09 PDT; no matching dedicated resources remained.
- Local DuckDB and source data: retained.
- No account/personal user identifiers or private credentials are included here.
