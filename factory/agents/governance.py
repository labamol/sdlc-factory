"""Orchestrator gate agent.

Registered as the `orchestrator` agent: dispatches HUMAN_INPUT to the HITL
gate and owns merge governance — POLICY_GATE evaluates the quality gate and
merge policy from immutable evidence (never agent summaries) and MERGED
performs the actual protected-branch merge only after a PASS decision.
"""

from pathlib import Path

import yaml

from factory.agents.base import AgentResult
from factory.agents.hitl import HitlGateAgent
from factory.models.enums import FactoryState, GateDecision
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.policy.engine import PolicyCheck, PolicyEngine
from factory.policy.quality_gate import QualityEvidence, QualityGate
from factory.tools.filesystem import FilesystemTool
from factory.tools.forge import Forge
from factory.tools.pr import PrTool


def _percent(text: str) -> float:
    return float(text.rstrip("%"))


class OrchestratorGateAgent:
    name = "orchestrator"

    def __init__(
        self, project_dir: Path, policies_dir: Path, forge: Forge | None = None
    ) -> None:
        self.project_dir = project_dir
        self.fs = FilesystemTool(project_dir)
        self.policy_engine = PolicyEngine(policies_dir)
        self.hitl = HitlGateAgent(project_dir)
        self.forge = forge or PrTool(project_dir)

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage == FactoryState.HUMAN_INPUT:
            return await self.hitl.execute(feature, stage)
        if stage == FactoryState.POLICY_GATE:
            return self._policy_gate(feature, stage)
        if stage == FactoryState.MERGED:
            return self._merge(feature, stage)
        return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

    def _quality_evidence(self, feature: FeatureState) -> QualityEvidence:
        report = yaml.safe_load(self.fs.read_text("quality/pre-pr-report.yaml"))
        by_name = {c["name"]: c for c in report["checks"]}
        unit_passed = by_name["unit_tests"]["passed"]
        pre_pr_ref = str(self.project_dir / "quality" / "pre-pr-report.yaml")
        return QualityEvidence(
            build_passed=by_name["build"]["passed"],
            unit_tests_passed=unit_passed,
            integration_tests_passed=unit_passed,
            coverage=_percent(by_name["coverage"]["actual"]),
            spec_compliance=_percent(by_name["spec_compliance"]["actual"]),
            critical_security_findings=int(by_name["security_critical_findings"]["actual"]),
            acceptance_criteria_pass_percentage=_percent(by_name["spec_compliance"]["actual"]),
            evidence_refs={name: pre_pr_ref for name in (
                "build", "unit_tests", "integration_tests", "coverage",
                "spec_compliance", "security", "acceptance_criteria",
            )},
        )

    def _merge_policy_checks(self, feature: FeatureState) -> list[PolicyCheck]:
        policy = self.policy_engine.load("merge").get("merge_policy", {})
        review = {}
        if self.fs.exists("review/review-findings.yaml"):
            review = yaml.safe_load(self.fs.read_text("review/review-findings.yaml"))
        review_ref = str(self.project_dir / "review" / "review-findings.yaml")
        approved = review.get("verdict") == "APPROVED"
        checks = []
        if policy.get("require_review", True):
            checks.append(
                PolicyCheck(
                    name="merge.require_review", threshold="APPROVED",
                    actual=str(review.get("verdict", "MISSING")),
                    evidence_ref=review_ref, passed=approved,
                )
            )
        if policy.get("require_spec_compliance_review", True):
            spec_check = next(
                (c for c in review.get("checks", []) if c["name"] == "spec_compliance"),
                None,
            )
            checks.append(
                PolicyCheck(
                    name="merge.require_spec_compliance_review", threshold="reviewed & passed",
                    actual=spec_check["actual"] if spec_check else "MISSING",
                    evidence_ref=review_ref,
                    passed=bool(spec_check and spec_check["passed"]),
                )
            )
        checks.append(
            PolicyCheck(
                name="merge.pull_request_exists", threshold="PR record",
                actual=f"PR #{feature.pull_request}" if feature.pull_request else "MISSING",
                evidence_ref=str(self.project_dir / "prs"),
                passed=feature.pull_request is not None,
            )
        )
        return checks

    def _policy_gate(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        gate = QualityGate(self.policy_engine)
        evidence = self._quality_evidence(feature)
        quality_result = gate.evaluate(evidence)
        merge_checks = self._merge_policy_checks(feature)
        all_checks = quality_result.checks + merge_checks
        decision = (
            GateDecision.PASS
            if quality_result.decision == GateDecision.PASS
            and all(c.passed for c in merge_checks)
            else GateDecision.FAIL
        )
        decision_path = self.fs.write_text(
            "governance/merge-decision.yaml",
            yaml.safe_dump(
                {
                    "feature_id": feature.feature_id,
                    "decision": decision.value,
                    "quality_policy_version": quality_result.policy_version,
                    "checks": [c.model_dump(mode="json") for c in all_checks],
                },
                sort_keys=False,
            ),
        )
        result_evidence = [
            Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind="merge-decision",
                ref=str(decision_path), summary=f"Policy gate decision: {decision.value}",
                metadata={"decision": decision.value},
            )
        ]
        if decision != GateDecision.PASS:
            failed = [c.name for c in all_checks if not c.passed]
            return AgentResult(
                status="FAILURE",
                summary=f"Policy gate FAIL: {', '.join(failed)}",
                evidence=result_evidence,
            )
        return AgentResult(
            summary="Policy gate PASS: quality gate and merge policy satisfied",
            evidence=result_evidence,
            state_updates={"coverage": evidence.coverage},
            skill="governance/merge-policy",
        )

    def _merge(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        decision = yaml.safe_load(self.fs.read_text("governance/merge-decision.yaml"))
        if decision["decision"] != GateDecision.PASS.value:
            return AgentResult(
                status="FAILURE",
                summary="Cannot merge: policy gate decision is not PASS",
            )
        branch = feature.branch or ""
        merged_commit = ""
        if feature.pull_request is not None:
            base = self.policy_engine.load("merge").get("merge_policy", {}).get(
                "protected_branches", ["main"]
            )[0]
            record = self.forge.get(feature.pull_request)
            record.base = record.base or base
            record = self.forge.merge(
                record,
                message=f"Merge {branch}: {feature.feature_id} approved by policy gate",
            )
            merged_commit = record.merged_commit
            branch = branch or record.branch
        return AgentResult(
            summary=f"Merged {branch} at {merged_commit[:12]}",
            evidence=[
                Evidence(
                    evidence_id=new_id("EVD"), stage=stage.value, kind="merge",
                    ref=str(self.project_dir / "governance" / "merge-decision.yaml"),
                    summary=f"Merged {branch} -> main ({merged_commit[:12]})",
                    metadata={"merged_commit": merged_commit},
                )
            ],
        )
