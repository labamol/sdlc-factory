"""Build the project knowledge graph from factory artifacts.

Maps requirements, backlog, decisions, assumptions and specs into
provenance-aware nodes and typed edges following the ontology.
"""

from pathlib import Path

import yaml

from factory.knowledge.graph.ontology import EdgeType, NodeType
from factory.knowledge.graph.store import SqliteGraphStore
from factory.models.graph import GraphEdge, GraphNode


def _load_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text()) or []


def _edge(from_id: str, to_id: str, edge_type: EdgeType, source: str) -> GraphEdge:
    return GraphEdge(
        edge_id=f"E-{edge_type.value}-{from_id}-{to_id}",
        from_id=from_id, to_id=to_id, edge_type=edge_type.value,
        source=source, created_by="graph-ingestion",
    )


def build_project_graph(project_dir: Path, store: SqliteGraphStore) -> tuple[int, int]:
    """Ingest project artifacts; returns (node_count, edge_count)."""
    edges: list[GraphEdge] = []

    requirements = _load_yaml(project_dir / "requirements" / "requirements.yaml")
    for req in requirements:
        store.add_node(
            GraphNode(
                node_id=req["req_id"], node_type=NodeType.REQUIREMENT.value,
                label=req["statement"][:120], source=req.get("source", ""),
                authority="authoritative",
            )
        )

    features = _load_yaml(project_dir / "backlog" / "features.yaml")
    for feat in features:
        store.add_node(
            GraphNode(
                node_id=feat["feature_id"], node_type=NodeType.FEATURE.value,
                label=feat["title"], source="backlog/features.yaml",
                authority="authoritative",
            )
        )
        for req_id in feat.get("requirements", []):
            edges.append(
                _edge(req_id, feat["feature_id"], EdgeType.DECOMPOSES_INTO,
                      "traceability/traceability.yaml")
            )

    stories = _load_yaml(project_dir / "backlog" / "stories.yaml")
    for story in stories:
        store.add_node(
            GraphNode(
                node_id=story["story_id"], node_type=NodeType.STORY.value,
                label=story["title"], source="backlog/stories.yaml",
                authority="authoritative",
            )
        )
        edges.append(
            _edge(story["feature_id"], story["story_id"], EdgeType.DECOMPOSES_INTO,
                  "backlog/stories.yaml")
        )
        for ac in story.get("acceptance_criteria", []):
            store.add_node(
                GraphNode(
                    node_id=ac["ac_id"], node_type=NodeType.ACCEPTANCE_CRITERION.value,
                    label=ac["description"][:120], source="backlog/stories.yaml",
                    authority="authoritative",
                )
            )
            edges.append(
                _edge(story["story_id"], ac["ac_id"], EdgeType.DECOMPOSES_INTO,
                      "backlog/stories.yaml")
            )

    for dec in _load_yaml(project_dir / "decisions" / "decisions.yaml"):
        store.add_node(
            GraphNode(
                node_id=dec["decision_id"], node_type=NodeType.DECISION.value,
                label=dec["decision"][:120], source=dec.get("source", ""),
                authority="binding" if dec.get("status") == "APPROVED" else "informative",
                effective_from=dec.get("effective_from"),
                status=dec.get("status", "APPROVED"),
            )
        )
        if dec.get("requirement"):
            edges.append(
                _edge(dec["requirement"], dec["decision_id"], EdgeType.RESOLVED_BY,
                      dec.get("source", ""))
            )
        if dec.get("supersedes"):
            edges.append(
                _edge(dec["decision_id"], dec["supersedes"], EdgeType.SUPERSEDES,
                      dec.get("source", ""))
            )

    for asm in _load_yaml(project_dir / "requirements" / "assumptions.yaml"):
        store.add_node(
            GraphNode(
                node_id=asm["asm_id"], node_type=NodeType.ASSUMPTION.value,
                label=asm["statement"][:120], source="requirements/assumptions.yaml",
                status=asm.get("status", "ACTIVE"),
            )
        )
        if asm.get("req_id"):
            edges.append(
                _edge(asm["req_id"], asm["asm_id"], EdgeType.ASSUMED_BY,
                      "requirements/assumptions.yaml")
            )

    specs_dir = project_dir / "specs"
    for feat in features:
        spec_file = specs_dir / feat["feature_id"] / "spec.md"
        if spec_file.exists():
            spec_id = f"SPEC-{feat['feature_id']}"
            store.add_node(
                GraphNode(
                    node_id=spec_id, node_type=NodeType.SPEC.value,
                    label=f"Specification for {feat['feature_id']}",
                    source=str(spec_file.relative_to(project_dir)),
                    authority="authoritative",
                )
            )
            edges.append(
                _edge(feat["feature_id"], spec_id, EdgeType.SPECIFIED_BY,
                      str(spec_file.relative_to(project_dir)))
            )

    for edge in edges:
        if store.get_node(edge.from_id) and store.get_node(edge.to_id):
            store.add_edge(edge)
    return store.counts()
