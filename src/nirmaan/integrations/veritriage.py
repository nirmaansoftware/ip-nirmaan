"""The VeriTriage bridge: the ONLY module in Nirmaan that imports VeriTriage.

VeriTriage is IP Nirmaan's verification-intelligence subsystem. The
organization reaches it here and nowhere else (a test enforces the law), and
only through its stable public surfaces: ``WorkspaceServices`` and the
Knowledge Pack registry. VeriTriage itself never imports Nirmaan.

What crosses the bridge is real: ``veritriage.investigate`` runs the full
deterministic pipeline and returns a session ID that a VERITRIAGE_SESSION
evidence record cites, which is how an organizational claim ("the regression
failure was triaged") becomes traceable into an Evidence Graph.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from nirmaan.runtime.tools import ToolOutcome, register_binding
from nirmaan.work.engine import TaskEngine


def _services(params: dict[str, str]):
    from veritriage.workspace import WorkspaceServices

    root = params.get("workspace")
    return WorkspaceServices(session_root=Path(root) / "sessions" if root else None)


@register_binding("veritriage.investigate")
def investigate(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    paths = [Path(p) for p in params.get("paths", "").split(",") if p.strip()]
    if not paths:
        return ToolOutcome(False, "no artifact paths given")
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        return ToolOutcome(False, f"artifacts not found: {', '.join(missing)}")
    services = _services(params)
    session = services.investigate(paths, record_history=False, automate=False, learn=False)
    services.save(session)
    summary = services.summary(session)
    top = f"; top hypothesis: {summary.top_hypothesis}" if summary.top_hypothesis else ""
    return ToolOutcome(
        True,
        f"VeriTriage classified {', '.join(p.name for p in paths)} as {summary.classification} "
        f"({summary.confidence}% confidence, {summary.evidence_nodes} evidence nodes){top}",
        references=(session.session_id,),
        data=summary.model_dump(mode="json"),
    )


@register_binding("veritriage.explain_log")
def explain_log(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    path = Path(params.get("path", ""))
    if not path.is_file():
        return ToolOutcome(False, f"no such log: {path}")
    annotations = _services(params).explain_log(path)
    return ToolOutcome(True, f"{len(annotations)} annotated regions in {path.name}",
                       data={"annotations": [a.model_dump(mode="json") for a in annotations]})


@register_binding("knowledge.search")
def search(params: dict[str, str], engine: TaskEngine) -> ToolOutcome:
    hits = _services(params).search_knowledge(params.get("query", ""))
    return ToolOutcome(True, f"{len(hits)} knowledge hits",
                       references=tuple(f"{h.pack}:{h.id}" for h in hits[:20]),
                       data={"hits": [h.model_dump(mode="json") for h in hits[:20]]})


def engine_version() -> str:
    """The installed VeriTriage engine's version."""
    import veritriage

    return veritriage.__version__


@lru_cache(maxsize=1)
def pack_catalog() -> dict[str, dict[str, str]]:
    """Registered VeriTriage Knowledge Packs: id -> name, domain, summary."""
    from veritriage.knowledge.registry import load_packs

    return {p.id: {"name": p.name, "domain": p.domain, "summary": p.summary} for p in load_packs()}


def missing_packs(org) -> list[str]:
    """Skill knowledge sources that cite a pack VeriTriage does not ship."""
    catalog = pack_catalog()
    return sorted(
        f"{skill.id} -> {src.ref}"
        for skill in org.skills.values()
        for src in skill.knowledge_sources
        if src.kind.value == "veritriage_pack" and src.ref not in catalog
    )
