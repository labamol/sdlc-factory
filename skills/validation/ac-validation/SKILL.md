# Skill: validation/ac-validation

## Purpose
Prove the deployed artifact satisfies every acceptance criterion: functional
tests run against the deployment (never the workspace), each AC maps to a
test outcome, and the tracker closes only on a PASS decision.

## Entry criteria
- Artifact DEPLOYED with passing smoke tests.

## Required context
- Deployed tests, backlog stories/ACs, `policies/deployment.yaml`
  (mandatory_ac_pass_percentage).

## Allowed tools
- pytest/playwright (scoped shell), jira (tracker), filesystem

## Steps
1. Functional: run the packaged test suite inside the deployment directory
   with per-test verbose output; persist `validation/functional-report.txt`.
2. AC mapping: resolve each AC ID to its test (AC IDs are embedded in test
   names) and record PASSED / FAILED / MISSING per criterion — a missing
   test is a failure, not a skip.
3. Decision: compute the mandatory-AC pass percentage and compare against
   the policy threshold (default 100%); persist
   `validation/validation-report.yaml` with per-AC results.
4. Closure: only on PASS, mark stories DONE and close their requirements in
   `tracker/completion.yaml` with links to the validation evidence.

## Output schema
Functional report, per-AC validation report, tracker completion record.

## Validation
- Every AC appears exactly once in the report; closure only after PASS.

## Failure modes
- Any mandatory AC below threshold -> FAIL, stories stay open.
