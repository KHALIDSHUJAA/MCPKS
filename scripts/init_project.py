from __future__ import annotations

import logging
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_os.client import MemoryOSClient
from memory_common import (
    ensure_project_state,
    parse_common_args,
    resolve_context,
    setup_logging,
    update_project_state,
    utc_now,
)


def main() -> int:
    parser = parse_common_args("Initialize project-aware Codex memory.")
    args = parser.parse_args()
    setup_logging(args.verbose)
    server_url = os.environ.get("MEMORY_OS_SERVER_URL")
    if server_url:
        ctx = resolve_context(args.project_root, args.memory_root)
        client = MemoryOSClient(server_url)
        detection = client.post("/detect_project", {"root": str(ctx.root)})
        summary = client.get("/summary", urllib.parse.urlencode({"root": str(ctx.root)}))
        print(f"[memory-os] Loading project memory: {detection['project_name']} ({detection['project_id']})")
        if summary.get("summary"):
            print("\n[memory-os] Existing project summary:\n")
            print(summary["summary"])
        else:
            print("[memory-os] No summary yet. It will be created at session end.")
        return 0

    ctx = resolve_context(args.project_root, args.memory_root)
    ensure_project_state(ctx)
    update_project_state(ctx, last_opened=utc_now())

    print(f"[codex-memory] Loading project memory: {ctx.project_name}")
    print(f"[codex-memory] Project: {ctx.root}")
    if ctx.summary_path.exists():
        print("\n[codex-memory] Existing project summary:\n")
        print(ctx.summary_path.read_text(encoding="utf-8"))
    else:
        logging.info("No summary exists yet for %s", ctx.project_name)
        print("[codex-memory] No summary yet. It will be created at session end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
