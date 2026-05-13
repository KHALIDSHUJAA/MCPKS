from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from memory_common import (
    file_md5,
    load_json,
    read_text_file,
    rel_path,
    should_skip_path,
    utc_now,
    write_json_atomic,
)


def empty_index() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "files": {},
    }


def load_index(index_path: Path) -> dict[str, Any]:
    index = load_json(index_path, empty_index())
    if "files" not in index or not isinstance(index["files"], dict):
        index = empty_index()
    return index


def save_index(index_path: Path, index: dict[str, Any]) -> None:
    index["updated_at"] = utc_now()
    write_json_atomic(index_path, index)


def iter_project_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip_path(path, root):
            continue
        yield path


def scan_changed_files(root: Path, index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    known_files = index.get("files", {})
    seen: set[str] = set()
    changed: list[dict[str, Any]] = []

    for path in iter_project_files(root):
        relative = rel_path(path, root)
        seen.add(relative)
        if read_text_file(path, max_bytes=64 * 1024) is None:
            continue
        try:
            stat = path.stat()
            digest = file_md5(path)
        except OSError as exc:
            logging.debug("Skipping %s: %s", path, exc)
            continue
        old = known_files.get(relative, {})
        if old.get("hash") != digest:
            changed.append(
                {
                    "path": path,
                    "relative_path": relative,
                    "hash": digest,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )

    removed = [relative for relative in known_files if relative not in seen]
    return changed, removed
