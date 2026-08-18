"""Apply edit operations to a plan — deterministically, in code.

The model proposes changes; this decides what actually happens. Anything it can't do
safely is refused and reported rather than approximated, because a silently-misapplied
edit is worse than a refused one: the user sees a diagram that looks plausible and is
wrong, with nothing to tell them which.

Two invariants:

  - **Never mutate the caller's plan.** Work on a copy, so a half-applied batch can be
    thrown away and the diagram on screen survives.
  - **Every op either applies or is reported.** `rejected` is shown in the run trace, so
    "5 changes" never quietly means three.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.graph.edit_llm import EditOp
from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode


@dataclass
class EditResult:
    plan: DiagramPlan
    applied: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.applied)


def _find_node(plan: DiagramPlan, node_id: str | None) -> PlanNode | None:
    return next((n for n in plan.nodes if n.id == node_id), None) if node_id else None


def _find_group(plan: DiagramPlan, group_id: str | None) -> PlanGroup | None:
    return next((g for g in plan.groups if g.id == group_id), None) if group_id else None


def _find_edge(plan: DiagramPlan, source: str | None, target: str | None) -> PlanEdge | None:
    if not source or not target:
        return None
    return next((e for e in plan.edges if e.source == source and e.target == target), None)


def apply_ops(plan: DiagramPlan, ops: list[EditOp]) -> EditResult:
    """Return a new plan with `ops` applied, plus what happened to each one."""
    draft = plan.model_copy(deep=True)
    result = EditResult(plan=draft)

    for op in ops:
        handler = _HANDLERS.get(op.op)
        if handler is None:
            result.rejected.append(f"unknown operation '{op.op}'")
            continue
        handler(draft, op, result)

    return result


# --- handlers ---------------------------------------------------------------------------


def _add_node(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    if not op.id or not op.label:
        out.rejected.append("add_node needs an id and a label")
        return
    if _find_node(plan, op.id):
        out.rejected.append(f"'{op.id}' already exists")
        return
    if op.group and not _find_group(plan, op.group):
        # Better a node with no group than a reference to a phase that doesn't exist —
        # the layout would strand it either way, but this way it isn't a dangling id.
        out.rejected.append(f"group '{op.group}' doesn't exist; added '{op.label}' ungrouped")
        op.group = None
    plan.nodes.append(
        PlanNode(
            id=op.id,
            label=op.label,
            kind=op.kind,
            subtitle=op.subtitle,
            group=op.group,
            icon=op.icon,
        )
    )
    out.applied.append(f"added '{op.label}'")


def _update_node(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    node = _find_node(plan, op.id)
    if node is None:
        out.rejected.append(f"no node '{op.id}' to update")
        return
    changes: list[str] = []
    if op.label and op.label != node.label:
        changes.append(f"label → {op.label}")
        node.label = op.label
    if op.kind and op.kind != node.kind:
        changes.append(f"kind → {op.kind}")
        node.kind = op.kind
    if op.subtitle is not None and op.subtitle != node.subtitle:
        changes.append("subtitle")
        node.subtitle = op.subtitle or None
    if op.icon:
        node.icon = op.icon
        changes.append("icon")
    if op.group:
        if _find_group(plan, op.group) is None:
            out.rejected.append(f"group '{op.group}' doesn't exist")
        elif op.group != node.group:
            changes.append(f"group → {op.group}")
            node.group = op.group
    if changes:
        out.applied.append(f"{node.label}: {', '.join(changes)}")


def _remove_node(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    node = _find_node(plan, op.id)
    if node is None:
        out.rejected.append(f"no node '{op.id}' to remove")
        return
    plan.nodes = [n for n in plan.nodes if n.id != op.id]
    # Edges to a node that no longer exists would be dropped by the validator anyway;
    # doing it here means the count we report is the truth.
    orphaned = [e for e in plan.edges if op.id in (e.source, e.target)]
    plan.edges = [e for e in plan.edges if op.id not in (e.source, e.target)]
    tail = f" and {len(orphaned)} connection(s)" if orphaned else ""
    out.applied.append(f"removed '{node.label}'{tail}")


def _add_edge(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    if not _find_node(plan, op.source) or not _find_node(plan, op.target):
        out.rejected.append(f"can't connect '{op.source}' → '{op.target}': unknown node")
        return
    if op.source == op.target:
        out.rejected.append(f"'{op.source}' can't connect to itself")
        return
    if _find_edge(plan, op.source, op.target):
        out.rejected.append(f"'{op.source}' → '{op.target}' already exists")
        return
    plan.edges.append(PlanEdge(source=op.source or "", target=op.target or "", label=op.label))
    out.applied.append(f"connected {op.source} → {op.target}")


def _update_edge(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    edge = _find_edge(plan, op.source, op.target)
    if edge is None:
        out.rejected.append(f"no connection '{op.source}' → '{op.target}'")
        return
    edge.label = op.label or None
    out.applied.append(f"relabelled {op.source} → {op.target}")


def _remove_edge(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    if _find_edge(plan, op.source, op.target) is None:
        out.rejected.append(f"no connection '{op.source}' → '{op.target}' to remove")
        return
    plan.edges = [e for e in plan.edges if not (e.source == op.source and e.target == op.target)]
    out.applied.append(f"disconnected {op.source} → {op.target}")


def _add_group(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    if not op.id or not op.label:
        out.rejected.append("add_group needs an id and a label")
        return
    if _find_group(plan, op.id):
        out.rejected.append(f"group '{op.id}' already exists")
        return
    plan.groups.append(PlanGroup(id=op.id, label=op.label, color=op.color))
    out.applied.append(f"added phase '{op.label}'")


def _update_group(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    group = _find_group(plan, op.id)
    if group is None:
        out.rejected.append(f"no phase '{op.id}' to update")
        return
    if op.label:
        group.label = op.label
    if op.color:
        group.color = op.color
    out.applied.append(f"updated phase '{group.label}'")


def _remove_group(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    group = _find_group(plan, op.id)
    if group is None:
        out.rejected.append(f"no phase '{op.id}' to remove")
        return
    plan.groups = [g for g in plan.groups if g.id != op.id]
    # Its members stay — dissolving a phase shouldn't delete the work inside it.
    freed = 0
    for node in plan.nodes:
        if node.group == op.id:
            node.group = None
            freed += 1
    out.applied.append(f"removed phase '{group.label}' ({freed} node(s) kept)")


def _set_title(plan: DiagramPlan, op: EditOp, out: EditResult) -> None:
    title = (op.title or op.label or "").strip()
    if not title:
        out.rejected.append("set_title needs a title")
        return
    plan.title = title
    out.applied.append(f"title → {title}")


_HANDLERS = {
    "add_node": _add_node,
    "update_node": _update_node,
    "remove_node": _remove_node,
    "add_edge": _add_edge,
    "update_edge": _update_edge,
    "remove_edge": _remove_edge,
    "add_group": _add_group,
    "update_group": _update_group,
    "remove_group": _remove_group,
    "set_title": _set_title,
}
