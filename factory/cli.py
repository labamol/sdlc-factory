"""Factory CLI.

`sdlc-factory demo` traverses one mocked feature through the full lifecycle,
persisting typed state, transitions, executions, evidence and audit events.

`sdlc-factory intake` runs the real Increment 2 pipeline: BRD -> requirements
-> clarification/assumptions (pausing on blocking ambiguity for human input)
-> decomposition -> Spec Kit specification, versioned in Git.

`sdlc-factory deliver` continues past knowledge mining into design, test
design, implementation by worker profiles, pre-PR quality checks and unit
test execution (UNIT_TESTED).

`sdlc-factory ship` continues through PR creation, code/security/spec/
coverage review, the merge policy gate and the protected-branch merge
(MERGED).

`sdlc-factory release` continues through packaging, publishing, deployment
with smoke tests, functional testing against the deployed artifact,
acceptance-criteria validation and tracker closure (STORY_COMPLETED).

`sdlc-factory learn` runs the full lifecycle including episodic learning and
governed promotion proposals (LEARNED).

`sdlc-factory heal` demonstrates bounded self-healing: it injects a defect
into the generated implementation after BUILT, lets unit testing fail, then
diagnoses, repairs and retests within the policy budget.

`sdlc-factory dashboard` serves the FastAPI observability service (REST +
SSE) over the durable project records, and the built React dashboard when
`ui/dist` exists (requires `pip install "sdlc-factory[observability]"`).
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

import yaml

from factory.agents.design import DesignAgent
from factory.agents.governance import OrchestratorGateAgent
from factory.agents.implementation import ImplementationAgent
from factory.agents.knowledge import KnowledgeAgent
from factory.agents.learning import LearningAgent
from factory.agents.mocked import build_mocked_agents
from factory.agents.product import ProductAgent
from factory.agents.release import ReleaseAgent
from factory.agents.requirements import RequirementsAgent
from factory.agents.review import ReviewAgent
from factory.agents.selfheal import SelfHealAgent
from factory.agents.specification import SpecificationAgent
from factory.agents.testeng import TestEngineeringAgent
from factory.agents.validation import ValidationAgent
from factory.healing.loop import run_self_heal
from factory.healing.memory import EpisodicMemory
from factory.models.enums import FactoryState
from factory.models.feature import FeatureState
from factory.orchestrator.engine import OrchestratorEngine
from factory.orchestrator.events import EventBus, JsonlEventSink
from factory.orchestrator.state_machine import STATE_MACHINE
from factory.orchestrator.store import FileStateStore
from factory.policy.engine import PolicyEngine
from factory.policy.quality_gate import QualityEvidence, QualityGate
from factory.tools.git import GitTool

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


DELIVER_STATES: tuple[FactoryState, ...] = (
    FactoryState.DESIGNED,
    FactoryState.TASKS_READY,
    FactoryState.TEST_DESIGNED,
    FactoryState.IMPLEMENTING,
    FactoryState.BUILT,
    FactoryState.UNIT_TESTED,
)

SHIP_STATES: tuple[FactoryState, ...] = (
    FactoryState.PR_CREATED,
    FactoryState.REVIEWED,
    FactoryState.MERGE_READY,
    FactoryState.POLICY_GATE,
    FactoryState.MERGED,
)

RELEASE_STATES: tuple[FactoryState, ...] = (
    FactoryState.PACKAGED,
    FactoryState.PUBLISHED,
    FactoryState.DEPLOYED,
    FactoryState.FUNCTIONAL_TESTED,
    FactoryState.AC_VALIDATED,
    FactoryState.STORY_COMPLETED,
)

DEFAULT_POLICIES_DIR = Path(__file__).resolve().parents[1] / "policies"


def _policies_dir(base_dir: Path) -> Path:
    candidate = base_dir / "policies"
    return candidate if candidate.exists() else DEFAULT_POLICIES_DIR


async def run_intake(
    base_dir: Path,
    brd: Path,
    meetings: list[Path],
    project_id: str = "PRJ-INTAKE",
    *,
    deliver: bool = False,
    ship: bool = False,
    release: bool = False,
    learn: bool = False,
    heal_demo: bool = False,
) -> FeatureState:
    projects_dir = base_dir / "projects"
    project_dir = projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "intake").mkdir(exist_ok=True)
    shutil.copy(brd, project_dir / "intake" / "brd.md")
    if meetings:
        (project_dir / "intake" / "meetings").mkdir(exist_ok=True)
        for meeting in meetings:
            shutil.copy(meeting, project_dir / "intake" / "meetings" / meeting.name)

    git = GitTool(project_dir)
    if not git.is_repo():
        git.init()
        git.configure_identity("sdlc-factory", "factory@localhost")

    store = FileStateStore(projects_dir)
    events = EventBus([JsonlEventSink(project_dir / "execution" / "events.jsonl")])
    agents = build_mocked_agents(project_dir)
    agents["requirements-agent"] = RequirementsAgent(project_dir)
    agents["product-agent"] = ProductAgent(project_dir)
    agents["specification-agent"] = SpecificationAgent(project_dir)
    agents["knowledge-agent"] = KnowledgeAgent(project_dir)
    agents["design-agent"] = DesignAgent(project_dir)
    agents["test-agent"] = TestEngineeringAgent(project_dir)
    agents["implementation-agent"] = ImplementationAgent(project_dir)
    agents["review-agent"] = ReviewAgent(project_dir)
    agents["orchestrator"] = OrchestratorGateAgent(project_dir, _policies_dir(base_dir))
    agents["release-agent"] = ReleaseAgent(project_dir)
    agents["validation-agent"] = ValidationAgent(project_dir, _policies_dir(base_dir))
    agents["self-heal-agent"] = SelfHealAgent(project_dir, _policies_dir(base_dir))
    agents["learning-agent"] = LearningAgent(project_dir, _policies_dir(base_dir))
    engine = OrchestratorEngine(
        state_machine=STATE_MACHINE, store=store, events=events, agents=agents
    )

    feature = FeatureState(
        feature_id="FEAT-000",
        project_id=project_id,
        title=f"BRD intake for {brd.name}",
    )
    store.save_feature(feature)

    feature = await engine.advance(feature, FactoryState.INTAKE)
    feature = await engine.advance(feature, FactoryState.CLARIFICATION)

    clarifications = yaml.safe_load(
        (project_dir / "requirements" / "clarifications.yaml").read_text()
    ) or []
    blocking_open = [
        c for c in clarifications
        if c["ambiguity_class"] == "BLOCKING" and c["status"] == "OPEN"
    ]
    if blocking_open:
        feature = await engine.advance(feature, FactoryState.HUMAN_INPUT)
        print(f"Feature {feature.feature_id} paused in state: {feature.current_state.value}")
        print(f"Blocking clarifications: {len(blocking_open)}")
        print(f"HITL request: {project_dir / 'hitl' / 'clarification-request.md'}")
        return feature

    targets: list[FactoryState] = [
        FactoryState.REQUIREMENTS_READY,
        FactoryState.DECOMPOSED,
        FactoryState.SPECIFIED,
        FactoryState.KNOWLEDGE_MINED,
    ]
    if heal_demo:
        targets += [s for s in DELIVER_STATES if s != FactoryState.UNIT_TESTED]
    elif deliver or ship or release or learn:
        targets += list(DELIVER_STATES)
    if ship or release or learn:
        targets += list(SHIP_STATES)
    if release or learn:
        targets += list(RELEASE_STATES)
    if learn:
        targets.append(FactoryState.LEARNED)
    for target in targets:
        feature = await engine.advance(feature, target)

    if heal_demo and feature.current_state == FactoryState.BUILT:
        module = next((project_dir / "workspace" / "src").glob("*.py"))
        module.write_text(
            module.read_text(encoding="utf-8")
            + '\nraise RuntimeError("injected template regression")\n',
            encoding="utf-8",
        )
        print(f"Injected defect into {module.name}")
        feature = await engine.advance(feature, FactoryState.UNIT_TESTED)
        if feature.current_state == FactoryState.DIAGNOSE:
            feature = await run_self_heal(engine, feature, project_dir)
        episodes = EpisodicMemory(project_dir).all()
        for episode in episodes:
            print(f"Episode {episode.episode_id}: {episode.failure_class} "
                  f"-> {episode.repair_action} [{episode.outcome}]")

    print(f"Feature {feature.feature_id} finished in state: {feature.current_state.value}")
    print(f"Requirements: {len(feature.requirements)}")
    print(f"Stories: {len(feature.stories)}  ACs: {len(feature.acceptance_criteria)}")
    print(f"Spec version: {feature.spec_version}")
    if deliver or ship or release:
        print(f"Branch: {feature.branch}")
        print(f"Unit tests: {feature.unit_test_status.value}")
    if ship or release:
        print(f"Pull request: #{feature.pull_request}")
        print(f"Coverage: {feature.coverage}")
    if release or learn:
        print(f"Deployed to: {feature.deployment_environment}")
        print(f"Functional tests: {feature.functional_test_status.value}")
    if heal_demo:
        print(f"Unit tests after healing: {feature.unit_test_status.value}")
    for transition in store.transitions_for(feature.feature_id):
        print(f"  {transition.from_state.value} -> {transition.to_state.value} "
              f"[{transition.agent}]")
    return feature


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdlc-factory")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Traverse one mocked feature end-to-end with evidence")
    demo.add_argument("--base-dir", type=Path, default=Path.cwd())
    intake = sub.add_parser(
        "intake", help="Run a BRD through requirements, clarification and specification"
    )
    intake.add_argument("--brd", type=Path, required=True)
    intake.add_argument("--meeting", type=Path, action="append", default=[])
    intake.add_argument("--base-dir", type=Path, default=Path.cwd())
    intake.add_argument("--project-id", default="PRJ-INTAKE")
    deliver = sub.add_parser(
        "deliver", help="Run intake plus design, implementation and unit testing"
    )
    deliver.add_argument("--brd", type=Path, required=True)
    deliver.add_argument("--meeting", type=Path, action="append", default=[])
    deliver.add_argument("--base-dir", type=Path, default=Path.cwd())
    deliver.add_argument("--project-id", default="PRJ-DELIVER")
    ship = sub.add_parser(
        "ship", help="Run delivery plus PR, review, policy gate and merge"
    )
    ship.add_argument("--brd", type=Path, required=True)
    ship.add_argument("--meeting", type=Path, action="append", default=[])
    ship.add_argument("--base-dir", type=Path, default=Path.cwd())
    ship.add_argument("--project-id", default="PRJ-SHIP")
    release = sub.add_parser(
        "release", help="Run shipping plus packaging, deploy, validation and closure"
    )
    release.add_argument("--brd", type=Path, required=True)
    release.add_argument("--meeting", type=Path, action="append", default=[])
    release.add_argument("--base-dir", type=Path, default=Path.cwd())
    release.add_argument("--project-id", default="PRJ-RELEASE")
    learn = sub.add_parser(
        "learn", help="Run the full lifecycle through episodic learning (LEARNED)"
    )
    learn.add_argument("--brd", type=Path, required=True)
    learn.add_argument("--meeting", type=Path, action="append", default=[])
    learn.add_argument("--base-dir", type=Path, default=Path.cwd())
    learn.add_argument("--project-id", default="PRJ-LEARN")
    heal = sub.add_parser(
        "heal", help="Demonstrate bounded self-healing from an injected defect"
    )
    heal.add_argument("--brd", type=Path, required=True)
    heal.add_argument("--meeting", type=Path, action="append", default=[])
    heal.add_argument("--base-dir", type=Path, default=Path.cwd())
    heal.add_argument("--project-id", default="PRJ-HEAL")
    dashboard = sub.add_parser(
        "dashboard", help="Serve the observability API and dashboard UI"
    )
    dashboard.add_argument("--base-dir", type=Path, default=Path.cwd())
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8600)
    args = parser.parse_args(argv)

    if args.command == "demo":
        feature = asyncio.run(run_demo(args.base_dir))
        return 0 if feature.current_state == FactoryState.LEARNED else 1
    if args.command == "intake":
        feature = asyncio.run(
            run_intake(args.base_dir, args.brd, args.meeting, args.project_id)
        )
        if feature.current_state == FactoryState.KNOWLEDGE_MINED:
            return 0
        return 3 if feature.current_state == FactoryState.HUMAN_INPUT else 1
    if args.command == "deliver":
        feature = asyncio.run(
            run_intake(
                args.base_dir, args.brd, args.meeting, args.project_id, deliver=True
            )
        )
        if feature.current_state == FactoryState.UNIT_TESTED:
            return 0
        return 3 if feature.current_state == FactoryState.HUMAN_INPUT else 1
    if args.command == "ship":
        feature = asyncio.run(
            run_intake(
                args.base_dir, args.brd, args.meeting, args.project_id, ship=True
            )
        )
        if feature.current_state == FactoryState.MERGED:
            return 0
        return 3 if feature.current_state == FactoryState.HUMAN_INPUT else 1
    if args.command == "release":
        feature = asyncio.run(
            run_intake(
                args.base_dir, args.brd, args.meeting, args.project_id, release=True
            )
        )
        if feature.current_state == FactoryState.STORY_COMPLETED:
            return 0
        return 3 if feature.current_state == FactoryState.HUMAN_INPUT else 1
    if args.command == "learn":
        feature = asyncio.run(
            run_intake(
                args.base_dir, args.brd, args.meeting, args.project_id, learn=True
            )
        )
        if feature.current_state == FactoryState.LEARNED:
            return 0
        return 3 if feature.current_state == FactoryState.HUMAN_INPUT else 1
    if args.command == "heal":
        feature = asyncio.run(
            run_intake(
                args.base_dir, args.brd, args.meeting, args.project_id, heal_demo=True
            )
        )
        return 0 if feature.current_state == FactoryState.UNIT_TESTED else 1
    if args.command == "dashboard":
        try:
            import uvicorn

            from factory.observability.api import create_app
        except ImportError:
            print('Install observability extras: pip install "sdlc-factory[observability]"')
            return 1
        uvicorn.run(create_app(args.base_dir), host=args.host, port=args.port)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
