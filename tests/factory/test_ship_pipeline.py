"""Factory tests: BRD through review, policy gate and protected-branch merge."""

import subprocess
from pathlib import Path

import pytest
import yaml

from factory.cli import run_intake
from factory.models.enums import FactoryState

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
BRD = EXAMPLES / "brd" / "sample-brd.md"
TRANSCRIPT = EXAMPLES / "meetings" / "kickoff-transcript.md"


@pytest.mark.asyncio
async def test_ship_reaches_merged_with_governed_merge(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-S1", ship=True
    )
    assert feature.current_state == FactoryState.MERGED
    assert feature.pull_request == 1
    assert feature.coverage == 100.0

    project_dir = tmp_path / "projects" / "PRJ-S1"

    # PR record: opened, then merged, with commit provenance
    pr = yaml.safe_load((project_dir / "prs" / "PR-1.yaml").read_text())
    assert pr["status"] == "MERGED"
    assert pr["branch"] == "feature/feat-000"
    assert pr["commit"] and pr["merged_commit"]
    assert any(f.startswith("workspace/src/") for f in pr["files"])

    # review artifacts with explainable checks and an APPROVED verdict
    findings = yaml.safe_load((project_dir / "review" / "review-findings.yaml").read_text())
    assert findings["verdict"] == "APPROVED"
    assert all(c["threshold"] and c["actual"] for c in findings["checks"])
    assert (project_dir / "review" / "review-report.md").exists()

    # merge decision recorded before merge, PASS, quality + merge policy checks
    decision = yaml.safe_load(
        (project_dir / "governance" / "merge-decision.yaml").read_text()
    )
    assert decision["decision"] == "PASS"
    names = {c["name"] for c in decision["checks"]}
    assert "coverage.minimum" in names
    assert "merge.require_review" in names
    assert all(c["passed"] for c in decision["checks"])

    # the feature branch was actually merged into main with a merge commit
    log = subprocess.run(
        ["git", "log", "--oneline", "-3", "main"],
        cwd=project_dir, capture_output=True, text=True, check=True,
    ).stdout
    assert "Merge feature/feat-000" in log
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_dir, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert branch == "main"
    assert (project_dir / "workspace" / "src").exists()


@pytest.mark.asyncio
async def test_policy_gate_blocks_merge_without_approved_review(tmp_path):
    feature = await run_intake(
        tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-S2", deliver=True
    )
    assert feature.current_state == FactoryState.UNIT_TESTED
    project_dir = tmp_path / "projects" / "PRJ-S2"
    assert not (project_dir / "governance" / "merge-decision.yaml").exists()
    assert not (project_dir / "prs").exists()
