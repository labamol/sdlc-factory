# Skill: knowledge/context-pack-building

## Purpose
Assemble a versioned, budgeted context pack for a task: the right knowledge,
at the right authority, within the token budget, with full provenance.

## Entry criteria
- Project artifacts exist (requirements, decisions, assumptions, specs).

## Required context
- The task/query (feature title plus requirement IDs).
- Current repo commit for provenance.

## Allowed tools
- knowledge store (SQL + exact + vector search)
- filesystem (persist pack artifacts)

## Steps
1. Ingest project artifacts into the knowledge store with authority levels
   (approved decisions binding; requirements/assumptions/specs authoritative;
   docs and code informative).
2. Retrieve candidates by vector similarity and exact/ID match.
3. Filter superseded versions out; never mix old and new decisions.
4. Detect same-subject conflicts; resolve by authority or surface unresolved.
5. Rerank: similarity + exact-match bonus + authority weight.
6. Fit to the token budget, admitting binding items first, never truncating
   mid-item.
7. Persist the pack (YAML + rendered markdown) with pack_id, spec version,
   repo commit, filters and per-item provenance.

## Output schema
`context/packs/<pack-id>.yaml` and `specs/context-pack.md`.

## Validation
- Every included item carries source, authority, version and score reasons.
- No superseded item appears in the pack.
- used_tokens <= budget_tokens.

## Failure modes
- Nothing to ingest -> ENVIRONMENT_DEFECT (upstream stages incomplete).
- Unresolved equal-authority conflict -> surface in pack; may block later gates.
