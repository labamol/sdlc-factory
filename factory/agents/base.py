"""Agent execution contract.

Agents reason and recommend; they never mutate systems directly (tools do)
and never decide gate progression (policy does). Agents do not rely on
conversation history as durable state: everything durable lives in the
typed FeatureState, evidence and events.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState


class AgentResult(BaseModel):
    status: str = "SUCCESS"  # SUCCESS | FAILURE
    summary: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    state_updates: dict = Field(default_factory=dict)
    skill: str | None = None


class Agent(Protocol):
    name: str

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult: ...
