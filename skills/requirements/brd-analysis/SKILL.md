# Skill: requirements/brd-analysis

## Purpose
Parse a Business Requirements Document, establish project context and extract
identifiable business requirements with stable IDs (BR-xx).

## Entry criteria
- BRD document available in `projects/<project-id>/intake/`.
- Project record exists in the state store.

## Required context
- BRD text and any supporting data files.
- Existing project vocabulary and prior decisions when available.

## Allowed tools
- filesystem (read intake documents, write requirements.md)
- documents (format conversion)

## Steps
1. Read the BRD and supporting data end-to-end.
2. Extract discrete business requirements; assign stable `BR-xx` IDs.
3. Record scope boundaries, actors, data sources and constraints.
4. Flag ambiguous statements for the ambiguity-detection skill.
5. Write `requirements.md` with provenance (document, section) per requirement.

## Output schema
`requirements.md`: one section per requirement with id, statement, source,
actors, data, constraints, open questions.

## Validation
- Every requirement has a stable ID and a source reference.
- No requirement is a duplicate restatement of another.

## Failure modes
- BRD unreadable/corrupt -> ENVIRONMENT_DEFECT.
- BRD lacks any identifiable requirement -> route to human clarification.
