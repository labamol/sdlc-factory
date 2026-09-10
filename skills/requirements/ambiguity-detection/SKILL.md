# Skill: requirements/ambiguity-detection

## Purpose
Classify ambiguity in extracted requirements into blocking, material-but-
assumable and implementation-detail classes, so the factory pauses only when
it genuinely must.

## Entry criteria
- `requirements/requirements.yaml` exists with stable BR-xx IDs.

## Required context
- Requirement statements with provenance.
- Prior decisions and active assumptions for the project.

## Allowed tools
- filesystem (write clarifications.yaml)

## Steps
1. Scan each requirement statement for ambiguity markers.
2. Classify: BLOCKING (TBD/unknown/conflict/pending decision),
   MATERIAL_ASSUMABLE (vague qualifiers like fast/scalable/user-friendly),
   IMPLEMENTATION_DETAIL (logging, naming, code style, library choice).
3. Raise one clarification per ambiguous requirement with the trigger phrase.
4. Blocking clarifications stay OPEN and pause scope; assumable ones proceed
   with a recorded assumption; detail-level ones apply engineering standards.

## Output schema
`clarifications.yaml`: list of {clr_id, req_id, question, ambiguity_class,
trigger, status, answer}.

## Validation
- Every clarification references an existing requirement.
- No blocking clarification is silently marked ASSUMED.

## Failure modes
- Requirement text missing -> ENVIRONMENT_DEFECT.
- Every requirement blocking -> route whole intake to human input.
