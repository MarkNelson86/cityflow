# Cityflow query benchmark

Dataset: NYC TLC yellow-taxi snapshot, January–March 2025.
Observed records: 11,198,001. Equivalent fact/mart count results: verified.

| Query | Result rows | Median s | Min s | Max s |
| --- | --- | --- | --- | --- |
| route_counts_from_fact | 103,709 | 0.867137 | 0.842345 | 0.978601 |
| route_counts_from_mart | 103,709 | 0.077661 | 0.070701 | 0.081895 |
| top_route_comparison | 3 | 0.020092 | 0.018029 | 0.023485 |

Median fact-query / mart-query elapsed ratio: 11.17×.

This ratio compares repeated reads of equivalent saved-count results. It does not include the cost of building or refreshing the marts.
One warm-up precedes each set of measured runs. Times include Python result fetching. Query order rotates; disk/OS caches are not reset.
EXPLAIN ANALYZE executes the query and records engine operator timings separately. Parallel operator times need not sum to the query wall time.
Tiny timings and a single run are insufficient evidence for a tuning claim. Use the same data, settings and result contract for comparisons.
