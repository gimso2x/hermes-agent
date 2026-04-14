from pathlib import Path

from agent.repo_map_cache import (
    compute_repo_map_cache_key,
    compute_repo_map_fingerprint,
    get_repo_map_cache_path,
    load_cached_repo_map,
    save_cached_repo_map,
)


def test_compute_repo_map_cache_key_is_stable(tmp_path):
    key1 = compute_repo_map_cache_key(tmp_path, "abc")
    key2 = compute_repo_map_cache_key(tmp_path, "abc")

    assert key1 == key2
    assert len(key1) >= 12


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes-home"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fingerprint = "fp-1"
    payload = {"repo_root": str(repo_root), "top_directories": ["agent"]}

    save_cached_repo_map(repo_root, fingerprint, payload)
    loaded = load_cached_repo_map(repo_root, fingerprint)

    assert loaded == payload


def test_cache_path_under_repo_map_cache_dir(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    path = get_repo_map_cache_path("abc123")

    assert str(path).startswith(str(hermes_home))
    assert "repo-map" in str(path)
    assert path.name == "abc123.json"


def test_fingerprint_changes_when_top_level_files_change(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("one")

    fp1 = compute_repo_map_fingerprint(repo_root)
    (repo_root / "pyproject.toml").write_text("[project]\nname='demo'\n")
    fp2 = compute_repo_map_fingerprint(repo_root)

    assert fp1 != fp2


def test_corrupted_cache_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes-home"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fingerprint = "fp-2"
    cache_path = get_repo_map_cache_path(compute_repo_map_cache_key(repo_root, fingerprint))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not-json")

    assert load_cached_repo_map(repo_root, fingerprint) is None
