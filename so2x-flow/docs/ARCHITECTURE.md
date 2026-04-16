# ARCHITECTURE

## Structure
- `skills/`: workflow definitions
- `docs/`: source-of-truth product and QA docs
- `DESIGN.md`: root design reference
- `prompts/`: role prompt templates
- `tasks/`: generated task documents
- `scripts/execute.py`: thin orchestrator
- `scripts/ccs_runner.py`: runner resolution and command construction
- `outputs/`: run artifacts

## Core Rules
- Docs first.
- No implementation without a task or plan document.
- Keep orchestration thin.
- Feature and QA flows are equal.
- Prefer `DESIGN.md`; only fall back to `docs/UI_GUIDE.md` when needed.

## Data Flow
1. User request enters a mode.
2. Relevant docs and optional design doc are collected.
3. A task or plan document is created if needed.
4. Prompt is built per role.
5. Runner is resolved (`ccs` or `claude`).
6. Role outputs are saved.
7. Run summary is written to `outputs/runs/` or `outputs/plans/`.

## Testing Notes
- v0 focuses on dry-run behavior.
- Each mode should produce stable artifacts.
- Feature and QA should both show planner/qa-planner -> implementer chaining.
- Dry-run output should show requested runner, selected runner, fallback state, and command preview.
