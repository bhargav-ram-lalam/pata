"""
tests/conftest.py
=================
Shared pytest fixtures and session-level setup.

Key fixture: reset_pipeline_singletons
---------------------------------------
The pipeline module keeps Agent singletons at module level (initialised once
on first call to resolve_address). This is correct for production (avoids
repeated IndicBERT model loads), but causes test cross-contamination:

  - If any test/import initialises the singletons with llm_provider="anthropic"
    (the default), subsequent tests that pass llm_provider="mock" are silently
    ignored because _agent4 is already set.

The fixture resets _agent1–_agent5 to None before *every* test that uses it,
forcing fresh initialisation on the next resolve_address() call.

Note: IndicBERT (Agent 2) is the expensive model to reload. We accept that
cost here because correctness of the test isolation matters more than speed,
and each test already calls get_ner_agent() which caches the model separately.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_pipeline_singletons():
    """
    Reset module-level pipeline agent singletons before every test.

    This ensures llm_provider="mock" (or any other override) passed to
    resolve_address() is always respected, regardless of initialisation
    order across the test session.
    """
    import pipeline as _pipeline_mod

    # Reset all five singleton slots
    _pipeline_mod._agent1 = None
    _pipeline_mod._agent2 = None
    _pipeline_mod._agent3 = None
    _pipeline_mod._agent4 = None
    _pipeline_mod._agent5 = None

    yield  # run the test

    # Post-test cleanup (belt-and-suspenders for parallel test scenarios)
    _pipeline_mod._agent1 = None
    _pipeline_mod._agent2 = None
    _pipeline_mod._agent3 = None
    _pipeline_mod._agent4 = None
    _pipeline_mod._agent5 = None
