"""Factory CLI.

`sdlc-factory demo` traverses one mocked feature through the full lifecycle,
persisting typed state, transitions, executions, evidence and audit events.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from factory.agents.mocked import build_mocked_agents
from factory.models.enums import FactoryState
from factory.models.feature import FeatureState
from factory.orchestrator.engine import OrchestratorEngine
from factory.orchestrator.events import EventBus, JsonlEventSink
from factory.orchestrator.state_machine import STATE_MACHINE
from factory.orchestrator.store import FileStateStore
from factory.policy.engine import PolicyEngine
from factory.policy.quality_gate import QualityEvidence, QualityGate

HAPPY_PATH: list[FactoryState] = [
    FactoryState.INTAKE,
    FactoryState.CLARIFICATION,
    FactoryState.REQUIREMENTS_READY,
    FactoryState.DECOMPOSED,
    FactoryState.SPECIFIED,
    FactoryState.KNOWLEDGE_MINED,
    FactoryState.DESIGNED,
    FactoryState.TASKS_READY,
    FactoryState.TEST_DESIGNED,
    FactoryState.IMPLEMENTING,
    FactoryState.BUILT,
    FactoryState.UNIT_TESTED,
    FactoryState.PR_CREATED,
    FactoryState.REVIEWED,
    FactoryState.MERGE_READY,
    FactoryState.POLICY_GATE,
    FactoryState.MERGED,
    FactoryState.PACKAGED,
    FactoryState.PUBLISHED,
    FactoryState.DEPLOYED,
    FactoryState.FUNCTIONAL_TESTED,
    FactoryState.AC_VALIDATED,
    FactoryState.STORY_COMPLETED,
    FactoryState.LEARNED,
]


async def run_demo(base_dir: Path, project_id: str = "PRJ-DEMO") -> FeatureState:
    projects_dir = base_dir / "projects"
    project_dir = projects_dir / project_id
    store = FileStateStore(projects_dir)
    events = EventBus([JsonlEventSink(project_dir / "execution" / "events.jsonl")])
    engine = OrchestratorEngine(
        state_machine=STATE_MACHINE,
        store=store,
        events=events,
        agents=build_mocked_agents(project_dir),
    )

    feature = FeatureState(
        feature_id="FEAT-001",
        project_id=project_id,
        title="Demo feature traversing the factory control plane",
        requirements=["BR-001"],
        stories=["STORY-001-01"],
        acceptance_criteria=["AC-001-01", "AC-001-02"],
    )
    store.save_feature(feature)

    feature = await engine.run_to_completion(feature, HAPPY_PATH)

    gate = QualityGate(PolicyEngine(base_dir / "policies"))
    result = gate.evaluate(
        QualityEvidence(
            build_passed=True,
            unit_tests_passed=True,
            integration_tests_passed=True,
            coverage=feature.coverage or 0.0,
            spec_compliance=97.0,
            critical_security_findings=0,
            acceptance_criteria_pass_percentage=100.0,
        )
    )

    print(f"Feature {feature.feature_id} finished in state: {feature.current_state.value}")
    print(f"Evidence artifacts: {len(feature.evidence)}")
    print(f"Quality gate decision: {result.decision.value}")
    for check in result.checks:
        print(f"  {check.name}: threshold={check.threshold} actual={check.actual} "
              f"{'PASS' if check.passed else 'FAIL'}")
    for transition in store.transitions_for(feature.feature_id):
        print(f"  {transition.from_state.value} -> {transition.to_state.value} "
              f"[{transition.agent}]")
    return feature


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-factory")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Traverse one mocked feature end-to-end with evidence")
    demo.add_argument("--base-dir", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    if args.command == "demo":
        feature = asyncio.run(run_demo(args.base_dir))
        return 0 if feature.current_state == FactoryState.LEARNED else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
