# CityFlow local dashboard results

- Dataset: real January–March 2025 snapshot
- Automated checks completed (UTC): 2026-10-14T23:52:12.486720+00:00
- Automated data checks: passed
- Raw records: 11,198,026
- Observed records: 11,198,001
- Daily / route-month / comparison rows: 90 / 133,377 / 133,377
- Route metric threshold: 30
- Monthly observed counts: [3475234, 3577542, 4145225]
- Environment: {'python': '3.11.4', 'duckdb': '1.5.6', 'streamlit': '1.50.0', 'pandas': '2.2.3', 'plotly': '6.3.0'}
- Backend: local DuckDB; read-only connections
- Snowflake resources: remain removed from the completed Snowflake phase
- Public hosting: not part of this phase
- Automated dashboard tests: 13 dashboard checks passed.
- Browser checks completed at: 2026-10-14 17:00 PDT

## Browser review

| Check | Result |
| --- | --- |
| Fixture warning and 12 observed trips | Pass |
| Zero-trip route month displays 0 and suppressed metrics | Pass |
| Growth from zero is undefined | Pass |
| Unmapped route is selectable and under-threshold metrics are hidden | Pass |
| Full real snapshot shows 11,198,001 observed trips | Pass |
| Date range changes counts and selected-day denominator | Pass |
| Route origin/destination/month controls work | Pass |
| Selected activity and route CSV downloads work | Pass |

## Validation scope

The known monthly counts, eligible cohort sizes, medians and p90 match the previously
established answers. Date-filtered activity reconciles with fact records. Route
samples are recomputed from fact records: Three highest-volume geographic routes (or all if fewer), plus one non-geographic route when present; not a full new parity scan.
The earlier full DuckDB–Snowflake parity evidence remains separate. Check timings
are development observations, not a cross-engine performance comparison.
