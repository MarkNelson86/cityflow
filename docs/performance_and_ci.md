# Performance measurement and continuous integration

## Scope and contracts

The completed January–March 2025 analytical run reconciled to 11,198,001
in-window records. The selected three-model/17-test build took about 6.7 seconds
on the author's Mac. This phase measures the existing design and automates its
correctness checks. It does not promise a speedup or introduce new model
materializations. Source ingestion is already incremental by file partition;
the fact and analytical tables currently rebuild in full.

| Measurement | Input | Meaning |
| --- | --- | --- |
| dbt build artifact | A successful selected analytical build | Construction/test cost for those selected nodes, with two overlapping threads |
| Fact route-count query | Observed geographic fact rows | Recalculate counts by actual pickup month and directed route |
| Mart route-count query | Saved route-month rows | Read the same positive counts; aggregation was paid for at build time |
| Top-route comparison | Saved route/month comparison and route/month marts | Retrieve three consecutive months for the quarter's most-recorded geographic route |

The first two SELECTs must return identical ordered rows, not merely identical
grand totals. The benchmark verifies that exact integer/date/key contract before
timing. Metrics, filtering definitions and grains must not change to make a query
appear faster. Null/Unknown/outside-city routes remain in the full marts, but both
count-comparison queries exclude them identically from geographic results.

## Benchmark protocol

`scripts/benchmark_queries.py` opens the existing database read-only and uses the
exporter's coverage/freshness/reconciliation checks. It sets two execution
threads and a 2GB DuckDB memory limit by default. Spill files, if needed, live
beside the ignored local database, under a separate benchmark spill directory.

Each query runs once to warm the connection and obtain verified results, then
five measured times. Query order rotates between rounds. A timer covers SQL
execution and Python `fetchall`; result hashing happens after the timer. These
are warm, local, single-client reads. OS caches are not reset, no concurrent
workload is modeled, and these are not disk-cold or server-latency benchmarks.

The runner saves median/min/max times, each timing sample, returned row counts,
result hashes, SQL hashes, source version hashes, software/platform/settings and
a Git commit/dirty flag. A dirty flag is expected when newly installed files are
not yet committed; individual script/query hashes capture that code. It refuses
to overwrite a nonempty output directory. Use a different directory per run.

`EXPLAIN ANALYZE` executes the SELECT again and saves its query plan separately
from the timed samples. Inspect scans, filters, groups, joins and actual row
counts from the inputs upward. Operator times may overlap across worker threads;
their sum is not necessarily total query wall time. The Python elapsed time also
includes result transfer, so it need not equal the engine's reported total.

No database writes, index creation or DuckDB `ANALYZE` statistics updates occur
in this runner. SQL `EXPLAIN ANALYZE` and the standalone `ANALYZE` statement have
different purposes.

## Optimization decisions

Reading a small stored aggregate can outperform recalculating it from millions
of facts. This is evidence for the existing materialization choice, not a newly
achieved before/after tuning improvement. Include the separate dbt refresh cost
when assessing how often reuse would be useful. Tiny fixture timings establish
correctness only, not real-data performance.

For a baseline, run the real benchmark twice under the same settings and examine
the range. A sound result may be "current analytical builds and reads are fast
enough; keep the simpler full builds." Record an explanation, not an invented
improvement. Avoid cross-machine speed claims and CI timing pass/fail gates.

If a bottleneck remains, choose one candidate and measure it separately against
the same baseline, with equivalent results. Projection/filter pushdown, redundant
work, expensive percentile groups or repeated refreshes may be worth inspecting;
the plan and workload decide. Optional thread comparisons measure configuration,
not SQL improvement. Incremental fact/mart models would need replacement/deletion
tests for changed source partitions, dimension changes and month boundaries.
Their correctness work is not justified solely by having millions of records.

## CI contract

`.github/workflows/ci.yml` runs on pull requests, pushes to main and manual
dispatch. A single Ubuntu 24.04/Python 3.11 job installs `requirements.txt`, checks
dependency compatibility and invokes `scripts/run_ci_checks.py`. The same command
is available locally. No real TLC downloads or cloud credentials are required.

The runner executes the complete pytest suite, then separately generates the
13-record analytical fixture, ingests it, builds all eight models/33 dbt tests
and exports a labeled synthetic report. Pytest's own isolated end-to-end builds
check known answers and failure paths; the visible fixture build additionally
retains inspectable dbt artifacts/report evidence. All fixture databases and
profiles are created inside its output directory. Your real warehouse and
dbt/target artifacts remain untouched.

The CI fixture uses `analytics_min_records: 2`, as before. It must not be mistaken
for the real-data default of 30. Its pickup-month counts are 5, 3 and 4; the
calendar has 90 rows and the route grid has 12 rows. Real snapshot checks remain
a local release checkpoint. Fixture success does not prove coverage or quality
of the external real source files.

Logs, pytest XML and small dbt/report artifacts are retained for seven days, even
when an earlier step fails. Generated databases and raw Parquet files are not
uploaded. The workflow uses a read-only repository token and no publishing step.
It has a ten-minute job limit and cancels superseded runs on the same PR/ref.

## Numerical regression

The real-data run exposed 15 false positives: `median` and `quantile_cont` differed
by roughly 1e-14 minutes for effectively equal values. The existing singular
invariant test now rejects a median above p90 only when the excess exceeds
1e-9 minutes. No stored metrics are rounded or changed. The new regression test
accepts last-bit noise and still rejects a genuine 0.1-minute inversion.

## Results review

Actual pickup months differ from source-file labels near boundaries. Always use
the relevant denominator: trip counts describe in-window source records,
duration/fare metrics use independent eligible cohorts, and trips/day uses all
31/28/31 calendar days. Same-zone trips are legitimate zone-level route records;
they do not imply that pickup and dropoff coordinates were identical.

Large highlighted route changes are selected from many comparisons. They are
exploratory candidates, not statistically significant findings. Inspect both
adjacent medians and cohort sizes. A cohort threshold of 30 is an explicit
reporting rule, not a confidence interval or control for trip mix. A future
inferential analysis would need a separate question and design.

## Official references

- [DuckDB EXPLAIN ANALYZE](https://duckdb.org/docs/current/guides/meta/explain_analyze)
- [dbt run results artifact](https://docs.getdbt.com/reference/artifacts/run-results-json)
- [GitHub Actions Python testing](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), [upload-artifact](https://github.com/actions/upload-artifact)
