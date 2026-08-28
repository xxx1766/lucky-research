"""Status board for one idea — the five gates are the progress axis.

Gate progress is driven by the manifest's ``status`` field, which
``registry.update_idea`` advances when a gate clears; the full decision log
lives in ``gates.md`` (rendered by :mod:`research_assistant.ideas.gates`) and
is linked from the board rather than re-parsed here.

Service artifacts (``scout.md``, ``evaluate.md``, …) are listed separately:
they are evidence the gates *use*, never progress in themselves. That
separation is the whole point of the refactor — "跑了 scout" is not "问题想清
楚了".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from research_assistant.ideas.gates import (
    GATE_LABELS,
    GATE_ORDER,
    GATE_STATUS,
    GateKey,
)
from research_assistant.ideas.registry import (
    STATUS_ORDER,
    idea_dir,
    load_idea,
)

#: Optional services, in the order the board lists them:
#: (label, subcommand, artifact file).
_SERVICES: tuple[tuple[str, str, str], ...] = (
    ("socratic 捕获", "socratic", "socratic.md"),
    ("brainstorm 换角度", "brainstorm", "brainstorm.md"),
    ("scout 近三年文献", "scout", "scout.md"),
    ("contrarian 反其道", "contrarian", "contrarian.md"),
    ("assumptions 隐含假设", "assumptions", "assumptions.md"),
    ("evaluate 价值/可行性打分", "evaluate", "evaluate.md"),
    ("venues 目标会议", "venues", "venues.md"),
    ("knowledge 知识索引", "knowledge", "knowledge.md"),
    ("2paper 故事包装", "2paper", "story.md"),
)


@dataclass(frozen=True)
class StageStatus:
    """Gate flags + which optional services have produced an artifact."""

    gates_cleared: tuple[GateKey, ...]
    handed_off: bool
    forced_gates: tuple[str, ...] = ()
    services: dict[str, bool] = field(default_factory=dict)

    def cleared(self, gate: GateKey) -> bool:
        return gate in self.gates_cleared

    @property
    def open_gate(self) -> GateKey | None:
        for gate in GATE_ORDER:
            if gate not in self.gates_cleared:
                return gate
        return None


def stage_status(slug: str) -> StageStatus:
    d = idea_dir(slug)
    manifest_status: str | None = None
    forced: list[str] = []
    try:
        manifest = load_idea(slug)
        manifest_status = manifest.status
        forced = list(manifest.forced_gates)
    except (FileNotFoundError, ValueError, KeyError):
        # A malformed or missing manifest must not crash the board — the user
        # needs to see the damage in order to fix it.
        pass

    def _at_or_past(status: str) -> bool:
        if manifest_status is None:
            return False
        try:
            return STATUS_ORDER.index(manifest_status) >= STATUS_ORDER.index(status)  # type: ignore[arg-type]
        except ValueError:
            return False

    cleared = tuple(g for g in GATE_ORDER if _at_or_past(GATE_STATUS[g]))
    services = {sub: (d / fname).is_file() for _label, sub, fname in _SERVICES}
    return StageStatus(
        gates_cleared=cleared,
        handed_off=manifest_status == "handed-off",
        forced_gates=tuple(forced),
        services=services,
    )


def render_status_md(slug: str) -> str:
    """Render the gate board for ``outputs/idea-checks/<slug>/status.md``."""
    s = stage_status(slug)
    forced = s.forced_gates

    lines = [f"# Status — `{slug}`", "", "## Gates (进度轴)", ""]
    for i, gate in enumerate(GATE_ORDER, start=1):
        mark = "x" if s.cleared(gate) else " "
        suffix = " — **forced**" if gate in forced else ""
        lines.append(f"- [{mark}] {i}. {GATE_LABELS[gate]} (`{gate}`){suffix}")
    lines.append(f"- [{'x' if s.handed_off else ' '}] handed-off")
    lines.append("")

    lines.append("## Services (证据来源，不占进度)")
    lines.append("")
    for label, sub, _fname in _SERVICES:
        mark = "x" if s.services.get(sub) else " "
        lines.append(f"- [{mark}] {label} — `/idea-check {sub}`")
    lines.append("")

    if forced:
        lines.append(
            f"⚠️ {len(forced)} 个关卡是强制放行的 (`{'`, `'.join(forced)}`) —— "
            "实验失败时先回来看这里。"
        )
        lines.append("")

    nxt = s.open_gate
    if nxt is not None:
        lines.append(f"_Next: `/idea-check {nxt}` ({GATE_LABELS[nxt]})_")
    elif not s.handed_off:
        lines.append("_五关全部通过 —— Next: `/idea-check handoff`_")
    else:
        lines.append("_已交给 `/paper`。_")
    return "\n".join(lines) + "\n"
