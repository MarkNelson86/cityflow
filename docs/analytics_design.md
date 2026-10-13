# Analytical models and interpretation

## Grains and dates

| Model | Grain | Key |
|---|---|---|
| mart_daily_activity | One calendar date | date_day |
| mart_route_monthly | Ordered route × pickup month | route_month_key |
| mart_route_month_comparison | Ordered route × pickup month | route_month_key |

All records used in these models satisfy `is_observed_trip`. The analytical month
is derived from the actual pickup date. It can differ from the file's source_month.
Routes are directed: 1->2 and 2->1 are distinct. Null IDs use the text token NULL
in route keys, so an unmapped/missing ID does not disappear during reconciliation.

## Counts, cohorts and distributions

Trip counts count in-window source records. They do not establish unique rides
or unmet demand. Duration and fare summaries use their separate eligibility
flags from stg_trips. Counts and cohort sizes are exported with the metrics.

Median is the 50th percentile. P90 duration is an interpolated 90th percentile
using DuckDB quantile_cont: about 90% of eligible recorded durations lie at or
below it. On very small samples it is an interpolation, not an observed duration
at an exact rank. Daily, route-month and overall month summaries recompute
percentiles from their eligible trip records. Never average lower-level medians
to obtain a pooled median.

The complete date dimension supplies every calendar day. The route universe is
the set of routes observed anywhere in the quarter. Crossing those routes with
the three calendar months retains zero-activity months. Zero trip counts and
null travel-time metrics have different meanings.

Coverage is checked for the entire three-file snapshot because source files can
contain cross-boundary timestamps. If any expected trip partition is absent, the
models flag snapshot_complete=false and leave numeric summaries null, rather
than presenting missing data as zero activity. Data tests fail and the exporter
refuses publication. This ensures known files are loaded; it cannot establish
that TLC's underlying vendor submissions capture every real-world taxi trip.

Trips/day divides by all calendar days: 31 in January, 28 in February, 31 in March.
It does not divide by only the days on which the route was observed.

## Geographic ranks and sample thresholds

All routes remain in aggregate tables and count reconciliation. Geographic
rankings require both zone IDs to match the dimension and both borough labels
to be one of Bronx, Brooklyn, Manhattan, Queens or Staten Island. This explicitly
omits Unknown/Unmapped and outside-city borough categories from geographic
highlights. It does not remove them from total activity.

Volume rank is dense_rank within a month, descending by trip count. Ties share
a rank; the next distinct count receives the next integer. Zero-activity routes
have no volume rank. Export display_order is separately deterministic and limits
the highlight tables to ten rows per month, breaking display ties by route key.

Default analytics_min_records=30 is a documented exploratory threshold, not a
statistical significance or precision guarantee. Duration and fare flags are
computed from their own cohort sizes. Under-threshold metrics remain visible in
full analytical tables with their flags; highlight exports suppress them.
Duration/fare changes are reported only when both adjacent cohorts meet the
respective threshold. The synthetic demo uses a threshold of two to illustrate
these rules; do not use that override for the real-data release.

## Month comparisons

LAG runs within each route, ordered by month_start. The complete grid guarantees
that March's predecessor is February, even for a route with zero February trips.
January has no predecessor. Count changes and calendar-day-normalized changes
are both provided. Percentage changes divide by NULLIF(previous value, 0), so
growth from zero is undefined/null and a decrease from positive volume to zero
is -100%. Months without an eligible duration have a null duration median;
comparisons do not skip over the missing month.

These descriptions do not control for changes in time of day, passengers,
payment/rate categories, or trip mix. Route-month changes should not be described
as causal congestion effects or population-wide fare inflation. Source-local
wall-clock timestamps retain daylight-saving ambiguity.

## Validation and exporting

The new tests reconcile counts/cohorts, enforce keys and calendars, check
percentile/cohort invariants, check adjacent predecessor months and verify that
fact rows use the currently registered source hashes. Original warehouse tests
remain available. The new fixture includes a January pickup in a February source
file, a zero February route month, ranking ties, null IDs and excluded records.
It has 13 raw records, 12 in-window records, four routes, 12 route-month rows and
90 date rows. Actual pickup-month counts are 5, 3 and 4.

The exporter checks coverage, fact source hashes, and total reconciliation before
writing outputs. It is not a substitute for dbt tests or rebuilding changed
models. Run the documented build/test commands immediately before exporting.
It writes full aggregates to ignored reports/ and small highlight/report files
that may be copied deliberately into docs/results/.

No new dependencies are required. Source ingestion stays incremental by file
partition; these analytical models are full table builds for now.
