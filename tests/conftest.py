"""Test-suite defaults.

The suite must stay hermetic: a developer machine with `OPENAI_API_KEY` or
`GITHUB_TOKEN` exported would otherwise send real requests — and real pushes —
from every lifecycle test. Tests that exercise LLM or forge behaviour construct
their runtime and forge explicitly.
"""

import pytest


@pytest.fixture(autouse=True)
def deterministic_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_LLM", "off")
    monkeypatch.setenv("FACTORY_FORGE", "off")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("FACTORY_TARGET_REPO", raising=False)
    monkeypatch.setenv("FACTORY_TRACKER", "off")
    monkeypatch.setenv("FACTORY_NOTIFY", "off")
    for name in ("JIRA_SITE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN",
                 "JIRA_PROJECT_KEY", "TEAMS_WEBHOOK_URL"):
        monkeypatch.delenv(name, raising=False)
