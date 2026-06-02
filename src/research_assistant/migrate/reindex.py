"""Re-emit AgentDB payloads from on-disk truth sources.

The replacement for the abandoned "AgentDB JSONL merge" idea. Instead of
trying to dump + merge two ``ruvector.db`` SQLite files (fragile because
agentic-flow owns that schema), this walks the markdown / YAML files that
are the *source of truth* and re-builds the indexing payloads from them.

Truth sources covered, namespace → on-disk artifact:

* ``project/past-work/<slug>``                 ← ``inputs/past-work/<slug>.md``
* ``project/experiments/<slug>``               ← ``outputs/experiments/<slug>/manifest.md``
* ``project/experiments/<slug>/versions``      ← ``outputs/experiments/<slug>/versions/<vN.M>.md``
* ``ideas/<slug>``                             ← ``outputs/idea-checks/<slug>/idea.md``
* ``project/boss/profile``                     ← ``inputs/boss-profile/profile.md``
* ``project/boss/meetings``                    ← ``inputs/boss-profile/meetings/<date>.md``
* ``project/research-notes/<slug>``            ← ``outputs/research-notes/<slug>/state.yaml``

Not covered (intentionally):

* ``papers/<slug>``  — re-summarizing PDFs is what ``/summarize`` is for; the
  same flow indexes ``papers/`` as a side effect. Faster than reverse-
  engineering the summary text from disk.
* ``ideas/<slug>/{socratic,brainstorm,scout,contrarian,evaluation,venues,knowledge}``
  — skill-driven sub-records produced inside ``/idea-check`` stages.
  Re-running the relevant stage rebuilds them.
* ``project/figure-refs/<slug>``  — rebuild via ``/figure ref sync``.

The yielded dicts match the shape ``mcp__claude-flow__memory_store`` takes
as ``**kwargs`` — ``{"namespace": str, "key": str, "value": str, "metadata": dict}``.
The CLI emits them as JSONL; the skill prompt reads the JSONL and feeds
each line into ``memory_store(**payload)``.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def _past_work_payloads() -> Iterator[dict]:
    from research_assistant.mentor.past_work import (
        list_entries, parse_entry, to_agentdb_payload,
    )
    for path in list_entries():
        try:
            entry = parse_entry(path)
            metadata = to_agentdb_payload(entry)
        except Exception:
            continue
        # Composed search text: title + venue/year/status header, then bullets.
        bits: list[str] = [f"Past-work {entry.slug}: {entry.title}"]
        if entry.year or entry.venue or entry.status:
            bits.append(
                f"Year {entry.year or '?'}, venue {entry.venue or '?'}, "
                f"status {entry.status or '?'}"
            )
        if entry.tags:
            bits.append(f"Tags: {', '.join(entry.tags)}")
        if entry.what_i_learned:
            bits.append("Learned: " + "; ".join(entry.what_i_learned))
        yield {
            "namespace": "project/past-work",
            "key": entry.slug,
            "value": "\n".join(bits),
            "metadata": metadata,
        }


def _experiment_payloads() -> Iterator[dict]:
    from research_assistant.experiments import (
        list_experiments, parse_experiment, to_agentdb_payload,
    )
    for manifest_path in list_experiments():
        try:
            exp = parse_experiment(manifest_path)
            metadata = to_agentdb_payload(exp)
        except Exception:
            continue
        bits = [f"Experiment {exp.slug}: {exp.title}"]
        if exp.tags:
            bits.append(f"Tags: {', '.join(exp.tags)}")
        if exp.papers:
            bits.append(f"Papers: {', '.join(exp.papers)}")
        if exp.status:
            bits.append(f"Status: {exp.status}")
        yield {
            "namespace": "project/experiments",
            "key": exp.slug,
            "value": "\n".join(bits),
            "metadata": metadata,
        }


def _experiment_version_payloads() -> Iterator[dict]:
    # Already returns full {namespace, key, value, metadata} dicts.
    from research_assistant.experiments import iter_version_indexing_payloads
    yield from iter_version_indexing_payloads()


def _idea_payloads() -> Iterator[dict]:
    from research_assistant.ideas.registry import list_ideas, to_agentdb_payload
    for manifest in list_ideas():
        try:
            metadata = to_agentdb_payload(manifest)
        except Exception:
            continue
        bits = [f"Idea {manifest.slug}: {manifest.statement}"]
        if manifest.area_tags:
            bits.append(f"Tags: {', '.join(manifest.area_tags)}")
        if manifest.status:
            bits.append(f"Status: {manifest.status}")
        if manifest.venue:
            bits.append(f"Venue: {manifest.venue}")
        if manifest.verdict:
            bits.append(f"Verdict: {manifest.verdict}")
        yield {
            "namespace": "ideas",
            "key": manifest.slug,
            "value": "\n".join(bits),
            "metadata": metadata,
        }


def _boss_payloads() -> Iterator[dict]:
    from research_assistant.common.io import BOSS_PROFILE_DIR
    from research_assistant.mentor.boss_profile import (
        list_meetings, parse_meeting, parse_profile, to_agentdb_payload,
    )
    profile_path = Path(BOSS_PROFILE_DIR) / "profile.md"
    if profile_path.is_file():
        try:
            profile = parse_profile(profile_path)
            metadata = to_agentdb_payload(profile)
            bits = [f"Boss: {profile.name}"]
            if profile.role:
                bits.append(f"Role: {profile.role}")
            if profile.research_interests:
                bits.append(f"Interests: {', '.join(profile.research_interests)}")
            if profile.hot_buttons:
                bits.append(f"Hot buttons: {', '.join(profile.hot_buttons)}")
            if profile.communication_style:
                bits.append(f"Style: {profile.communication_style}")
            yield {
                "namespace": "project/boss",
                "key": "profile",
                "value": "\n".join(bits),
                "metadata": metadata,
            }
        except Exception:
            pass
    for mpath in list_meetings():
        try:
            meeting = parse_meeting(mpath)
            metadata = to_agentdb_payload(meeting)
        except Exception:
            continue
        bits = [f"Meeting {meeting.date.isoformat()}: {meeting.topic}"]
        if meeting.mode:
            bits.append(f"Mode: {meeting.mode}")
        if meeting.feedback:
            bits.append(f"Feedback: {meeting.feedback}")
        if meeting.action_items:
            bits.append("Action items: " + "; ".join(meeting.action_items))
        yield {
            "namespace": "project/boss/meetings",
            "key": meeting.date.isoformat(),
            "value": "\n".join(bits),
            "metadata": metadata,
        }


def _research_notes_payloads() -> Iterator[dict]:
    from research_assistant.mentor.research_notes import (
        list_projects, read_state, to_agentdb_payload,
    )
    for slug in list_projects():
        try:
            state = read_state(slug)
            metadata = to_agentdb_payload(state)
        except Exception:
            continue
        bits = [f"Research-notes {state.slug}: {state.title}"]
        if state.research_question:
            bits.append(f"Question: {state.research_question}")
        yield {
            "namespace": "project/research-notes",
            "key": state.slug,
            "value": "\n".join(bits),
            "metadata": metadata,
        }


# Order matters: smaller namespaces first so a summary count is easier to scan.
# Each emitter swallows its own per-file errors, so a corrupt entry in one
# namespace can't poison reindex for the rest.
_EMITTERS: list[tuple[str, callable]] = [
    ("project/past-work", _past_work_payloads),
    ("project/boss", _boss_payloads),
    ("project/experiments", _experiment_payloads),
    ("project/experiments/<slug>/versions", _experiment_version_payloads),
    ("ideas", _idea_payloads),
    ("project/research-notes", _research_notes_payloads),
]


def iter_reindex_payloads(namespace_filter: str | None = None) -> Iterator[dict]:
    """Yield every reindexable payload across all truth sources.

    ``namespace_filter`` is a prefix match against each yielded dict's
    ``namespace``. Pass e.g. ``"project/experiments"`` to scope a reindex to
    just experiments (catches both the per-experiment and per-version
    namespaces). Pass ``"project/boss"`` to scope to profile + meetings.
    """
    for _label, emitter in _EMITTERS:
        for payload in emitter():
            if namespace_filter and not payload["namespace"].startswith(namespace_filter):
                continue
            yield payload


def cmd_reindex(args) -> int:
    """CLI handler for ``python -m research_assistant.migrate reindex``.

    Emits JSONL (default) or a per-namespace count summary (``--summary``).
    Doesn't talk to AgentDB itself — the calling skill prompt pipes each
    line into ``memory_store(**payload)``. Keeps the agentic-flow MCP
    coupling at the skill layer.
    """
    import json
    if args.summary:
        counts = count_by_namespace(args.namespace)
        total = sum(counts.values())
        if not counts:
            print("(no reindexable payloads found)")
            return 0
        print("namespace                                count")
        print("---------------------------------------- -----")
        for ns in sorted(counts):
            print(f"{ns:<40} {counts[ns]:>5}")
        print("---------------------------------------- -----")
        print(f"{'total':<40} {total:>5}")
        return 0
    for payload in iter_reindex_payloads(args.namespace):
        print(json.dumps(payload, ensure_ascii=False, default=str))
    return 0


def count_by_namespace(namespace_filter: str | None = None) -> dict[str, int]:
    """Group ``iter_reindex_payloads`` output by namespace and return counts.

    Used by the ``--summary`` CLI mode so the user sees "how many entries
    would land in each bucket" before deciding whether to actually pipe the
    JSONL into a memory_store loop.
    """
    counts: dict[str, int] = {}
    for payload in iter_reindex_payloads(namespace_filter):
        counts[payload["namespace"]] = counts.get(payload["namespace"], 0) + 1
    return counts
