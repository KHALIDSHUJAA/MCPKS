from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_indexer import load_index
from memory_os.client import MemoryOSClient
from memory_common import (
    architecture_score,
    get_collection,
    load_json,
    parse_common_args,
    resolve_context,
    setup_logging,
    stdin_json,
)


def extract_prompt(args: argparse.Namespace) -> str:
    if args.query:
        return args.query
    payload = stdin_json()
    for key in ("prompt", "user_prompt", "input", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    env_prompt = os.environ.get("CODEX_USER_PROMPT")
    return env_prompt.strip() if env_prompt else ""


def build_context(results: dict[str, Any], index: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] or [0.0] * len(documents)
    rows: list[dict[str, Any]] = []
    seen_content: set[str] = set()

    for document, metadata, distance in zip(documents, metadatas, distances):
        metadata = metadata or {}
        digest = metadata.get("content_hash") or hashlib.sha1(document.encode("utf-8")).hexdigest()
        if digest in seen_content:
            continue
        seen_content.add(digest)
        file_path = str(metadata.get("file_path", "unknown"))
        file_entry = index.get("files", {}).get(file_path, {})
        recency = float(file_entry.get("mtime", metadata.get("mtime", 0.0)) or 0.0)
        rows.append(
            {
                "file_path": file_path,
                "chunk_index": metadata.get("chunk_index", 0),
                "distance": float(distance),
                "recency": recency,
                "architecture": architecture_score(file_path),
                "text": document.strip(),
            }
        )

    rows.sort(key=lambda row: (row["distance"], -row["architecture"], -row["recency"]))
    return rows[:limit]


def render_context(ctx, rows: list[dict[str, Any]], summary: str | None) -> str:
    lines = [
        "<codex_memory_context>",
        f"project: {ctx.project_name}",
        f"root: {ctx.root}",
    ]
    if summary:
        clipped = "\n".join(summary.strip().splitlines()[:40])
        lines.extend(["", "summary:", clipped])
    if rows:
        lines.append("")
        lines.append("relevant_chunks:")
        for row in rows:
            lines.append(f"\n--- {row['file_path']}#chunk-{row['chunk_index']} ---")
            lines.append(row["text"][:3000])
    else:
        lines.append("No relevant memory chunks found.")
    lines.append("</codex_memory_context>")
    return "\n".join(lines)


def main() -> int:
    parser = parse_common_args("Retrieve relevant persistent project memory.")
    parser.add_argument("query", nargs="?", help="User prompt or search query.")
    parser.add_argument("--top-k", type=int, default=8, help="Maximum chunks to output.")
    parser.add_argument("--candidate-k", type=int, default=20, help="Raw Chroma candidates before re-ranking.")
    args = parser.parse_args()
    setup_logging(args.verbose)
    query = extract_prompt(args)
    ctx = resolve_context(args.project_root, args.memory_root)
    server_url = os.environ.get("MEMORY_OS_SERVER_URL")
    if server_url:
        client = MemoryOSClient(server_url)
        result = client.post(
            "/retrieve",
            {
                "root": str(ctx.root),
                "query": query or "project architecture recent changes",
                "top_k": max(1, min(args.top_k, 10)),
            },
        )
        lines = [
            "<codex_memory_context>",
            f"project: {result.get('project_name')}",
            f"project_id: {result.get('project_id')}",
        ]
        if result.get("summary"):
            lines.extend(["", "summary:", "\n".join(result["summary"].splitlines()[:40])])
        chunks = result.get("chunks") or []
        if chunks:
            lines.extend(["", "relevant_chunks:"])
            for chunk in chunks:
                path = chunk.get("file_path") or chunk.get("layer")
                lines.append(f"\n--- {path}#chunk-{chunk.get('chunk_index', 0)} [{chunk.get('layer')}] ---")
                lines.append((chunk.get("text") or "")[:3000])
        else:
            lines.append("No relevant memory chunks found.")
        lines.append("</codex_memory_context>")
        print("\n".join(lines))
        return 0

    index = load_index(ctx.index_path)
    state = load_json(ctx.state_path, {})
    summary = ctx.summary_path.read_text(encoding="utf-8") if ctx.summary_path.exists() else None

    if not query:
        query = " ".join(state.get("active_files", [])[:5]) or "project architecture recent changes"

    try:
        collection = get_collection(ctx)
        count = collection.count()
        if count == 0:
            print(render_context(ctx, [], summary))
            return 0
        results = collection.query(query_texts=[query], n_results=min(args.candidate_k, count))
    except RuntimeError as exc:
        logging.error("%s", exc)
        if summary:
            print(render_context(ctx, [], summary))
            return 0
        return 2

    rows = build_context(results, index, max(1, min(args.top_k, 10)))
    print(render_context(ctx, rows, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
