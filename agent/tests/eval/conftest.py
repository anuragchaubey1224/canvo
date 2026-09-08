"""Tier 2 knobs. See EVAL-PLAN.md §7 (phase 03).

Tier 2 replays recorded model responses by default — no network, safe for CI, runs in the
normal suite. `--record` is the one deliberate exception: it hits the live model, refreshes
`responses/`, and prints what the pass cost. It exists to be run by hand, once, with the
spend agreed first (EVAL-PLAN.md §8, ground rule 1).
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("canvo-eval")
    group.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Tier 2: call the live model and rewrite tests/eval/responses/. Spends money.",
    )
    group.addoption(
        "--record-only",
        action="store",
        default=None,
        metavar="IDS",
        help="With --record, restrict recording to this comma-separated list of case ids.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "tier2: recorded-response eval of the freeform LLM path (EVAL-PLAN.md §7)"
    )


@pytest.fixture(scope="session")
def record_mode(pytestconfig: pytest.Config) -> bool:
    return bool(pytestconfig.getoption("--record"))


@pytest.fixture(scope="session")
def record_only(pytestconfig: pytest.Config) -> set[str] | None:
    raw = pytestconfig.getoption("--record-only")
    if not raw:
        return None
    return {s.strip() for s in str(raw).split(",") if s.strip()}
