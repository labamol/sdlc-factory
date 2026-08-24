# Skill: implementation/react-frontend

## Purpose
Implement React frontend stories: typed components, controlled forms,
API-client separation and accessibility defaults.

## Entry criteria
- Tasks READY tagged frontend/UI; API contract available from the spec.

## Required context
- Context pack (spec, design tokens, API contract).

## Allowed tools
- filesystem, git, terminal, playwright

## Steps
1. One component per story under `src/components/`; props typed.
2. Forms are controlled; validation mirrors the API contract; errors surfaced
   inline (negative criteria).
3. API access goes through a single client module; no fetch calls in
   components.
4. Add Playwright coverage for each acceptance criterion before hand-off.

## Output schema
`src/components/<Story>.tsx` plus `e2e/<story>.spec.ts`.

## Validation
- Build passes; Playwright specs exist per AC.

## Failure modes
- Missing API contract -> SPEC_DEFECT (return to specification).
