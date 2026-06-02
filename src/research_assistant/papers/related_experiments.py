"""Find local experiments touching a given (venue, direction).

Consumed by ``/paper scout`` (Stage 3 of paper-architect) so the user sees not
just external literature but also their own experiments bound to this paper
direction. Two binding sources are merged:

* ``manifest.papers`` entries containing ``<venue>/<direction>`` (declarative).
* ``expert.md`` frontmatter ``experiment:`` slug (the bound primary, set by
  ``/paper bind``) — included even if its manifest omits the venue/direction
  string, since `/paper bind` doesn't auto-edit the experiment's manifest.

The helper returns small dicts (not full :class:`Experiment` objects) so the
skill prompt can render a one-row-per-experiment table without re-parsing.
"""
from __future__ import annotations

from pathlib import Path

from research_assistant.experiments import (
    latest_version,
    list_experiments,
    parse_experiment,
    result_path,
)
from research_assistant.papers.binding import read_binding_from_expert_md


def find_experiments_for_paper(venue: str, direction: str) -> list[dict]:
    """Return experiments bound to ``(venue, direction)``.

    Each dict has: ``slug``, ``title``, ``status``, ``papers`` (the manifest
    field, for context), ``latest_version`` (``vN.M`` or ``None``), and
    ``binding_source`` (``"manifest"``, ``"expert.md"``, or ``"both"``) so the
    skill can show *how* the link was established.

    Empty list when no experiments exist or none match. Malformed manifests
    are skipped — matches :func:`parse_data_index`'s tolerance for
    user-edited registries. ``list_experiments()`` already returns ``[]`` when
    the experiments dir is missing, so no eager existence check is needed
    here (and adding one would defeat monkeypatching of
    ``common.io.EXPERIMENTS_DIR`` in tests).
    """
    needle = f"{venue}/{direction}"
    bound_primary = read_binding_from_expert_md(venue, direction)

    hits: dict[str, dict] = {}
    for manifest in list_experiments():
        try:
            exp = parse_experiment(manifest)
        except Exception:
            continue
        manifest_match = needle in (exp.papers or [])
        primary_match = bound_primary == exp.slug
        if not (manifest_match or primary_match):
            continue
        if manifest_match and primary_match:
            source = "both"
        elif manifest_match:
            source = "manifest"
        else:
            source = "expert.md"
        try:
            latest = latest_version(exp.slug)
        except Exception:
            latest = None
        hits[exp.slug] = {
            "slug": exp.slug,
            "title": exp.title,
            "status": exp.status,
            "papers": list(exp.papers or []),
            "latest_version": latest,
            "binding_source": source,
        }
    return sorted(hits.values(), key=lambda h: h["slug"])


def collect_experiment_results_for_paper(venue: str, direction: str) -> list[dict]:
    """Return per-experiment latest-results pointers for ``/paper write results``.

    For each experiment bound to ``(venue, direction)`` (via
    :func:`find_experiments_for_paper`), looks up its latest
    ``versions/<vN.M>.md`` and resolves the matching
    ``outputs/experiments/<slug>/results/<vN.M>/`` directory. Returns:

    * ``slug``, ``title``, ``latest_version``, ``binding_source`` — context
      from the binding hit.
    * ``results_dir`` — :class:`Path` to ``results/<latest>/`` or ``None`` if
      the directory hasn't been mirrored yet.
    * ``analysis_tex`` — :class:`Path` to ``analysis.tex`` if present, else
      ``None``. This is the LaTeX paragraph block produced by
      ``/experiment analyze`` — designed to be pasted under
      ``\\section{Results}``.
    * ``analysis_md`` — :class:`Path` to ``analysis.md`` if present, else
      ``None``. The audit log for spot-checking.
    * ``other_files`` — sorted list of :class:`Path` for non-analysis files
      mirrored into the results dir (CSVs, JSONs, plots, …).

    Experiments without a ``latest_version`` are still returned (with
    ``results_dir=None``) so the caller can show "no results yet" for them
    rather than silently hide them.
    """
    out: list[dict] = []
    for hit in find_experiments_for_paper(venue, direction):
        slug = hit["slug"]
        latest = hit["latest_version"]
        results_dir: Path | None = None
        analysis_tex: Path | None = None
        analysis_md: Path | None = None
        other_files: list[Path] = []
        if latest:
            try:
                candidate = result_path(slug, latest)
            except Exception:
                candidate = None
            if candidate is not None and candidate.is_dir():
                results_dir = candidate
                for child in sorted(candidate.iterdir()):
                    if not child.is_file():
                        continue
                    if child.name == "analysis.tex":
                        analysis_tex = child
                    elif child.name == "analysis.md":
                        analysis_md = child
                    else:
                        other_files.append(child)
        out.append({
            "slug": slug,
            "title": hit["title"],
            "latest_version": latest,
            "binding_source": hit["binding_source"],
            "results_dir": results_dir,
            "analysis_tex": analysis_tex,
            "analysis_md": analysis_md,
            "other_files": other_files,
        })
    return out
