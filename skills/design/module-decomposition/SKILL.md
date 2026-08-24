# Skill: design/module-decomposition

## Purpose
Turn a specified backlog into a technical design: module boundaries, worker
assignment per feature and test layout, before any code is written.

## Entry criteria
- Features/stories specified; context pack built (KNOWLEDGE_MINED).

## Required context
- Context pack; worker profiles and their tech hints.

## Allowed tools
- filesystem, git

## Steps
1. One module per feature; one entry function per story; tests mirror the
   module layout.
2. Select the worker profile whose tech hints match the feature text; record
   the assignment with its skills.
3. Record data strategy (synthetic, seeded from story IDs).
4. Persist design.md and worker-assignments.yaml as evidence.

## Output schema
`design/design.md`, `design/worker-assignments.yaml`.

## Validation
- Every feature has a worker, module path and test path.

## Failure modes
- No matching worker profile -> default python worker, flag for human review.
