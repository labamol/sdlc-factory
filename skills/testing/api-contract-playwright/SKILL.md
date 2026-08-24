# Skill: testing/api-contract-playwright

## Purpose
Verify API contracts and browser flows: schema-level API assertions plus
Playwright end-to-end coverage of user-facing acceptance criteria.

## Entry criteria
- Deployed or locally-served application; AC list available.

## Required context
- API contract from the spec; synthetic accounts/data (never real data).

## Allowed tools
- terminal, playwright, pytest

## Steps
1. API: assert status codes, response schema and error contracts per AC.
2. E2E: one Playwright spec per user-facing AC; selectors by role/label,
   not CSS position.
3. Run against the deployment produced by the release stage; record traces
   on failure.
4. Persist reports as functional-test evidence for the validation gate.

## Output schema
`e2e/*.spec.ts` and functional-report artifacts.

## Validation
- Specs map 1:1 to user-facing ACs; reports stored as evidence.

## Failure modes
- Environment unreachable -> ENVIRONMENT_DEFECT (not a code defect).
