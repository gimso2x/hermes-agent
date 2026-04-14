from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.approval import approval_policy_summary
from tools.process_registry import process_registry


def _stringify(value: Any, default: str = "(unknown)") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def summarize_runtime_contract(*, provider_label: str, terminal_backend: str, memory_mode: str, model_name: str | None = None) -> list[str]:
    provider_text = _stringify(provider_label)
    if model_name:
        provider_text = f"{provider_text} / {_stringify(model_name)}"
    return [
        f"모델/프로바이더: {provider_text}",
        f"터미널 백엔드: {_stringify(terminal_backend)}",
        f"메모리 모드: {_stringify(memory_mode)}",
        "자율 실행: cron / background process 지원",
    ]


def summarize_autonomous_execution(*, hermes_home: Path) -> list[str]:
    jobs_file = hermes_home / "cron" / "jobs.json"
    scheduled = paused = delivery_failures = local_only = 0
    jobs_error = ""
    if jobs_file.exists():
        try:
            payload = json.loads(jobs_file.read_text(encoding="utf-8"))
            jobs = payload.get("jobs", [])
            scheduled = sum(1 for job in jobs if job.get("enabled", True))
            paused = sum(1 for job in jobs if not job.get("enabled", True))
            delivery_failures = sum(1 for job in jobs if job.get("last_delivery_error"))
            local_only = sum(1 for job in jobs if (job.get("deliver") or "local") == "local")
        except Exception:
            jobs_error = "cron 상태 파일 읽기 오류"

    process_state = process_registry.get_state_snapshot()

    lines = [
        f"예약됨: {scheduled}",
        f"일시정지: {paused}",
        f"로컬 전용: {local_only}",
        f"전달 실패: {delivery_failures}",
        f"백그라운드 실행 중: {process_state['running']}",
        f"최근 종료됨: {process_state['finished_recent']}",
        f"watch 비활성화: {process_state['watch_disabled']}",
    ]
    if jobs_error:
        lines.append(f"상태 메모: {jobs_error}")
    lines.append("다음 확인: hermes cron list / process(action='poll') / process(action='wait')")
    return lines


def summarize_security_boundaries() -> list[str]:
    policy = approval_policy_summary()
    examples = ", ".join(policy.get("examples", []))
    approval_scope = "세션 기준으로 확인받음" if policy.get("session_scoped", False) else "세션 고정 아님"
    lines = [
        f"dangerous command approval: enabled ({policy.get('dangerous_pattern_count', 0)} patterns)",
        f"고위험 예시: {examples}" if examples else "고위험 예시: (없음)",
        "시크릿 표면: API 키/토큰 표시는 redaction 우선",
        f"승인 경계: 파괴적 명령은 {approval_scope}",
    ]
    return lines
