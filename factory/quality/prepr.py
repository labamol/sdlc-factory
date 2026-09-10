"""Pre-PR quality pipeline.

Deterministic checks run inside the feature workspace before any PR exists:
formatting/lint, build, unit tests, security scan, spec compliance and a
coverage measure. Every check records threshold, actual and evidence so the
policy gate decision is explainable.
"""

import py_compile
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from factory.implementation.codegen import story_function_name
from factory.models.story import Story
from factory.policy.engine import PolicyCheck
from factory.tools.shell import ShellTool

SECURITY_PATTERNS = [
    (re.compile(r"\beval\s*\("), "use of eval()"),
    (re.compile(r"\bexec\s*\("), "use of exec()"),
    (re.compile(r"shell\s*=\s*True"), "subprocess with shell=True"),
    (re.compile(r"(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
     "hardcoded credential"),
]
MAX_LINE_LENGTH = 100


class PrePrReport(BaseModel):
    checks: list[PolicyCheck] = Field(default_factory=list)
    test_output: str = ""

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def _py_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py")) if directory.exists() else []


def _check_format(workspace: Path) -> PolicyCheck:
    violations = []
    for path in _py_files(workspace / "src") + _py_files(workspace / "tests"):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if line != line.rstrip() or "\t" in line or len(line) > MAX_LINE_LENGTH:
                violations.append(f"{path.name}:{number}")
    return PolicyCheck(
        name="formatting", threshold="0 violations", actual=f"{len(violations)} violations",
        evidence_ref=";".join(violations[:5]), passed=not violations,
    )


def _check_build(workspace: Path) -> PolicyCheck:
    errors = []
    for path in _py_files(workspace / "src"):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path.name}: {exc.msg}")
    return PolicyCheck(
        name="build", threshold="compiles", actual="ok" if not errors else errors[0],
        evidence_ref="src", passed=not errors,
    )


def _check_security(workspace: Path) -> PolicyCheck:
    findings = []
    for path in _py_files(workspace / "src"):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            for pattern, label in SECURITY_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.name}:{number} {label}")
    return PolicyCheck(
        name="security_critical_findings", threshold="0",
        actual=str(len(findings)), evidence_ref=";".join(findings[:5]),
        passed=not findings,
    )


def _check_tests(workspace: Path) -> tuple[PolicyCheck, str]:
    shell = ShellTool(workspace)
    result = shell.run([sys.executable, "-m", "pytest", "tests", "-q", "--rootdir", "."])
    output = result.stdout + result.stderr
    return (
        PolicyCheck(
            name="unit_tests", threshold="all pass",
            actual="pass" if result.ok else "fail",
            evidence_ref="tests", passed=result.ok,
        ),
        output,
    )


def _check_spec_compliance(workspace: Path, stories: list[Story]) -> PolicyCheck:
    src_text = "".join(p.read_text() for p in _py_files(workspace / "src"))
    test_text = "".join(p.read_text() for p in _py_files(workspace / "tests"))
    expected = [story_function_name(s.story_id) for s in stories]
    expected += [ac.ac_id for s in stories for ac in s.acceptance_criteria]
    satisfied = sum(
        1 for name in expected if name in src_text or name in test_text
    )
    percent = 100.0 * satisfied / len(expected) if expected else 0.0
    return PolicyCheck(
        name="spec_compliance", threshold=">=95%", actual=f"{percent:.1f}%",
        evidence_ref="src+tests", passed=percent >= 95.0,
    )


def _check_coverage(workspace: Path, stories: list[Story]) -> PolicyCheck:
    test_text = "".join(p.read_text() for p in _py_files(workspace / "tests"))
    functions = [story_function_name(s.story_id) for s in stories]
    covered = sum(1 for f in functions if f in test_text)
    percent = 100.0 * covered / len(functions) if functions else 0.0
    return PolicyCheck(
        name="coverage", threshold=">=80%", actual=f"{percent:.1f}%",
        evidence_ref="tests", passed=percent >= 80.0,
    )


def run_pre_pr_checks(workspace: Path, stories: list[Story]) -> PrePrReport:
    checks = [
        _check_format(workspace),
        _check_build(workspace),
        _check_security(workspace),
    ]
    tests_check, output = _check_tests(workspace)
    checks.append(tests_check)
    checks.append(_check_spec_compliance(workspace, stories))
    checks.append(_check_coverage(workspace, stories))
    return PrePrReport(checks=checks, test_output=output)
