# Graphify P0 Repo-Map Absorption Plan

> For Hermes: implement this in small, verified slices. Do not widen scope. The repo is currently dirty (`.plans/archon-p0-implementation-plan.md`, `download.html`), so this plan must stay surgical and avoid unrelated files.

**Goal:** Bring graphify’s best operating idea into Hermes: before the agent starts blindly reading raw files in a large repo, give it a cached repo map and a focused submap path for the user’s question.

**Architecture:** Start with a tiny read-only repo-map subsystem instead of a full graph engine. Add one pure analyzer module that builds a lightweight repo summary from filenames, key docs, and code/test counts; one cache module under `~/.hermes/cache/repo-map/`; and one narrow integration point that can surface repo-map hints before raw file spelunking. Keep P0 deterministic, local, and markdown/JSON-first.

**Tech Stack:** Python, existing Hermes agent/tool pipeline, file tools, `hermes_constants.get_hermes_dir()`, pytest.

---

## Constraints and non-goals

- Do not touch unrelated dirty files: `.plans/archon-p0-implementation-plan.md`, `download.html`.
- Do not add embeddings, vector DBs, Neo4j, Whisper, or any external model dependency.
- Do not build a full knowledge graph engine in P0.
- Do not add a new always-on hook system just for this feature.
- Do not widen scope into gateway/cron unless the basic local repo-map path is already proven.
- Prefer one small analyzer, one small cache layer, one integration seam, and focused tests.

---

## Current repo reality checked first

Validated in `/home/ubuntu/.hermes/hermes-agent`:

- repo root: `/home/ubuntu/.hermes/hermes-agent`
- remote: `origin https://github.com/NousResearch/hermes-agent.git`
- dirty worktree before planning:
  - `?? .plans/archon-p0-implementation-plan.md`
  - `?? download.html`

Relevant existing seams already in this repo:

- `agent/subdirectory_hints.py` — lazily injects subdirectory context after file/tool navigation starts
- `agent/prompt_builder.py` — startup context loading and hint policy
- `tools/file_tools.py` — repeated file read/search behavior and task-scoped state
- `hermes_constants.py` — canonical cache directory helpers via `get_hermes_dir()`
- `tests/agent/test_subdirectory_hints.py`
- `tests/tools/test_file_tools.py`

This means the cleanest P0 is not "new framework" but "one more deterministic context layer" that complements existing hints.

---

## Target outcome for P0

By the end of this plan, Hermes should have:

1. A deterministic `repo map` builder for a local repository root.
2. A cache file under `~/.hermes/cache/repo-map/` keyed by repo root + relevant metadata.
3. A compact markdown summary with:
   - repo root
   - git remote/default branch if available
   - top directories
   - representative docs/configs/entrypoints/tests
   - file-type distribution
4. A focused `submap` extractor that answers narrow questions like:
   - auth flow
   - cron path
   - gateway platform adapters
   by selecting only relevant files/dirs/notes from the cached repo map.
5. One narrow integration seam so the agent can see repo-map hints before falling into repeated raw reads/searches.
6. Tests that lock behavior and make future overengineering harder.

---

## Proposed file layout

### New files
- `agent/repo_map.py` — deterministic repo-map builder and submap extraction
- `agent/repo_map_cache.py` — cache path, hash keying, load/save/invalidity helpers
- `tests/agent/test_repo_map.py` — analyzer and submap tests
- `tests/agent/test_repo_map_cache.py` — cache behavior tests

### Existing files likely to modify
- `tools/file_tools.py` — optional narrow hook to surface repo-map summary before repeated broad reads/searches
- `agent/subdirectory_hints.py` — optional helper reuse if repo-map hint text should share formatting style
- `tests/tools/test_file_tools.py` — regression tests for repo-map-assisted read/search behavior
- `run_agent.py` or `model_tools.py` — only if a better integration seam is discovered during implementation; avoid unless necessary

---

## Task 1: Build the repo-map analyzer module

**Objective:** Create a pure function that inspects a repo root and returns a compact structured map without touching model code.

**Files:**
- Create: `agent/repo_map.py`
- Test: `tests/agent/test_repo_map.py`

**Step 1: Write failing tests for repo-map generation**

Create `tests/agent/test_repo_map.py` with a synthetic repo fixture covering:
- root docs: `README.md`, `AGENTS.md`
- source dirs: `agent/`, `tools/`, `tests/`
- key config file: `pyproject.toml`
- a few code files and test files

Minimum failing tests:
1. `build_repo_map(root)` returns repo root, top directories, representative files, and suffix counts
2. hidden junk like `.git/` is excluded from summaries
3. `build_repo_map()` flags likely entrypoints/config/tests without reading the entire repo into memory
4. markdown rendering is stable and human-readable

Suggested API:

```python
from agent.repo_map import build_repo_map, render_repo_map_markdown


def test_build_repo_map_collects_top_level_summary(tmp_path):
    (tmp_path / "README.md").write_text("# Demo")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "worker.py").write_text("print('x')")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_worker.py").write_text("def test_x(): pass")

    result = build_repo_map(tmp_path)

    assert result["repo_root"] == str(tmp_path)
    assert "agent" in result["top_directories"]
    assert any(p.endswith("README.md") for p in result["representative_files"])
    assert result["suffix_counts"][".py"] >= 2


def test_render_repo_map_markdown_includes_human_sections(tmp_path):
    (tmp_path / "README.md").write_text("# Demo")
    result = build_repo_map(tmp_path)
    text = render_repo_map_markdown(result)
    assert "리포 지도" in text
    assert "상위 디렉터리" in text
    assert "대표 파일" in text
```

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py -q`

Expected:
- FAIL because `agent.repo_map` does not exist yet.

**Step 3: Implement minimal analyzer**

In `agent/repo_map.py`, implement only these functions first:

```python
def build_repo_map(repo_root: Path | str, *, max_files: int = 400) -> dict: ...
def render_repo_map_markdown(repo_map: dict) -> str: ...
def _collect_representative_files(root: Path, files: list[Path]) -> list[str]: ...
def _suffix_counts(files: list[Path]) -> dict[str, int]: ...
```

Implementation rules:
- deterministic ordering only
- skip `.git`, `node_modules`, `.venv`, `dist`, `build`, `__pycache__`
- cap traversal so giant repos do not explode P0
- use relative paths where possible
- detect representative files by explicit priority, not fuzzy LLM nonsense
  - root docs/configs first
  - common entrypoints (`main.py`, `cli.py`, `app.py`, `run.py`, `index.ts`, etc.)
  - a few test files

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py -q`

Expected:
- PASS

**Step 5: Do not commit yet**

This repo is already dirty. Stage only the new repo-map files after the whole slice is proven.

---

## Task 2: Add a cache layer for repo maps

**Objective:** Cache repo-map JSON so repeated analysis of the same repo stops pretending it is the first time.

**Files:**
- Create: `agent/repo_map_cache.py`
- Modify: `agent/repo_map.py`
- Test: `tests/agent/test_repo_map_cache.py`

**Step 1: Write failing cache tests**

Add tests for:
1. stable cache path for a repo root
2. cache save/load roundtrip
3. cache invalidates when a tracked fingerprint changes
4. corrupted cache file fails safely and rebuilds

Suggested API:

```python
from agent.repo_map_cache import (
    compute_repo_map_cache_key,
    get_repo_map_cache_path,
    load_cached_repo_map,
    save_cached_repo_map,
)
```

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map_cache.py -q`

Expected:
- FAIL because cache module does not exist yet.

**Step 3: Implement minimal cache behavior**

Use `hermes_constants.get_hermes_dir("cache/repo-map", "repo_map_cache")` for storage.

Cache key should be derived from deterministic inputs only:
- resolved repo root
- maybe top-level file mtimes or a small fingerprint from representative files

Do not hash the whole repo in P0. That’s how people accidentally build a furnace.

Recommended functions:

```python
def compute_repo_map_cache_key(repo_root: Path | str, fingerprint: str) -> str: ...
def get_repo_map_cache_path(cache_key: str) -> Path: ...
def load_cached_repo_map(repo_root: Path | str, fingerprint: str) -> dict | None: ...
def save_cached_repo_map(repo_root: Path | str, fingerprint: str, repo_map: dict) -> Path: ...
def compute_repo_map_fingerprint(repo_root: Path | str) -> str: ...
```

Keep fingerprint cheap:
- resolved root path
- git HEAD if available
- top-level file names/mtimes
- maybe a bounded sample of representative file mtimes

**Step 4: Thread cache into `build_repo_map()`**

Add a small convenience wrapper:

```python
def get_or_build_repo_map(repo_root: Path | str) -> dict:
    ...
```

Behavior:
- try cache
- on miss/corruption rebuild
- save rebuilt map

**Step 5: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py tests/agent/test_repo_map_cache.py -q`

Expected:
- PASS

---

## Task 3: Add focused submap extraction

**Objective:** Make the repo map actually useful for a question, not just pretty.

**Files:**
- Modify: `agent/repo_map.py`
- Test: `tests/agent/test_repo_map.py`

**Step 1: Write failing tests for query-focused extraction**

Add tests for:
1. a question like `"auth flow"` prefers files/dirs containing auth/login/session terms
2. a question like `"gateway adapters"` surfaces `gateway/platforms/*` over unrelated files
3. result is compact and deterministic

Suggested API:

```python
def extract_focused_submap(repo_map: dict, question: str, *, limit: int = 8) -> dict: ...
def render_focused_submap_markdown(submap: dict) -> str: ...
```

Expected output shape:
- `question`
- `matched_directories`
- `matched_files`
- `reason_terms`
- optional `next_raw_targets`

**Step 2: Run tests to verify failure**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py -q`

Expected:
- FAIL because focused extraction does not exist yet.

**Step 3: Implement minimal term-based ranking**

Rules:
- simple normalized keyword overlap only
- prefer exact path matches over broad suffix matches
- weight directories and representative files separately
- no embeddings, no model calls
- if nothing matches, return the top-level repo map summary rather than hallucinating

**Step 4: Run tests to verify pass**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py -q`

Expected:
- PASS

---

## Task 4: Surface repo-map hints in one narrow integration seam

**Objective:** Make the repo map influence behavior before repeated raw reads/searches start.

**Files:**
- Modify: `tools/file_tools.py`
- Possibly modify: `agent/subdirectory_hints.py` (only for shared formatting helper if clearly useful)
- Test: `tests/tools/test_file_tools.py`

**Step 1: Inspect the current seam before editing**

Read and understand first:
- `tools/file_tools.py`
- how per-task read tracking currently works
- where tool result strings are assembled

Do not edit until you know exactly where a small hint can be appended without breaking output contracts.

**Step 2: Write failing tests for repo-map hint surfacing**

Add tests that prove:
1. first broad repo read/search on a git/project root can append a repo-map summary hint
2. repeated identical reads do not spam the same summary forever
3. narrow file reads still behave normally
4. no hint is added for non-project temp directories with trivial contents

Possible behavior contract:
- only trigger on broad search/read patterns
- only trigger once per task/repo root unless fingerprint changes
- append human-readable markdown similar to subdirectory hints

Suggested text shape:

```text
[Repo map available: /path/to/repo]
리포 지도 요약
- 상위 디렉터리: ...
- 대표 파일: ...
- 먼저 볼 후보: ...
```

**Step 3: Implement the narrowest working integration**

Preferred approach:
- add a tiny per-task tracker in `file_tools.py`
- when a call targets a probable project root or broad search path, call `get_or_build_repo_map()`
- append formatted repo-map text to the existing tool result

Do not:
- change every tool in the system
- inject into the system prompt
- add network calls

**Step 4: Run targeted tests**

Run:
`source venv/bin/activate && pytest tests/tools/test_file_tools.py tests/agent/test_subdirectory_hints.py -q`

Expected:
- PASS

**Step 5: Manual sanity check**

Run one local smoke path in the Hermes repo itself:

```bash
source venv/bin/activate && python - <<'PY'
from agent.repo_map import get_or_build_repo_map, render_repo_map_markdown, extract_focused_submap, render_focused_submap_markdown
repo = get_or_build_repo_map('.')
print(render_repo_map_markdown(repo)[:1200])
print('---')
print(render_focused_submap_markdown(extract_focused_submap(repo, 'gateway adapters')))
PY
```

Expected:
- markdown summary mentions `agent/`, `tools/`, `gateway/`, `tests/`
- focused submap for `gateway adapters` pulls `gateway/platforms`-adjacent paths instead of random files

---

## Task 5: Add one explicit user-facing command or helper surface

**Objective:** Make the feature manually inspectable instead of purely implicit.

**Files:**
- Modify: `cli.py` or `hermes_cli/main.py` and `hermes_cli/commands.py`
- Test: matching CLI tests (`tests/cli/...` or `tests/hermes_cli/...`)

**Step 1: Pick the least invasive surface**

Preferred order:
1. slash command `/repomap [question]`
2. `hermes repomap <path> [question]`
3. hidden developer helper only if command wiring turns out bigger than expected

P0 recommendation: slash command or CLI subcommand that prints:
- repo summary by default
- focused submap when question is provided

**Step 2: Write failing command test**

Add one small test proving command registration and output path.

**Step 3: Implement minimal command**

Keep it boring:
- default path = current working directory
- optional question narrows results
- no agent conversation required

**Step 4: Run command tests**

Use the narrowest matching test command for the chosen command path.

---

## Task 6: Full verification for the slice

**Objective:** Prove the repo-map slice works and did not spill everywhere.

**Files:**
- No new files unless tiny docs note is genuinely necessary

**Step 1: Run focused test bundle**

Run:
`source venv/bin/activate && pytest tests/agent/test_repo_map.py tests/agent/test_repo_map_cache.py tests/tools/test_file_tools.py tests/agent/test_subdirectory_hints.py -q`

If a CLI command was added, include its test file too.

**Step 2: Run one smoke check in the Hermes repo**

Use the manual sanity command from Task 4.

**Step 3: Check diff scope**

Run:
`git diff -- agent/repo_map.py agent/repo_map_cache.py tools/file_tools.py tests/agent/test_repo_map.py tests/agent/test_repo_map_cache.py tests/tools/test_file_tools.py`

Expected:
- only repo-map-related files changed
- dirty unrelated files still untouched

**Step 4: Commit surgically**

Only after the slice passes:

```bash
git add agent/repo_map.py agent/repo_map_cache.py tools/file_tools.py tests/agent/test_repo_map.py tests/agent/test_repo_map_cache.py tests/tools/test_file_tools.py
# add command/test files too only if they were actually needed
git commit -m "feat: add deterministic repo-map summaries"
```

---

## Acceptance criteria

The slice is done when all of these are true:

- Hermes can deterministically summarize a repo into a compact repo map.
- Repo maps are cached under `~/.hermes/cache/repo-map/`.
- Hermes can produce a focused submap for a narrow question.
- At least one existing tool path can surface repo-map hints before repeated blind raw-file exploration.
- Tests cover analyzer, cache, and integration behavior.
- No external model/service dependency was added.
- Unrelated dirty files were not modified.

---

## Non-goal reminder

If implementation starts drifting toward any of these, stop:
- graph database export
- embeddings
- semantic search infra
- multimodal ingestion
- cross-platform hook rollout
- giant framework rename/reorg

P0 is a repo map. Not a religion.
