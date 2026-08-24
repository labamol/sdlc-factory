"""Factory tests: the intake pipeline produces a queryable knowledge graph."""

from pathlib import Path

import pytest

from factory.cli import run_intake
from factory.knowledge.graph.ontology import NodeType
from factory.knowledge.graph.store import SqliteGraphStore
from factory.knowledge.graph.traversal import impact, lineage

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
BRD = EXAMPLES / "brd" / "sample-brd.md"
TRANSCRIPT = EXAMPLES / "meetings" / "kickoff-transcript.md"


@pytest.mark.asyncio
async def test_graph_built_from_intake_artifacts(tmp_path):
    await run_intake(tmp_path, BRD, [TRANSCRIPT], project_id="PRJ-G1")
    project_dir = tmp_path / "projects" / "PRJ-G1"

    store = SqliteGraphStore(project_dir / "context" / "graph.db")
    try:
        assert len(store.nodes_by_type(NodeType.REQUIREMENT)) == 8
        assert len(store.nodes_by_type(NodeType.FEATURE)) == 3
        assert len(store.nodes_by_type(NodeType.STORY)) == 8
        assert len(store.nodes_by_type(NodeType.ACCEPTANCE_CRITERION)) == 16
        assert store.nodes_by_type(NodeType.DECISION)
        assert len(store.nodes_by_type(NodeType.SPEC)) == 3

        # every AC has lineage back to a requirement
        for ac in store.nodes_by_type(NodeType.ACCEPTANCE_CRITERION):
            upstream = lineage(store, ac.node_id)
            assert any(u.startswith("BR-") for u in upstream), ac.node_id

        # a resolved requirement's impact includes its decision and backlog
        downstream = impact(store, "BR-06")
        assert any(d.startswith("DEC-") for d in downstream)
        assert any(d.startswith("STORY-") for d in downstream)
    finally:
        store.close()

    report = (project_dir / "specs" / "knowledge-graph.md").read_text()
    assert "BR-06" in report and "impact" in report
