from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class RunnerResolution:
    requested_runner: str
    selected_runner: str
    fallback_used: bool
    fallback_reason: str | None


@dataclass
class RoleResult:
    role: str
    runner: str
    engine: str
    model: str
    status: str
    output: str
    command: list[str]
    command_preview: str


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def resolve_runner(requested_runner: str, *, has_ccs: bool | None = None) -> RunnerResolution:
    ccs_available = has_ccs if has_ccs is not None else has_command("ccs")
    normalized = requested_runner or "auto"
    if normalized == "claude":
        return RunnerResolution(normalized, "claude", False, None)
    if normalized == "auto":
        if ccs_available:
            return RunnerResolution(normalized, "ccs", False, None)
        return RunnerResolution(normalized, "claude", True, "ccs not found in PATH")
    if normalized == "ccs":
        if ccs_available:
            return RunnerResolution(normalized, "ccs", False, None)
        return RunnerResolution(normalized, "claude", True, "ccs not found in PATH")
    raise ValueError(f"Unsupported runner: {requested_runner}")


def build_ccs_command(role: str, prompt: str, role_config: dict) -> list[str]:
    command = [role_config.get("command", "ccs"), role_config.get("engine", role)]
    model = role_config.get("model")
    profile = role_config.get("profile") or role_config.get("ccs_profile")
    extra_args = role_config.get("extra_args", [])
    if model:
        command.extend(["--model", model])
    if profile:
        command.extend(["--profile", profile])
    command.extend(extra_args)
    command.extend(["-p", prompt])
    return command


def build_claude_command(role: str, prompt: str, role_config: dict, runtime_config: dict | None = None) -> list[str]:
    runtime = runtime_config or {}
    command = [role_config.get("command", runtime.get("claude_command", "claude"))]
    extra_args = role_config.get("extra_args", [])
    claude_role = role_config.get("claude_role")
    if claude_role:
        command.extend(["--append-system-prompt", f"role={claude_role}"])
    command.extend(extra_args)
    command.extend([runtime.get("claude_headless_flag", "-p"), prompt])
    return command


def build_runner_command(
    *,
    runner: str,
    role: str,
    prompt: str,
    role_config: dict,
    runtime_config: dict | None = None,
) -> list[str]:
    if runner == "ccs":
        return build_ccs_command(role=role, prompt=prompt, role_config=role_config)
    if runner == "claude":
        return build_claude_command(role=role, prompt=prompt, role_config=role_config, runtime_config=runtime_config)
    raise ValueError(f"Unsupported runner: {runner}")


def command_preview(command: list[str]) -> str:
    return shlex.join(command)


def run_role(
    *,
    runner: str,
    role: str,
    prompt: str,
    role_config: dict,
    runtime_config: dict | None = None,
    dry_run: bool,
) -> RoleResult:
    command = build_runner_command(
        runner=runner,
        role=role,
        prompt=prompt,
        role_config=role_config,
        runtime_config=runtime_config,
    )
    preview = command_preview(command)
    engine = role_config.get("engine", role_config.get("claude_role", role))
    model = role_config.get("model", runner)
    if dry_run:
        output = f"[dry-run] runner={runner} role={role} engine={engine} model={model} command={preview}\n\n{prompt}"
        return RoleResult(role=role, runner=runner, engine=engine, model=model, status="dry-run", output=output, command=command, command_preview=preview)

    raise NotImplementedError(f"Live {runner} execution is not implemented yet for role={role}")


def run_role_subprocess(
    *,
    runner: str,
    role: str,
    prompt: str,
    role_config: dict,
    runtime_config: dict | None = None,
    timeout: int = 300,
) -> RoleResult:
    command = build_runner_command(
        runner=runner,
        role=role,
        prompt=prompt,
        role_config=role_config,
        runtime_config=runtime_config,
    )
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
    engine = role_config.get("engine", role_config.get("claude_role", role))
    model = role_config.get("model", runner)
    preview = command_preview(command)
    return RoleResult(role=role, runner=runner, engine=engine, model=model, status="success", output=completed.stdout, command=command, command_preview=preview)
