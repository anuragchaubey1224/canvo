"""The suite must never be able to make a billed request.

This is a regression test for a real incident: adding `test_auth.py` made the suite import
`app.main`, whose module-level `load_dotenv()` put the developer's OpenRouter key into the
environment. Tests that were asserting on the deterministic stub quietly started calling a
live model instead — passing, failing, and spending money for reasons nobody could see.
"""

from __future__ import annotations

import os


def test_no_provider_key_reaches_the_suite():
    import app.main  # noqa: F401 — the import that used to leak the key

    assert not os.getenv("OPENROUTER_API_KEY")
    assert not os.getenv("ANTHROPIC_API_KEY")


def test_the_llm_layer_resolves_to_no_credentials():
    from app.llm import resolve_config

    for role in (None, "spec", "plan", "vision"):
        assert resolve_config(role=role).api_key is None, "a test could make a billed call"
