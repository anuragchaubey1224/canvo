"""Spec Writer — turns a vague request into a precise diagram specification.

Why this stage exists (the "spec → diagram" promise): a single text→graph call has to
do two unrelated jobs at once — understand the *domain* and emit a *well-formed graph* —
and the domain half always loses. The model answers the schema, not the question, so a
one-line prompt yields a thin, generic diagram. Splitting the work gives the planner an
unambiguous, already-complete brief and reduces its job to faithful mapping.

The spec is compact markdown, not a structured-output call: cheaper for the same content,
and it is the artifact we show the user. Anything the model adds beyond the user's own
words lands in ASSUMPTIONS, so invented detail is *visible and correctable* instead of
silently baked into the picture — that's how we keep "zero hallucination" honest:

  stated facts        must survive into the diagram
  canonical knowledge allowed, but declared in ASSUMPTIONS
  speculation         forbidden (generic "Database", never "PostgreSQL 15")
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.graph.planner_llm import DiagramPlan, PlanEdge, PlanGroup, PlanNode
from app.llm import build_chat_model, resolve_config

logger = logging.getLogger(__name__)

_SYSTEM = """You are a senior solutions architect. Turn the user's request into a precise \
diagram specification that a diagrammer will follow literally. You do not draw.

Steps:
1. Pick the diagram type: workflow | architecture | sequence | data-model | state | other.
2. List every component the user STATED.
3. Complete the picture with standard, widely-accepted knowledge for this domain, \
including failure and alternate paths. A flow with only the happy path is incomplete.
4. Attach concrete detail where it is standard (HTTP method + path, status code, token \
type, protocol) as short annotations — never prose.

Grounding (strict):
- Never invent product names, versions, vendors, numbers, or tech choices the user did \
not state. Use generic labels: "Database", not "PostgreSQL".
- Every addition beyond the user's words goes in ASSUMPTIONS, one line each.
- If the request is ambiguous, take the most likely reading and say so in ASSUMPTIONS.

This becomes a picture, not a call log:
- Each component appears exactly ONCE, in the one phase where it plays its main role. \
A step may point back at an earlier component; that is a returning arrow, not a new box.
- FLOW is forward progression. Write a return step ONLY when it carries something the \
reader must see — tokens issued, an error returned, a decision outcome. Routine \
acknowledgements ("database returns the record") are not steps.
- Every decision needs its OUTCOMES as components, not just the check: a diagram that \
asks "expired?" and never shows the new token it produces has lost the plot of the story.
- Every phase holds at least 2 components. A phase with one is not a phase — fold it in.
- Keep every line under 12 words.

Scale: 10-16 components, 12-20 flow steps, 3-5 phases. Fewer only if the request is \
genuinely small.

Output EXACTLY these sections, nothing before or after:

TITLE: <5 words max>
TYPE: <diagram type>
COMPONENTS:
- <Name> (<client|service|datastore|decision|external|queue|start|end>) - <short detail or ->
FLOW:
1. <Source> -> <Target>: <what moves, or the branch condition>
PHASES:
1. <Phase name>: <component names>
ASSUMPTIONS:
- <one line each>"""

# Section headers, tolerant of the markdown some models wrap them in ("## FLOW:", "**TITLE:**").
_HEAD = re.compile(
    r"^\s*[#*]*\s*(TITLE|TYPE|COMPONENTS|FLOW|PHASES|ASSUMPTIONS)\s*\**\s*[:：]\s*\**\s*(.*?)\s*\**$",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")
# "Auth Service (service) - POST /auth/login" → name / kind / detail
_COMPONENT = re.compile(r"^(?P<name>.*?)(?:\s*\((?P<kind>[^)]*)\))?(?:\s+[-–—]\s+(?P<detail>.*))?$")
_KINDS = {"client", "service", "datastore", "decision", "external", "queue", "start", "end", "note"}


class SpecComponent(BaseModel):
    name: str
    kind: str | None = None
    detail: str | None = None


class DiagramSpec(BaseModel):
    """The parsed brief. `raw` is what the planner reads; the rest drives the UI, the
    validator's coverage checks, and the deterministic fallback in `spec_to_plan`."""

    raw: str
    title: str | None = None
    diagram_type: str | None = None
    components: list[SpecComponent] = Field(default_factory=list)
    flow_steps: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @property
    def component_names(self) -> list[str]:
        return [c.name for c in self.components]


def _text_of(response: Any) -> str:
    """LangChain message content is a str for OpenAI-shaped models, a block list for Anthropic."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block if isinstance(block, str) else str(block.get("text", ""))
            for block in content
            if isinstance(block, str | dict)
        ]
        return "\n".join(p for p in parts if p)
    return str(content)


def _component(line: str) -> SpecComponent | None:
    """'Auth Service (service) - POST /auth/login' → name / kind / detail."""
    match = _COMPONENT.match(line.strip())
    if not match:
        return None
    name = (match.group("name") or "").strip()
    if not name:
        return None
    kind = (match.group("kind") or "").strip().lower() or None
    detail = (match.group("detail") or "").strip() or None
    return SpecComponent(
        name=name,
        kind=kind if kind in _KINDS else None,
        detail=None if detail in ("-", "—", "–") else detail,
    )


def parse_spec(raw: str) -> DiagramSpec:
    """Split the markdown spec into its sections. Tolerant: unknown lines are ignored,
    missing sections just come back empty — the raw text is always kept intact."""
    spec = DiagramSpec(raw=raw.strip())
    section: str | None = None
    buckets: dict[str, list[str]] = {"components": [], "flow": [], "phases": [], "assumptions": []}

    for line in raw.splitlines():
        head = _HEAD.match(line)
        if head:
            section = head.group(1).lower()
            inline = head.group(2).strip()
            if section == "title":
                spec.title = inline or None
            elif section == "type":
                spec.diagram_type = inline.lower() or None
            elif inline:  # some models put the first item on the header line
                buckets[section].append(inline)
            continue
        if section in buckets:
            item = _BULLET.match(line)
            if item:
                buckets[section].append(item.group(1))

    spec.components = [c for line in buckets["components"] if (c := _component(line))]
    spec.flow_steps = buckets["flow"]
    spec.phases = buckets["phases"]
    spec.assumptions = buckets["assumptions"]
    return spec


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", name).strip("-").lower() or "n"


def spec_to_plan(spec: DiagramSpec) -> DiagramPlan | None:
    """Build a diagram from the spec alone — no LLM.

    The spec already names every component, every flow step and every phase; the planner's
    job is to render that as a typed graph, and that is mechanical enough to do in code.
    So when the planner call fails, we do NOT have to fall back to the two-box stub — we
    can draw the brief we already paid for. Returns None only if the spec has no usable
    `A -> B` steps, in which case there is genuinely no flow to draw.
    """
    if not spec.components:
        return None

    nodes: list[PlanNode] = []
    node_id: dict[str, str] = {}
    for component in spec.components:
        nid = _slug(component.name)
        if nid in node_id.values():
            continue
        node_id[_key(component.name)] = nid
        nodes.append(
            PlanNode(id=nid, label=component.name, kind=component.kind, subtitle=component.detail)
        )

    def resolve(name: str) -> str | None:
        key = _key(name)
        if key in node_id:
            return node_id[key]
        # the FLOW section often abbreviates ("Gateway" for "API Gateway")
        matches = [nid for k, nid in node_id.items() if key and (key in k or k in key)]
        return matches[0] if len(matches) == 1 else None

    groups: list[PlanGroup] = []
    group_of: dict[str, str] = {}
    for i, line in enumerate(spec.phases, 1):
        label, _, members = line.partition(":")
        gid = f"phase-{i}"
        # The bullet parser strips the list marker, so "1. Login" arrives as "Login" —
        # put the number back, panels read as numbered stages.
        title = label.strip() or f"Phase {i}"
        groups.append(PlanGroup(id=gid, label=title if title[0].isdigit() else f"{i}. {title}"))
        for member in members.split(","):
            member_id = resolve(member.strip())
            if member_id and member_id not in group_of:
                group_of[member_id] = gid
    for node in nodes:
        node.group = group_of.get(node.id)
    groups = [g for g in groups if g.id in set(group_of.values())]

    edges: list[PlanEdge] = []
    seen: set[tuple[str, str]] = set()
    for step in spec.flow_steps:
        source, arrow, rest = step.partition("->")
        if not arrow:
            continue
        target, _, label = rest.partition(":")
        src, dst = resolve(source.strip()), resolve(target.strip())
        if not src or not dst or src == dst or (src, dst) in seen:
            continue
        seen.add((src, dst))
        words = label.strip().split()
        edges.append(PlanEdge(source=src, target=dst, label=" ".join(words[:2]) or None))

    if not edges:
        return None
    return DiagramPlan(title=spec.title, nodes=nodes, edges=edges, groups=groups)


async def write_spec(message: str, llm_override: dict | None = None) -> DiagramSpec | None:
    """Freeform request → DiagramSpec. Returns None with no key, on error, or when the
    model answered in a shape we can't parse — the planner then reads the raw text as before."""
    cfg = resolve_config(llm_override, role="spec")
    if not cfg.api_key or not message.strip():
        return None

    model = build_chat_model(cfg)
    try:
        response = await model.ainvoke([("system", _SYSTEM), ("human", message.strip())])
    except Exception:
        # Logged, not silent: a swallowed failure here shows up much later as a thin
        # diagram, and the cause is invisible unless it was recorded at the point of use.
        logger.warning("spec stage failed (model=%s)", cfg.model, exc_info=True)
        return None

    spec = parse_spec(_text_of(response))
    if not spec.phases or not spec.assumptions:
        # Both sections come last in the output format, so losing them means the response
        # was cut short — almost always `max_tokens` being spent on reasoning tokens.
        logger.warning(
            "spec looks truncated (model=%s, phases=%d, assumptions=%d) — check max_tokens",
            cfg.model,
            len(spec.phases),
            len(spec.assumptions),
        )
    # A spec with no components tells the planner nothing — fall back to the direct path.
    return spec if spec.components else None
