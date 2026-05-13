from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_os.config import Settings
from memory_os.schemas import MemoryEntry, RetrieveRequest, StoreRequest
from memory_os.service import MemoryOS


def main() -> int:
    os.environ.setdefault("CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS", "1")
    workspace = Path(__file__).resolve().parents[1]
    project = workspace / ".smoke-memory-os-project"
    memory = workspace / ".smoke-memory-os-store"
    shutil.rmtree(project, ignore_errors=True)
    shutil.rmtree(memory, ignore_errors=True)
    (project / "src").mkdir(parents=True)
    (project / "README.md").write_text(
        "# Memory OS Smoke\n\nArchitecture: route to AuthService then store.\n",
        encoding="utf-8",
    )
    (project / "src" / "auth.py").write_text(
        "class AuthService:\n    def login(self, user):\n        return user == 'admin'\n",
        encoding="utf-8",
    )

    service = MemoryOS(
        Settings(
            memory_root=memory,
            match_threshold=0.85,
            cache_ttl_seconds=30,
            max_retrieve_chunks=8,
            max_scan_files=200,
        )
    )
    first = service.store(StoreRequest(root=str(project), scan_files=True, async_store=False, tool="smoke"))
    second = service.store(StoreRequest(root=str(project), scan_files=True, async_store=False, tool="smoke"))
    (project / "src" / "auth.py").write_text(
        "class AuthService:\n    def login(self, user):\n        return user in {'admin', 'manager'}\n\n    def logout(self):\n        return True\n",
        encoding="utf-8",
    )
    third = service.store(
        StoreRequest(
            root=str(project),
            scan_files=True,
            entries=[MemoryEntry(layer="semantic", text="Decision: AuthService accepts admin and manager roles.")],
            async_store=False,
            tool="smoke",
        )
    )
    retrieved = service.retrieve(RetrieveRequest(root=str(project), query="manager login AuthService decision", top_k=5))
    assert first.indexed_files == 2, first
    assert second.indexed_files == 0, second
    assert third.indexed_files == 1, third
    assert any("manager" in chunk.text for chunk in retrieved.chunks), retrieved
    print(
        "smoke ok:",
        {
            "project_id": retrieved.project_id,
            "initial_indexed": first.indexed_files,
            "unchanged_indexed": second.indexed_files,
            "changed_indexed": third.indexed_files,
            "retrieved_chunks": len(retrieved.chunks),
        },
    )
    shutil.rmtree(project, ignore_errors=True)
    shutil.rmtree(memory, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
