"""Increment 1 exit criterion: one feature traverses persisted mocked states
with evidence."""

import shutil
from pathlib import Path

from factory.cli import HAPPY_PATH, run_demo
from factory.models.enums import FactoryState
from factory.orchestrator.events import read_events
from factory.orchestrator.store import FileStateStore

REPO_ROOT = Path(__file__).resolve().parents[2]


async def test_demo_feature_traverses_all_states(tmp_path):
    shutil.copytree(REPO_ROOT / "policies", tmp_path / "policies")

    feature = await run_demo(tmp_path)

    assert feature.current_state == FactoryState.LEARNED
    assert feature.spec_version == "v1"
    assert feature.pull_request == 1
    assert feature.coverage == 86.4
    assert feature.evidence, "expected evidence artifacts"
    for evidence in feature.evidence:
        assert Path(evidence.ref).exists()

    store = FileStateStore(tmp_path / "projects")
    persisted = store.load_feature("PRJ-DEMO", "FEAT-001")
    assert persisted is not None
    assert persisted.current_state == FactoryState.LEARNED

    transitions = store.transitions_for("FEAT-001")
    assert len(transitions) == len(HAPPY_PATH)
    assert [t.to_state for t in transitions] == HAPPY_PATH

    executions = store.executions_for("FEAT-001")
    assert len(executions) == len(HAPPY_PATH)
    assert all(e.status == "SUCCESS" for e in executions)

    events = read_events(tmp_path / "projects" / "PRJ-DEMO" / "execution" / "events.jsonl")
    types = {e.event_type for e in events}
    assert {"AGENT_EXECUTION_STARTED", "AGENT_EXECUTION_COMPLETED", "STATE_TRANSITION"} <= types
