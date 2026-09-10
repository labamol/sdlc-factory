import pytest

from factory.knowledge.graph.ontology import EdgeType, NodeType, validate_edge
from factory.knowledge.graph.store import SqliteGraphStore
from factory.knowledge.graph.traversal import impact, lineage, traverse
from factory.models.graph import GraphEdge, GraphNode


def _node(node_id: str, node_type: NodeType, **kwargs) -> GraphNode:
    return GraphNode(node_id=node_id, node_type=node_type.value, **kwargs)


def _edge(from_id: str, to_id: str, edge_type: EdgeType) -> GraphEdge:
    return GraphEdge(
        edge_id=f"E-{edge_type.value}-{from_id}-{to_id}",
        from_id=from_id, to_id=to_id, edge_type=edge_type.value,
    )


def _delivery_graph() -> SqliteGraphStore:
    store = SqliteGraphStore(":memory:")
    store.add_node(_node("BR-01", NodeType.REQUIREMENT, label="Submit feedback",
                         source="brd.md#s1", authority="authoritative"))
    store.add_node(_node("FEAT-01", NodeType.FEATURE))
    store.add_node(_node("STORY-01.01", NodeType.STORY))
    store.add_node(_node("AC-01.01.01", NodeType.ACCEPTANCE_CRITERION))
    store.add_node(_node("DEC-01", NodeType.DECISION, authority="binding"))
    store.add_edge(_edge("BR-01", "FEAT-01", EdgeType.DECOMPOSES_INTO))
    store.add_edge(_edge("FEAT-01", "STORY-01.01", EdgeType.DECOMPOSES_INTO))
    store.add_edge(_edge("STORY-01.01", "AC-01.01.01", EdgeType.DECOMPOSES_INTO))
    store.add_edge(_edge("BR-01", "DEC-01", EdgeType.RESOLVED_BY))
    return store


def test_ontology_rejects_invalid_edge_shapes():
    validate_edge(EdgeType.DECOMPOSES_INTO, NodeType.REQUIREMENT, NodeType.FEATURE)
    with pytest.raises(ValueError, match="Ontology violation"):
        validate_edge(EdgeType.DECOMPOSES_INTO, NodeType.DECISION, NodeType.TEST)


def test_store_enforces_ontology_and_known_nodes():
    store = _delivery_graph()
    with pytest.raises(ValueError, match="Ontology violation"):
        store.add_edge(_edge("DEC-01", "AC-01.01.01", EdgeType.DECOMPOSES_INTO))
    with pytest.raises(ValueError, match="unknown node"):
        store.add_edge(_edge("BR-01", "MISSING", EdgeType.DECOMPOSES_INTO))
    store.close()


def test_nodes_carry_provenance():
    store = _delivery_graph()
    node = store.get_node("BR-01")
    assert node is not None
    assert node.source == "brd.md#s1"
    assert node.authority == "authoritative"
    store.close()


def test_impact_walks_downstream():
    store = _delivery_graph()
    assert impact(store, "BR-01") == ["FEAT-01", "DEC-01", "STORY-01.01", "AC-01.01.01"]
    assert impact(store, "STORY-01.01") == ["AC-01.01.01"]
    store.close()


def test_lineage_walks_upstream_to_requirement():
    store = _delivery_graph()
    assert lineage(store, "AC-01.01.01") == ["STORY-01.01", "FEAT-01", "BR-01"]
    store.close()


def test_traverse_respects_max_depth_and_unknown_start():
    store = _delivery_graph()
    shallow = traverse(store, "BR-01", max_depth=1)
    assert {e.to_id for e in shallow} == {"FEAT-01", "DEC-01"}
    with pytest.raises(ValueError, match="Unknown node"):
        traverse(store, "NOPE")
    store.close()
