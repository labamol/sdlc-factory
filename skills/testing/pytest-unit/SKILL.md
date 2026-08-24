# Skill: testing/pytest-unit

## Purpose
Design and run unit/acceptance tests: one test per acceptance criterion,
generated before implementation (test-first), executed through the scoped
shell tool with a durable report.

## Entry criteria
- Stories with acceptance criteria exist (TASKS_READY).

## Required context
- Story contracts and synthetic data fixtures.

## Allowed tools
- filesystem, pytest, terminal

## Steps
1. Name tests after AC IDs (`test_ac_01_01_01`) for traceability.
2. Positive criteria exercise the story function with synthetic records;
   negative criteria assert the contract error type.
3. Keep tests independent: reset module state via an autouse fixture.
4. Execute with `pytest -q`; persist the full output as the test report
   evidence; never edit tests to make them pass.

## Output schema
`workspace/tests/test_<feature>.py`, `testing/test-plan.yaml`, report txt.

## Validation
- Every AC has exactly one test; report evidence recorded.

## Failure modes
- Failing tests -> DIAGNOSE with failure classification (never silently skip).
