# /flow-init

Use this command to bootstrap a new project workspace for so2x-flow.

## Responsibilities
- Initialize the standard directory structure.
- Create shared docs drafts.
- Create command/settings/hooks skeleton files.
- Make the workspace ready for future `/flow-feature`, `/flow-qa`, `/flow-review`, and `/flow-plan` usage.

## Must create
- `CLAUDE.md`
- `.claude/commands/*`
- `.claude/settings.json`
- `config/ccs-map.yaml`
- `docs/*`
- `prompts/*`
- `tasks/feature/_template.md`
- `tasks/qa/_template.md`
- `scripts/execute.py`
- `scripts/hooks/*`
- `outputs/plans/`
- `outputs/runs/`

## Rules
- Bootstrap only.
- Do not perform feature implementation.
- Do not create branch/commit automation.
- Keep outputs simple and file-based.
