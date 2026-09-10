from datetime import date

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Provenance-aware knowledge graph node."""

    node_id: str  # e.g. BR-01, FEAT-01, STORY-01.01, AC-01.01.01, DEC-01
    node_type: str  # ontology NodeType value
    label: str = ""
    source: str = ""  # document/section provenance
    authority: str = "informative"
    version: str = "v1"
    effective_from: date | None = None
    status: str = "ACTIVE"
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Provenance-aware, typed relationship between two nodes."""

    edge_id: str
    from_id: str
    to_id: str
    edge_type: str  # ontology EdgeType value
    source: str = ""
    created_by: str = ""  # agent or ingestion pipeline
    metadata: dict = Field(default_factory=dict)
