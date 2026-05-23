"""``python -m research_assistant.migrate`` — CLI entry for /migrate.

Two subcommands:

* ``export`` — scan repo, build archive, write to ``outputs/migrate/``.
  Surfaces unregistered >1GB files interactively unless ``--non-interactive``.
* ``import`` — open archive, apply merge policy, write a Markdown
  ``ImportReport``.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from research_assistant.common.io import OUTPUTS_DIR, REPO_ROOT
from research_assistant.migrate.archive import (
    ArchiveEntry,
    iter_entries,
    open_archive,
    read_manifest,
    write_archive,
)
from research_assistant.migrate.manifest import (
    ArtifactRecord,
    ImportReport,
    external_artifacts_path,
    read_external_artifacts,
    write_external_artifacts,
)
from research_assistant.migrate.merge import apply as merge_apply
from research_assistant.migrate.scan import (
    DEFAULT_UNREGISTERED_THRESHOLD,
    FileItem,
    RegisteredMatch,
    ScanResult,
    UnregisteredItem,
    scan_repo,
)

MIGRATE_DIR = OUTPUTS_DIR / "migrate"
IMPORTS_DIR = MIGRATE_DIR / "imports"


# ---------- export ----------

def cmd_export(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root or REPO_ROOT).resolve()
    out_dir = Path(args.out) if args.out else MIGRATE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    include_inputs = "inputs" in args.include if args.include else True
    include_outputs = "outputs" in args.include if args.include else True
    include_dbs = "dbs" in args.include if args.include else True
    include_claude_config = "claude_config" in args.include if args.include else True

    scope = []
    if include_inputs:
        scope.append("inputs")
    if include_outputs:
        scope.append("outputs")
    if include_dbs:
        scope.append("dbs")
    if include_claude_config:
        scope.append("claude_config")

    result = scan_repo(
        repo_root,
        unregistered_threshold=args.threshold,
        include_inputs=include_inputs,
        include_outputs=include_outputs,
        include_dbs=include_dbs,
        include_claude_config=include_claude_config,
    )

    if result.excluded_unregistered:
        if args.non_interactive:
            print(
                "ERROR: --non-interactive set but found {n} unregistered file(s) "
                "≥{thresh_gb:.1f}GB in experiments without entries in "
                "external-artifacts.md:".format(
                    n=len(result.excluded_unregistered),
                    thresh_gb=args.threshold / 1024**3,
                ),
                file=sys.stderr,
            )
            for u in result.excluded_unregistered:
                print(f"  - {u.rel_path}  ({_fmt_size(u.size)})", file=sys.stderr)
            print(
                "\nRun /experiment artifacts scan in each affected experiment "
                "to register them, then re-run /migrate export.",
                file=sys.stderr,
            )
            return 2
        result = _interactive_register(result, repo_root)

    _print_partition_summary(result)

    if args.dry_run:
        print("\n(dry-run; archive not written)")
        return 0

    archive_name = (
        f"migrate-{_safe_hostname()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    )
    archive_path = out_dir / archive_name

    all_items: list[FileItem] = list(result.must)

    print(f"\nWriting {archive_path} ...")
    outcome = write_archive(
        archive_path,
        all_items,
        scope=scope,
        excluded_artifacts=result.excluded_artifacts(),
        repo_root=repo_root,
        progress=None,
    )

    print(f"\nDone. {archive_path}")
    print(f"  files:      {len(outcome.manifest.files)}")
    print(f"  databases:  {len(outcome.manifest.dbs)}")
    print(f"  excluded:   {len(outcome.manifest.excluded_artifacts)} external artifact(s)")
    print(f"  size:       {_fmt_size(archive_path.stat().st_size)}")
    if outcome.manifest.excluded_artifacts:
        print("\nOn the destination machine, re-fetch these after /migrate import:")
        for a in outcome.manifest.excluded_artifacts:
            print(f"  - {a.experiment} / {a.name}  ({a.size_estimate or 'size unknown'})")
            if a.fetch_cmd:
                for line in a.fetch_cmd.strip().splitlines():
                    print(f"      {line}")
    return 0


# ---------- import ----------

def cmd_import(args: argparse.Namespace) -> int:
    archive_path = Path(args.archive).resolve()
    if not archive_path.is_file():
        print(f"ERROR: archive not found: {archive_path}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root or REPO_ROOT).resolve()

    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        entries: list[ArchiveEntry] = list(iter_entries(zf, manifest))
        verdicts = merge_apply(
            zf, entries, repo_root=repo_root, dry_run=args.dry_run,
        )

    report = ImportReport(
        archive=archive_path.name,
        imported_at=datetime.now().astimezone(),
        source=manifest.source,
        entries=verdicts,
        excluded_artifacts=manifest.excluded_artifacts,
    )

    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_name = f"{archive_path.stem}.report.md"
    report_path = IMPORTS_DIR / report_name
    if not args.dry_run:
        report_path.write_text(report.to_markdown(), encoding="utf-8")

    print()
    print(report.to_markdown())
    if not args.dry_run:
        print(f"\nReport written: {report_path}")
    else:
        print("\n(dry-run; report not written)")
    return 0


# ---------- interactive registration ----------

def _interactive_register(
    result: ScanResult, repo_root: Path
) -> ScanResult:
    """Walk every unregistered-but-large file; ask the user what to do.

    On `(1) externally fetchable`, prompt for source metadata, append to the
    experiment's ``external-artifacts.md``, and reclassify the file. On
    `(2) include`, leave as-is (moved to MUST). On `(3) skip`, drop the file.
    Re-classifies in place and returns the same :class:`ScanResult`.
    """
    n = len(result.excluded_unregistered)
    print(
        f"\nFound {n} file(s) ≥{DEFAULT_UNREGISTERED_THRESHOLD / 1024**3:.0f}GB "
        "in experiments without an external-artifacts.md entry."
    )
    keep: list[UnregisteredItem] = []
    for i, u in enumerate(result.excluded_unregistered, start=1):
        print()
        print(f"[{i}/{n}] {u.rel_path}")
        print(f"        experiment: {u.experiment_slug}")
        print(f"        size:       {_fmt_size(u.size)}")
        choice = _prompt(
            "(1) externally fetchable — register & exclude\n"
            "        (2) include in archive\n"
            "        (3) skip entirely\n"
            "        choice [1/2/3]"
        )
        if choice == "2":
            result.must.append(FileItem(u.abs_path, u.rel_path, u.size))
            continue
        if choice == "3":
            continue
        record = _prompt_artifact_record(u)
        # Append to external-artifacts.md.
        ea_path = external_artifacts_path(u.experiment_slug)
        ea = read_external_artifacts(ea_path)
        ea.artifacts.append(record)
        write_external_artifacts(ea_path, ea)
        result.artifacts_by_experiment.setdefault(u.experiment_slug, []).append(record)
        result.excluded_registered.append(
            RegisteredMatch(u.abs_path, u.rel_path, u.size, u.experiment_slug, record)
        )
        keep.append(u)  # noqa: F841 — accumulated for symmetry, not used downstream
    result.excluded_unregistered = []  # all resolved
    return result


def _prompt_artifact_record(u: UnregisteredItem) -> ArtifactRecord:
    """Ask the user just enough to build an :class:`ArtifactRecord`."""
    print("        Source type:")
    print("          1) huggingface")
    print("          2) http")
    print("          3) git-lfs")
    print("          4) s3")
    print("          5) other")
    choice = _prompt("        choice [1-5]")
    src = {
        "1": "huggingface", "2": "http", "3": "git-lfs", "4": "s3", "5": "other",
    }.get(choice, "other")
    name = _prompt("        Short name (e.g. llama2-7b-base)")
    # Default the artifact path to the directory containing this file inside
    # the experiment — the most common case is "all big shards in this dir".
    default_path = str(Path(u.in_experiment_rel).parent)
    if default_path == ".":
        default_path = u.in_experiment_rel
    path = _prompt(f"        Experiment-relative dir [default: {default_path}]") or default_path
    default_glob = "model-*.safetensors" if u.in_experiment_rel.endswith(".safetensors") else Path(u.in_experiment_rel).name
    glob = _prompt(f"        Glob for files to exclude [default: {default_glob}]") or default_glob
    repo = _prompt("        Source repo / URL (optional)") or None
    revision = _prompt("        Revision / branch / sha (optional)") or None
    size = _prompt(f"        Size estimate [default: {_fmt_size(u.size)}]") or _fmt_size(u.size)
    fetch_cmd = _synthesize_fetch_cmd(src, repo, revision, path)
    custom_cmd = _prompt(f"        Fetch command [default synthesized]:\n          {fetch_cmd}\n        override? (blank to keep)")
    if custom_cmd.strip():
        fetch_cmd = custom_cmd
    return ArtifactRecord(
        name=name or u.in_experiment_rel,
        path=path,
        glob=glob,
        type=src,  # type: ignore[arg-type]
        repo=repo,
        revision=revision,
        size_estimate=size,
        fetch_cmd=fetch_cmd,
    )


def _synthesize_fetch_cmd(
    src: str, repo: str | None, revision: str | None, dest_in_experiment: str
) -> str:
    if src == "huggingface" and repo:
        rev_arg = f" --revision {revision}" if revision else ""
        return (
            f"huggingface-cli download {repo}{rev_arg} "
            f"--local-dir <experiment>/{dest_in_experiment}"
        )
    if src == "http" and repo:
        return f"curl -L -o <experiment>/{dest_in_experiment} {repo}"
    if src == "git-lfs" and repo:
        return f"git lfs clone {repo} <experiment>/{dest_in_experiment}"
    return f"# TODO: re-fetch {dest_in_experiment}"


def _prompt(label: str) -> str:
    try:
        return input(f"        {label}: ").strip()
    except EOFError:
        return ""


# ---------- pretty-printing ----------

def _print_partition_summary(result: ScanResult) -> None:
    total_must = sum(it.size for it in result.must)
    total_excl_reg = sum(rm.size for rm in result.excluded_registered)
    total_unreg = sum(u.size for u in result.excluded_unregistered)
    print()
    print("Scan summary:")
    print(f"  must include:           {len(result.must)} files, {_fmt_size(total_must)}")
    print(
        f"  excluded (registered):  {len(result.excluded_registered)} files, "
        f"{_fmt_size(total_excl_reg)}"
    )
    if result.excluded_unregistered:
        print(
            f"  unregistered ≥threshold: {len(result.excluded_unregistered)} files, "
            f"{_fmt_size(total_unreg)}  ← will prompt"
        )
    print(f"  intentionally skipped:  {len(result.skipped)} files")


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def _safe_hostname() -> str:
    import socket
    name = socket.gethostname() or "host"
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name)


# ---------- argparse ----------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m research_assistant.migrate",
        description="Cross-machine state migration for lucky-research.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    _add_artifacts_subcommands(sub)

    p_exp = sub.add_parser("export", help="Bundle per-user state into a zip.")
    p_exp.add_argument("--out", help="Output dir (default outputs/migrate/).")
    p_exp.add_argument(
        "--include", action="append", choices=["inputs", "outputs", "dbs", "claude_config"],
        help="Restrict scope. Repeatable. Default = all four.",
    )
    p_exp.add_argument(
        "--threshold", type=int, default=DEFAULT_UNREGISTERED_THRESHOLD,
        help="Bytes; files ≥this in experiments need external-artifacts.md "
             f"entries. Default {DEFAULT_UNREGISTERED_THRESHOLD} (1 GiB).",
    )
    p_exp.add_argument("--dry-run", action="store_true", help="Scan + report only.")
    p_exp.add_argument(
        "--non-interactive", action="store_true",
        help="Fail (exit 2) if any unregistered ≥threshold files are found.",
    )
    p_exp.add_argument("--repo-root", help="Override repo root (testing).")
    p_exp.set_defaults(func=cmd_export)

    p_imp = sub.add_parser("import", help="Restore a migrate archive on this machine.")
    p_imp.add_argument("archive", help="Path to migrate-*.zip")
    p_imp.add_argument("--dry-run", action="store_true", help="Plan moves only.")
    p_imp.add_argument("--repo-root", help="Override repo root (testing).")
    p_imp.set_defaults(func=cmd_import)
    return p


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
        help=f"Bytes; default {DEFAULT_UNREGISTERED_THRESHOLD} (1 GiB).",
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
        # If a record already matches, skip.
        from research_assistant.migrate.scan import _match_artifact
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
