"""Deterministic multi-dimensional PR review.

Four review dimensions, each producing explainable policy checks:
code review (maintainability findings), security review, specification
compliance review and coverage review. The verdict is APPROVED only when no
blocking findings remain and every dimension passes its threshold.
"""

import re
from pathlib import Path

from pydantic import BaseModel, Field

from factory.models.story import Story
from factory.policy.engine import PolicyCheck
from factory.quality.prepr import (
    SECURITY_PATTERNS,
    run_pre_pr_checks,
)

TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)
BARE_EXCEPT_PATTERN = re.compile(r"^\s*except\s*:\s*$")


class ReviewFinding(BaseModel):
    finding_id: str
    category: str  # code | security | spec | coverage
    severity: str  # CRITICAL | MAJOR | MINOR
    file: str = ""
    line: int = 0
    message: str


class ReviewReport(BaseModel):
    verdict: str = "CHANGES_REQUESTED"  # APPROVED | CHANGES_REQUESTED
    findings: list[ReviewFinding] = Field(default_factory=list)
    checks: list[PolicyCheck] = Field(default_factory=list)

    @property
    def blocking_findings(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity in ("CRITICAL", "MAJOR")]


def _py_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py")) if directory.exists() else []


def _code_findings(workspace: Path) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    counter = 0

    def add(category: str, severity: str, file: str, line: int, message: str) -> None:
        nonlocal counter
        counter += 1
        findings.append(
            ReviewFinding(
                finding_id=f"RF-{counter:03d}", category=category,
                severity=severity, file=file, line=line, message=message,
            )
        )

    for path in _py_files(workspace / "src"):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].lstrip().startswith(('"""', '#', "'''")):
            add("code", "MINOR", path.name, 1, "module missing docstring header")
        for number, line in enumerate(lines, start=1):
            if TODO_PATTERN.search(line):
                add("code", "MAJOR", path.name, number, "unresolved TODO/FIXME marker")
            if BARE_EXCEPT_PATTERN.match(line):
                add("code", "MAJOR", path.name, number, "bare except swallows errors")
            for pattern, label in SECURITY_PATTERNS:
                if pattern.search(line):
                    add("security", "CRITICAL", path.name, number, label)
    return findings


def run_review(workspace: Path, stories: list[Story]) -> ReviewReport:
    findings = _code_findings(workspace)
    pre_pr = run_pre_pr_checks(workspace, stories)
    by_name = {c.name: c for c in pre_pr.checks}

    blocking = [f for f in findings if f.severity in ("CRITICAL", "MAJOR")]
    checks = [
        PolicyCheck(
            name="code_review_blocking_findings", threshold="0",
            actual=str(len(blocking)),
            evidence_ref=";".join(f"{f.file}:{f.line}" for f in blocking[:5]),
            passed=not blocking,
        ),
        by_name["security_critical_findings"],
        by_name["spec_compliance"],
        by_name["coverage"],
        by_name["unit_tests"],
    ]
    verdict = "APPROVED" if all(c.passed for c in checks) else "CHANGES_REQUESTED"
    return ReviewReport(verdict=verdict, findings=findings, checks=checks)


def render_review_md(report: ReviewReport, feature_id: str) -> str:
    lines = [
        f"# Review Report — {feature_id}",
        "",
        f"Verdict: **{report.verdict}**",
        "",
        "## Checks",
        "",
        "| check | threshold | actual | decision |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            f"| {check.name} | {check.threshold} | {check.actual} | "
            f"{'PASS' if check.passed else 'FAIL'} |"
        )
    lines += ["", "## Findings", ""]
    if not report.findings:
        lines.append("No findings.")
    for finding in report.findings:
        lines.append(
            f"- **{finding.severity}** [{finding.category}] "
            f"{finding.file}:{finding.line} — {finding.message}"
        )
    lines.append("")
    return "\n".join(lines)
