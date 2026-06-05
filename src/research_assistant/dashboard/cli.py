"""``python -m research_assistant.dashboard`` — build or serve the HTML overview.

Two modes:

* ``build`` (default) — render ``outputs/dashboard.html`` once and print a text
  summary. Bare ``python -m research_assistant.dashboard`` runs this.
* ``serve`` — run a localhost HTTP server that regenerates the page live on
  every request and auto-refreshes the browser on an interval.

Stays read-only over ``inputs/``/``outputs/`` except for the single HTML file
``build`` emits (``serve`` writes nothing to disk).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from research_assistant.common.io import OUTPUTS_DIR
from research_assistant.dashboard import build_dashboard, collect

_DEFAULT_OUT = OUTPUTS_DIR / "dashboard.html"
_DEFAULT_PORT = 8765
_DEFAULT_REFRESH = 30


def _cmd_build(args: argparse.Namespace) -> int:
    out = build_dashboard(args.out)
    data = collect()  # cheap re-walk for the text summary

    print(f"dashboard → {out.resolve()}")
    print(f"  papers: {len(data.papers)} · experiments: {len(data.experiments)} · ideas: {len(data.ideas)}")
    for p in data.papers:
        name = f"{p.venue}/{p.direction}" if p.direction else f"{p.venue} (no direction)"
        due = p.deadline_date.isoformat() if (p.deadline_date and p.deadline_text != "TBD") else "TBD"
        gaps = f" · {p.open_placeholders} gaps" if p.open_placeholders else ""
        print(f"    {name:<48} {p.percent:>3}%  due {due}{gaps}")
    for e in data.experiments:
        print(f"    exp {e.slug:<44} {e.percent:>3}%  {e.status} · {e.versions} versions")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    # Imported lazily so `build` never pays for the http.server import.
    from research_assistant.dashboard.server import serve

    return serve(port=args.port, refresh_seconds=args.refresh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research_assistant.dashboard",
        description="Build or serve an HTML dashboard of ideas + paper progress.",
    )
    sub = parser.add_subparsers(dest="cmd")

    pb = sub.add_parser("build", help="render the HTML file once (default)")
    pb.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help=f"output HTML path (default: {_DEFAULT_OUT})",
    )
    pb.set_defaults(func=_cmd_build)

    ps = sub.add_parser("serve", help="run a localhost live-refresh server")
    ps.add_argument(
        "--port", type=int, default=_DEFAULT_PORT,
        help=f"localhost port (default: {_DEFAULT_PORT})",
    )
    ps.add_argument(
        "--refresh", type=int, default=_DEFAULT_REFRESH,
        help=f"browser auto-refresh interval in seconds (default: {_DEFAULT_REFRESH})",
    )
    ps.set_defaults(func=_cmd_serve)

    # Default subcommand: bare invocation (or leading flag) means `build`.
    raw = list(argv) if argv is not None else None
    args_list = raw
    if args_list is None:
        import sys
        args_list = sys.argv[1:]
    if not args_list or args_list[0].startswith("-"):
        args_list = ["build", *args_list]

    args = parser.parse_args(args_list)
    return args.func(args)
