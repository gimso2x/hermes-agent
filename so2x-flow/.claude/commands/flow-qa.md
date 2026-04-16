# /flow-qa

Use this command when a QA issue or bug report needs a document-first fix flow.

## Required flow
1. Read `docs/QA.md` first.
2. Create `tasks/qa/<slug>.md` first.
3. Capture reproduction, expected, actual, minimal fix, and regression checklist.
4. Run QA planner first.
5. Pass planner output to implementer.
6. Save outputs under `outputs/runs/`.

## Rules
- QA is a first-class flow, not a sub-case of feature work.
- Prefer the smallest safe fix.
- Do not skip the QA task document.
- Keep regression notes explicit.

## Minimum task sections
- QA ID
- Reproduction
- Actual
- Expected
- Minimal Fix
- Regression Checklist
