"""Validate the committed Q1 exports and plot daily records plus monthly rates."""
import argparse
import csv
import hashlib
import json
import math
import platform
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = date(2025, 1, 1)
DAYS = [START + timedelta(days=offset) for offset in range(90)]
MONTHS = [(date(2025, 1, 1), 31), (date(2025, 2, 1), 28), (date(2025, 3, 1), 31)]


def read_csv(path, required):
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f'{path.name}: missing required columns {sorted(required)}')
        return list(reader)


def trailing_mean(values, window=7):
    """A full trailing window; the first window-1 entries remain missing."""
    return [None if index < window - 1 else sum(values[index-window+1:index+1]) / window
            for index in range(len(values))]


def load_inputs(daily_path, monthly_path, metadata_path):
    daily = read_csv(daily_path, {'date_day', 'trip_count', 'snapshot_complete'})
    daily.sort(key=lambda row: row['date_day'])
    dates = [date.fromisoformat(row['date_day']) for row in daily]
    if dates != DAYS:
        raise ValueError('Daily CSV must contain each Q1 2025 date exactly once (90 days)')
    if any(row['snapshot_complete'].lower() not in ('true', '1') for row in daily):
        raise ValueError('Daily CSV has incomplete source coverage; do not plot missing data as zero')
    try:
        counts = [int(row['trip_count']) for row in daily]
    except (TypeError, ValueError) as error:
        raise ValueError('Daily trip counts must be non-null integers') from error
    if any(count < 0 for count in counts):
        raise ValueError('Daily trip counts must be nonnegative')
    monthly = read_csv(monthly_path, {'month_start', 'calendar_days', 'trip_count',
                                      'trips_per_calendar_day'})
    monthly.sort(key=lambda row: row['month_start'])
    if [date.fromisoformat(row['month_start']) for row in monthly] != [m for m, _ in MONTHS]:
        raise ValueError('Monthly CSV must contain January, February and March exactly once')
    rates = []
    for row, (month_start, calendar_days) in zip(monthly, MONTHS):
        observed = sum(count for day, count in zip(dates, counts)
                       if day.month == month_start.month)
        if int(row['calendar_days']) != calendar_days or int(row['trip_count']) != observed:
            raise ValueError('Daily and monthly trip counts/calendar lengths do not reconcile')
        rate = float(row['trips_per_calendar_day'])
        if not math.isfinite(rate) or not math.isclose(rate, observed / calendar_days,
                                                       rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError('Monthly rate does not equal trips divided by all calendar days')
        rates.append(rate)
    metadata = json.loads(metadata_path.read_text())
    if metadata.get('observed_records') != sum(counts):
        raise ValueError('Export metadata and daily trip totals do not reconcile')
    label = metadata.get('label')
    if not isinstance(label, str) or not label.strip():
        raise ValueError('Export metadata must identify its dataset label')
    return {'dates': dates, 'counts': counts, 'rolling': trailing_mean(counts),
            'monthly_rates': rates, 'observed_records': sum(counts),
            'label': label, 'source_metadata': metadata}


def render(data, output):
    # Import lazily: CSV validation tests run in core CI without plotting packages.
    try:
        import matplotlib
    except ImportError as error:
        raise SystemExit('Install plotting packages: python -m pip install -r requirements-viz.txt') from error
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    synthetic = 'synthetic' in data['label'].lower()
    title = 'Synthetic fixture | plot preview' if synthetic else 'CityFlow | daily yellow-taxi records'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#d4dbe2', 'axes.labelcolor': '#263445',
                         'xtick.color': '#526273', 'ytick.color': '#526273',
                         'svg.hashsalt': 'cityflow-portfolio-q1', 'svg.fonttype': 'none'})
    fig = plt.figure(figsize=(12, 8), facecolor='white')
    grid = fig.add_gridspec(2, 1, height_ratios=[2.5, 1.2],
                           left=.09, right=.97, top=.79, bottom=.17, hspace=.60)
    ax, bars = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    fig.text(.09, .945, title, fontsize=22, fontweight='bold', color='#172c42')
    fig.text(.09, .901, data['label'], fontsize=11, color='#526273')
    fig.text(.09, .854, f"{data['observed_records']:,} in-window records  |  "
             '90 calendar days  |  Actual pickup dates', color='#263445', fontsize=12)
    ax.plot(data['dates'], data['counts'], color='#889bad', linewidth=1.2,
            label='Daily records', zorder=2)
    ax.plot(data['dates'], [float('nan') if value is None else value for value in data['rolling']],
            color='#007b83', linewidth=2.5, label='Trailing 7-day mean', zorder=3)
    ax.fill_between(data['dates'], data['counts'], color='#dce7ed', alpha=.45, zorder=1)
    ax.set_xlim(DAYS[0], DAYS[-1])
    ax.set_ylim(0, max(data['counts'], default=0) * 1.22 or 1)
    ticks = [date(2025, 1, 1), date(2025, 1, 15), date(2025, 2, 1), date(2025, 2, 15),
             date(2025, 3, 1), date(2025, 3, 15), date(2025, 3, 31)]
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.set_ylabel('Recorded trips')
    ax.grid(axis='y', color='#e9eef2')
    ax.set_axisbelow(True)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    formatter = FuncFormatter(lambda value, _: f'{value / 1000:,.0f}k' if max(data['counts']) >= 10000
                              else f'{value:,.0f}')
    ax.yaxis.set_major_formatter(formatter)
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), ncol=2, frameon=False, borderaxespad=0)
    peak = max(range(len(data['counts'])), key=data['counts'].__getitem__)
    ax.scatter([data['dates'][peak]], [data['counts'][peak]], color='#172c42', s=25, zorder=4)
    ax.annotate(f"Peak: {data['dates'][peak]:%b %d}\n{data['counts'][peak]:,} records",
                xy=(data['dates'][peak], data['counts'][peak]),
                xytext=(-125 if peak > 45 else 35, 12), textcoords='offset points',
                fontsize=9, color='#263445',
                arrowprops={'arrowstyle': '-', 'color': '#889bad'},
                bbox={'boxstyle': 'round,pad=.3', 'facecolor': 'white', 'edgecolor': 'none'})
    positions = [0, 1, 2]
    bars.bar(positions, data['monthly_rates'], color=['#96c7cd', '#4fa6ad', '#007b83'], width=.48)
    bars.set_xticks(positions, ['January\n31 calendar days', 'February\n28 calendar days',
                               'March\n31 calendar days'])
    bars.set_ylim(0, max(data['monthly_rates'], default=0) * 1.30 or 1)
    bars.set_ylabel('Trips / calendar day')
    bars.yaxis.set_major_locator(MaxNLocator(3))
    bars.yaxis.set_major_formatter(formatter)
    bars.grid(axis='y', color='#e9eef2')
    bars.set_axisbelow(True)
    bars.set_title('Monthly recorded activity, normalized for month length',
                   loc='left', fontsize=11, pad=13, color='#263445')
    for x, rate in zip(positions, data['monthly_rates']):
        bars.text(x, rate + max(data['monthly_rates'], default=0) * .04,
                  f'{rate:,.0f}', ha='center', va='bottom', fontsize=11, color='#172c42')
    fig.text(.09, .075, 'Trailing mean uses the current day and prior six days; '
             'the first six dates have no full window.', fontsize=9.5, color='#526273')
    fig.text(.09, .046, 'Recorded taxi source trips describe this snapshot. '
             'The smoothing line is descriptive; it is not a forecast or confidence interval.',
             fontsize=9.5, color='#526273')
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / 'daily_activity_2025q1.png', dpi=180,
                metadata={'Software': 'Cityflow portfolio plot'})
    fig.savefig(output / 'daily_activity_2025q1.svg', metadata={'Date': None})
    plt.close(fig)
    return matplotlib.__version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--daily', type=Path, default=ROOT / 'docs/results/daily_activity_2025q1.csv')
    parser.add_argument('--monthly', type=Path, default=ROOT / 'docs/results/monthly_activity_2025q1.csv')
    parser.add_argument('--metadata', type=Path, default=ROOT / 'docs/results/run_metadata_2025q1.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/portfolio')
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit('Output directory is not empty; choose a fresh --output-dir')
    data = load_inputs(args.daily, args.monthly, args.metadata)
    version = render(data, args.output_dir)
    metadata = {
        'dataset': data['label'], 'observed_records': data['observed_records'],
        'calendar_days': 90, 'window_days': 7, 'window_alignment': 'trailing full window',
        'monthly_rates': data['monthly_rates'], 'python_version': platform.python_version(),
        'matplotlib_version': version,
        'source_versions': data['source_metadata'].get('sources', []),
        'input_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                         for name, path in [('daily_csv', args.daily), ('monthly_csv', args.monthly),
                                            ('export_metadata', args.metadata)]},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.output_dir / 'figure_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('Dataset:', data['label'])
    print('Validated:', data['observed_records'], 'records across 90 days')
    print('Monthly trips/day:', [round(value, 2) for value in data['monthly_rates']])
    print('PNG, SVG and figure metadata:', args.output_dir)


if __name__ == '__main__':
    main()
