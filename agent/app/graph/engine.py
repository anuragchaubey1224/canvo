"""Canvo's own tiny graph engine — our orchestration, no framework.

Replaces LangGraph for Canvo's needs: a few nodes wired into a directed graph with one
conditional edge (the Critic's refine loop). We hand-roll it so we own the whole
execution + streaming path and carry no orchestration dependency.

Contract (unchanged from before, minus the library):
  - A **node** is a plain function `state -> partial_update`. It may be sync or async.
    It receives the full accumulated state and returns a dict of keys to merge in
    (or nothing). The engine shallow-merges each update into the running state.
  - Edges are either **static** (`add_edge`) or **conditional** (`add_conditional`,
    a router function whose returned key selects the next node via a mapping).
  - `END` terminates the walk. `START`/`set_entry` marks where it begins.

`astream` yields each node's delta as it runs — that's what powers the observable
self-correction stream in the SSE endpoint. `ainvoke` just drains it and returns the
final state. A hard step cap guards against a mis-wired infinite loop.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

END = "__end__"
START = "__start__"

NodeFn = Callable[[Any], Any]  # (state) -> partial update dict | awaitable of that
RouterFn = Callable[[Any], str]  # (state) -> branch key

_MAX_STEPS = 64  # safety backstop; the real loop bound is MAX_ITERATIONS in the Critic


class Graph:
    """A directed graph of node functions with optional conditional branching."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str] = {}  # node -> next node (static)
        self._cond: dict[str, tuple[RouterFn, dict[str, str]]] = {}  # node -> (router, mapping)
        self._entry: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> None:
        self._nodes[name] = fn

    def set_entry(self, name: str) -> None:
        self._entry = name

    def add_edge(self, src: str, dst: str) -> None:
        self._edges[src] = dst

    def add_conditional(self, src: str, router: RouterFn, mapping: Mapping[str, str]) -> None:
        self._cond[src] = (router, dict(mapping))

    def _next(self, node: str, state: dict[str, Any]) -> str:
        """Resolve the node to run after `node` (conditional wins over static)."""
        if node in self._cond:
            router, mapping = self._cond[node]
            key = router(state)
            if key not in mapping:
                raise KeyError(f"router for '{node}' returned unmapped key '{key}'")
            return mapping[key]
        return self._edges.get(node, END)

    async def _run(self, name: str, state: dict[str, Any]) -> dict[str, Any]:
        """Invoke one node, awaiting it if it's async; normalise None → {}."""
        result = self._nodes[name](state)
        if inspect.isawaitable(result):
            result = await result
        return result or {}

    async def astream(self, state: dict[str, Any]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Walk the graph from the entry node, merging each update into `state`.

        Yields `(node_name, update)` after every node runs (the delta, not the full
        state) — mutates the provided `state` in place, so pass a fresh dict per run.
        """
        if self._entry is None:
            raise RuntimeError("no entry node set — call set_entry() first")

        node = self._entry
        steps = 0
        while node != END:
            if steps >= _MAX_STEPS:
                raise RuntimeError(f"graph exceeded {_MAX_STEPS} steps — possible infinite loop")
            steps += 1
            update = await self._run(node, state)
            state.update(update)
            yield node, update
            node = self._next(node, state)

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the graph to completion and return the final merged state."""
        async for _node, _update in self.astream(state):
            pass
        return state
