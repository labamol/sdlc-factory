"""Forge selection from the environment.

Without `GITHUB_TOKEN` + `FACTORY_TARGET_REPO` the factory uses its local PR
registry, which is what keeps demos and the test suite self-contained. Setting
both promotes the same lifecycle to a real repository: no agent, policy or
state transition changes.
"""

import os
from pathlib import Path

from factory.tools.forge import Forge
from factory.tools.pr import PrTool

ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def forge_enabled() -> bool:
    """Remote forging is opt-out: set FACTORY_FORGE=off to stay local."""
    return os.environ.get("FACTORY_FORGE", "on").strip().lower() in ENABLED_VALUES


def target_repo() -> str:
    return os.environ.get("FACTORY_TARGET_REPO", "").strip()


def forge_from_env(project_dir: Path) -> Forge:
    """Return the configured forge, defaulting to the project-local registry."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = target_repo()
    if not forge_enabled() or not token or not repo:
        return PrTool(project_dir)
    from factory.tools.github import (
        DEFAULT_API_URL,
        DEFAULT_BASE_BRANCH,
        DEFAULT_GIT_BASE_URL,
        GitHubForge,
    )

    return GitHubForge(
        repo=repo,
        token=token,
        project_dir=project_dir,
        api_url=os.environ.get("GITHUB_API_URL", "").strip() or DEFAULT_API_URL,
        git_base_url=os.environ.get("GITHUB_GIT_URL", "").strip() or DEFAULT_GIT_BASE_URL,
        base_branch=os.environ.get("FACTORY_TARGET_BRANCH", "").strip() or DEFAULT_BASE_BRANCH,
    )
