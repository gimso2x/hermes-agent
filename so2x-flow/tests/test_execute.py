import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXECUTE = ROOT / "scripts" / "execute.py"
RUNS_DIR = ROOT / "outputs" / "runs"
PLANS_DIR = ROOT / "outputs" / "plans"
CONFIG_PATH = ROOT / "config" / "ccs-map.yaml"


def run_execute(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXECUTE), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def output_path(stdout: str, label: str) -> Path:
    prefix = f"{label}: "
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return ROOT / line[len(prefix) :]
    raise AssertionError(f"Could not find {label} in stdout:\n{stdout}")


def test_init_dry_run_writes_outputs_and_lists_bootstrap_artifacts():
    result = run_execute("init", "개인용 운동 코칭 앱 MVP", "--dry-run")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["mode"] == "init"
    assert "skills/flow-init.md" in payload["artifacts"]
    assert "DESIGN.md" in payload["artifacts"]
    assert payload["roles"] == ["planner"]


def test_feature_dry_run_collects_design_doc_creates_task_and_chains_planner_to_implementer():
    result = run_execute("feature", "로그인 기능 구현", "--dry-run")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["mode"] == "feature"
    assert payload["design_doc"] == "DESIGN.md"
    assert payload["docs_used"] == [
        "docs/PRD.md",
        "docs/ARCHITECTURE.md",
        "docs/ADR.md",
        "DESIGN.md",
    ]
    assert [item["role"] for item in payload["role_results"]] == ["planner", "implementer"]
    assert payload["artifacts"] == ["tasks/feature/로그인-기능-구현.md"]
    implementer_output = payload["role_results"][1]["output"]
    assert "planner_output:" in implementer_output
    assert "role: planner" in implementer_output


def test_qa_dry_run_prioritizes_qa_doc_and_uses_qa_planner():
    result = run_execute("qa", "QA-001 홈 버튼 클릭 안됨", "--qa-id", "QA-001", "--dry-run")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["mode"] == "qa"
    assert payload["docs_used"][0] == "docs/QA.md"
    assert [item["role"] for item in payload["role_results"]] == ["qa_planner", "implementer"]
    task_text = (ROOT / payload["artifacts"][0]).read_text(encoding="utf-8")
    assert "## Reproduction" in task_text
    assert "## Expected" in task_text
    assert "## Actual" in task_text
    assert "## Minimal Fix" in task_text
    assert "qa_id: QA-001" in payload["role_results"][1]["output"]


def test_review_dry_run_uses_reviewer_only_and_includes_design_doc():
    result = run_execute("review", "이번 변경 QA 관점 점검", "--dry-run")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["mode"] == "review"
    assert payload["roles"] == ["reviewer"]
    assert payload["design_doc"] == "DESIGN.md"
    assert payload["artifacts"] == []


def test_plan_dry_run_writes_outputs_under_plans_directory():
    result = run_execute("plan", "결제 기능 작업 분해", "--dry-run")
    output_json = output_path(result.stdout, "output_json")
    output_md = output_path(result.stdout, "output_md")
    payload = read_json(output_json)
    assert payload["mode"] == "plan"
    assert output_json.parent == PLANS_DIR
    assert output_md.parent == PLANS_DIR
    assert payload["artifacts"] == ["outputs/plans/결제-기능-작업-분해.md"]


def test_skip_plan_removes_planner_role_from_feature_run():
    result = run_execute("feature", "프로필 편집", "--skip-plan", "--dry-run")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["roles"] == ["implementer"]
    assert "planner_output:" not in payload["role_results"][0]["output"]


def test_review_mode_collects_related_task_document_when_passed_via_task_option():
    feature_result = run_execute("feature", "세션 만료 처리", "--dry-run")
    feature_payload = read_json(output_path(feature_result.stdout, "output_json"))
    task_relpath = feature_payload["artifacts"][0]
    review_result = run_execute("review", "세션 만료 처리 검토", "--task", task_relpath, "--dry-run")
    review_payload = read_json(output_path(review_result.stdout, "output_json"))
    reviewer_output = review_payload["role_results"][0]["output"]
    assert task_relpath in review_payload["docs_used"]
    assert "## Proposed Steps" in reviewer_output


def test_legacy_mode_aliases_still_work():
    qa_payload = read_json(output_path(run_execute("qa-fix", "QA-009 토글 오동작", "--qa-id", "QA-009", "--dry-run").stdout, "output_json"))
    plan_payload = read_json(output_path(run_execute("plan-only", "결제 기능 작업 분해", "--dry-run").stdout, "output_json"))
    assert qa_payload["mode"] == "qa"
    assert plan_payload["mode"] == "plan"


def test_requested_ccs_falls_back_to_claude_when_ccs_missing():
    original = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    updated = json.loads(json.dumps(original))
    updated["runtime"]["runner"] = "ccs"
    CONFIG_PATH.write_text(yaml.safe_dump(updated, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        result = run_execute("review", "출력 경로 확인", "--dry-run")
    finally:
        CONFIG_PATH.write_text(yaml.safe_dump(original, allow_unicode=True, sort_keys=False), encoding="utf-8")
    payload = read_json(output_path(result.stdout, "output_json"))
    assert payload["requested_runner"] == "ccs"
    assert payload["selected_runner"] in {"ccs", "claude"}
    if payload["selected_runner"] == "claude":
        assert payload["fallback_used"] is True
        assert "claude -p" or payload["role_results"][0]["command_preview"]


def test_execute_uses_runner_resolution_layer():
    execute_text = EXECUTE.read_text(encoding="utf-8")
    assert "from scripts.ccs_runner import resolve_runner, run_role" in execute_text
