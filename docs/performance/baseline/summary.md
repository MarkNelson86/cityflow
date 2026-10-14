# Cityflow query benchmark

Dataset: NYC TLC yellow-taxi snapshot, January–March 2025.
Observed records: 11,198,001. Equivalent fact/mart count results: verified.

| Query | Result rows | Median s | Min s | Max s |
| --- | --- | --- | --- | --- |
| route_counts_from_fact | 103,709 | 0.822633 | 0.821011 | 0.853000 |
| route_counts_from_mart | 103,709 | 0.076882 | 0.070390 | 0.077633 |
| top_route_comparison | 3 | 0.018437 | 0.018026 | 0.018568 |

Median fact-query / mart-query elapsed ratio: 10.70×.

This ratio compares repeated reads of equivalent saved-count results. It does not include the cost of building or refreshing the marts.
One warm-up precedes each set of measured runs. Times include Python result fetching. Query order rotates; disk/OS caches are not reset.
EXPLAIN ANALYZE executes the query and records engine operator timings separately. Parallel operator times need not sum to the query wall time.
Tiny timings and a single run are insufficient evidence for a tuning claim. Use the same data, settings and result contract for comparisons.
