from pathlib import Path

from agent.repo_map import (
    build_repo_map,
    extract_focused_submap,
    render_focused_submap_markdown,
    render_repo_map_markdown,
)


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / "AGENTS.md").write_text("Use tests\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n")

    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "main.py").write_text("def main():\n    return 'ok'\n")
    (tmp_path / "agent" / "auth_flow.py").write_text("def login():\n    return True\n")

    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "run.py").write_text("def run():\n    return 'gateway'\n")
    (tmp_path / "gateway" / "platforms").mkdir(parents=True, exist_ok=True)
    (tmp_path / "gateway" / "platforms" / "telegram.py").write_text("class TelegramPlatform: ...\n")
    (tmp_path / "gateway" / "platforms" / "discord.py").write_text("class DiscordPlatform: ...\n")

    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "file_tools.py").write_text("def read_file():\n    return {}\n")

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_gateway.py").write_text("def test_gateway():\n    assert True\n")
    return tmp_path


def test_build_repo_map_collects_top_level_summary(tmp_path):
    repo = _make_repo(tmp_path)
    result = build_repo_map(repo)

    assert result["repo_root"] == str(repo.resolve())
    assert "agent" in result["top_directories"]
    assert "gateway" in result["top_directories"]
    assert any(path.endswith("README.md") for path in result["representative_files"])
    assert result["suffix_counts"][".py"] >= 6


def test_build_repo_map_excludes_git_directory_from_summary(tmp_path):
    repo = _make_repo(tmp_path)
    result = build_repo_map(repo)

    assert ".git" not in result["top_directories"]
    assert all(".git/" not in path for path in result["representative_files"])


def test_build_repo_map_flags_entrypoints_and_tests(tmp_path):
    repo = _make_repo(tmp_path)
    result = build_repo_map(repo)

    assert any(path.endswith("agent/main.py") for path in result["representative_files"])
    assert any(path.endswith("gateway/run.py") for path in result["representative_files"])
    assert any(path.endswith("tests/test_gateway.py") for path in result["representative_files"])


def test_render_repo_map_markdown_includes_human_sections(tmp_path):
    repo = _make_repo(tmp_path)
    result = build_repo_map(repo)
    text = render_repo_map_markdown(result)

    assert "리포 지도" in text
    assert "상위 디렉터리" in text
    assert "대표 파일" in text


def test_extract_focused_submap_prefers_auth_files(tmp_path):
    repo = _make_repo(tmp_path)
    repo_map = build_repo_map(repo)

    submap = extract_focused_submap(repo_map, "auth flow")

    assert any("auth" in path for path in submap["matched_files"])
    assert "auth" in submap["reason_terms"]


def test_extract_focused_submap_prefers_gateway_platform_adapters(tmp_path):
    repo = _make_repo(tmp_path)
    repo_map = build_repo_map(repo)

    submap = extract_focused_submap(repo_map, "gateway adapters")

    assert any("gateway/platforms" in path for path in submap["matched_files"])
    assert any(term in submap["reason_terms"] for term in ["gateway", "adapters"])


def test_render_focused_submap_markdown_is_compact_and_human(tmp_path):
    repo = _make_repo(tmp_path)
    repo_map = build_repo_map(repo)

    text = render_focused_submap_markdown(extract_focused_submap(repo_map, "gateway adapters"))

    assert "질문:" in text
    assert "먼저 볼 후보" in text
    assert "gateway/platforms" in text
