from __future__ import annotations

import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chunker import chunk_text
from file_indexer import load_index, save_index, scan_changed_files
from memory_os.client import MemoryOSClient
from memory_common import (
    get_collection,
    parse_common_args,
    read_text_file,
    resolve_context,
    setup_logging,
    stable_doc_id,
    update_project_state,
    utc_now,
)


def delete_existing_chunks(collection: Any, file_entry: dict[str, Any] | None) -> None:
    ids = (file_entry or {}).get("ids", [])
    if ids:
        collection.delete(ids=ids)


def index_file(ctx, collection: Any, file_info: dict[str, Any], old_entry: dict[str, Any] | None) -> dict[str, Any] | None:
    text = read_text_file(file_info["path"])
    if text is None:
        return None

    chunks = chunk_text(text)
    delete_existing_chunks(collection, old_entry)
    if not chunks:
        return {
            "hash": file_info["hash"],
            "size": file_info["size"],
            "mtime": file_info["mtime"],
            "chunk_count": 0,
            "ids": [],
            "last_indexed": utc_now(),
        }

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for chunk in chunks:
        content_hash = hashlib.sha1(chunk.text.encode("utf-8")).hexdigest()
        doc_id = stable_doc_id(ctx.project_name, file_info["relative_path"], chunk.index, content_hash)
        ids.append(doc_id)
        documents.append(chunk.text)
        metadatas.append(
            {
                "file_path": file_info["relative_path"],
                "project_name": ctx.project_name,
                "chunk_index": chunk.index,
                "content_hash": content_hash,
                "indexed_at": utc_now(),
                "mtime": file_info["mtime"],
                "is_architecture": int(
                    any(
                        hint in file_info["relative_path"].lower()
                        for hint in ("readme", "architecture", "design", "config", "route", "schema", "model")
                    )
                ),
            }
        )

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return {
        "hash": file_info["hash"],
        "size": file_info["size"],
        "mtime": file_info["mtime"],
        "chunk_count": len(chunks),
        "ids": ids,
        "last_indexed": utc_now(),
    }


def main() -> int:
    parser = parse_common_args("Store changed project files in persistent Chroma memory.")
    parser.add_argument("--max-files", type=int, default=250, help="Safety cap for changed files per run.")
    args = parser.parse_args()
    setup_logging(args.verbose)
    ctx = resolve_context(args.project_root, args.memory_root)
    server_url = os.environ.get("MEMORY_OS_SERVER_URL")
    if server_url:
        client = MemoryOSClient(server_url)
        result = client.post(
            "/store",
            {
                "root": str(ctx.root),
                "scan_files": True,
                "tool": os.environ.get("MEMORY_OS_TOOL", "codex"),
                "event": os.environ.get("MEMORY_OS_EVENT", "PostToolUse"),
                "async_store": False,
            },
        )
        print(
            f"[memory-os] Indexed {result.get('indexed_files', 0)} changed file(s), "
            f"removed {result.get('removed_files', 0)} deleted file(s), "
            f"stored {result.get('stored_entries', 0)} event(s)."
        )
        return 0

    index = load_index(ctx.index_path)
    changed, removed = scan_changed_files(ctx.root, index)

    if not changed and not removed:
        print("[codex-memory] No changed files to index.")
        return 0

    if len(changed) > args.max_files:
        logging.warning("Changed file count %s exceeds cap %s; indexing first batch only", len(changed), args.max_files)
        changed = changed[: args.max_files]

    try:
        collection = get_collection(ctx)
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 2

    for relative in removed:
        delete_existing_chunks(collection, index["files"].get(relative))
        index["files"].pop(relative, None)

    indexed_paths: list[str] = []
    for file_info in changed:
        relative = file_info["relative_path"]
        old_entry = index["files"].get(relative)
        entry = index_file(ctx, collection, file_info, old_entry)
        if entry is not None:
            index["files"][relative] = entry
            indexed_paths.append(relative)

    save_index(ctx.index_path, index)
    if indexed_paths:
        update_project_state(ctx, active_files=indexed_paths)

    print(
        f"[codex-memory] Indexed {len(indexed_paths)} changed file(s), "
        f"removed {len(removed)} deleted file(s) for {ctx.project_name}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
