# Skill: specification/spec-kit-lifecycle

## Purpose
Run the Spec Kit lifecycle (specify -> clarify -> plan -> tasks -> analyze)
per feature and version the resulting artifacts in Git. Spec Kit is a
specification service inside the factory, not the whole factory.

## Entry criteria
- Backlog decomposed: features, stories and acceptance criteria exist.

## Required context
- `backlog/features.yaml`, `backlog/stories.yaml`.
- `requirements/requirements.yaml`, `requirements/assumptions.yaml`.
- `decisions/decisions.yaml` (approved decisions folded into the spec).

## Allowed tools
- filesystem (write specs/<feature-id>/ artifacts)
- speckit (lifecycle execution)
- git (spec versioning)

## Steps
1. specify: render spec.md from requirements, stories and ACs.
2. clarify: fold approved decisions and active assumptions in.
3. plan: render the architecture/technology plan.
4. tasks: render implementation and test tasks per story/AC.
5. analyze: verify every requirement, story and AC is covered; fail closed.
6. Commit `specs/<feature-id>/` with the spec version.

## Output schema
`specs/<feature-id>/{spec.md, clarifications.md, plan.md, tasks.md,
analysis.md}` plus a Git commit per spec version.

## Validation
- analysis.md reports PASS with zero uncovered items.
- The spec commit hash is recorded as evidence metadata.

## Failure modes
- Coverage gap found by analyze -> SPEC_AMBIGUITY, route to clarification.
- Git commit fails -> artifacts remain, evidence notes missing version.
