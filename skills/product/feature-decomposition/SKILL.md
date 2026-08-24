# Skill: product/feature-decomposition

## Purpose
Decompose baselined requirements into features, stories and acceptance
criteria with stable traceability IDs (BR -> FEAT -> STORY -> AC).

## Entry criteria
- Requirements baselined (no open blocking clarification).

## Required context
- `requirements/requirements.yaml` with sections and provenance.
- Approved decisions affecting scope.

## Allowed tools
- filesystem (write backlog and traceability files)
- jira (tracker mutation, when configured)

## Steps
1. Group requirements into cohesive features (by BRD section by default).
2. Derive one story per requirement with a testable description.
3. Write at least one positive and one negative/boundary acceptance
   criterion per story.
4. Emit the machine-readable traceability map.

## Output schema
`backlog/features.yaml`, `backlog/stories.yaml`,
`traceability/traceability.yaml` (BR -> FEAT -> STORY -> AC).

## Validation
- Every requirement appears in exactly one feature.
- Every story has at least one mandatory acceptance criterion.
- Traceability covers 100% of requirements.

## Failure modes
- Requirement not groupable -> assign to a General feature and flag.
