"""Retry budgets, escalation and validation enforcement in the engine."""

import pytest

from factory.agents.base import AgentResult
from factory.models.enums import FactoryState
from factory.models.feature import FeatureState
from factory.orchestrator.engine import OrchestratorEngine, TransitionError
from factory.orchestrator.events import EventBus, InMemoryEventSink
from factory.orchestrator.state_machine import STATE_MACHINE
from factory.orchestrator.store import FileStateStore


class FailingAgent:
    name = "requirements-agent"

    async def execute(self, feature, stage):
        return AgentResult(status="FAILURE", summary="simulated failure")


class SucceedingAgent:
    name = "requirements-agent"

    async def execute(self, feature, stage):
        return AgentResult(status="SUCCESS", summary="ok")


def _engine(tmp_path, agent, sink):
    return OrchestratorEngine(
        state_machine=STATE_MACHINE,
        store=FileStateStore(tmp_path / "projects"),
        events=EventBus([sink]),
        agents={"requirements-agent": agent},
    )


def _feature() -> FeatureState:
    return FeatureState(feature_id="FEAT-X", project_id="PRJ-X")


async def test_disallowed_transition_raises(tmp_path):
    engine = _engine(tmp_path, SucceedingAgent(), InMemoryEventSink())
    with pytest.raises(TransitionError):
        await engine.advance(_feature(), FactoryState.MERGED)


async def test_repeated_failure_escalates_to_human(tmp_path):
    sink = InMemoryEventSink()
    engine = _engine(tmp_path, FailingAgent(), sink)
    feature = _feature()
    for _ in range(3):
        feature = await engine.advance(feature, FactoryState.INTAKE)
    assert feature.current_state == FactoryState.HUMAN_ESCALATION
    assert any(e.event_type == "HUMAN_ESCALATION" for e in sink.events)
    retries = [e for e in sink.events if e.event_type == "TRANSITION_RETRY"]
    assert len(retries) == 2  # third failure escalates instead of retrying


async def test_missing_agent_is_failure_not_crash(tmp_path):
    sink = InMemoryEventSink()
    engine = OrchestratorEngine(
        state_machine=STATE_MACHINE,
        store=FileStateStore(tmp_path / "projects"),
        events=EventBus([sink]),
        agents={},
    )
    feature = await engine.advance(_feature(), FactoryState.INTAKE)
    assert feature.retry_count == 1
    assert feature.current_state == FactoryState.BRD_RECEIVED


async def test_validation_failure_counts_as_retry(tmp_path):
    # INTAKE requires stage evidence; SucceedingAgent produces none.
    sink = InMemoryEventSink()
    engine = _engine(tmp_path, SucceedingAgent(), sink)
    feature = await engine.advance(_feature(), FactoryState.INTAKE)
    assert feature.current_state == FactoryState.BRD_RECEIVED
    assert feature.retry_count == 1
