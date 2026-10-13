# Cityflow analytical results

Dataset: NYC TLC yellow-taxi snapshot, January–March 2025. Exported: 2026-10-13T23:38:54.042789+00:00.
The three analytical models reconcile to **11,198,001 in-window source records**.
The calendar includes 90 days. Peak recorded activity: **2025-03-01**, with **164,226 records**.

## Monthly activity

| Pickup month | Days | Recorded trips | Trips/day | Duration cohort | Fare cohort | Median min | P90 min | Median fare USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01-01 | 31 | 3,475,234 | 112,104.32 | 3,471,806 | 3,331,116 | 11.70 | 27.52 | 12.80 |
| 2025-02-01 | 28 | 3,577,542 | 127,769.36 | 3,571,077 | 3,394,887 | 12.22 | 27.83 | 13.50 |
| 2025-03-01 | 31 | 4,145,225 | 133,716.94 | 4,121,371 | 3,936,501 | 12.52 | 29.27 | 14.10 |

## Most recorded geographic routes

| Month | Pickup | Dropoff | Recorded trips | Median min | P90 min |
| --- | --- | --- | --- | --- | --- |
| 2025-01-01 | Upper East Side South | Upper East Side North | 24,839 | 6.60 | 11.52 |
| 2025-01-01 | Upper East Side North | Upper East Side South | 21,843 | 7.27 | 12.13 |
| 2025-01-01 | Upper East Side North | Upper East Side North | 18,221 | 4.15 | 7.56 |
| 2025-01-01 | Upper East Side South | Upper East Side South | 17,441 | 4.62 | 8.55 |
| 2025-01-01 | Midtown Center | Upper East Side South | 11,463 | 8.15 | 13.92 |
| 2025-01-01 | Upper East Side South | Midtown Center | 10,168 | 8.73 | 15.57 |
| 2025-01-01 | Midtown Center | Upper East Side North | 9,845 | 12.07 | 18.92 |
| 2025-01-01 | Upper West Side South | Upper West Side North | 9,595 | 4.82 | 7.92 |
| 2025-01-01 | Lincoln Square East | Upper West Side South | 9,141 | 5.77 | 9.35 |
| 2025-01-01 | Upper West Side South | Lincoln Square East | 8,844 | 5.70 | 9.08 |
| 2025-02-01 | Upper East Side South | Upper East Side North | 23,201 | 6.52 | 11.15 |
| 2025-02-01 | Upper East Side North | Upper East Side South | 20,159 | 7.27 | 12.00 |
| 2025-02-01 | Upper East Side North | Upper East Side North | 16,603 | 4.12 | 7.45 |
| 2025-02-01 | Upper East Side South | Upper East Side South | 15,750 | 4.58 | 8.32 |
| 2025-02-01 | Midtown Center | Upper East Side South | 10,693 | 8.78 | 14.95 |
| 2025-02-01 | Upper East Side South | Midtown Center | 9,266 | 9.07 | 15.52 |
| 2025-02-01 | Upper West Side South | Upper West Side North | 9,052 | 4.85 | 7.96 |
| 2025-02-01 | Midtown Center | Upper East Side North | 9,002 | 12.63 | 19.80 |
| 2025-02-01 | Lincoln Square East | Upper West Side South | 8,500 | 5.77 | 9.33 |
| 2025-02-01 | Upper West Side South | Lincoln Square East | 8,210 | 5.67 | 9.13 |
| 2025-03-01 | Upper East Side South | Upper East Side North | 23,653 | 6.33 | 11.05 |
| 2025-03-01 | Upper East Side North | Upper East Side South | 20,392 | 7.10 | 12.07 |
| 2025-03-01 | Upper East Side South | Upper East Side South | 16,443 | 4.55 | 8.38 |
| 2025-03-01 | Upper East Side North | Upper East Side North | 16,342 | 3.98 | 7.23 |
| 2025-03-01 | Midtown Center | Upper East Side South | 11,366 | 8.43 | 14.36 |
| 2025-03-01 | Upper East Side South | Midtown Center | 10,316 | 9.02 | 15.63 |
| 2025-03-01 | Midtown Center | Upper East Side North | 9,899 | 12.17 | 19.30 |
| 2025-03-01 | Upper West Side South | Upper West Side North | 9,256 | 4.80 | 7.82 |
| 2025-03-01 | Lincoln Square East | Upper West Side South | 9,196 | 5.73 | 9.27 |
| 2025-03-01 | Upper West Side South | Lincoln Square East | 8,992 | 5.58 | 9.00 |

## Adjacent-month duration changes

| Month | Pickup | Dropoff | Median change min | Trips/day change % |
| --- | --- | --- | --- | --- |
| 2025-02-01 | Prospect-Lefferts Gardens | Downtown Brooklyn/MetroTech | -11.29 | 29.17 |
| 2025-02-01 | East New York | Flatbush/Ditmas Park | -10.25 | 61.58 |
| 2025-02-01 | Lenox Hill East | Downtown Brooklyn/MetroTech | 9.67 | 21.79 |
| 2025-02-01 | Midtown Center | Crown Heights North | 8.83 | 61.33 |
| 2025-02-01 | Borough Park | Midwood | -8.07 | 23.37 |
| 2025-02-01 | Crown Heights North | Brooklyn Heights | -8.02 | 80.64 |
| 2025-02-01 | SoHo | JFK Airport | 7.77 | -16.07 |
| 2025-02-01 | JFK Airport | Morrisania/Melrose | -7.22 | -29.55 |
| 2025-02-01 | Lenox Hill East | East Concourse/Concourse Village | 7.07 | 24.55 |
| 2025-02-01 | Hamilton Heights | Murray Hill | -6.65 | 36.55 |
| 2025-03-01 | JFK Airport | South Williamsburg | 10.38 | -4.53 |
| 2025-03-01 | LaGuardia Airport | East Flatbush/Farragut | 10.05 | -7.10 |
| 2025-03-01 | Midtown Center | Crown Heights North | -9.87 | 20.43 |
| 2025-03-01 | Woodside | JFK Airport | 8.73 | 19.54 |
| 2025-03-01 | JFK Airport | Dyker Heights | 8.58 | 1.01 |
| 2025-03-01 | JFK Airport | Highbridge | 7.40 | 19.73 |
| 2025-03-01 | JFK Airport | Co-Op City | 6.97 | 8.76 |
| 2025-03-01 | Sunnyside | Central Harlem North | 6.78 | -9.68 |
| 2025-03-01 | JFK Airport | DUMBO/Vinegar Hill | 6.72 | 26.97 |
| 2025-03-01 | JFK Airport | Spuyten Duyvil/Kingsbridge | 6.72 | 3.84 |

## Interpretation

All month labels use actual pickup dates, not source-file months. The rate denominator
is every calendar day in the month (31, 28, 31). Percentiles are recomputed from
eligible trip records; they are not averages of daily or route medians.

Route highlights require matched pickup/dropoff zones in NYC's five boroughs.
Unknown and outside-city routes remain in the complete analytical aggregates.
Volume ranks use recorded counts, with ties sharing a dense rank.

Route metrics in the highlight tables are suppressed below the configured cohort
threshold, shown in `run_metadata.json`. Duration comparisons require adequate
duration cohorts in both adjacent months. A blank comparison table means no route
met the requirements. Percentage change from zero is undefined and remains blank.

These are descriptive recorded taxi patterns. They do not establish changes in
all urban travel, causal congestion effects, or a travel-time forecast. Payment
categories and trip mix can affect comparisons. Wall-clock duration ambiguities
around daylight-saving changes remain part of the source limitations.

See `docs/analytics_design.md` for grains, definitions and validation.
