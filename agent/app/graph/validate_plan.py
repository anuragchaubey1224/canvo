"""Plan validator — the deterministic half of diagram quality.

Anything a plain function can check, we never pay an LLM to check. This module runs
between the Planner and the Drawer and does two jobs:

  `sanitize`  silently repairs structural slips (dangling edges, self-loops, duplicate
              ids, group references pointing nowhere). These are always safe to fix in
              code — the alternative is a broken canvas.

  `validate`  finds *content* problems code can detect but not fix: a decision node with
              only one branch, an isolated node, spec components that never made it into
              the plan. Those become a single, targeted repair prompt — the planner is
              told exactly what is missing instead of being asked to "try again".

Only `error`-severity issues trigger the repair call, and only once per run, so the cost
ceiling stays at one extra request in the cases that actually need it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.graph.planner_llm import DiagramPlan
from app.graph.spec_llm import DiagramSpec

# A plan that maps well under these bars is considered faithful to its spec.
_COVERAGE_MIN = 0.6  # edges vs the spec's FLOW steps
_MISSING_COMPONENTS_OK = 1  # one dropped component is a judgement call, two is a miss


@dataclass(frozen=True)
class PlanIssue:
    kind: str
    severity: str  # "error" → worth an LLM repair; "warning" → report only
    message: str


@dataclass
class PlanReport:
    issues: list[PlanIssue] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)  # deterministic repairs already applied

    @property
    def blocking(self) -> list[PlanIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def is_clean(self) -> bool:
        return not self.issues


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def sanitize(plan: DiagramPlan) -> list[str]:
    """Repair structural slips in place. Returns a human-readable list of what changed."""
    fixes: list[str] = []

    seen: set[str] = set()
    unique_nodes = []
    for node in plan.nodes:
        if node.id in seen:
            fixes.append(f"dropped duplicate node '{node.id}'")
            continue
        seen.add(node.id)
        unique_nodes.append(node)
    plan.nodes = unique_nodes

    known = {n.id for n in plan.nodes}
    kept_edges = []
    edge_keys: set[tuple[str, str]] = set()
    for edge in plan.edges:
        if edge.source not in known or edge.target not in known:
            fixes.append(f"dropped edge to unknown node ({edge.source}→{edge.target})")
            continue
        if edge.source == edge.target:
            fixes.append(f"dropped self-loop on '{edge.source}'")
            continue
        key = (edge.source, edge.target)
        if key in edge_keys:
            fixes.append(f"dropped duplicate edge ({edge.source}→{edge.target})")
            continue
        edge_keys.add(key)
        kept_edges.append(edge)
    plan.edges = kept_edges

    group_ids = {g.id for g in plan.groups}
    for node in plan.nodes:
        if node.group and node.group not in group_ids:
            fixes.append(f"cleared unknown group '{node.group}' on node '{node.id}'")
            node.group = None

    used_groups = {n.group for n in plan.nodes if n.group}
    if empty := [g for g in plan.groups if g.id not in used_groups]:
        fixes += [f"dropped empty group '{g.id}'" for g in empty]
        plan.groups = [g for g in plan.groups if g.id in used_groups]

    return fixes


def validate(plan: DiagramPlan, spec: DiagramSpec | None = None) -> PlanReport:
    """Content checks. Assumes `sanitize` already ran, so every edge resolves."""
    report = PlanReport()
    out_edges: dict[str, list[str | None]] = {n.id: [] for n in plan.nodes}
    in_count: dict[str, int] = dict.fromkeys(out_edges, 0)
    for edge in plan.edges:
        out_edges[edge.source].append(edge.label)
        in_count[edge.target] += 1

    if not plan.nodes:
        report.issues.append(PlanIssue("empty_plan", "error", "the plan has no nodes"))
        return report

    # A group with no internal edges is a legitimate *reference* panel, not a mistake —
    # the reference diagram's "Token Anatomy" lane is three cards (header / payload /
    # signature) with no arrows at all. Only nodes stranded inside a group that IS a flow
    # count as dropped connections; otherwise a repair pass would invent fake arrows.
    group_of = {n.id: n.group for n in plan.nodes}
    flowing_groups = {
        group_of[e.source]
        for e in plan.edges
        if group_of.get(e.source) and group_of[e.source] == group_of.get(e.target)
    }

    for node in plan.nodes:
        stranded = not out_edges[node.id] and not in_count[node.id]
        if stranded and (node.group is None or node.group in flowing_groups):
            report.issues.append(
                PlanIssue("isolated_node", "error", f"'{node.label}' has no connections")
            )
        if node.kind == "decision":
            branches = out_edges[node.id]
            if len(branches) < 2:
                report.issues.append(
                    PlanIssue(
                        "single_branch",
                        "error",
                        f"decision '{node.label}' has {len(branches)} outgoing branch(es); "
                        "a decision needs at least two",
                    )
                )
            elif not any(b for b in branches):
                report.issues.append(
                    PlanIssue(
                        "unlabeled_branches",
                        "warning",
                        f"branches out of '{node.label}' are unlabeled",
                    )
                )

    if spec:
        labels = {_norm(n.label) for n in plan.nodes} | {_norm(n.id) for n in plan.nodes}
        missing = [
            c
            for c in spec.component_names
            if (key := _norm(c)) and not any(key in lab or lab in key for lab in labels if lab)
        ]
        if len(missing) > _MISSING_COMPONENTS_OK:
            report.issues.append(
                PlanIssue(
                    "missing_components",
                    "error",
                    "spec components absent from the plan: " + ", ".join(missing[:6]),
                )
            )
        elif missing:
            report.issues.append(
                PlanIssue("missing_components", "warning", f"spec component dropped: {missing[0]}")
            )

        if spec.flow_steps and len(plan.edges) < _COVERAGE_MIN * len(spec.flow_steps):
            report.issues.append(
                PlanIssue(
                    "thin_coverage",
                    "error",
                    f"the spec has {len(spec.flow_steps)} flow steps but the plan has only "
                    f"{len(plan.edges)} edges — steps were dropped",
                )
            )

        if len(spec.phases) >= 2 and not plan.groups:
            report.issues.append(
                PlanIssue(
                    "no_groups", "warning", f"the spec defines {len(spec.phases)} phases, none used"
                )
            )

    # A→B alongside B→A reads as a call/response log rather than a flow, and the two
    # arrows compete for the same corridor. Reported, never dropped: the return arrow is
    # sometimes the point of the diagram, and that call belongs to the user.
    pairs = {(e.source, e.target) for e in plan.edges}
    reciprocal = {tuple(sorted(p)) for p in pairs if (p[1], p[0]) in pairs}
    if reciprocal:
        report.issues.append(
            PlanIssue(
                "reciprocal_edges",
                "warning",
                f"{len(reciprocal)} node pair(s) point at each other in both directions",
            )
        )

    # A one-node phase reads as an unfinished thought — usually the outcome nodes that
    # belonged with it ended up somewhere else, or nowhere.
    members: dict[str, int] = dict.fromkeys((g.id for g in plan.groups), 0)
    for node in plan.nodes:
        if node.group in members:
            members[node.group] += 1
    if thin := [g.label for g in plan.groups if members[g.id] < 2]:
        report.issues.append(
            PlanIssue("thin_phase", "warning", f"phase(s) with a single node: {', '.join(thin)}")
        )

    ungrouped = [n for n in plan.nodes if plan.groups and not n.group]
    if len(ungrouped) > 2:
        report.issues.append(
            PlanIssue(
                "ungrouped_nodes",
                "warning",
                f"{len(ungrouped)} nodes sit outside every group",
            )
        )

    return report


def repair_brief(issues: list[PlanIssue]) -> str:
    """The issue list as instructions for the planner's one repair pass."""
    return "\n".join(f"- {i.message}" for i in issues)
