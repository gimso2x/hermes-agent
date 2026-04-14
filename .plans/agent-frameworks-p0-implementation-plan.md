# Agent Frameworks P0 Implementation Plan

> For Hermes: implement this in small, verified slices. Do not widen scope. The repo is currently dirty (`?? download.html`), so this plan must stay surgical and avoid unrelated files.

**Goal:** Translate the useful bones from `awesome-agent-frameworks` into Hermes without cargo-culting another framework: clearer contract-first product surfaces, stronger security-boundary explanation, and more queryable autonomous-execution status.

**Architecture:** Keep this as a docs-and-surface pass, not a core runtime rewrite. Reuse existing Hermes mechanisms (`tools/approval.py`, `tools/process_registry.py`, `cron/scheduler.py`, `hermes_cli/status.py`, `hermes_cli/doctor.py`) and add thin shared helpers only where repetition already exists. The first slice should improve what users can understand and verify before inventing new subsystems.

**Tech Stack:** Python, Hermes CLI/gateway/cron surfaces, pytest.

---

## Constraints and non-goals

- Do not touch unrelated dirty file: `download.html`.
- Do not introduce a new workflow engine, queue system, or agent runtime.
- Do not copy ZeroClaw/IronClaw/TinyAGI directory structures or terminology.
- Do not add speculative proactive agents or a giant “agent OS” layer.
- Prefer one shared helper per concern plus narrow call-site wiring.
- User-facing text should stay plain and readable in Telegram/CLI, not enum soup.

---

## Current repo reality checked first

Validated in `/home/ubuntu/.hermes/hermes-agent`:

- repo root: `/home/ubuntu/.hermes/hermes-agent`
- remotes:
  - `gimso2x https://github.com/gimso2x/hermes-agent.git`
  - `origin https://github.com/NousResearch/hermes-agent.git`
- dirty worktree before planning:
  - `?? download.html`

This means implementation must avoid collateral edits and stage only feature files.

---

## Why this plan and not something dumber

The external repo was useful for three things only:

1. `contract-first explanation` — users should be able to tell what Hermes components exist and what boundaries they have.
2. `security boundary visibility` — dangerous tool execution is less scary when the block/approval/redaction boundaries are explicit.
3. `autonomous execution observability` — cron/background/process behavior should tell users what happened, what is running, and what to do next.

Everything else — huge Agent OS fantasies, branded ontology, framework cosplay — is noise.

---

## Target outcome for P0

By the end of this plan, Hermes should have:

1. A small shared contract-surface helper that summarizes the active runtime shape in human terms:
   - model/provider
   - terminal backend
   - enabled tool behavior signals
   - memory/provider mode
2. A clearer security-boundary section in CLI status/doctor that explains:
   - dangerous command approval exists
   - what kinds of actions trigger it
   - what secret redaction / protection surfaces exist
3. A more queryable autonomous-execution section that distinguishes:
   - cron jobs scheduled vs paused vs failed delivery
   - background processes running vs exited vs watch-disabled
   - what the user should run next (`process poll`, `process wait`, `/status`, etc.)
4. Focused tests that lock these surfaces so they do not drift.

---

## Files likely to change

### Product code
- `hermes_cli/status.py`
- `hermes_cli/doctor.py`
- `tools/approval.py`
- `tools/process_registry.py`
- `cron/scheduler.py`
- `model_tools.py` (only if a shared contract-summary helper belongs here)
- `agent/` new helper module only if repeated formatting cannot stay inside `hermes_cli/`

### Tests
- `tests/hermes_cli/test_status.py`
- `tests/hermes_cli/test_doctor.py`
- `tests/gateway/test_status.py`
- `tests/cron/test_scheduler.py`
- `tests/tools/` new focused test file if approval/process summary helpers become reusable modules

### Docs
- `AGENTS.md` only if the final implementation adds or changes a stable development rule or canonical surface
- otherwise keep docs changes out of P0

---

## Slice order

Implement in this order:

1. Contract-first runtime summary
2. Security-boundary surfacing
3. Autonomous execution observability
4. Final polish and regression tests

That order matters. Users trust execution more when they can first see the shape of the system, then the guardrails, then the runtime state.

---

## Task 1: Inventory current status/doctor/runtime surfaces before editing

**Objective:** Confirm the exact seams already present so P0 can reuse them instead of inventing new ones.

**Files:**
- Read: `hermes_cli/status.py`
- Read: `hermes_cli/doctor.py`
- Read: `tools/approval.py`
- Read: `tools/process_registry.py`
- Read: `cron/scheduler.py`
- Read: `tests/hermes_cli/test_status.py`
- Read: `tests/hermes_cli/test_doctor.py`
- Read: `tests/gateway/test_status.py`
- Read: `tests/cron/test_scheduler.py`

**Step 1: Identify existing user-facing sections in status/doctor**

Capture where these already exist:
- environment/model/provider summary
- memory/provider reporting
- gateway/runtime reporting
- warnings and next-step hints

**Step 2: Identify security-relevant helpers already present**

Confirm exact reusable functions/patterns:
- `tools.approval.detect_dangerous_command`
- approval pattern descriptions in `DANGEROUS_PATTERNS`
- redaction helpers already used by status/auth display

**Step 3: Identify runtime-state seams already present**

Confirm how runtime state is already represented:
- `ProcessRegistry` session fields (`exited`, `exit_code`, `watch_patterns`, `notify_on_complete`, `watch disabled` metadata)
- cron job delivery/status fields in `cron/scheduler.py`

**Step 4: Write a short implementation note in the branch scratchpad or commit message draft**

Do not create a new tracked file for this. The goal is to avoid wandering.

**Verification:**
- You can name the exact functions and files that will carry each P0 slice.

---

## Task 2: Add a shared contract-summary helper

**Objective:** Give status/doctor one canonical human-readable summary of Hermes’ active runtime contract.

**Files:**
- Create: `agent/runtime_contract_summary.py` or `hermes_cli/runtime_contract_summary.py`
- Modify: `hermes_cli/status.py`
- Modify: `hermes_cli/doctor.py`
- Test: `tests/hermes_cli/test_status.py`
- Test: `tests/hermes_cli/test_doctor.py`

**Preferred module shape:**

```python
from __future__ import annotations

from typing import Any


def summarize_runtime_contract(*, config: dict, provider_label: str, terminal_backend: str,
                               memory_mode: str, tool_signals: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append(f"모델/프로바이더: {provider_label}")
    lines.append(f"터미널 백엔드: {terminal_backend}")
    lines.append(f"메모리 모드: {memory_mode}")
    if tool_signals.get("mutating_tools"):
        lines.append(f"변경 가능 도구: {tool_signals['mutating_tools']}")
    if tool_signals.get("background_runtime"):
        lines.append("자율 실행: cron / background process 지원")
    return lines
```

**Implementation rules:**
- Do not make this a huge abstraction layer.
- It should be pure and formatting-only.
- It should produce human-readable Korean labels.
- Status and doctor should both use it so the meaning stays aligned.

**Step 1: Write failing tests**

Add tests asserting that status/doctor output now includes a compact “runtime contract” section with:
- provider/model signal
- terminal backend signal
- memory signal
- autonomous execution support signal

Suggested assertions:

```python
assert "Runtime Contract" in output
assert "모델/프로바이더:" in output
assert "터미널 백엔드:" in output
assert "메모리 모드:" in output
```

**Step 2: Run focused tests and verify failure**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py tests/hermes_cli/test_doctor.py -q`

Expected:
- FAIL because the new section does not exist yet.

**Step 3: Implement the helper and wire it into status/doctor**

Preferred status placement:
- after Environment / Provider summary, before lower-level API key dump

Preferred doctor placement:
- after Python/config checks, before long dependency/provider detail sections

**Step 4: Run focused tests and verify pass**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py tests/hermes_cli/test_doctor.py -q`

Expected:
- PASS for the new contract summary assertions.

---

## Task 3: Surface security boundaries instead of making users infer them

**Objective:** Make approval and secret-protection boundaries visible in CLI status/doctor.

**Files:**
- Modify: `tools/approval.py` (only if one tiny export/helper is needed)
- Modify: `hermes_cli/status.py`
- Modify: `hermes_cli/doctor.py`
- Test: `tests/hermes_cli/test_status.py`
- Test: `tests/hermes_cli/test_doctor.py`
- Optional create: `tests/tools/test_approval_summary.py`

**Preferred helper addition in `tools/approval.py`:**

```python
def approval_policy_summary() -> dict[str, object]:
    return {
        "dangerous_pattern_count": len(DANGEROUS_PATTERNS),
        "examples": [
            "recursive delete",
            "git reset --hard",
            "force push",
            "write into /etc/",
        ],
        "session_scoped": True,
    }
```

Keep this tiny. The goal is not policy logic changes; only a reusable summary.

**Status output target:**
Add a `Security Boundaries` section with lines like:
- dangerous command approval enabled
- examples of blocked/high-risk operations
- secret/credential redaction active where applicable
- next step for explicit approval path when relevant

**Doctor output target:**
Add a `Security Boundaries` check block that can say:
- approval engine available
- dangerous pattern inventory loaded
- if helpers fail to import, show a warning

**Step 1: Write failing tests**

Add assertions like:

```python
assert "Security Boundaries" in output
assert "dangerous command approval" in output.lower()
assert "git reset --hard" in output or "recursive delete" in output
```

**Step 2: Run focused tests and verify failure**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py tests/hermes_cli/test_doctor.py -q`

Expected:
- FAIL because the section is missing.

**Step 3: Implement the summary wiring**

Rules:
- No security theater.
- Do not claim protections that do not exist.
- Use current actual mechanisms from `tools/approval.py` and existing redaction behavior only.
- Prefer “막는 것 / 확인받는 것 / 숨기는 것” wording over abstract jargon.

**Step 4: Re-run focused tests**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py tests/hermes_cli/test_doctor.py -q`

Expected:
- PASS.

---

## Task 4: Make background process status more queryable to humans

**Objective:** Expose background runtime state with direct next actions instead of opaque process internals.

**Files:**
- Modify: `tools/process_registry.py` (formatting/helper only if needed)
- Modify: `hermes_cli/status.py`
- Test: `tests/hermes_cli/test_status.py`
- Optional create: `tests/tools/test_process_registry_summary.py`

**Desired behavior:**
Status should communicate, in plain terms:
- whether background processes are currently tracked
- how many are running vs finished-recently
- whether any watch patterns were disabled due to overload
- the next command the user should run

**Preferred helper shape:**

```python
def summarize_process_registry_state(registry) -> dict[str, int | bool | str]:
    return {
        "running": ...,
        "finished_recent": ...,
        "watch_disabled": ...,
        "hint": "Use process(action='poll') or process(action='wait') for active jobs.",
    }
```

**Step 1: Write failing tests**

Test either helper output directly or status rendering with a monkeypatched registry.

Suggested assertions:
- `Background Runtime` section appears
- counts for running/finished are shown
- hint text includes `process(action='poll')` or equivalent human wording

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py -q`

**Step 3: Implement minimal summary logic**

Rules:
- Reuse `ProcessRegistry` state; do not redesign the registry.
- Avoid exposing raw internal field names.
- Prefer short, human labels.
- If there are zero tracked processes, say so cleanly.

**Step 4: Re-run tests**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py -q`

---

## Task 5: Make cron runtime state and delivery meaning more explicit

**Objective:** Tell users what cron is doing without making them read scheduler internals.

**Files:**
- Modify: `cron/scheduler.py` (helper only if needed)
- Modify: `hermes_cli/status.py`
- Modify: `hermes_cli/doctor.py` only if a health check belongs there
- Test: `tests/cron/test_scheduler.py`
- Test: `tests/hermes_cli/test_status.py`
- Test: `tests/gateway/test_status.py`

**Desired behavior:**
Surface these distinctions explicitly:
- scheduled vs paused jobs
- last run vs next run meaning
- last delivery error vs execution error
- local-only jobs vs auto-delivered jobs

**Preferred helper shape:**

```python
def summarize_cron_runtime(jobs: list[dict]) -> dict[str, object]:
    return {
        "scheduled": ...,
        "paused": ...,
        "local_only": ...,
        "delivery_failures": ...,
        "next_hint": "Use 'hermes cron list' to inspect jobs in detail.",
    }
```

**Step 1: Write failing tests**

Add tests asserting that status output includes a cron/autonomous execution section with counts and direct next-step hints.

Suggested assertions:
- `Autonomous Execution` or `Cron Runtime` section exists
- paused count is distinct from scheduled count
- delivery error count is visible if present
- list command hint is present

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/cron/test_scheduler.py tests/hermes_cli/test_status.py tests/gateway/test_status.py -q`

**Step 3: Implement the summary wiring**

Rules:
- Use job metadata already saved by cron.
- Do not add new cron persistence fields unless an existing test gap proves it is required.
- Focus on rendering and aggregation first.

**Step 4: Re-run focused tests**

Run:
`source venv/bin/activate && pytest tests/cron/test_scheduler.py tests/hermes_cli/test_status.py tests/gateway/test_status.py -q`

---

## Task 6: Align wording across status, doctor, and gateway-facing status surfaces

**Objective:** Stop each surface from inventing its own meaning for the same runtime state.

**Files:**
- Modify: `hermes_cli/status.py`
- Modify: `hermes_cli/doctor.py`
- Modify: `tests/gateway/test_status.py`
- Modify: `tests/hermes_cli/test_status.py`
- Modify: `tests/hermes_cli/test_doctor.py`

**What must align:**
- runtime contract labels
- security boundary labels
- cron/background runtime labels
- next-action hints

**Step 1: Identify duplicated phrases in the three surfaces**

Find lines that talk about the same concept with different wording.

**Step 2: Normalize the wording**

Preferred style:
- short Korean label
- one factual line
- one next-action hint if relevant

Bad style:
- giant paragraphs
- internal enum labels
- contradictory terminology (`managed`, `active`, `running`, `healthy`) for the same thing

**Step 3: Re-run tests for all touched surfaces**

Run:
`source venv/bin/activate && pytest tests/hermes_cli/test_status.py tests/hermes_cli/test_doctor.py tests/gateway/test_status.py -q`

---

## Task 7: Final regression run for the whole P0 slice

**Objective:** Verify that the P0 surface work did not break adjacent runtime behavior.

**Files:**
- No new files
- Use the existing touched files only

**Run:**

```bash
source venv/bin/activate && pytest \
  tests/hermes_cli/test_status.py \
  tests/hermes_cli/test_doctor.py \
  tests/gateway/test_status.py \
  tests/cron/test_scheduler.py -q
```

If any new helper landed under `tests/tools/`, include it too.

**Expected:**
- all targeted tests pass
- no unrelated dirty files changed

**Verification commands:**

```bash
git status --short
git diff -- hermes_cli/status.py hermes_cli/doctor.py tools/approval.py tools/process_registry.py cron/scheduler.py
```

Expected:
- only intended files plus tests appear
- `download.html` remains untouched

---

## Acceptance criteria

This plan is complete when all of the following are true:

- `hermes status` explains the runtime contract in plain language.
- `hermes status` and/or `hermes doctor` clearly expose security boundaries that already exist.
- cron/background runtime state is surfaced with direct next-step hints.
- wording is consistent across status/doctor/gateway surfaces.
- focused tests cover the new sections and pass.
- no speculative architecture rewrite was introduced.

---

## Risks and tradeoffs

### Risk 1: Turning status into a novel
The fix is to keep each section short: state, count, next action. Not essays.

### Risk 2: Security theater
If the product does not actually block or redact something, do not imply it does. This P0 is about surfacing existing guardrails, not inventing fake ones.

### Risk 3: Helper sprawl
If a helper is used once, keep it inline. Only extract formatting logic when at least two surfaces share the same meaning.

### Risk 4: Scope creep into runtime redesign
The second someone starts talking about a new scheduler, agent kernel, or proactive hand system, the plan has already gone to shit. Stop and cut scope back down.

---

## Non-goals for this P0

- proactive always-on agent workers
- new queue/persistence backend
- new plugin framework
- UI redesign
- provider/backend expansion
- deep memory architecture changes

---

## Recommended commit boundaries

1. `feat: add runtime contract summary to status and doctor`
2. `feat: surface security boundaries in cli diagnostics`
3. `feat: clarify cron and background runtime state`
4. `test: align status and doctor runtime wording`

If a slice is tiny, squash 3 and 4. But do not bury everything in one mystery commit.
