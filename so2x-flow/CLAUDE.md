# so2x-flow workspace guide

## Core workflow skills
- `flow-init`: bootstrap only
- `flow-feature`: create feature task doc first, then execute
- `flow-qa`: create QA task doc first, then execute
- `flow-review`: review against docs/tasks
- `flow-plan`: planning only, no implementation

## Principles
- Docs first. Do not implement without a task or plan document.
- Treat feature work and QA work as first-class flows.
- Keep orchestration thin.
- Prefer small explicit documents over hidden state.
- Skills are the workflow source of truth; commands are optional wrappers.

## Required docs
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/QA.md`
- `DESIGN.md` (preferred)
- `docs/UI_GUIDE.md` (fallback only)

## Execution rules
- For feature work, create `tasks/feature/<slug>.md` first.
- For QA work, create `tasks/qa/<slug>.md` first.
- `Proposed Steps` must exist before implementation.
- Use `config/ccs-map.yaml` to select `auto`, `ccs`, or `claude` runner.
- In v0, `scripts/execute.py` is validated primarily in `--dry-run` mode.
