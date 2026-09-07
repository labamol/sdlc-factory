"""Test-suite defaults.

The suite must stay hermetic: a developer machine with `OPENAI_API_KEY`
exported would otherwise send real requests from every lifecycle test. Tests
that exercise LLM behaviour construct their runtime explicitly.
"""

import pytest


@pytest.fixture(autouse=True)
def deterministic_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_LLM", "off")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
