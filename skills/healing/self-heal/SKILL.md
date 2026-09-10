# Skill: healing/self-heal

## Purpose
Diagnose a failing test/build report into the failure taxonomy, route the
repair to its owning agent, apply autonomous repairs deterministically, and
record every episode so recurring failures are recognized.

## Entry criteria
- Feature in DIAGNOSE with a failed test report under `testing/`.

## Required context
- `policies/quality.yaml` (`max_self_heal_attempts`, default 3).
- Backlog (`backlog/features.yaml`, `backlog/stories.yaml`) for regeneration.
- Episodic memory (`learning/episodes.yaml`) for known repairs.

## Allowed tools
- filesystem, terminal, pytest, git

## Steps
1. Classify the report with the ordered taxonomy rules (first match wins) and
   derive a stable signature (addresses/numbers/paths normalized, hashed).
2. Look up the repair route for the failure class; consult episodic memory
   for prior REPAIRED episodes with the same signature.
3. Enforce the attempt budget: attempts so far + 1 must not exceed
   `max_self_heal_attempts`; otherwise fail so the orchestrator escalates.
4. Persist `healing/diagnosis-<attempt>.yaml` (class, signature, route,
   attempt, budget) before any repair.
5. Autonomous classes only (CODE, TEST, DATA, FACTORY_TEMPLATE): regenerate
   the implementation, tests or synthetic data from deterministic templates.
   Non-autonomous classes (SPEC*, DEPENDENCY, ENVIRONMENT, CONFIGURATION)
   record an ESCALATED episode and fail — never guess.
6. Record the episode (feature, stage, class, signature, action, owner,
   attempt); the loop marks it REPAIRED/ESCALATED from the measured retest.

## Output schema
`healing/diagnosis-<n>.yaml`; episode appended to `learning/episodes.yaml`.

## Validation
- Every DIAGNOSE pass leaves a diagnosis artifact and an episode.
- No repair without a persisted diagnosis; no attempt beyond the budget.

## Failure modes
- Budget exhausted or non-autonomous class -> FAILURE, human escalation.
- Missing test report -> FAILURE (nothing to diagnose).
