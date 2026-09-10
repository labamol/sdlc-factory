"""Policy engine: agents may recommend; policy decides progression.

Each check compares a threshold from a versioned policy file against a
measured value with an evidence reference, so every gate decision is
explainable (threshold, actual, evidence, decision).
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from factory.models.enums import GateDecision


class PolicyCheck(BaseModel):
    name: str
    threshold: str
    actual: str
    evidence_ref: str = ""
    passed: bool


class PolicyResult(BaseModel):
    policy_name: str
    policy_version: str = "1"
    decision: GateDecision
    checks: list[PolicyCheck] = Field(default_factory=list)

    @property
    def failed_checks(self) -> list[PolicyCheck]:
        return [c for c in self.checks if not c.passed]


class PolicyEngine:
    """Loads YAML policies and evaluates measured values against them."""

    def __init__(self, policies_dir: Path) -> None:
        self.policies_dir = policies_dir

    def load(self, policy_name: str) -> dict:
        path = self.policies_dir / f"{policy_name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Policy not found: {path}")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
