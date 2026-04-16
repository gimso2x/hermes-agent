# ADR

## Principles
- Prefer explicit markdown docs over hidden state.
- Separate planning from implementation.
- Keep the harness lightweight.
- Make skills the workflow source of truth.

## Decision 1
- Decision: define `flow-init`, `flow-feature`, `flow-qa`, `flow-review`, and `flow-plan` as skills.
- Why: the workflow stays reusable across natural-language entrypoints without a heavy command layer.
- Trade-off: slash-command UX becomes optional instead of primary.

## Decision 2
- Decision: use docs as source of truth.
- Why: planning, QA, and review should remain inspectable.
- Trade-off: more up-front writing.

## Decision 3
- Decision: keep `scripts/execute.py` as a thin orchestrator.
- Why: avoid accidental framework bloat.
- Trade-off: advanced automation is deferred.

## Decision 4
- Decision: choose the runner from config and resolve `ccs` vs `claude -p` at runtime.
- Why: keep the harness thin while allowing `ccs` when available.
- Trade-off: fallback behavior must be visible in logs and dry-run output.
