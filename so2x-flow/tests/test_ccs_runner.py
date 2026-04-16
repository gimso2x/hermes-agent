import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "ccs_runner.py"

spec = importlib.util.spec_from_file_location("so2x_flow_ccs_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
assert spec.loader is not None
spec.loader.exec_module(runner)


def test_resolve_runner_prefers_ccs_when_auto_and_available():
    result = runner.resolve_runner("auto", has_ccs=True)
    assert result.selected_runner == "ccs"
    assert result.fallback_used is False


def test_resolve_runner_falls_back_to_claude_when_ccs_missing():
    result = runner.resolve_runner("ccs", has_ccs=False)
    assert result.requested_runner == "ccs"
    assert result.selected_runner == "claude"
    assert result.fallback_used is True
    assert "ccs not found" in result.fallback_reason


def test_build_ccs_command_uses_role_config_fields():
    command = runner.build_ccs_command(
        role="implementer",
        prompt="hello",
        role_config={
            "engine": "glm",
            "model": "glm-4.5",
            "profile": "impl",
            "command": "ccs",
            "extra_args": ["--json"],
        },
    )
    assert command[:2] == ["ccs", "glm"]
    assert command[-2:] == ["-p", "hello"]


def test_build_claude_command_uses_headless_flag_and_role_hint():
    command = runner.build_claude_command(
        role="planner",
        prompt="hello",
        role_config={"command": "claude", "claude_role": "planner", "extra_args": ["--verbose"]},
        runtime_config={"claude_headless_flag": "-p"},
    )
    assert command[:1] == ["claude"]
    assert "--append-system-prompt" in command
    assert command[-2:] == ["-p", "hello"]


def test_run_role_dry_run_includes_runner_and_command_preview():
    result = runner.run_role(
        runner="ccs",
        role="planner",
        prompt="hello",
        role_config={"engine": "codex", "model": "codex", "command": "ccs"},
        dry_run=True,
    )
    assert result.status == "dry-run"
    assert result.runner == "ccs"
    assert "runner=ccs" in result.output
    assert "command=ccs codex" in result.output


def test_run_role_live_path_requires_real_runner():
    try:
        runner.run_role(
            runner="claude",
            role="planner",
            prompt="hello",
            role_config={"command": "claude", "claude_role": "planner"},
            runtime_config={"claude_headless_flag": "-p"},
            dry_run=False,
        )
    except NotImplementedError as exc:
        assert "live claude execution" in str(exc).lower()
    else:
        raise AssertionError("Expected NotImplementedError for live path")
