"""Slug + filesystem-path helpers + semver for the experiments package.

Pure path math — no I/O beyond `exists() / is_dir() / glob()`. All path helpers
guard against directory traversal via `_guard_under`. ``EXPERIMENTS_DIR`` is
read via the parent package at call time so test monkeypatches on
``research_assistant.experiments.EXPERIMENTS_DIR`` keep working after the
1285-line ``__init__.py`` was split.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

import research_assistant.experiments as _exp  # late attribute access; see module docstring

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_SEMVER_RE = re.compile(r"^v(\d+)\.(\d+)$")
_DESIGN_SEMVER_RE = re.compile(r"^d(\d+)\.(\d+)$")
_FEASIBILITY_RE = re.compile(r"^feasibility-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$")


# ---------- slug helpers ----------

def slugify_experiment(title: str) -> str:
    """Build a kebab-case slug from a free-form title. Raise on empty."""
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty experiment slug for title={title!r}")
    return cleaned


def next_available_slug(base: str) -> str:
    """Collision-safe variant. ``base`` -> ``base``, ``base-2``, ``base-3`` ...

    Mirrors :func:`research_assistant.mentor.boss_profile.rehearsal_path`.
    """
    if not base:
        raise ValueError("empty base slug")
    if not (_exp.EXPERIMENTS_DIR / base).exists():
        return base
    n = 2
    while (_exp.EXPERIMENTS_DIR / f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"


def _guard_under(root: Path, candidate: Path, what: str) -> Path:
    """Raise ``ValueError`` if ``candidate`` resolves outside ``root``."""
    rr = root.resolve()
    cc = candidate.resolve()
    if rr != cc and rr not in cc.parents:
        raise ValueError(f"{what} escapes {root.name}: {candidate}")
    return cc


# ---------- path helpers ----------

def experiment_path(slug: str) -> Path:
    """Resolve ``outputs/experiments/<slug>/``. Path-traversal guarded."""
    if not slug:
        raise ValueError("empty experiment slug")
    return _guard_under(_exp.EXPERIMENTS_DIR, _exp.EXPERIMENTS_DIR / slug, "experiment slug")


def manifest_path(slug: str) -> Path:
    return experiment_path(slug) / "manifest.md"


def legacy_design_path(slug: str) -> Path:
    """Pre-refactor singleton ``design.md`` location.

    Kept as a defensive fallback for :func:`stage_status` — the canonical
    path now lives at :func:`latest_design_path` (under ``designs/d<N.M>.md``).
    """
    return experiment_path(slug) / "design.md"


def references_path(slug: str) -> Path:
    return experiment_path(slug) / "references.md"


def status_path(slug: str) -> Path:
    return experiment_path(slug) / "status.md"


def data_index_path(slug: str) -> Path:
    return experiment_path(slug) / "data" / "index.md"


def repo_clone_path(slug: str) -> Path:
    return experiment_path(slug) / "repo"


def version_path(slug: str, version: str) -> Path:
    """Resolve ``versions/<vN.M>.md`` under an experiment. Both args validated."""
    parse_semver(version)
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "versions" / f"{version}.md", "version slug")


def result_path(slug: str, version: str) -> Path:
    """Resolve ``results/<vN.M>/`` under an experiment. Both args validated."""
    parse_semver(version)
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "results" / version, "version slug")


def resolve_result_in_repo(slug: str, repo_rel_path: str) -> Path:
    """Resolve a repo-relative result path to an absolute Path under the clone.

    Raises ``ValueError`` on empty/traversal. Used by ``register_version`` to
    locate the source file before mirroring.
    """
    if not repo_rel_path:
        raise ValueError("empty result path")
    repo = repo_clone_path(slug)
    return _guard_under(repo, repo / repo_rel_path, "result path")


def design_version_path(slug: str, version: str) -> Path:
    """Resolve ``designs/<dN.M>.md`` under an experiment. Both args validated.

    The design plan is versioned in parallel with run versions (``versions/v<N.M>``);
    ``/experiment feasibility apply`` writes a new design version after the user
    adopts suggestions from a feasibility report.
    """
    parse_semver(version, prefix="d")
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "designs" / f"{version}.md", "design version")


def latest_design_path(slug: str) -> Path | None:
    """Return the path of the highest-semver design file, or ``None`` if absent."""
    v = latest_design(slug)
    return design_version_path(slug, v) if v else None


def fleet_input_path() -> Path:
    """``inputs/fleet.md`` — user-maintained machine-inventory manifest.

    Read by ``/experiment feasibility`` and merged with hosts auto-derived from
    ``versions/*.md`` frontmatter. When the user volunteers fleet info during a
    feasibility check, the skill body writes it here immediately so the next
    check doesn't re-ask.
    """
    return _exp.FLEET_INPUT_PATH


def feasibility_path(slug: str, d: date | None = None) -> Path:
    """Collision-safe path to a feasibility report.

    Mirrors :func:`research_assistant.mentor.boss_profile.rehearsal_path`: same
    date produces ``feasibility-<date>.md``, ``feasibility-<date>-2.md``,
    ``feasibility-<date>-3.md``, ...
    """
    if d is None:
        d = date.today()
    exp_dir = experiment_path(slug)
    base = f"feasibility-{d.isoformat()}"
    candidate = exp_dir / f"{base}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        nth = exp_dir / f"{base}-{n}.md"
        if not nth.exists():
            return nth
        n += 1


def _parse_feasibility_filename(name: str) -> tuple[date, int] | None:
    """Parse ``feasibility-<YYYY-MM-DD>[-<n>].md`` into ``(date, suffix)``.

    Returns ``None`` if the name doesn't match. Lexical sort on
    ``feasibility-<date>.md`` filenames is unreliable (``"."`` > ``"-"`` in
    ASCII puts the unsuffixed file AFTER the ``-2`` suffix in lex order),
    so :func:`latest_feasibility` sorts on this tuple instead.
    """
    m = _FEASIBILITY_RE.match(name)
    if not m:
        return None
    try:
        d = date.fromisoformat(m.group(1))
    except ValueError:
        return None
    suffix = int(m.group(2)) if m.group(2) else 1
    return (d, suffix)


def latest_feasibility(slug: str) -> Path | None:
    """Return the newest feasibility report for ``slug`` (date + suffix order)."""
    exp_dir = experiment_path(slug)
    if not exp_dir.is_dir():
        return None
    parsed: list[tuple[tuple[date, int], Path]] = []
    for p in exp_dir.glob("feasibility-*.md"):
        info = _parse_feasibility_filename(p.name)
        if info:
            parsed.append((info, p))
    if not parsed:
        return None
    parsed.sort()
    return parsed[-1][1]


# ---------- semver ----------

def _semver_regex(prefix: str) -> re.Pattern[str]:
    if prefix == "v":
        return _SEMVER_RE
    if prefix == "d":
        return _DESIGN_SEMVER_RE
    raise ValueError(f"unsupported semver prefix: {prefix!r}")


def parse_semver(s: str, prefix: str = "v") -> tuple[int, int]:
    """``'v1.2'`` -> ``(1, 2)``. Raise on malformed.

    ``prefix`` controls the expected version prefix; pass ``"d"`` for the
    parallel design-plan semver (``d1.0``, ``d1.1`` ...).
    """
    m = _semver_regex(prefix).match(s) if isinstance(s, str) else None
    if not m:
        raise ValueError(f"malformed semver: {s!r}")
    return int(m.group(1)), int(m.group(2))


def format_semver(major: int, minor: int, prefix: str = "v") -> str:
    return f"{prefix}{major}.{minor}"


def bump_major(v: str, prefix: str = "v") -> str:
    major, _ = parse_semver(v, prefix=prefix)
    return format_semver(major + 1, 0, prefix=prefix)


def bump_minor(v: str, prefix: str = "v") -> str:
    major, minor = parse_semver(v, prefix=prefix)
    return format_semver(major, minor + 1, prefix=prefix)


def _list_semver_files(dir_path: Path, prefix: str) -> list[str]:
    """Read ``*.md`` files under ``dir_path``, filter to well-formed semver
    stems for ``prefix``, return sorted numerically by (major, minor).
    """
    if not dir_path.is_dir():
        return []
    out: list[str] = []
    for p in dir_path.glob("*.md"):
        try:
            parse_semver(p.stem, prefix=prefix)
        except ValueError:
            continue
        out.append(p.stem)
    out.sort(key=lambda s: parse_semver(s, prefix=prefix))
    return out


def list_versions(slug: str) -> list[str]:
    """Read ``versions/*.md``, return semver-sorted slugs (numeric, not lexical)."""
    return _list_semver_files(experiment_path(slug) / "versions", "v")


def list_designs(slug: str) -> list[str]:
    """Read ``designs/*.md``, return semver-sorted slugs (numeric).

    Mirror of :func:`list_versions` for design-plan semver (``d1.0`` ...).
    """
    return _list_semver_files(experiment_path(slug) / "designs", "d")


def latest_version(slug: str) -> str | None:
    vs = list_versions(slug)
    return vs[-1] if vs else None


def latest_design(slug: str) -> str | None:
    ds = list_designs(slug)
    return ds[-1] if ds else None


def _next_in_series(vs: list[str], kind: str, prefix: str) -> str:
    """Suggest the next semver from a sorted list. Empty -> ``<prefix>1.0``."""
    if kind not in ("major", "minor"):
        raise ValueError(f"unknown bump kind: {kind!r}")
    if not vs:
        return format_semver(1, 0, prefix=prefix)
    if kind == "major":
        return bump_major(vs[-1], prefix=prefix)
    highest_major = parse_semver(vs[-1], prefix=prefix)[0]
    candidates = [v for v in vs if parse_semver(v, prefix=prefix)[0] == highest_major]
    return bump_minor(candidates[-1], prefix=prefix)


def next_version(slug: str, kind: Literal["major", "minor"]) -> str:
    """Suggest the next run-semver. ``'major'`` bumps the highest major; ``'minor'``
    bumps the highest minor under the current highest major. Empty -> ``v1.0``.

    Suggestion only — callers are free to register a non-monotonic explicit
    version (e.g. skip from ``v1.3`` to ``v3.0``).
    """
    return _next_in_series(list_versions(slug), kind, "v")


def next_design_version(slug: str, kind: Literal["major", "minor"]) -> str:
    """Suggest the next design-plan semver. Mirror of :func:`next_version`."""
    return _next_in_series(list_designs(slug), kind, "d")
