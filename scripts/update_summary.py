from __future__ import annotations

from collections import Counter
import os
import sys
import urllib.parse
from pathlib import PurePosixPath
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_indexer import load_index
from memory_os.client import MemoryOSClient
from memory_common import (
    ensure_project_state,
    parse_common_args,
    resolve_context,
    setup_logging,
    utc_now,
    write_json_atomic,
)


def markdown_list(items: list[str], empty: str = "None recorded.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def top_directories(files: list[str], limit: int = 10) -> list[str]:
    counts: Counter[str] = Counter()
    for file_path in files:
        parent = str(PurePosixPath(file_path).parent)
        counts[parent if parent != "." else "/"] += 1
    return [f"{directory}: {count} file(s)" for directory, count in counts.most_common(limit)]


def write_summary(ctx, state: dict, index: dict) -> None:
    files = sorted(index.get("files", {}).keys())
    chunk_total = sum(int(entry.get("chunk_count", 0)) for entry in index.get("files", {}).values())
    active_files = state.get("active_files", [])
    lines = [
        f"# Project Memory Summary: {ctx.project_name}",
        "",
        f"- Project root: `{ctx.root}`",
        f"- Last opened: {state.get('last_opened', 'unknown')}",
        f"- Summary updated: {utc_now()}",
        f"- Indexed files: {len(files)}",
        f"- Indexed chunks: {chunk_total}",
        "",
        "## Active Files",
        markdown_list(active_files[:25]),
        "",
        "## Known Bugs",
        markdown_list(state.get("known_bugs", [])),
        "",
        "## Decisions",
        markdown_list(state.get("decisions", [])),
        "",
        "## Todos",
        markdown_list(state.get("todos", [])),
        "",
        "## Indexed Areas",
        markdown_list(top_directories(files)),
        "",
        "## Recent Indexed Files",
        markdown_list(files[-25:]),
        "",
    ]
    ctx.summary_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = parse_common_args("Update readable project memory summary.")
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
                "scan_files": False,
                "tool": os.environ.get("MEMORY_OS_TOOL", "codex"),
                "event": "Session stopped; update summary",
                "async_store": False,
            },
        )
        summary = client.get("/summary", urllib.parse.urlencode({"root": str(ctx.root)}))
        print(f"[memory-os] Summary available for {summary.get('project_name')} after store {result.get('project_id')}.")
        return 0

    state = ensure_project_state(ctx)
    index = load_index(ctx.index_path)
    write_summary(ctx, state, index)
    write_json_atomic(ctx.state_path, state)
    print(f"[codex-memory] Summary updated: {ctx.summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
