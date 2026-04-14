# Archon P0 Execution Surface Implementation Plan

> For Hermes: implement this in small, verified slices. Do not widen scope. The repo is currently dirty (`package-lock.json`, `download.html`), so this plan must stay surgical and avoid unrelated files.

**Goal:** Bring Archon’s useful operational ideas into Hermes without importing Archon’s YAML religion: clearer stage-aware execution summaries, stronger target/dirty-repo surfacing, and consistent user-facing status meaning across cron and gateway paths.

**Architecture:** Add one new formatter module for deterministic execution summaries, thread it into existing cron/gateway final-response surfaces, and add a tiny repo-scope/dirty-tree inspector helper that can be reused by gateway-facing execution paths later. Keep the first slice read-only on product architecture: new helper module, small call-site wiring, focused tests, no broad framework rewrite.

**Tech Stack:** Python, existing Hermes gateway/cron/runtime surfaces, pytest.

---

## Constraints and non-goals

- Do not touch unrelated dirty files: `package-lock.json`, `download.html`.
- Do not invent a new workflow engine.
- Do not add YAML workflow files or Archon-style command DSL.
- Do not attempt a giant “harness framework” rewrite in one pass.
- Prefer one new helper module plus narrow integrations.

---

## Current repo reality checked first

Validated in `/home/ubuntu/.hermes/hermes-agent`:

- repo root: `/home/ubuntu/.hermes/hermes-agent`
- remote: `origin https://github.com/NousResearch/hermes-agent.git`
- dirty worktree before any code work:
  - `M package-lock.json`
  - `?? download.html`

This means implementation must stay isolated and explicitly avoid collateral edits.

---

## Target outcome for P0

By the end of this plan, Hermes should have:

1. A shared deterministic formatter for execution-style results that can produce short human summaries such as:
   - 현재 단계
   - 완료 단계 수
   - 남은 단계 수
   - 막힌 이유 / 다음 액션
2. Cron delivery using that shared formatter instead of blindly shipping raw `final_response`.
3. Gateway/background completion path using the same summary meaning set for long-running completions.
4. A small repo-scope inspector helper that surfaces:
   - target repo root
   - remote
   - dirty status
   for future harness/multi-repo execution calls.
5. Tests that lock the behavior so this doesn’t rot immediately.

---

## Task 1: Create a deterministic execution-summary formatter module

**Objective:** Introduce one shared place for stage-aware execution summaries instead of scattering ad-hoc formatting across cron/gateway paths.

**Files:**
- Create: `agent/deterministic_reports.py`
- Test: `tests/agent/test_deterministic_reports.py`

**Step 1: Write failing tests for summary formatting**

Create `tests/agent/test_deterministic_reports.py` with focused unit tests for three helpers:

- `summarize_execution_result(result: dict, *, platform: str | None = None) -> str`
- `summarize_cron_result(result: dict) -> str`
- `extract_stage_metadata(result: dict) -> dict`

Minimum failing tests:

1. raw string `final_response` passes through unchanged when no structured hints exist
2. JSON-ish dict result with fields like `current_stage`, `completed_stages`, `remaining_stages`, `next_action`, `blocked_reason` becomes a short Korean summary
3. Telegram mode is shorter than default mode
4. empty/garbage input falls back safely instead of crashing

Suggested test skeleton:

```python
from agent.deterministic_reports import (
    summarize_execution_result,
    summarize_cron_result,
    extract_stage_metadata,
)


def test_summarize_execution_result_passes_plain_text_through():
    result = {"final_response": "작업 완료"}
    assert summarize_execution_result(result) == "작업 완료"


def test_extract_stage_metadata_reads_common_fields():
    result = {
        "final_response": "done",
        "structured_result": {
            "current_stage": "구현",
            "completed_stages": ["계획"],
            "remaining_stages": ["검증"],
            "next_action": "테스트 실행",
            "blocked_reason": "pytest 미실행",
        },
    }
    meta = extract_stage_metadata(result)
    assert meta["current_stage"] == "구현"
    assert meta["completed_count"] == 1
    assert meta["remaining_count"] == 1
    assert meta["next_action"] == "테스트 실행"
    assert meta["blocked_reason"] == "pytest 미실행"


def test_summarize_execution_result_renders_stage_summary_in_korean():
    result = {
        "final_response": "작업 완료",
        "structured_result": {
            "current_stage": "검증",
            "completed_stages": ["계획", "구현"],
            "remaining_stages": ["리뷰"],
            "next_action": "리뷰 반영",
        },
    }
    text = summarize_execution_result(result)
    assert "현재 단계: 검증" in text
    assert "완료: 2" in text
    assert "남음: 1" in text
    assert "다음: 리뷰 반영" in text


def test_summarize_cron_result_prefers_short_human_summary():
    result = {
        "final_response": '{"status":"ok","current_stage":"검증"}',
        "structured_result": {
            "current_stage": "검증",
            "completed_stages": ["계획", "구현"],
            "remaining_stages": [],
            "next_action": "배포 없음",
        },
    }
    text = summarize_cron_result(result)
    assert "현재 단계: 검증" in text
    assert "{" not in text
```

**Step 2: Run the tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/agent/test_deterministic_reports.py -q`

Expected:
- FAIL with `ModuleNotFoundError` or import failure because the new module does not exist yet.

**Step 3: Implement the formatter module**

Create `agent/deterministic_reports.py`.

Implementation rules:

- Keep it tiny and pure.
- No side effects.
- Accept partial dicts and malformed data.
- Prefer user-facing Korean labels.
- If no stage metadata exists, return the original `final_response` string.
- If `final_response` looks like raw JSON but structured metadata exists, prefer the formatted summary.

Minimum module shape:

```python
from __future__ import annotations

import json
from typing import Any


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _coerce_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def extract_stage_metadata(result: dict | None) -> dict:
    result = result or {}
    structured = result.get("structured_result") if isinstance(result, dict) else {}
    if not isinstance(structured, dict):
        structured = {}

    current_stage = _coerce_str(structured.get("current_stage") or result.get("current_stage"))
    completed = _coerce_list(structured.get("completed_stages") or result.get("completed_stages"))
    remaining = _coerce_list(structured.get("remaining_stages") or result.get("remaining_stages"))
    next_action = _coerce_str(structured.get("next_action") or result.get("next_action"))
    blocked_reason = _coerce_str(structured.get("blocked_reason") or result.get("blocked_reason"))

    return {
        "current_stage": current_stage,
        "completed_stages": completed,
        "remaining_stages": remaining,
        "completed_count": len(completed),
        "remaining_count": len(remaining),
        "next_action": next_action,
        "blocked_reason": blocked_reason,
    }


def summarize_execution_result(result: dict | None, *, platform: str | None = None) -> str:
    result = result or {}
    final_response = _coerce_str(result.get("final_response"))
    meta = extract_stage_metadata(result)

    has_stage_signal = any([
        meta["current_stage"],
        meta["completed_count"],
        meta["remaining_count"],
        meta["next_action"],
        meta["blocked_reason"],
    ])
    if not has_stage_signal:
        return final_response

    lines = []
    if final_response and not final_response.startswith("{"):
        lines.append(final_response)
    if meta["current_stage"]:
        lines.append(f"현재 단계: {meta['current_stage']}")
    lines.append(f"완료: {meta['completed_count']}")
    lines.append(f"남음: {meta['remaining_count']}")
    if meta["blocked_reason"]:
        lines.append(f"막힘: {meta['blocked_reason']}")
    if meta["next_action"]:
        lines.append(f"다음: {meta['next_action']}")

    if platform == "telegram":
        return "\n".join(lines[:4])
    return "\n".join(lines)


def summarize_cron_result(result: dict | None) -> str:
    return summarize_execution_result(result)
```

Do not overbuild beyond this first slice.

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/agent/test_deterministic_reports.py -q`

Expected:
- PASS

**Step 5: Commit**

Do not commit yet if later tasks are incomplete. This repo is already dirty. Stage only the plan-related files when the whole slice is done.

---

## Task 2: Wire the cron path to the shared formatter

**Objective:** Stop cron from shipping raw or JSON-ish `final_response` blindly when a stage-aware summary can be produced.

**Files:**
- Modify: `cron/scheduler.py` around the `result.get("final_response")` handling near lines 830-851
- Test: `tests/cron/test_scheduler.py`

**Step 1: Write failing cron tests**

Add focused tests in `tests/cron/test_scheduler.py` for the helper path that builds the delivered response.

Minimum tests:

1. structured stage metadata produces formatted human text
2. plain text final response remains unchanged
3. empty final response still behaves as no-delivery / no-crash according to existing semantics

If an isolated helper does not exist yet in `scheduler.py`, add a narrow one during implementation instead of testing giant control flow directly.

Suggested target helper:

```python
def _select_delivery_response(result: dict) -> str:
    ...
```

Suggested failing test shape:

```python
from cron.scheduler import _select_delivery_response


def test_select_delivery_response_prefers_formatted_stage_summary():
    result = {
        "final_response": '{"status":"ok"}',
        "structured_result": {
            "current_stage": "검증",
            "completed_stages": ["계획", "구현"],
            "remaining_stages": [],
            "next_action": "배포 없음",
        },
    }
    text = _select_delivery_response(result)
    assert "현재 단계: 검증" in text
    assert "{" not in text
```

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/cron/test_scheduler.py -q`

Expected:
- FAIL for missing helper or old behavior.

**Step 3: Implement minimal cron integration**

In `cron/scheduler.py`:

1. import the new formatter:
```python
from agent.deterministic_reports import summarize_cron_result
```

2. add helper:
```python
def _select_delivery_response(result: dict) -> str:
    final_response = result.get("final_response", "") or ""
    formatted = summarize_cron_result(result)
    return formatted if formatted else final_response
```

3. replace the direct assignment near line ~830:
```python
final_response = _select_delivery_response(result)
```

Important:
- Preserve existing empty-response delivery semantics.
- Keep `logged_response` logic intact.
- Do not widen `_deliver_result()` itself yet.

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/cron/test_scheduler.py tests/agent/test_deterministic_reports.py -q`

Expected:
- PASS

---

## Task 3: Wire the gateway completion path to the same summary meaning

**Objective:** Make long-running gateway completion notifications use the same deterministic summary semantics instead of ad-hoc raw `final_response` only.

**Files:**
- Modify: `gateway/run.py` around the background completion path near lines 5335-5365
- Modify: `gateway/run.py` around the main conversation result normalization near lines 8018-8134
- Test: `tests/gateway/test_status.py`
- Test: `tests/gateway/test_status_command.py` only if needed

**Step 1: Write failing gateway tests**

Add focused tests around a tiny normalization helper rather than the full gateway monster.

Create or extract a helper in `gateway/run.py`, for example:

```python
def _normalize_user_facing_final_response(result: dict, *, platform: str | None = None) -> str:
    ...
```

Minimum tests:

1. background completion path uses formatted summary when structured stage metadata exists
2. Telegram mode uses the shorter variant
3. plain text final response remains unchanged

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/gateway/test_status.py -q`

Expected:
- FAIL because the helper or formatting behavior does not exist.

**Step 3: Implement minimal gateway integration**

In `gateway/run.py`:

1. import formatter:
```python
from agent.deterministic_reports import summarize_execution_result
```

2. add helper close to other small gateway formatting helpers:

```python
def _normalize_user_facing_final_response(result: dict, *, platform: str | None = None) -> str:
    final_response = (result or {}).get("final_response", "") or ""
    formatted = summarize_execution_result(result or {}, platform=platform)
    return formatted if formatted else final_response
```

3. use it in the background completion path near line ~5343:
```python
response = _normalize_user_facing_final_response(result, platform=platform_key) if result else ""
```

4. use it in the main conversation result path before returning the final payload near line ~8018:
```python
final_response = _normalize_user_facing_final_response(result, platform=platform_key)
```

Keep existing MEDIA tag handling after that normalization.

Important:
- Do not break image/media extraction.
- Do not rewrite the stream consumer.
- Do not invent a new response object contract.

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/gateway/test_status.py tests/agent/test_deterministic_reports.py -q`

Expected:
- PASS

---

## Task 4: Add a repo-scope / dirty-tree inspector helper for future execution surfaces

**Objective:** Start P0-2 without boiling the ocean: create a reusable helper that reports target repo root, remotes, and dirty state for user-facing execution surfaces.

**Files:**
- Create: `agent/execution_scope.py`
- Test: `tests/agent/test_execution_scope.py`

**Step 1: Write failing tests**

Create tests for a small helper:

```python
def inspect_repo_scope(cwd: str | None = None) -> dict:
    ...
```

Minimum cases:

1. non-git directory returns `is_git_repo: False`
2. git repo returns root path
3. dirty file is detected
4. remote list is returned safely

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/agent/test_execution_scope.py -q`

Expected:
- FAIL because the module doesn’t exist.

**Step 3: Implement the helper**

Create `agent/execution_scope.py` with a tiny subprocess-based helper using `git`.

Suggested shape:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def inspect_repo_scope(cwd: str | None = None) -> dict:
    cwd = cwd or str(Path.cwd())
    ok, root = _run_git(["rev-parse", "--show-toplevel"], cwd)
    if not ok:
        return {
            "cwd": cwd,
            "is_git_repo": False,
            "repo_root": "",
            "dirty": False,
            "status_lines": [],
            "remotes": [],
        }

    _, status = _run_git(["status", "--short"], cwd)
    _, remotes = _run_git(["remote", "-v"], cwd)
    status_lines = [line for line in status.splitlines() if line.strip()]
    remote_lines = [line for line in remotes.splitlines() if line.strip()]
    return {
        "cwd": cwd,
        "is_git_repo": True,
        "repo_root": root,
        "dirty": bool(status_lines),
        "status_lines": status_lines,
        "remotes": remote_lines,
    }
```

Do not wire this into every path yet. That is task 5.

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/agent/test_execution_scope.py -q`

Expected:
- PASS

---

## Task 5: Surface repo scope in one user-visible execution path only

**Objective:** Use the new repo inspector in one small place so the feature becomes real without a broad rewrite.

**Files:**
- Modify: `gateway/run.py`
- Test: `tests/gateway/test_status.py`

**Step 1: Write failing test**

Pick one narrow path: background completion header or gateway status response assembly.

Example expectation:
- when a result includes execution metadata and the current cwd is a dirty git repo, the user-facing completion text gets a short prefix like:
  - `대상 리포: /repo`
  - `작업 트리: 변경 있음`

Do not shove full `git status` into the chat. One short line is enough.

**Step 2: Run test to verify failure**

Run:
`source venv/bin/activate && pytest tests/gateway/test_status.py -q`

Expected:
- FAIL because the repo-scope line does not exist.

**Step 3: Implement minimal surfacing**

In `gateway/run.py`:

- import `inspect_repo_scope`
- only in one targeted execution-completion path, prepend a compact repo summary when `is_git_repo` is true:

```python
scope = inspect_repo_scope()
prefix_lines = []
if scope.get("is_git_repo"):
    prefix_lines.append(f"대상 리포: {scope['repo_root']}")
    prefix_lines.append("작업 트리: 변경 있음" if scope.get("dirty") else "작업 트리: 깨끗함")
```

Keep it tiny. This is a proof slice, not the final universal policy.

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/gateway/test_status.py tests/agent/test_execution_scope.py -q`

Expected:
- PASS

---

## Task 6: Add config/docs touchpoints only if the code now needs them

**Objective:** Update config/docs only if task 1-5 required new knobs.

**Files:**
- Modify if needed: `hermes_cli/config.py`
- Modify if needed: `AGENTS.md`
- Modify if needed: `README.md` or `website/docs/...`

**Step 1: Decide if config is actually needed**

Default answer: probably no new config for the first slice.

Only add config if you truly need something like:
- `display.include_repo_scope_summary`
- `display.telegram_execution_summary_compact`

If no config is needed, skip this task.

**Step 2: If config is added, update all required touchpoints**

Per repo rules:
- add to `DEFAULT_CONFIG`
- bump `_config_version`
- add tests if migration behavior matters
- update docs/AGENTS only if user-facing behavior changed materially

**Step 3: Run focused tests**

If config changed:
`source venv/bin/activate && pytest tests/hermes_cli -q`

Otherwise skip.

---

## Final verification

Run the smallest honest suite that covers this slice:

```bash
source venv/bin/activate && pytest \
  tests/agent/test_deterministic_reports.py \
  tests/agent/test_execution_scope.py \
  tests/cron/test_scheduler.py \
  tests/gateway/test_status.py -q
```

If gateway helper wiring touched other status command paths, also run:

```bash
source venv/bin/activate && pytest tests/gateway/test_status_command.py -q
```

If config changed, also run:

```bash
source venv/bin/activate && pytest tests/hermes_cli -q
```

---

## Acceptance criteria

- [ ] `agent/deterministic_reports.py` exists and is pure/helper-only
- [ ] cron uses the shared formatter instead of raw `final_response` only
- [ ] gateway completion paths use the same summary meaning set
- [ ] `agent/execution_scope.py` exists and reports repo root / remotes / dirty state
- [ ] one user-visible execution path surfaces repo scope compactly
- [ ] no unrelated dirty files were touched
- [ ] focused pytest suite passes

---

## Rollback plan

If this slice goes sideways, rollback in reverse order:

1. remove repo-scope prefix wiring from `gateway/run.py`
2. revert `agent/execution_scope.py` and its tests
3. revert formatter wiring in `gateway/run.py`
4. revert formatter wiring in `cron/scheduler.py`
5. remove `agent/deterministic_reports.py` and its tests

This is why the plan stays modular. If one part sucks, it should die alone.
