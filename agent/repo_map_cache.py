from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hermes_constants import get_hermes_dir

_REPO_MAP_CACHE_VERSION = "v2"


def compute_repo_map_cache_key(repo_root: Path | str, fingerprint: str) -> str:
    root = str(Path(repo_root).expanduser().resolve())
    seed = f"{_REPO_MAP_CACHE_VERSION}|{root}|{fingerprint}".encode("utf-8", errors="replace")
    return hashlib.sha256(seed).hexdigest()[:24]


def get_repo_map_cache_path(cache_key: str) -> Path:
    return get_hermes_dir("cache/repo-map", "repo_map_cache") / f"{cache_key}.json"


def compute_repo_map_fingerprint(repo_root: Path | str) -> str:
    root = Path(repo_root).expanduser().resolve()
    parts = [str(root)]
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if path.name in {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}:
            continue
        stat = path.stat()
        parts.append(f"{path.name}:{int(stat.st_mtime_ns)}:{stat.st_size}")
    return hashlib.sha256("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:24]


def load_cached_repo_map(repo_root: Path | str, fingerprint: str) -> dict | None:
    path = get_repo_map_cache_path(compute_repo_map_cache_key(repo_root, fingerprint))
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_cached_repo_map(repo_root: Path | str, fingerprint: str, repo_map: dict) -> Path:
    path = get_repo_map_cache_path(compute_repo_map_cache_key(repo_root, fingerprint))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(repo_map, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path
