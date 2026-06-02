"""``migrate artifacts {list,register,scan}`` — sub-commands for the artifact registry.

Extracted from :mod:`research_assistant.migrate.cli` to keep the parent CLI
file under 500 lines. ``_add_artifacts_subcommands`` is the entry point;
each ``cmd_artifacts_*`` is a self-contained handler driven by argparse.

Shared interactive helpers (``_prompt``, ``_prompt_artifact_record``,
``_synthesize_fetch_cmd``, ``_fmt_size``) still live in :mod:`.cli` since
``cmd_export`` uses them too — we import them from there rather than
duplicate.
"""
from __future__ import annotations

import argparse
import sys

from research_assistant.migrate.manifest import (
    ArtifactRecord,
    external_artifacts_path,
    read_external_artifacts,
    write_external_artifacts,
)
from research_assistant.migrate.scan import (
    DEFAULT_UNREGISTERED_THRESHOLD,
    UnregisteredItem,
)


def _add_artifacts_subcommands(sub: argparse._SubParsersAction) -> None:
    """Wire up ``migrate artifacts {list,register,scan}`` (used by /experiment artifacts)."""
    p = sub.add_parser(
        "artifacts",
        help="Manage external-artifacts.md for a given experiment.",
    )
    p.add_argument("--slug", required=True, help="Experiment slug.")
    asub = p.add_subparsers(dest="acmd", required=True)

    a_list = asub.add_parser("list", help="Print this experiment's external-artifacts.md.")
    a_list.set_defaults(func=cmd_artifacts_list)

    a_reg = asub.add_parser(
        "register",
        help="Append one record to external-artifacts.md (non-interactive).",
    )
    a_reg.add_argument("--name", required=True, help="Short artifact name.")
    a_reg.add_argument("--path", required=True, help="Experiment-relative dir.")
    a_reg.add_argument("--glob", default="*", help="Glob under --path (default '*').")
    a_reg.add_argument(
        "--source", default="other",
        choices=["huggingface", "http", "git-lfs", "s3", "other"],
        help="Source type (default 'other').",
    )
    a_reg.add_argument("--repo", default=None, help="Source repo / URL.")
    a_reg.add_argument("--revision", default=None, help="Source revision / SHA / branch.")
    a_reg.add_argument("--size", default=None, help="Size estimate (free-form).")
    a_reg.add_argument("--fetch-cmd", default=None, help="Custom fetch command.")
    a_reg.set_defaults(func=cmd_artifacts_register)

    a_scan = asub.add_parser(
        "scan",
        help="Walk the experiment dir for >=threshold files lacking an entry; "
             "prompt the user to register each.",
    )
    a_scan.add_argument(
        "--threshold", type=int, default=DEFAULT_UNREGISTERED_THRESHOLD,
        metavar="BYTES",
        help=f"Bytes; default {DEFAULT_UNREGISTERED_THRESHOLD / 1024**3:.0f} GiB "
             f"({DEFAULT_UNREGISTERED_THRESHOLD} bytes).",
    )
    a_scan.set_defaults(func=cmd_artifacts_scan)


def cmd_artifacts_list(args: argparse.Namespace) -> int:
    ea_path = external_artifacts_path(args.slug)
    ea = read_external_artifacts(ea_path)
    if not ea.artifacts:
        print(f"(no external artifacts registered for {args.slug})")
        return 0
    print(f"External artifacts for {args.slug}:")
    print()
    for r in ea.artifacts:
        print(f"- {r.name}")
        print(f"    path:      {r.path}")
        print(f"    glob:      {r.glob}")
        print(f"    type:      {r.type}")
        if r.repo:
            print(f"    repo:      {r.repo}")
        if r.revision:
            print(f"    revision:  {r.revision}")
        if r.size_estimate:
            print(f"    size:      {r.size_estimate}")
        if r.fetch_cmd:
            print("    fetch_cmd:")
            for line in r.fetch_cmd.strip().splitlines():
                print(f"      {line}")
    return 0


def cmd_artifacts_register(args: argparse.Namespace) -> int:
    # Lazy import — cli.py owns `_synthesize_fetch_cmd` and may import this
    # module from inside its own `_build_parser` (function-scope), so this
    # module's load must not depend on cli.py being fully imported.
    from research_assistant.migrate.cli import _synthesize_fetch_cmd

    ea_path = external_artifacts_path(args.slug)
    ea = read_external_artifacts(ea_path)
    record = ArtifactRecord(
        name=args.name,
        path=args.path,
        glob=args.glob,
        type=args.source,  # type: ignore[arg-type]
        repo=args.repo,
        revision=args.revision,
        size_estimate=args.size,
        fetch_cmd=args.fetch_cmd or _synthesize_fetch_cmd(
            args.source, args.repo, args.revision, args.path,
        ),
    )
    ea.artifacts.append(record)
    write_external_artifacts(ea_path, ea)
    print(f"Registered {record.name} under {args.slug} → {ea_path}")
    return 0


def cmd_artifacts_scan(args: argparse.Namespace) -> int:
    """Walk only this experiment's dir; reuse the export prompt loop."""
    from research_assistant.common.io import EXPERIMENTS_DIR
    from research_assistant.migrate.cli import (
        _fmt_size,
        _prompt,
        _prompt_artifact_record,
    )
    from research_assistant.migrate.scan import _match_artifact

    exp_dir = EXPERIMENTS_DIR / args.slug
    if not exp_dir.is_dir():
        print(f"ERROR: no such experiment: {args.slug}", file=sys.stderr)
        return 2
    ea_path = external_artifacts_path(args.slug)
    ea = read_external_artifacts(ea_path)
    records = list(ea.artifacts)

    unregistered: list[UnregisteredItem] = []
    for fpath in exp_dir.rglob("*"):
        if not fpath.is_file():
            continue
        try:
            size = fpath.stat().st_size
        except OSError:
            continue
        if size < args.threshold:
            continue
        in_exp = fpath.relative_to(exp_dir).as_posix()
        if _match_artifact(in_exp, records):
            continue
        unregistered.append(UnregisteredItem(
            abs_path=fpath, rel_path=str(fpath), size=size,
            experiment_slug=args.slug, in_experiment_rel=in_exp,
        ))

    if not unregistered:
        print(f"No unregistered files ≥{args.threshold} bytes in {args.slug}.")
        return 0

    print(f"Found {len(unregistered)} unregistered file(s) in {args.slug}:")
    for i, u in enumerate(unregistered, start=1):
        print(f"\n[{i}/{len(unregistered)}] {u.in_experiment_rel}  ({_fmt_size(u.size)})")
        choice = _prompt(
            "(1) register as externally fetchable\n"
            "        (2) leave as-is (include in future exports)\n"
            "        (3) skip\n"
            "        choice [1/2/3]"
        )
        if choice == "1":
            record = _prompt_artifact_record(u)
            ea.artifacts.append(record)
            write_external_artifacts(ea_path, ea)
            records.append(record)
            print(f"        Registered {record.name}.")
    return 0
