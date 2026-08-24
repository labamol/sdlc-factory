"""Deterministic quality gate evaluated before merge."""

from pydantic import BaseModel, Field

from factory.models.enums import GateDecision
from factory.policy.engine import PolicyCheck, PolicyEngine, PolicyResult


class QualityEvidence(BaseModel):
    """Measured values gathered from immutable evidence, not agent summaries."""

    build_passed: bool = False
    unit_tests_passed: bool = False
    integration_tests_passed: bool = False
    coverage: float = 0.0
    spec_compliance: float = 0.0
    critical_security_findings: int = 0
    acceptance_criteria_pass_percentage: float = 0.0
    evidence_refs: dict[str, str] = Field(default_factory=dict)


class QualityGate:
    def __init__(self, engine: PolicyEngine, policy_name: str = "quality") -> None:
        self.engine = engine
        self.policy_name = policy_name

    def evaluate(self, evidence: QualityEvidence) -> PolicyResult:
        policy = self.engine.load(self.policy_name)
        gate = policy.get("quality_gate", {})
        refs = evidence.evidence_refs

        checks = [
            PolicyCheck(
                name="build.must_pass",
                threshold=str(gate.get("build", {}).get("must_pass", True)),
                actual=str(evidence.build_passed),
                evidence_ref=refs.get("build", ""),
                passed=evidence.build_passed or not gate.get("build", {}).get("must_pass", True),
            ),
            PolicyCheck(
                name="unit_tests.must_pass",
                threshold=str(gate.get("unit_tests", {}).get("must_pass", True)),
                actual=str(evidence.unit_tests_passed),
                evidence_ref=refs.get("unit_tests", ""),
                passed=evidence.unit_tests_passed
                or not gate.get("unit_tests", {}).get("must_pass", True),
            ),
            PolicyCheck(
                name="integration_tests.must_pass",
                threshold=str(gate.get("integration_tests", {}).get("must_pass", True)),
                actual=str(evidence.integration_tests_passed),
                evidence_ref=refs.get("integration_tests", ""),
                passed=evidence.integration_tests_passed
                or not gate.get("integration_tests", {}).get("must_pass", True),
            ),
            PolicyCheck(
                name="coverage.minimum",
                threshold=str(gate.get("coverage", {}).get("minimum", 80)),
                actual=str(evidence.coverage),
                evidence_ref=refs.get("coverage", ""),
                passed=evidence.coverage >= gate.get("coverage", {}).get("minimum", 80),
            ),
            PolicyCheck(
                name="spec_compliance.minimum",
                threshold=str(gate.get("spec_compliance", {}).get("minimum", 95)),
                actual=str(evidence.spec_compliance),
                evidence_ref=refs.get("spec_compliance", ""),
                passed=evidence.spec_compliance
                >= gate.get("spec_compliance", {}).get("minimum", 95),
            ),
            PolicyCheck(
                name="critical_security_findings.maximum",
                threshold=str(gate.get("critical_security_findings", {}).get("maximum", 0)),
                actual=str(evidence.critical_security_findings),
                evidence_ref=refs.get("security", ""),
                passed=evidence.critical_security_findings
                <= gate.get("critical_security_findings", {}).get("maximum", 0),
            ),
            PolicyCheck(
                name="acceptance_criteria.mandatory_pass_percentage",
                threshold=str(
                    gate.get("acceptance_criteria", {}).get("mandatory_pass_percentage", 100)
                ),
                actual=str(evidence.acceptance_criteria_pass_percentage),
                evidence_ref=refs.get("acceptance_criteria", ""),
                passed=evidence.acceptance_criteria_pass_percentage
                >= gate.get("acceptance_criteria", {}).get("mandatory_pass_percentage", 100),
            ),
        ]
        decision = (
            GateDecision.PASS if all(c.passed for c in checks) else GateDecision.FAIL
        )
        return PolicyResult(
            policy_name=self.policy_name,
            policy_version=str(policy.get("version", "1")),
            decision=decision,
            checks=checks,
        )
