"""Factory tests for the intake pipeline (BRD -> ... -> KNOWLEDGE_MINED)."""

import subprocess
from pathlib import Path

import pytest
import yaml

from factory.cli import run_intake
from factory.models.enums import FactoryState
from factory.orchestrator.events import read_events

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
BRD = EXAMPLES / "brd" / "sample-brd.md"
TRANSCRIPT = EXAMPLES / "meetings" / "kickoff-transcript.md"


@pytest.mark.asyncio
async def test_blocking_ambiguity_pauses_at_human_input(tmp_path):
    feature = await run_intake(tmp_path, BRD, [], project_id="PRJ-T1")
    assert feature.current_state == FactoryState.HUMAN_INPUT

    project_dir = tmp_path / "projects" / "PRJ-T1"
    request = (project_dir / "hitl" / "clarification-request.md").read_text()
    assert "BR-06" in request
    assert "BR-08" in request

    clarifications = yaml.safe_load(
        (project_dir / "requirements" / "clarifications.yaml").read_text()
    )
    blocking = [c for c in clarifications if c["ambiguity_class"] == "BLOCKING"]
    assert blocking and all(c["status"] == "OPEN" for c in blocking)


@pytest.mark.asyncio
async def test_meeting_decisions_unblock_and_reach_knowledge_mined(tmp_path):
    feature = await run_intake(tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-T2")
    assert feature.current_state == FactoryState.KNOWLEDGE_MINED
    assert feature.spec_version == "v1"
    assert len(feature.requirements) == 8
    assert feature.stories and feature.acceptance_criteria

    project_dir = tmp_path / "projects" / "PRJ-T2"
    decisions = yaml.safe_load((project_dir / "decisions" / "decisions.yaml").read_text())
    assert {d["requirement"] for d in decisions if d["requirement"]} >= {"BR-06", "BR-08"}

    clarifications = yaml.safe_load(
        (project_dir / "requirements" / "clarifications.yaml").read_text()
    )
    blocking = [c for c in clarifications if c["ambiguity_class"] == "BLOCKING"]
    assert blocking and all(c["status"] == "ANSWERED" for c in blocking)

    assumptions = yaml.safe_load(
        (project_dir / "requirements" / "assumptions.yaml").read_text()
    )
    assert assumptions, "material ambiguity should produce recorded assumptions"


@pytest.mark.asyncio
async def test_spec_artifacts_exist_per_feature_and_are_git_versioned(tmp_path):
    await run_intake(tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-T3")
    project_dir = tmp_path / "projects" / "PRJ-T3"

    features = yaml.safe_load((project_dir / "backlog" / "features.yaml").read_text())
    assert len(features) == 3  # one per BRD section
    for feat in features:
        spec_dir = project_dir / "specs" / feat["feature_id"]
        for name in ("spec.md", "clarifications.md", "plan.md", "tasks.md", "analysis.md"):
            assert (spec_dir / name).exists(), f"{feat['feature_id']}/{name} missing"
        assert "PASS" in (spec_dir / "analysis.md").read_text()

    trace = yaml.safe_load(
        (project_dir / "traceability" / "traceability.yaml").read_text()
    )
    traced_reqs = {r for f in trace["features"] for r in f["requirements"]}
    assert traced_reqs == {f"BR-{i:02d}" for i in range(1, 9)}

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=project_dir, capture_output=True, text=True
    ).stdout
    assert "spec(" in log


@pytest.mark.asyncio
async def test_intake_events_and_transitions_are_recorded(tmp_path):
    await run_intake(tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-T4")
    project_dir = tmp_path / "projects" / "PRJ-T4"
    events = read_events(project_dir / "execution" / "events.jsonl")
    types = {e.event_type for e in events}
    assert {"AGENT_EXECUTION_STARTED", "AGENT_EXECUTION_COMPLETED", "STATE_TRANSITION"} <= types
    stages = {e.stage for e in events if e.event_type == "STATE_TRANSITION"}
    assert {
        "INTAKE", "CLARIFICATION", "REQUIREMENTS_READY",
        "DECOMPOSED", "SPECIFIED", "KNOWLEDGE_MINED",
    } <= stages


@pytest.mark.asyncio
async def test_context_pack_produced_with_provenance(tmp_path):
    await run_intake(tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-T5")
    project_dir = tmp_path / "projects" / "PRJ-T5"

    packs = list((project_dir / "context" / "packs").glob("PACK-*.yaml"))
    assert len(packs) == 1
    pack = yaml.safe_load(packs[0].read_text())
    assert pack["used_tokens"] <= pack["budget_tokens"]
    assert pack["items"], "context pack should contain items"
    for scored in pack["items"]:
        item = scored["item"]
        assert item["source"] and item["authority"] and item["version"]

    rendered = (project_dir / "specs" / "context-pack.md").read_text()
    assert "Context Pack" in rendered
