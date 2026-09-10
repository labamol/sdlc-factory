# Skill: implementation/python-fastapi

## Purpose
Implement Python service/API stories: one module per feature, one entry
function per story, explicit input validation and stable identifiers.

## Entry criteria
- Tasks READY with story IDs and acceptance criteria; tests already designed.

## Required context
- Context pack for the feature (spec, decisions, assumptions).
- Worker assignment from the design.

## Allowed tools
- filesystem, git, terminal, pytest

## Steps
1. Read the story contract (title, description, acceptance criteria).
2. Generate/extend `src/<feature_module>.py`; keep functions stdlib-only and
   deterministic; validate inputs and raise `ServiceError` on contract
   violations (covers negative/boundary criteria).
3. Embed traceability: story ID and AC IDs in docstrings.
4. Run the pre-PR quality pipeline before handing off to test execution.

## Output schema
`workspace/src/<feature_module>.py` with one function per story.

## Validation
- Module compiles; pre-PR checks pass; every story has a function.

## Failure modes
- Unclear contract -> SPEC_AMBIGUITY (route to clarification, not guessing).
