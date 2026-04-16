#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ccs_runner import resolve_runner, run_role

CONFIG_PATH = ROOT / "config" / "ccs-map.yaml"
OUTPUT_RUNS = ROOT / "outputs" / "runs"
OUTPUT_PLANS = ROOT / "outputs" / "plans"
PROMPTS_DIR = ROOT / "prompts"

MODE_ALIASES = {
    "qa-fix": "qa",
    "plan-only": "plan",
}

BOOTSTRAP_FILES: dict[str, str] = {
    "CLAUDE.md": "# so2x-flow workspace guide\n\nSee `skills/` for workflow definitions and `config/ccs-map.yaml` for runner policy.\n",
    ".claude/settings.json": '{\n  "hooks": {\n    "preToolUse": [\n      "scripts/hooks/dangerous-cmd-guard.sh"\n    ],\n    "postToolUse": [],\n    "userPromptSubmit": [\n      "scripts/hooks/tdd-guard.sh"\n    ],\n    "stop": [\n      "scripts/hooks/circuit-breaker.sh"\n    ]\n  }\n}\n',
    "skills/README.md": "# so2x-flow skills\n\nWorkflow source of truth.\n",
    "skills/flow-init.md": "# flow-init\n\nBootstrap only.\n",
    "skills/flow-feature.md": "# flow-feature\n\nCreate task docs before implementation.\n",
    "skills/flow-qa.md": "# flow-qa\n\nCreate QA task docs before fixes.\n",
    "skills/flow-review.md": "# flow-review\n\nReview only, no code changes.\n",
    "skills/flow-plan.md": "# flow-plan\n\nPlanning only, no implementation.\n",
    "config/ccs-map.yaml": "runtime:\n  runner: auto\n",
    "docs/PRD.md": "# PRD\n",
    "docs/ARCHITECTURE.md": "# ARCHITECTURE\n",
    "docs/ADR.md": "# ADR\n",
    "docs/QA.md": "# QA\n",
    "DESIGN.md": "# DESIGN\n",
    "prompts/planner.md": "# planner\n",
    "prompts/implementer.md": "# implementer\n",
    "prompts/qa-planner.md": "# qa-planner\n",
    "prompts/reviewer.md": "# reviewer\n",
    "tasks/feature/_template.md": "# Feature Task\n",
    "tasks/qa/_template.md": "# QA Fix Task\n",
    "scripts/hooks/tdd-guard.sh": "#!/usr/bin/env sh\nexit 0\n",
    "scripts/hooks/dangerous-cmd-guard.sh": "#!/usr/bin/env sh\nexit 0\n",
    "scripts/hooks/circuit-breaker.sh": "#!/usr/bin/env sh\nexit 0\n",
    "outputs/plans/.gitkeep": "",
    "outputs/runs/.gitkeep": "",
}

BOOTSTRAP_DIRS = [
    ".claude",
    "skills",
    "config",
    "docs",
    "prompts",
    "scripts/hooks",
    "tasks/feature",
    "tasks/qa",
    "outputs/plans",
    "outputs/runs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="so2x-flow execution entrypoint")
    parser.add_argument("mode", choices=["init", "feature", "qa", "qa-fix", "review", "plan", "plan-only"])
    parser.add_argument("request")
    parser.add_argument("--task")
    parser.add_argument("--qa-id")
    parser.add_argument("--docs", nargs="*")
    parser.add_argument("--skip-plan", action="store_true")
    parser.add_argument("--with-design", action="store_true")
    parser.add_argument("--output-name")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def canonical_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    return text.strip("-") or "run"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_bootstrap_files() -> list[str]:
    artifacts: list[str] = []
    for rel_dir in BOOTSTRAP_DIRS:
        (ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
    for rel_path, content in BOOTSTRAP_FILES.items():
        path = ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        artifacts.append(rel_path)
    return artifacts


def collect_design_doc(mode: str, with_design: bool) -> str | None:
    preferred = ROOT / "DESIGN.md"
    fallback = ROOT / "docs" / "UI_GUIDE.md"
    if with_design or mode in {"feature", "review", "plan"}:
        if preferred.exists():
            return "DESIGN.md"
        if fallback.exists():
            return "docs/UI_GUIDE.md"
    if mode == "qa" and with_design:
        if preferred.exists():
            return "DESIGN.md"
        if fallback.exists():
            return "docs/UI_GUIDE.md"
    return None


def collect_docs(mode: str, extra_docs: list[str] | None, task: str | None = None, with_design: bool = False) -> tuple[list[str], str | None]:
    if mode == "init":
        docs = []
    elif mode == "feature":
        docs = ["docs/PRD.md", "docs/ARCHITECTURE.md", "docs/ADR.md"]
    elif mode == "qa":
        docs = ["docs/QA.md", "docs/PRD.md", "docs/ARCHITECTURE.md", "docs/ADR.md"]
    elif mode == "review":
        docs = ["docs/PRD.md", "docs/ARCHITECTURE.md", "docs/ADR.md", "docs/QA.md"]
    else:
        docs = ["docs/PRD.md", "docs/ARCHITECTURE.md", "docs/ADR.md"]

    design_doc = collect_design_doc(mode, with_design)
    if design_doc and design_doc not in docs:
        docs.append(design_doc)
    if task and task not in docs:
        docs.append(task)
    for item in extra_docs or []:
        if item not in docs:
            docs.append(item)
    return docs, design_doc


def load_docs_bundle(docs_used: list[str]) -> str:
    blocks: list[str] = []
    for rel_path in docs_used:
        path = ROOT / rel_path
        if path.exists():
            blocks.append(f"### {rel_path}\n{load_text(path).strip()}")
        else:
            blocks.append(f"### {rel_path}\n(MISSING)")
    return "\n\n".join(blocks) if blocks else "(none)"


def prompt_path_for_role(role: str) -> Path:
    mapping = {
        "planner": "planner.md",
        "implementer": "implementer.md",
        "qa_planner": "qa-planner.md",
        "reviewer": "reviewer.md",
    }
    return PROMPTS_DIR / mapping[role]


def load_prompt_template(role: str) -> str:
    return load_text(prompt_path_for_role(role))


def render_feature_task(request: str) -> str:
    return f'''# Feature Task

## Title
{request}

## Summary
- Requested feature: {request}

## Context
- Capture user-facing context and constraints here.

## Related Docs
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ADR.md
- DESIGN.md

## Relevant Files
- List candidate files to inspect or modify.

## Scope
- Define the minimum implementation slice for this feature.

## Out of Scope
- Explicitly list what this task will not change.

## Proposed Steps
1. Clarify the exact user-visible behavior.
2. Identify the smallest implementation change.
3. Implement and verify the change.

## Acceptance
- Define the minimum accepted outcome.

## Verification Checklist
- [ ] Behavior implemented as planned
- [ ] Relevant tests executed
- [ ] Docs updated if needed
'''


def render_qa_task(request: str, qa_id: str | None) -> str:
    qa_label = qa_id or "QA-TBD"
    return f'''# QA Fix Task

## Title
{request}

## Issue Summary
- Summarize the bug and affected user flow.

## QA ID
{qa_label}

## References
- docs/QA.md
- Related screenshots, issues, or logs if available.

## Reproduction
- Describe how to reproduce the issue.

## Expected
- Describe the intended behavior.

## Actual
- Describe the current broken behavior.

## Suspected Scope
- List the likely files, modules, or UI areas involved.

## Minimal Fix
- Describe the smallest safe repair.

## Regression Checklist
- [ ] Original issue no longer reproduces
- [ ] Adjacent flow still works
- [ ] No broader scope added without approval
'''


def render_plan_doc(request: str, docs_used: list[str]) -> str:
    return "\n".join([
        "# Plan",
        "",
        f"## Request\n{request}",
        "",
        "## Related Docs",
        *[f"- {doc}" for doc in docs_used],
        "",
        "## Proposed Steps",
        "1. Clarify scope.",
        "2. Break work into reviewable slices.",
        "3. Define verification before implementation.",
    ])


def build_prompt(
    role: str,
    mode: str,
    request: str,
    docs_used: list[str],
    docs_bundle: str,
    task_path: str | None,
    qa_id: str | None,
    planner_output: str | None,
    design_doc: str | None,
) -> str:
    prompt_template = load_prompt_template(role)
    lines = [
        f"role: {role}",
        f"mode: {mode}",
        f"request: {request}",
        f"docs_used: {', '.join(docs_used) if docs_used else '(none)'}",
        f"design_doc: {design_doc or '(none)'}",
        "",
        "prompt_template:",
        prompt_template.strip(),
        "",
        "docs_content:",
        docs_bundle,
    ]
    if task_path:
        task_file = ROOT / task_path
        lines.extend(["", f"task_path: {task_path}", "task_content:", load_text(task_file).strip()])
    if qa_id:
        lines.append(f"qa_id: {qa_id}")
    if planner_output:
        lines.extend(["", "planner_output:", planner_output])
    return "\n".join(lines)


def save_run_outputs(payload: dict, markdown: str, output_name: str) -> tuple[Path, Path]:
    target_dir = OUTPUT_PLANS if payload["mode"] == "plan" else OUTPUT_RUNS
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / f"{output_name}.json"
    md_path = target_dir / f"{output_name}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


def render_markdown_summary(payload: dict) -> str:
    docs_used = payload["docs_used"] or ["(none)"]
    artifacts = payload["artifacts"] or ["(none)"]
    return "\n".join(
        [
            "# Run Summary",
            "",
            "## Request Summary",
            f"- Mode: {payload['mode']}",
            f"- Request: {payload['request']}",
            f"- Dry Run: {payload['dry_run']}",
            f"- Requested Runner: {payload['requested_runner']}",
            f"- Selected Runner: {payload['selected_runner']}",
            f"- Fallback Used: {payload['fallback_used']}",
            f"- Fallback Reason: {payload['fallback_reason'] or '(none)'}",
            f"- Design Doc: {payload['design_doc'] or '(none)'}",
            "",
            "## Docs Used",
            *[f"- {doc}" for doc in docs_used],
            "",
            "## Roles Executed",
            *[
                f"- {item['role']} ({item['runner']} / {item['engine']}:{item['model']}) -> {item['status']}"
                for item in payload['role_results']
            ],
            "",
            "## Artifact List",
            *[f"- {item}" for item in artifacts],
            "",
            "## Final Summary",
            f"- Output JSON: {payload['output_json']}",
            f"- Output MD: {payload['output_md']}",
            "",
        ]
    )


def print_summary(payload: dict) -> None:
    print(f"mode: {payload['mode']}")
    print(f"request: {payload['request']}")
    print(f"dry_run: {payload['dry_run']}")
    print(f"requested_runner: {payload['requested_runner']}")
    print(f"selected_runner: {payload['selected_runner']}")
    print(f"fallback_used: {payload['fallback_used']}")
    print(f"fallback_reason: {payload['fallback_reason'] or '(none)'}")
    print(f"design_doc: {payload['design_doc'] or '(none)'}")
    print("docs_used:")
    for doc in payload["docs_used"]:
        print(f"  - {doc}")
    print("roles:")
    for item in payload["role_results"]:
        print(f"  - {item['role']} ({item['status']})")
    print("commands:")
    for item in payload["role_results"]:
        print(f"  - {item['role']}: {item['command_preview']}")
    print("artifacts:")
    for artifact in payload["artifacts"]:
        print(f"  - {artifact}")
    print(f"output_json: {payload['output_json']}")
    print(f"output_md: {payload['output_md']}")


def main() -> int:
    args = parse_args()
    mode = canonical_mode(args.mode)
    artifacts = ensure_bootstrap_files() if mode == "init" else []
    config = load_config()
    docs_used, design_doc = collect_docs(mode, args.docs, args.task, args.with_design)
    docs_bundle = load_docs_bundle(docs_used)
    configured_roles = config["modes"][mode]["roles"]
    skip_roles = {"planner", "qa_planner"} if args.skip_plan else set()
    roles = [role for role in configured_roles if role not in skip_roles]
    planner_output = None
    task_path = None

    if mode == "feature":
        task_path = f"tasks/feature/{slugify(args.request)}.md"
        path = ROOT / task_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_feature_task(args.request), encoding="utf-8")
        artifacts.append(task_path)
    elif mode == "qa":
        task_path = f"tasks/qa/{slugify(args.request)}.md"
        path = ROOT / task_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_qa_task(args.request, args.qa_id), encoding="utf-8")
        artifacts.append(task_path)
    elif mode == "plan":
        task_path = f"outputs/plans/{slugify(args.request)}.md"
        path = ROOT / task_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_plan_doc(args.request, docs_used), encoding="utf-8")
        artifacts.append(task_path)

    runtime_config = config.get("runtime", {})
    resolution = resolve_runner(runtime_config.get("runner", "auto"))
    role_results = []
    for role in roles:
        role_config = config["roles"][role][resolution.selected_runner]
        shared_role_config = {
            **config["roles"][role],
            **role_config,
        }
        prompt = build_prompt(role, mode, args.request, docs_used, docs_bundle, task_path, args.qa_id, planner_output, design_doc)
        result = run_role(
            runner=resolution.selected_runner,
            role=role,
            prompt=prompt,
            role_config=shared_role_config,
            runtime_config=runtime_config,
            dry_run=args.dry_run,
        )
        role_results.append(
            {
                "role": result.role,
                "runner": result.runner,
                "engine": result.engine,
                "model": result.model,
                "status": result.status,
                "output": result.output,
                "command": result.command,
                "command_preview": result.command_preview,
            }
        )
        if role in {"planner", "qa_planner"}:
            planner_output = result.output

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_name = args.output_name or f"{mode}-{slugify(args.request)}-{timestamp}"
    payload = {
        "mode": mode,
        "request": args.request,
        "dry_run": args.dry_run,
        "requested_runner": resolution.requested_runner,
        "selected_runner": resolution.selected_runner,
        "fallback_used": resolution.fallback_used,
        "fallback_reason": resolution.fallback_reason,
        "design_doc": design_doc,
        "docs_used": docs_used,
        "roles": roles,
        "role_results": role_results,
        "artifacts": artifacts,
        "output_json": "",
        "output_md": "",
    }
    json_path, md_path = save_run_outputs(payload, render_markdown_summary(payload), output_name)
    payload["output_json"] = str(json_path.relative_to(ROOT))
    payload["output_md"] = str(md_path.relative_to(ROOT))
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_summary(payload), encoding="utf-8")
    print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
