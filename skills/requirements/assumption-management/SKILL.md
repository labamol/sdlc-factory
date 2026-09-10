# Skill: requirements/assumption-management

## Purpose
Record explicit, reviewable assumptions for material-but-assumable ambiguity
so the factory can proceed without silent guessing.

## Entry criteria
- `requirements/clarifications.yaml` exists with classified ambiguity.

## Required context
- Clarifications classified MATERIAL_ASSUMABLE.
- Project engineering standards and approved templates.

## Allowed tools
- filesystem (write assumptions.yaml)

## Steps
1. For each assumable clarification, state the default interpretation.
2. Record rationale, risk level and scope for each assumption.
3. Mark the originating clarification ASSUMED.
4. Invalidate or supersede assumptions when a human decision arrives.

## Output schema
`assumptions.yaml`: list of {asm_id, req_id, statement, rationale, risk,
scope, status}.

## Validation
- Every ACTIVE assumption traces to a requirement and a clarification.
- Superseded assumptions are never deleted, only re-statused.

## Failure modes
- Assumption contradicts an approved decision -> raise blocking clarification.
