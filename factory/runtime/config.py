"""Runtime selection from the environment.

The factory is fully operable without an LLM: when no provider is configured
every agent uses its deterministic path, which is also what keeps the test
suite hermetic. Configuring `OPENAI_API_KEY` upgrades the reasoning steps in
place, without changing agents, skills, policies or the state machine.
"""

import os

from factory.runtime.llm import LLMError, LLMRuntime

ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def llm_enabled() -> bool:
    """LLM reasoning is opt-out: set FACTORY_LLM=off to force deterministic runs."""
    return os.environ.get("FACTORY_LLM", "on").strip().lower() in ENABLED_VALUES


def runtime_from_env() -> LLMRuntime | None:
    """Return a configured runtime, or None to use deterministic reasoning."""
    if not llm_enabled():
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from factory.runtime.openai import DEFAULT_BASE_URL, DEFAULT_MODEL, OpenAIRuntime
    except ImportError as exc:  # httpx ships with the `llm` extra
        raise LLMError(
            'OPENAI_API_KEY is set but the LLM extra is missing: '
            'pip install "sdlc-factory[llm]"'
        ) from exc
    return OpenAIRuntime(
        api_key=api_key,
        model=os.environ.get("FACTORY_MODEL", "").strip() or DEFAULT_MODEL,
        base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or DEFAULT_BASE_URL,
    )
