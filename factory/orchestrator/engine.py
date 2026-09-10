"""Orchestrator engine: drives features through the declarative state machine.

The engine owns WHEN. It resolves the responsible agent for a transition,
executes it, validates expected artifacts, persists typed state, records
immutable transitions/executions and emits audit events. Retry budgets are
bounded; exhaustion always routes to HUMAN_ESCALATION with evidence.
"""

import time

from factory.agents.base import Agent, AgentResult
from factory.models.enums import FactoryState
from factory.models.execution import AgentExecution, StateTransition
from factory.models.feature import FeatureState
from factory.orchestrator.events import EventBus, FactoryEvent, new_id
from factory.orchestrator.state_machine import StateMachine, TransitionSpec
from factory.orchestrator.store import StateStore


class TransitionError(Exception):
    pass


class OrchestratorEngine:
    def __init__(
        self,
        state_machine: StateMachine,
        store: StateStore,
        events: EventBus,
        agents: dict[str, Agent],
    ) -> None:
        self.state_machine = state_machine
        self.store = store
        self.events = events
        self.agents = agents

    async def advance(
        self,
        feature: FeatureState,
        to_state: FactoryState,
        *,
        human_intervention: bool = False,
        reason: str = "",
    ) -> FeatureState:
        """Execute one transition, including agent execution and validation."""
        spec = self.state_machine.find(feature.current_state, to_state)
        if spec is None:
            raise TransitionError(
                f"Transition {feature.current_state.value} -> {to_state.value} is not allowed"
            )

        execution = await self._execute_agent(feature, spec)

        if execution.status == "SUCCESS" and spec.validate_outcome(feature):
            self._commit_transition(feature, spec, execution, human_intervention, reason)
            return feature

        return self._handle_failure(feature, spec, execution)

    async def _execute_agent(self, feature: FeatureState, spec: TransitionSpec) -> AgentExecution:
        execution = AgentExecution(
            execution_id=new_id("EX"),
            feature_id=feature.feature_id,
            project_id=feature.project_id,
            stage=spec.to_state,
            agent=spec.agent,
            spec_version=feature.spec_version,
            retry_number=feature.retry_count,
        )
        self.events.emit(
            FactoryEvent(
                event_type="AGENT_EXECUTION_STARTED",
                project_id=feature.project_id,
                feature_id=feature.feature_id,
                execution_id=execution.execution_id,
                stage=spec.to_state.value,
                agent=spec.agent,
                retry_number=feature.retry_count,
            )
        )
        started = time.monotonic()
        agent = self.agents.get(spec.agent)
        if agent is None:
            result = AgentResult(status="FAILURE", summary=f"No agent registered: {spec.agent}")
        else:
            try:
                result = await agent.execute(feature, spec.to_state)
            except Exception as exc:  # noqa: BLE001 - agent failures are classified, not fatal
                result = AgentResult(status="FAILURE", summary=f"{type(exc).__name__}: {exc}")

        for evidence in result.evidence:
            feature.add_evidence(evidence)
        for field, value in result.state_updates.items():
            setattr(feature, field, value)

        execution.duration_seconds = round(time.monotonic() - started, 3)
        execution.status = result.status
        execution.skill = result.skill
        execution.result_summary = result.summary
        execution.evidence_refs = [e.evidence_id for e in result.evidence]
        self.store.record_execution(execution)
        self.events.emit(
            FactoryEvent(
                event_type="AGENT_EXECUTION_COMPLETED",
                project_id=feature.project_id,
                feature_id=feature.feature_id,
                execution_id=execution.execution_id,
                stage=spec.to_state.value,
                agent=spec.agent,
                skill=result.skill,
                status=result.status,
                retry_number=feature.retry_count,
                payload={"duration_seconds": execution.duration_seconds},
                evidence_refs=execution.evidence_refs,
            )
        )
        return execution

    def _commit_transition(
        self,
        feature: FeatureState,
        spec: TransitionSpec,
        execution: AgentExecution,
        human_intervention: bool,
        reason: str,
    ) -> None:
        transition = StateTransition(
            transition_id=new_id("TRN"),
            feature_id=feature.feature_id,
            project_id=feature.project_id,
            from_state=feature.current_state,
            to_state=spec.to_state,
            agent=spec.agent,
            reason=reason,
            retry_number=feature.retry_count,
            human_intervention=human_intervention,
            evidence_refs=execution.evidence_refs,
        )
        feature.current_state = spec.to_state
        feature.retry_count = 0
        self.store.record_transition(transition)
        self.store.save_feature(feature)
        self.events.emit(
            FactoryEvent(
                event_type="STATE_TRANSITION",
                project_id=feature.project_id,
                feature_id=feature.feature_id,
                execution_id=execution.execution_id,
                stage=spec.to_state.value,
                agent=spec.agent,
                status="SUCCESS",
                human_intervention=human_intervention,
                payload={"from_state": transition.from_state.value, "reason": reason},
                evidence_refs=execution.evidence_refs,
            )
        )

    def _handle_failure(
        self, feature: FeatureState, spec: TransitionSpec, execution: AgentExecution
    ) -> FeatureState:
        feature.retry_count += 1
        if feature.retry_count >= spec.max_attempts:
            feature.current_state = spec.escalation_state
            self.store.save_feature(feature)
            self.events.emit(
                FactoryEvent(
                    event_type="HUMAN_ESCALATION",
                    project_id=feature.project_id,
                    feature_id=feature.feature_id,
                    execution_id=execution.execution_id,
                    stage=spec.to_state.value,
                    agent=spec.agent,
                    status="ESCALATED",
                    retry_number=feature.retry_count,
                    payload={"reason": execution.result_summary},
                    evidence_refs=execution.evidence_refs,
                )
            )
            return feature

        if spec.retry_route is not None and self.state_machine.is_allowed(
            feature.current_state, spec.retry_route
        ):
            feature.current_state = spec.retry_route
        self.store.save_feature(feature)
        self.events.emit(
            FactoryEvent(
                event_type="TRANSITION_RETRY",
                project_id=feature.project_id,
                feature_id=feature.feature_id,
                execution_id=execution.execution_id,
                stage=spec.to_state.value,
                agent=spec.agent,
                status="RETRY",
                retry_number=feature.retry_count,
                payload={"reason": execution.result_summary},
            )
        )
        return feature

    async def run_to_completion(
        self, feature: FeatureState, route: list[FactoryState], *, max_steps: int = 100
    ) -> FeatureState:
        """Drive a feature along a route of target states until terminal or blocked."""
        steps = 0
        for target in route:
            while feature.current_state != target:
                if steps >= max_steps:
                    raise TransitionError("Exceeded maximum orchestration steps")
                if feature.current_state == FactoryState.HUMAN_ESCALATION:
                    return feature
                feature = await self.advance(feature, target)
                steps += 1
        return feature
