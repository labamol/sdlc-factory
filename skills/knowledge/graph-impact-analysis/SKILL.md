# Skill: knowledge/graph-impact-analysis

## Purpose
Maintain a provenance-aware knowledge graph of the delivery flow and answer
two questions deterministically: "what justifies this artifact?" (lineage)
and "what does changing this artifact affect?" (impact).

## Entry criteria
- Requirements, backlog, decisions, assumptions and specs exist for the project.

## Required context
- The ontology: node types (REQUIREMENT, FEATURE, STORY, ACCEPTANCE_CRITERION,
  DECISION, ASSUMPTION, SPEC, CODE_MODULE, TEST, DEPLOYMENT) and typed edges
  (DECOMPOSES_INTO, SPECIFIED_BY, RESOLVED_BY, ASSUMED_BY, IMPLEMENTED_BY,
  VERIFIED_BY, DEPLOYED_IN, SUPERSEDES, DEPENDS_ON).

## Allowed tools
- graph store (SQLite)
- filesystem (persist graph report)

## Steps
1. Ingest project artifacts as nodes with source, authority, version and
   status provenance.
2. Create only ontology-valid edges; reject shape violations.
3. Point edges downstream in the delivery flow so lineage is an upstream walk
   and impact is a downstream walk.
4. For change requests, run impact(node) to enumerate affected stories, ACs,
   code and deployments before approving the change.
5. For audits, run lineage(node) to produce the provenance chain back to the
   originating requirement and decisions.

## Output schema
`context/graph.db` plus `specs/knowledge-graph.md` report.

## Validation
- Every node carries source provenance.
- Every edge conforms to ALLOWED_EDGES.
- Every acceptance criterion has a lineage path to a requirement.

## Failure modes
- Ontology violation on ingest -> ENVIRONMENT_DEFECT (bad upstream artifact).
- Orphan nodes (no lineage to a requirement) -> flag for human review.
