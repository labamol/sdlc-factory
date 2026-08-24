# Skill: learning/episodic-memory

## Purpose
Aggregate episodic memory and human feedback into a durable learning record
at LEARNED, and propose governed promotion candidates from recurring
successful repairs — without ever mutating skills or templates directly.

## Entry criteria
- Feature reached STORY_COMPLETED; episodes/feedback may be empty.

## Required context
- `learning/episodes.yaml`, `learning/feedback.yaml`
- `policies/learning.yaml` (promotion thresholds, approval requirement).

## Allowed tools
- filesystem

## Steps
1. Load all episodes and feedback (feedback must carry a named author).
2. Group REPAIRED episodes by signature; propose a promotion candidate when a
   signature has at least `min_successful_repairs` successes and no existing
   candidate (idempotent per signature).
3. Candidates stay PROPOSED while `require_human_approval: true`; approval
   and rejection both require a named human and are persisted in
   `learning/promotions.yaml`.
4. Write `learning/learning-record.yaml`: episode totals and per-class
   counts, feedback totals by rating, promotions proposed/total/approved and
   the active policy.

## Output schema
`learning/learning-record.yaml`; candidates in `learning/promotions.yaml`.

## Validation
- Promotion never auto-applies; APPROVED requires `approved_by`.
- The learning record references only measured episode/feedback data.

## Failure modes
- Feedback without an author is rejected at write time.
- Unknown candidate IDs fail approval/rejection loudly.
