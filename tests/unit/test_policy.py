from pathlib import Path

from factory.models.enums import GateDecision
from factory.policy.engine import PolicyEngine
from factory.policy.quality_gate import QualityEvidence, QualityGate

POLICIES_DIR = Path(__file__).resolve().parents[2] / "policies"


def _gate() -> QualityGate:
    return QualityGate(PolicyEngine(POLICIES_DIR))


def _passing_evidence(**overrides) -> QualityEvidence:
    values = dict(
        build_passed=True,
        unit_tests_passed=True,
        integration_tests_passed=True,
        coverage=86.4,
        spec_compliance=97.0,
        critical_security_findings=0,
        acceptance_criteria_pass_percentage=100.0,
    )
    values.update(overrides)
    return QualityEvidence(**values)


def test_quality_gate_passes():
    result = _gate().evaluate(_passing_evidence())
    assert result.decision == GateDecision.PASS
    assert not result.failed_checks


def test_quality_gate_fails_on_low_coverage():
    result = _gate().evaluate(_passing_evidence(coverage=42.0))
    assert result.decision == GateDecision.FAIL
    assert [c.name for c in result.failed_checks] == ["coverage.minimum"]


def test_quality_gate_fails_on_security_findings():
    result = _gate().evaluate(_passing_evidence(critical_security_findings=1))
    assert result.decision == GateDecision.FAIL


def test_quality_gate_fails_on_failed_build():
    result = _gate().evaluate(_passing_evidence(build_passed=False))
    assert result.decision == GateDecision.FAIL


def test_checks_are_explainable():
    result = _gate().evaluate(_passing_evidence())
    for check in result.checks:
        assert check.threshold != ""
        assert check.actual != ""
