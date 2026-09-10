# Skill: requirements/meeting-decision-extraction

## Purpose
Normalize meeting transcripts into durable decision records with provenance,
authority, status and supersession — transcripts are never used directly as
coding context.

## Entry criteria
- Transcript file(s) available under `intake/meetings/`.

## Required context
- Open clarifications awaiting answers.
- Existing decision records (for supersession checks).

## Allowed tools
- filesystem (read transcripts, write decisions.yaml)

## Steps
1. Parse speaker/role lines and detect decision cues
   (decided/agreed/confirmed/approved/let's go with).
2. Attach the preceding question when the decision answers one.
3. Resolve FEAT-xx / BR-xx references to link decisions to scope.
4. Record decided_by, source, confidence, status and effective date.
5. Mark matching open clarifications ANSWERED.

## Output schema
`decisions.yaml`: list of {decision_id, source, feature, requirement, type,
question, decision, decided_by, confidence, status, effective_from,
supersedes, source_version}.

## Validation
- Every decision has provenance (source) and an author (decided_by).
- Superseding decisions reference the superseded decision_id.

## Failure modes
- Transcript with no detectable decisions -> no-op, clarifications stay OPEN.
- Conflicting decisions in one transcript -> blocking clarification.
