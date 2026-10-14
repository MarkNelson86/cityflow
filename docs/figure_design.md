# Recorded activity plot

`scripts/plot_portfolio.py` creates a two-panel Q1 2025 activity figure from the
committed daily/monthly CSVs and export metadata under `docs/results/`.

The upper panel shows the count of in-window source trip records on each actual
pickup date. It overlays a full trailing seven-day arithmetic mean: the current
day and previous six days. The first six dates have no full window and no smoothed
value. The largest daily count is annotated; ties use the earliest date.

The lower panel shows monthly recorded trips divided by all calendar days in
the month: 31, 28 and 31. A month-length normalization is needed to compare rates
between February and the longer months. Neither panel uses only active days as
its denominator. The count axis begins at zero.

The rolling line summarizes the observed series. It is not a forecast, a fitted
trend, a confidence interval or a significance test. This figure describes one
recorded yellow-taxi snapshot and does not estimate all NYC travel or unmet demand.

The script requires all 90 dates exactly once, complete coverage, integer
nonnegative daily counts, monthly/daily reconciliation, valid calendar-day rates
and a matching export total. It does not independently re-read raw trip data:
the analytical models and their dbt tests establish upstream correctness. The
plot's known-answer tests validate the additional transformation and input rules.

Outputs are a PNG for GitHub presentation, an SVG for scaling/editing and
`figure_metadata.json` recording input SHA-256 hashes, original source versions,
the script hash, plotting/Python versions and smoothing definition. The guide
also records the installed plot environment. Reproduction means the same data
and transformation; file bytes or glyph rendering can differ across platforms.

Matplotlib is installed through the optional `requirements-viz.txt`. Core tests
import only the standard-library validation functions; image rendering is lazy
and does not add a required plotting dependency to the warehouse CI job.

If the dataset label contains "synthetic", the image is explicitly titled as a
synthetic preview. Synthetic images are for development and must not replace the
real results figure on the project README.

Regenerate using the defaults after installing the optional plot dependencies:

```bash
python -m pip install -r requirements-viz.txt
python scripts/plot_portfolio.py --output-dir reports/portfolio/new_render
```

Verify the dataset label, observed total, monthly rates and appearance before
copying new outputs into `docs/figures/`. Existing nonempty output directories
are protected; use a new directory for another render.
