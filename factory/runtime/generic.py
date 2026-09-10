"""Runtime portability: agents and skills are portable across execution
products (Copilot, Claude, Cursor, generic LLM APIs) through this protocol.
Concrete adapters arrive with the real reasoning agents (Increment 2+)."""

from typing import Protocol

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.feature import FeatureState
from factory.skills.registry import Skill


class AgentRuntime(Protocol):
    name: str

    async def execute(
        self,
        agent_name: str,
        feature: FeatureState,
        stage: FactoryState,
        skills: list[Skill],
        context: str,
    ) -> AgentResult: ...
