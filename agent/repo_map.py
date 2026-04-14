from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Iterable

from agent.repo_map_cache import (
    compute_repo_map_fingerprint,
    load_cached_repo_map,
    save_cached_repo_map,
)

_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".tmp",
    ".mypy_cache",
    ".ruff_cache",
}

_REPRESENTATIVE_PRIORITY = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "main.py",
    "cli.py",
    "app.py",
    "run.py",
    "index.ts",
    "index.js",
]

_STOPWORDS = {
    "what", "show", "the", "and", "for", "with", "path", "flow", "files",
    "file", "about", "from", "into", "this", "that", "repo", "repository",
}

_DIR_PRIORITY = [
    "agent",
    "tools",
    "gateway",
    "tests",
    "hermes_cli",
    "cron",
    "acp_adapter",
    ".github",
    ".plans",
]


def _iter_files(root: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        if any(part.startswith(".") and part not in {".github", ".plans"} for part in rel_parts[:-1]):
            continue
        if path.is_file():
            if path.name.startswith(".") and path.name not in {".dockerignore", ".env.example", ".envrc"}:
                continue
            files.append(path)
        if len(files) >= max_files:
            break
    return files


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _suffix_counts(files: Iterable[Path]) -> dict[str, int]:
    counts = Counter()
    for path in files:
        counts[path.suffix or "[noext]"] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _collect_representative_files(root: Path, files: list[Path], *, limit: int = 12) -> list[str]:
    rels = [_rel(path, root) for path in files]
    chosen: list[str] = []
    seen: set[str] = set()

    for name in _REPRESENTATIVE_PRIORITY:
        for rel in rels:
            if rel.endswith(name) and rel not in seen:
                chosen.append(rel)
                seen.add(rel)
                if len(chosen) >= limit:
                    return chosen

    for rel in rels:
        if rel.startswith("tests/") and rel not in seen:
            chosen.append(rel)
            seen.add(rel)
            if len(chosen) >= limit:
                return chosen

    priority_prefixes = tuple(prefix + "/" for prefix in _DIR_PRIORITY)
    for rel in rels:
        if rel.startswith(priority_prefixes) and rel not in seen:
            chosen.append(rel)
            seen.add(rel)
            if len(chosen) >= limit:
                return chosen

    for rel in rels:
        if rel not in seen:
            chosen.append(rel)
            seen.add(rel)
            if len(chosen) >= limit:
                return chosen

    return chosen


def build_repo_map(repo_root: Path | str, *, max_files: int = 400) -> dict:
    root = Path(repo_root).expanduser().resolve()
    files = _iter_files(root, max_files=max_files)
    top_directory_counts = Counter(
        p.relative_to(root).parts[0] for p in files if len(p.relative_to(root).parts) > 1
    )
    ordered_top_directories = sorted(
        top_directory_counts,
        key=lambda name: (
            0 if name in _DIR_PRIORITY else 1,
            _DIR_PRIORITY.index(name) if name in _DIR_PRIORITY else 999,
            -top_directory_counts[name],
            name,
        ),
    )
    representative_files = _collect_representative_files(root, files)
    rel_files = [_rel(path, root) for path in files]
    return {
        "repo_root": str(root),
        "top_directories": ordered_top_directories,
        "representative_files": representative_files,
        "all_files": rel_files,
        "suffix_counts": _suffix_counts(files),
        "file_count": len(files),
    }



def get_or_build_repo_map(repo_root: Path | str, *, max_files: int = 400) -> dict:
    fingerprint = compute_repo_map_fingerprint(repo_root)
    cached = load_cached_repo_map(repo_root, fingerprint)
    if cached:
        return cached
    repo_map = build_repo_map(repo_root, max_files=max_files)
    save_cached_repo_map(repo_root, fingerprint, repo_map)
    return repo_map


def render_repo_map_markdown(repo_map: dict) -> str:
    lines = [
        "리포 지도",
        f"- 루트: {repo_map.get('repo_root', '')}",
        f"- 파일 수: {repo_map.get('file_count', 0)}",
        "",
        "상위 디렉터리",
    ]
    for name in repo_map.get("top_directories", [])[:12]:
        lines.append(f"- {name}")
    lines.append("")
    lines.append("대표 파일")
    for path in repo_map.get("representative_files", [])[:12]:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("파일 타입 분포")
    for suffix, count in list(repo_map.get("suffix_counts", {}).items())[:10]:
        lines.append(f"- {suffix}: {count}")
    return "\n".join(lines).strip()


def _normalize_terms(question: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_\-/]+", (question or "").lower())
    result = []
    for token in tokens:
        for part in re.split(r"[/_-]", token):
            part = part.strip()
            if len(part) >= 3 and part not in _STOPWORDS:
                result.append(part)
    return list(dict.fromkeys(result))


def extract_focused_submap(repo_map: dict, question: str, *, limit: int = 8) -> dict:
    terms = _normalize_terms(question)
    files = repo_map.get("all_files") or repo_map.get("representative_files", [])
    dirs = repo_map.get("top_directories", [])

    def score_path(path: str) -> tuple[int, str]:
        lower = path.lower()
        score = 0
        for term in terms:
            if term in lower:
                score += 4
            if lower.endswith(term + ".py") or f"/{term}." in lower:
                score += 3
            if f"/{term}/" in lower:
                score += 3
        if lower.startswith("gateway/platforms/") and any(term in {"gateway", "adapter", "adapters", "platform", "platforms"} for term in terms):
            score += 6
        if lower.startswith("tests/"):
            score -= 1
        return (score, path)

    scored = sorted((score_path(path) for path in files), reverse=True)
    matched_files = [path for score, path in scored if score > 0][:limit]
    matched_directories = [name for name in dirs if any(term in name.lower() for term in terms)][:limit]

    if not matched_files:
        matched_files = (repo_map.get("representative_files", []) or files)[: min(limit, len(files))]

    return {
        "question": question,
        "reason_terms": terms,
        "matched_directories": matched_directories,
        "matched_files": matched_files,
        "next_raw_targets": matched_files[:3],
    }


def render_focused_submap_markdown(submap: dict) -> str:
    lines = [
        f"질문: {submap.get('question', '')}",
        f"근거 키워드: {', '.join(submap.get('reason_terms', [])) or '없음'}",
        "",
        "먼저 볼 후보",
    ]
    for path in submap.get("matched_files", [])[:8]:
        lines.append(f"- {path}")
    if submap.get("matched_directories"):
        lines.append("")
        lines.append("관련 디렉터리")
        for name in submap.get("matched_directories", [])[:8]:
            lines.append(f"- {name}")
    return "\n".join(lines).strip()
