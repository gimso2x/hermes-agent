import json
from types import SimpleNamespace

from hermes_cli.status import show_status
from hermes_cli import runtime_surfaces


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1234567890abcdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_show_status_termux_gateway_section_skips_systemctl(monkeypatch, capsys, tmp_path):
    from hermes_cli import status as status_mod
    import hermes_cli.auth as auth_mod
    import hermes_cli.gateway as gateway_mod

    monkeypatch.setenv("TERMUX_VERSION", "0.118.3")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(status_mod, "get_env_path", lambda: tmp_path / ".env", raising=False)
    monkeypatch.setattr(status_mod, "get_hermes_home", lambda: tmp_path, raising=False)
    monkeypatch.setattr(status_mod, "load_config", lambda: {"model": "gpt-5.4"}, raising=False)
    monkeypatch.setattr(status_mod, "resolve_requested_provider", lambda requested=None: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "resolve_provider", lambda requested=None, **kwargs: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "provider_label", lambda provider: "OpenAI Codex", raising=False)
    monkeypatch.setattr(auth_mod, "get_nous_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(auth_mod, "get_codex_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda exclude_pids=None: [], raising=False)

    def _unexpected_systemctl(*args, **kwargs):
        raise AssertionError("systemctl should not be called in the Termux status view")

    monkeypatch.setattr(status_mod.subprocess, "run", _unexpected_systemctl)

    status_mod.show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Manager:      Termux / manual process" in output
    assert "Start with:   hermes gateway" in output
    assert "systemd (user)" not in output


def test_show_status_includes_runtime_contract_security_and_runtime_sections(monkeypatch, capsys, tmp_path):
    from hermes_cli import status as status_mod
    import hermes_cli.auth as auth_mod

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(status_mod, "get_env_path", lambda: tmp_path / ".env", raising=False)
    monkeypatch.setattr(status_mod, "get_hermes_home", lambda: tmp_path, raising=False)
    monkeypatch.setattr(
        status_mod,
        "load_config",
        lambda: {"model": {"default": "gpt-5.4"}, "memory": {"provider": "holographic"}, "terminal": {"backend": "local"}},
        raising=False,
    )
    monkeypatch.setattr(status_mod, "resolve_requested_provider", lambda requested=None: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "resolve_provider", lambda requested=None, **kwargs: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "provider_label", lambda provider: "OpenAI Codex", raising=False)
    monkeypatch.setattr(auth_mod, "get_nous_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(auth_mod, "get_codex_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(auth_mod, "get_qwen_auth_status", lambda: {}, raising=False)

    cron_dir = tmp_path / "cron"
    cron_dir.mkdir(parents=True, exist_ok=True)
    (cron_dir / "jobs.json").write_text(json.dumps({
        "jobs": [
            {"id": "job1", "enabled": True, "deliver": "origin", "last_delivery_error": "boom"},
            {"id": "job2", "enabled": False, "deliver": "local"},
        ]
    }))

    status_mod.show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "◆ Runtime Contract" in output
    assert "모델/프로바이더:" in output
    assert "터미널 백엔드:" in output
    assert "메모리 모드:" in output
    assert "◆ Security Boundaries" in output
    assert "dangerous command approval" in output.lower()
    assert "git reset --hard" in output
    assert "세션 기준으로 확인받음" in output
    assert "◆ Autonomous Execution" in output
    assert "예약됨: 1" in output
    assert "일시정지: 1" in output
    assert "전달 실패: 1" in output
    assert "hermes cron list" in output
    assert "process(action='poll')" in output


def test_summarize_autonomous_execution_shows_jobs_file_parse_hint(monkeypatch, tmp_path):
    cron_dir = tmp_path / "cron"
    cron_dir.mkdir(parents=True, exist_ok=True)
    (cron_dir / "jobs.json").write_text("{broken json", encoding="utf-8")
    monkeypatch.setattr(
        runtime_surfaces.process_registry,
        "get_state_snapshot",
        lambda: {"running": 2, "finished_recent": 1, "watch_disabled": 3},
        raising=False,
    )

    lines = runtime_surfaces.summarize_autonomous_execution(hermes_home=tmp_path)

    assert "상태 메모: cron 상태 파일 읽기 오류" in lines
    assert "백그라운드 실행 중: 2" in lines
    assert "최근 종료됨: 1" in lines
    assert "watch 비활성화: 3" in lines


def test_summarize_security_boundaries_reflects_non_session_scoped_policy(monkeypatch):
    monkeypatch.setattr(
        runtime_surfaces,
        "approval_policy_summary",
        lambda: {
            "dangerous_pattern_count": 4,
            "examples": ["force push"],
            "session_scoped": False,
        },
        raising=False,
    )

    lines = runtime_surfaces.summarize_security_boundaries()

    assert "dangerous command approval: enabled (4 patterns)" in lines
    assert "고위험 예시: force push" in lines
    assert "승인 경계: 파괴적 명령은 세션 고정 아님" in lines
