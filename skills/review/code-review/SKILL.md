# Skill: review/code-review

## Purpose
Review a PR across four dimensions — code quality, security, specification
compliance and coverage — producing explainable findings and policy checks,
never an unexplained approve/reject.

## Entry criteria
- PR record exists (PR_CREATED); pre-PR quality report available.

## Required context
- Story contracts and acceptance criteria; the changed files.

## Allowed tools
- github (PR registry), scanners, filesystem

## Steps
1. Code: flag unresolved TODO/FIXME, bare except, missing module docstrings;
   classify severity (CRITICAL / MAJOR / MINOR).
2. Security: scan changed source for eval/exec, shell=True and hardcoded
   credentials; every hit is CRITICAL.
3. Spec compliance: every story function and AC ID must appear in the diff's
   src+tests; report the percentage against the >=95% threshold.
4. Coverage: every story function must be exercised by tests (>=80%).
5. Record each dimension as a policy check (threshold, actual, evidence,
   decision) and persist review-report.md + review-findings.yaml.
6. Verdict is APPROVED only when no CRITICAL/MAJOR findings remain and all
   checks pass; otherwise CHANGES_REQUESTED routes back to IMPLEMENTING.

## Output schema
`review/review-report.md`, `review/review-findings.yaml`, PR status update.

## Validation
- Every finding has file/line/severity; verdict consistent with checks.

## Failure modes
- Missing pre-PR report -> return to BUILT (evidence gap, not opinion).
