from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.file_indexer import iter_project_files
from scripts.memory_common import read_text_file, rel_path, sanitize_project_name


MANIFESTS = (
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "Cargo.toml",
    "go.mod",
    "pubspec.yaml",
    "composer.json",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "settings.gradle",
    "Dockerfile",
    "docker-compose.yml",
)


def safe_git(root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def dependency_text(root: Path) -> tuple[list[str], str]:
    found: list[str] = []
    snippets: list[str] = []
    for name in MANIFESTS:
        path = root / name
        if not path.exists() or not path.is_file():
            continue
        found.append(name)
        text = read_text_file(path, max_bytes=120_000)
        if text:
            snippets.append(f"--- {name} ---\n{text[:8000]}")
    return found, "\n".join(snippets)


def folder_snapshot(root: Path, max_files: int = 600) -> dict[str, Any]:
    suffix_counts: Counter[str] = Counter()
    top_dirs: Counter[str] = Counter()
    files: list[str] = []
    for index, path in enumerate(iter_project_files(root)):
        if index >= max_files:
            break
        relative = rel_path(path, root)
        files.append(relative)
        suffix_counts[path.suffix.lower() or "<none>"] += 1
        first = relative.split("/", 1)[0]
        top_dirs[first] += 1
    manifests, deps = dependency_text(root)
    return {
        "files": files[:120],
        "suffix_counts": dict(suffix_counts.most_common(30)),
        "top_dirs": dict(top_dirs.most_common(30)),
        "manifests": manifests,
        "dependency_text": deps,
    }


def build_fingerprint(root: Path, max_files: int = 600) -> dict[str, Any]:
    root = root.resolve()
    snapshot = folder_snapshot(root, max_files=max_files)
    git_remote = safe_git(root, ["config", "--get", "remote.origin.url"])
    git_top = safe_git(root, ["rev-parse", "--show-toplevel"])
    git_head = safe_git(root, ["rev-parse", "--short", "HEAD"])
    identity_text = "\n".join(
        [
            f"name: {root.name}",
            f"path_leaf: {sanitize_project_name(root.name)}",
            f"manifests: {', '.join(snapshot['manifests'])}",
            f"top_dirs: {json.dumps(snapshot['top_dirs'], sort_keys=True)}",
            f"suffixes: {json.dumps(snapshot['suffix_counts'], sort_keys=True)}",
            f"git_remote: {git_remote or ''}",
            f"files: {' '.join(snapshot['files'][:80])}",
            snapshot["dependency_text"][:12000],
        ]
    )
    structure_hash = hashlib.sha1(
        json.dumps(
            {
                "manifests": snapshot["manifests"],
                "top_dirs": snapshot["top_dirs"],
                "suffix_counts": snapshot["suffix_counts"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "root": str(root),
        "name": sanitize_project_name(root.name),
        "identity_text": identity_text,
        "structure_hash": structure_hash,
        "manifests": snapshot["manifests"],
        "top_dirs": snapshot["top_dirs"],
        "suffix_counts": snapshot["suffix_counts"],
        "git_remote": git_remote,
        "git_top": git_top,
        "git_head": git_head,
        "files": snapshot["files"],
    }


def jaccard_dict(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_keys = set(left)
    right_keys = set(right)
    if not left_keys and not right_keys:
        return 0.0
    return len(left_keys & right_keys) / max(1, len(left_keys | right_keys))


def manifest_score(left: list[str], right: list[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def git_score(left: dict[str, Any], right: dict[str, Any]) -> float:
    if left.get("git_remote") and left.get("git_remote") == right.get("git_remote"):
        return 1.0
    if left.get("git_top") and left.get("git_top") == right.get("git_top"):
        return 0.8
    return 0.0
