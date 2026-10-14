"""Compare equivalent queries and record warm timings and EXPLAIN ANALYZE plans."""
import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.export_analytics import require_ready

NAMES = ('route_counts_from_fact', 'route_counts_from_mart', 'top_route_comparison')


def fingerprint(rows):
    encoded = json.dumps(rows, default=str, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify_equivalent(left, right):
    if left != right:
        raise ValueError('Fact and mart route counts differ; rebuild/test before benchmarking')


def git_value(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def benchmark(con, queries, repeats):
    """Warm once, verify equivalence, then rotate query order between measured rounds."""
    if repeats < 3:
        raise ValueError('Use at least three measured repeats')
    warm = {name: con.execute(sql).fetchall() for name, sql in queries.items()}
    verify_equivalent(warm['route_counts_from_fact'], warm['route_counts_from_mart'])
    expected = {name: fingerprint(rows) for name, rows in warm.items()}
    samples = []
    names = list(queries)
    for iteration in range(repeats):
        offset = iteration % len(names)
        for name in names[offset:] + names[:offset]:
            start = time.perf_counter()
            rows = con.execute(queries[name]).fetchall()
            seconds = time.perf_counter() - start
            if fingerprint(rows) != expected[name]:
                raise ValueError(f'Results changed during benchmark: {name}')
            samples.append({'query': name, 'repeat': iteration + 1,
                            'seconds': seconds, 'returned_rows': len(rows)})
    summaries = []
    for name in names:
        timings = [row['seconds'] for row in samples if row['query'] == name]
        summaries.append({'query': name, 'returned_rows': len(warm[name]),
                          'median_seconds': statistics.median(timings),
                          'min_seconds': min(timings), 'max_seconds': max(timings),
                          'result_sha256': expected[name],
                          'sql_sha256': hashlib.sha256(queries[name].encode()).hexdigest()})
    return samples, summaries


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/warehouse/cityflow.duckdb')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/performance/baseline')
    parser.add_argument('--label', default='NYC TLC yellow-taxi snapshot, January–March 2025')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--memory-limit', default='2GB')
    args = parser.parse_args()
    if args.repeats < 3 or args.threads < 1:
        parser.error('repeats must be at least three; threads must be positive')
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit('Output directory is not empty; choose a new run directory')
    queries = {name: (ROOT / f'sql/benchmarks/{name}.sql').read_text() for name in NAMES}
    with duckdb.connect(str(args.database), read_only=True) as con:
        con.execute('SET threads = ?', [args.threads])
        con.execute('SET memory_limit = ?', [args.memory_limit])
        spill = args.database.resolve().with_suffix('.benchmark_spill')
        con.execute('SET temp_directory = ?', [str(spill)])
        observed = require_ready(con)
        sources = con.execute('SELECT partition_key, source_sha256, row_count '
                              'FROM meta.loaded_sources ORDER BY partition_key').fetchall()
        samples, summaries = benchmark(con, queries, args.repeats)
        # Plans execute each query once more; these runs are not in the timed samples.
        plans = {name: '\n'.join(str(row[-1]) for row in con.execute(
            'EXPLAIN ANALYZE ' + sql).fetchall()) for name, sql in queries.items()}
    metadata = {
        'label': args.label, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'observed_records': observed, 'duckdb_version': duckdb.__version__,
        'python_version': platform.python_version(), 'os': platform.system(),
        'os_release': platform.release(), 'machine': platform.machine(),
        'logical_cpus': os.cpu_count(), 'threads': args.threads,
        'memory_limit': args.memory_limit, 'measured_repeats': args.repeats,
        'warmup_runs_per_query': 1,
        'timing_scope': 'execute + fetchall in one connection; preflight/verification/plans excluded',
        'cache_scope': 'warm repeats; operating-system caches are not reset',
        'git_commit': git_value('rev-parse', 'HEAD'),
        'working_tree_dirty': bool(git_value('status', '--porcelain')),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'sources': [dict(zip(('partition', 'sha256', 'rows'), row)) for row in sources],
        'queries': summaries,
        'equivalent_count_results': True,
    }
    output = args.output_dir
    (output / 'plans').mkdir(parents=True, exist_ok=True)
    write_csv(output / 'timings.csv', samples)
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    for name, plan in plans.items():
        (output / 'plans' / (name + '.txt')).write_text(plan + '\n')
    by_name = {row['query']: row for row in summaries}
    speedup = (by_name['route_counts_from_fact']['median_seconds'] /
               by_name['route_counts_from_mart']['median_seconds'])
    lines = ['# Cityflow query benchmark', '', f'Dataset: {args.label}.',
             f'Observed records: {observed:,}. Equivalent fact/mart count results: verified.', '',
             '| Query | Result rows | Median s | Min s | Max s |',
             '| --- | --- | --- | --- | --- |']
    for row in summaries:
        lines.append(f"| {row['query']} | {row['returned_rows']:,} | "
                     f"{row['median_seconds']:.6f} | {row['min_seconds']:.6f} | "
                     f"{row['max_seconds']:.6f} |")
    lines += ['', f'Median fact-query / mart-query elapsed ratio: {speedup:.2f}×.', '',
              'This ratio compares repeated reads of equivalent saved-count results. '
              'It does not include the cost of building or refreshing the marts.',
              'One warm-up precedes each set of measured runs. Times include Python result '
              'fetching. Query order rotates; disk/OS caches are not reset.',
              'EXPLAIN ANALYZE executes the query and records engine operator timings separately. '
              'Parallel operator times need not sum to the query wall time.',
              'Tiny timings and a single run are insufficient evidence for a tuning claim. '
              'Use the same data, settings and result contract for comparisons.', '']
    (output / 'summary.md').write_text('\n'.join(lines))
    print('\n'.join(lines))
    print('Saved:', output)


if __name__ == '__main__':
    main()
