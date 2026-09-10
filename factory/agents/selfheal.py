"""Self-heal agent.

Owns the DIAGNOSE -> RETEST repair step: classifies the failing test report
into the failure taxonomy, consults episodic memory for known repairs,
applies the routed repair when it is autonomous (regenerating implementation,
tests or synthetic data from their deterministic templates), and records the
episode. Attempts are bounded by the quality policy's max_self_heal_attempts;
exhaustion and non-autonomous classes fail so the orchestrator escalates to
a human instead of guessing.
"""

import json
from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.healing.memory import Episode, EpisodicMemory
from factory.healing.repair import REPAIR_ROUTES, RepairRoute
from factory.healing.taxonomy import Diagnosis, classify_failure
from factory.implementation.codegen import feature_module_name, generate_feature_module
from factory.implementation.synthdata import generate_synthetic_records
from factory.implementation.testgen import generate_feature_tests
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.models.requirement import Feature
from factory.models.story import Story
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool

TEST_REPORTS = ("testing/retest-report.txt", "testing/unit_tested-report.txt")
DEFAULT_MAX_ATTEMPTS = 3


class SelfHealAgent:
    name = "self-heal-agent"

    def __init__(self, project_dir: Path, policies_dir: Path) -> None:
        self.project_dir = project_dir
        self.policies_dir = policies_dir
        self.fs = FilesystemTool(project_dir)
        self.memory = EpisodicMemory(project_dir)

    def _max_attempts(self) -> int:
        policy_path = self.policies_dir / "quality.yaml"
        if not policy_path.exists():
            return DEFAULT_MAX_ATTEMPTS
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        return int(
            policy.get("quality_gate", {}).get(
                "max_self_heal_attempts", DEFAULT_MAX_ATTEMPTS
            )
        )

    def _load(self, relative: str) -> list[dict]:
        if not self.fs.exists(relative):
            return []
        return yaml.safe_load(self.fs.read_text(relative)) or []

    def _latest_report(self) -> str:
        for relative in TEST_REPORTS:
            if self.fs.exists(relative):
                return self.fs.read_text(relative)
        return ""

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage not in (FactoryState.RETEST, FactoryState.DIAGNOSE):
            return AgentResult(
                status="FAILURE", summary=f"Unsupported stage {stage.value}"
            )

        attempt = self.memory.attempts_for(feature.feature_id) + 1
        max_attempts = self._max_attempts()
        if attempt > max_attempts:
            return AgentResult(
                status="FAILURE",
                summary=f"Self-heal budget exhausted ({max_attempts} attempts)",
            )

        report_text = self._latest_report()
        if not report_text:
            return AgentResult(status="FAILURE", summary="No failing test report found")

        diagnosis = classify_failure(report_text)
        route = REPAIR_ROUTES[diagnosis.failure_class]
        known = [
            e for e in self.memory.find_by_signature(diagnosis.signature)
            if e.outcome == "REPAIRED"
        ]

        episode = Episode(
            episode_id=new_id("EPI"),
            feature_id=feature.feature_id,
            stage=stage.value,
            failure_class=diagnosis.failure_class.value,
            signature=diagnosis.signature,
            diagnosis_summary=diagnosis.excerpt,
            repair_action=route.action,
            repair_owner=route.owner_agent,
            attempt=attempt,
        )

        diagnosis_path = self.fs.write_text(
            f"healing/diagnosis-{attempt}.yaml",
            yaml.safe_dump(
                {
                    "diagnosis": diagnosis.model_dump(mode="json"),
                    "repair_route": route.model_dump(mode="json"),
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "known_repairs": len(known),
                },
                sort_keys=False,
            ),
        )
        evidence = [
            Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind="diagnosis",
                ref=str(diagnosis_path),
                summary=f"{diagnosis.failure_class.value} sig={diagnosis.signature} "
                        f"attempt {attempt}/{max_attempts}",
                metadata={"failure_class": diagnosis.failure_class.value},
            )
        ]

        if not route.autonomous:
            episode.outcome = "ESCALATED"
            self.memory.record(episode)
            return AgentResult(
                status="FAILURE",
                summary=f"{diagnosis.failure_class.value} requires "
                        f"{route.owner_agent} with human input ({route.action})",
                evidence=evidence,
            )

        repaired = self._apply_repair(route, diagnosis)
        self.memory.record(episode)
        evidence.append(
            Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind="repair",
                ref=str(self.project_dir / "learning" / "episodes.yaml"),
                summary=f"{route.action} on {len(repaired)} artifact(s)",
                metadata={"episode_id": episode.episode_id},
            )
        )
        return AgentResult(
            summary=f"Applied {route.action} for {diagnosis.failure_class.value} "
                    f"(attempt {attempt}/{max_attempts})",
            evidence=evidence,
            skill="healing/self-heal",
        )

    def _apply_repair(self, route: RepairRoute, diagnosis: Diagnosis) -> list[str]:
        features = [Feature.model_validate(f) for f in self._load("backlog/features.yaml")]
        stories = [Story.model_validate(s) for s in self._load("backlog/stories.yaml")]
        repaired: list[str] = []
        for feat in features:
            feature_stories = [s for s in stories if s.feature_id == feat.feature_id]
            module = feature_module_name(feat.feature_id)
            if route.action == "regenerate-implementation":
                self.fs.write_text(
                    f"workspace/src/{module}.py",
                    generate_feature_module(feat, feature_stories),
                )
                repaired.append(f"workspace/src/{module}.py")
            elif route.action == "regenerate-tests":
                self.fs.write_text(
                    f"workspace/tests/test_{module}.py",
                    generate_feature_tests(feat, feature_stories),
                )
                repaired.append(f"workspace/tests/test_{module}.py")
        if route.action == "regenerate-synthetic-data":
            data = {
                s.story_id: generate_synthetic_records(s.story_id, count=3)
                for s in stories
            }
            self.fs.write_text("workspace/data/synthetic.json", json.dumps(data, indent=2))
            repaired.append("workspace/data/synthetic.json")
        return repaired
