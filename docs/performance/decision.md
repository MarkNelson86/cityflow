# Performance decision

Decision: retain the current model materializations for the frozen January–March
2025 workload. Ingestion remains incremental by source partition; the fact and
analytical marts rebuild in full.

Evidence: two warm SELECT benchmark runs with exact route/month count equivalence,
plus a separate selected analytical build-cost capture. See baseline/, repeat_a/
and dbt_analytics/ for measured values, settings and plans.

The fact/mart read comparison measures reuse of aggregates already stored by dbt.
It does not establish a newly achieved SQL optimization, an end-to-end refresh
speedup, or performance on another machine. No current refresh requirement
justifies the added correctness complexity of incremental analytical models.

Revisit this decision if the source window expands, refresh frequency increases,
or the measured workload exceeds an explicit user-facing latency requirement.
