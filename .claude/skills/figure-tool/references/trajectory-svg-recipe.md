# Optimization-trajectory plot — self-contained SVG recipe

> **Source:** adapted from
> [Orchestra-Research/AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs)
> (MIT) `0-autoresearch-skill/references/progress-reporting.md` — the
> "Karpathy-style optimization trajectory" plot. Reproduced and adapted
> here with permission of the MIT license.

A research project's most compelling figure is often the simplest: a
metric improvement curve over experiment runs, with the baseline marked
as a reference line. This recipe is a single pure-Python function that
emits an SVG — no `matplotlib`, no `cairosvg`, no external dependency.
The figure-tool's regular `kind=data` path uses `matplotlib`; this
recipe is the no-dep fallback when:

* the user wants a quick HTML status email / Slack drop with the
  trajectory inline (SVG is the only universal embed),
* the experiment runs in an environment without `matplotlib`
  (lightweight CI / serverless),
* the user just wants to paste it into Notion / Confluence.

## When `/figure new <slug>` should reach for this

In Step 2 (kind), if the user says `data` and the intent contains
"trajectory" / "training curve" / "metric over runs" — and either
"send to chat" or "no matplotlib" — propose this recipe in Step 6
*instead of* the matplotlib path. Write `plot_<slug>.svg.py` instead of
`plot_<slug>.py`, and set `backend: trajectory-svg` in the note.

For all other "metric over time" plots, the matplotlib path is still
preferred (better palette integration, sits with the rest of the
`figures/_scripts/` directory).

## The recipe

```python
def trajectory_svg(
    trajectory: list[dict],
    *,
    width: int = 800,
    height: int = 400,
    title: str = "Optimization trajectory",
    metric_format: str = "{:.3f}",
) -> str:
    """Render an experiment trajectory as a self-contained SVG.

    Each item in ``trajectory`` is a dict with keys ``run`` (int label for
    the x-axis tick), ``metric`` (float — the y-value), and optionally
    ``label`` (annotation text rendered above the point).

    The first point's ``metric`` is treated as the baseline and shown as a
    dashed reference line across the plot.

    Returns the SVG as a string. The caller is responsible for writing it
    to a file or embedding it directly in HTML/Markdown.
    """
    if not trajectory:
        return "<svg><text x='10' y='20'>no experiments yet</text></svg>"

    metrics = [d["metric"] for d in trajectory]
    min_m, max_m = min(metrics), max(metrics)
    margin = (max_m - min_m) * 0.1 or 0.1
    y_min, y_max = min_m - margin, max_m + margin

    padding = 60
    plot_w = width - 2 * padding
    plot_h = height - 2 * padding
    n = len(trajectory)

    def x_pos(i: int) -> float:
        return padding + (i / max(n - 1, 1)) * plot_w

    def y_pos(v: float) -> float:
        return padding + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    parts = [
        f'<svg width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="serif">',
        f'<rect width="{width}" height="{height}" fill="#1a1a2e" rx="8"/>',
    ]

    # Grid lines + y-axis ticks.
    for i in range(5):
        y = padding + i * plot_h / 4
        val = y_max - i * (y_max - y_min) / 4
        parts.append(
            f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" '
            f'stroke="#333" stroke-dasharray="4"/>'
        )
        parts.append(
            f'<text x="{padding-8}" y="{y+4}" fill="#888" '
            f'text-anchor="end" font-size="11">{metric_format.format(val)}</text>'
        )

    # Baseline (first point) as a dashed reference line.
    baseline = trajectory[0]["metric"]
    by = y_pos(baseline)
    parts.append(
        f'<line x1="{padding}" y1="{by}" x2="{width-padding}" y2="{by}" '
        f'stroke="#ff6b6b" stroke-dasharray="6" opacity="0.7"/>'
    )
    parts.append(
        f'<text x="{width-padding+5}" y="{by+4}" fill="#ff6b6b" '
        f'font-size="10">baseline</text>'
    )

    # Data polyline.
    points = " ".join(f"{x_pos(i)},{y_pos(d['metric'])}" for i, d in enumerate(trajectory))
    parts.append(
        f'<polyline points="{points}" fill="none" stroke="#4ecdc4" stroke-width="2"/>'
    )

    # Data points + optional annotations.
    for i, d in enumerate(trajectory):
        cx, cy = x_pos(i), y_pos(d["metric"])
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#4ecdc4"/>')
        if d.get("label"):
            label = (
                d["label"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            parts.append(
                f'<text x="{cx}" y="{cy-10}" fill="#eee" text-anchor="middle" '
                f'font-size="10">{label}</text>'
            )

    # Title + x-axis label.
    parts.append(
        f'<text x="{width/2}" y="24" fill="#eee" text-anchor="middle" '
        f'font-size="14" font-weight="bold">{title}</text>'
    )
    parts.append(
        f'<text x="{width/2}" y="{height-10}" fill="#888" '
        f'text-anchor="middle" font-size="11">Experiment run</text>'
    )
    parts.append('</svg>')
    return "\n".join(parts)
```

## Suggested driver script

When `/figure new` writes `plot_<slug>.svg.py` for this recipe, the
driver should read trajectory data from a JSON file (so the user can
regenerate the figure without re-running the function inline), then
write the SVG next to it. The JSON shape matches the per-version
record under `outputs/experiments/<slug>/results/<vN.M>/`.

```python
import json
from pathlib import Path

# from research_assistant.figures.trajectory import trajectory_svg
# (paste the function above inline if the helper isn't on the path)

DATA = Path(__file__).parent / "trajectory.json"
OUT = Path(__file__).parent / "trajectory.svg"

points = json.loads(DATA.read_text(encoding="utf-8"))
OUT.write_text(trajectory_svg(points, title="Method X — val loss"), encoding="utf-8")
```

## Caption rules

Per `paper-architect/references/latex-conventions.md` "Caption format":

* Title Case noun phrase, no trailing period:
  `Optimization trajectory of Method X on validation loss`.
* Avoid `The figure shows ...` / `This diagram illustrates ...`.
* Quantify the headline result in the caption itself when there's room:
  `Optimization trajectory of Method X on validation loss (3.2x speedup
  over baseline at run 14)`.

## Limitations

The recipe is intentionally minimal:

* Dark theme only. For a light theme, replace `#1a1a2e` background
  + `#eee` text + `#888` ticks with light equivalents.
* No log-scale axis support. For multi-order-of-magnitude metrics,
  reach for the matplotlib path instead.
* No confidence bands / error bars. If the trajectory has multiple
  seeds, fall back to the matplotlib `带置信区域的折线图` from the
  19-chart library (see `chart-recommender-prompt.md`).
