# Skill: governance/merge-policy

## Purpose
Decide merge progression from immutable evidence: the quality gate plus the
merge policy. Agents recommend; this policy decides.

## Entry criteria
- Review verdict recorded (MERGE_READY); pre-PR quality report available.

## Required context
- `policies/quality.yaml` and `policies/merge.yaml` (versioned thresholds).

## Allowed tools
- policy, git

## Steps
1. Load measured values only from evidence artifacts (pre-PR report, review
   findings) — never from agent summaries.
2. Evaluate the quality gate: build, unit/integration tests, coverage >=80,
   spec compliance >=95, critical security findings <=0, AC pass 100%.
3. Evaluate the merge policy: review APPROVED, spec-compliance review passed,
   PR record exists.
4. Persist `governance/merge-decision.yaml` with every check (threshold,
   actual, evidence ref, decision) before any merge action.
5. Only on PASS: merge the feature branch into the protected branch with a
   no-ff merge commit and mark the PR MERGED with the merge commit SHA.

## Output schema
`governance/merge-decision.yaml`; merge commit on the protected branch.

## Validation
- Decision file exists before the merge commit; FAIL never merges.

## Failure modes
- Any failed check -> FAIL decision, feature stays unmerged, evidence shows
  exactly which threshold failed.
