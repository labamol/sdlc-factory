"""Knowledge graph ontology: node types, edge types and allowed shapes.

Edges always point downstream in the delivery flow (requirement -> feature ->
story -> acceptance criterion -> test/code -> deployment), so lineage is an
upstream walk and impact analysis is a downstream walk.
"""

from enum import Enum


class NodeType(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    FEATURE = "FEATURE"
    STORY = "STORY"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    DECISION = "DECISION"
    ASSUMPTION = "ASSUMPTION"
    SPEC = "SPEC"
    CODE_MODULE = "CODE_MODULE"
    TEST = "TEST"
    DEPLOYMENT = "DEPLOYMENT"


class EdgeType(str, Enum):
    DECOMPOSES_INTO = "DECOMPOSES_INTO"  # requirement -> feature -> story -> AC
    SPECIFIED_BY = "SPECIFIED_BY"  # feature -> spec
    RESOLVED_BY = "RESOLVED_BY"  # requirement -> decision
    ASSUMED_BY = "ASSUMED_BY"  # requirement -> assumption
    IMPLEMENTED_BY = "IMPLEMENTED_BY"  # story -> code module
    VERIFIED_BY = "VERIFIED_BY"  # AC -> test
    DEPLOYED_IN = "DEPLOYED_IN"  # code module -> deployment
    SUPERSEDES = "SUPERSEDES"  # decision -> decision
    DEPENDS_ON = "DEPENDS_ON"  # story -> story / module -> module


ALLOWED_EDGES: dict[EdgeType, set[tuple[NodeType, NodeType]]] = {
    EdgeType.DECOMPOSES_INTO: {
        (NodeType.REQUIREMENT, NodeType.FEATURE),
        (NodeType.FEATURE, NodeType.STORY),
        (NodeType.STORY, NodeType.ACCEPTANCE_CRITERION),
    },
    EdgeType.SPECIFIED_BY: {(NodeType.FEATURE, NodeType.SPEC)},
    EdgeType.RESOLVED_BY: {(NodeType.REQUIREMENT, NodeType.DECISION)},
    EdgeType.ASSUMED_BY: {(NodeType.REQUIREMENT, NodeType.ASSUMPTION)},
    EdgeType.IMPLEMENTED_BY: {(NodeType.STORY, NodeType.CODE_MODULE)},
    EdgeType.VERIFIED_BY: {(NodeType.ACCEPTANCE_CRITERION, NodeType.TEST)},
    EdgeType.DEPLOYED_IN: {(NodeType.CODE_MODULE, NodeType.DEPLOYMENT)},
    EdgeType.SUPERSEDES: {(NodeType.DECISION, NodeType.DECISION)},
    EdgeType.DEPENDS_ON: {
        (NodeType.STORY, NodeType.STORY),
        (NodeType.CODE_MODULE, NodeType.CODE_MODULE),
    },
}


def validate_edge(edge_type: EdgeType, from_type: NodeType, to_type: NodeType) -> None:
    if (from_type, to_type) not in ALLOWED_EDGES[edge_type]:
        raise ValueError(
            f"Ontology violation: {edge_type.value} not allowed from "
            f"{from_type.value} to {to_type.value}"
        )
