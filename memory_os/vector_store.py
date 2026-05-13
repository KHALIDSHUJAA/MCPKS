from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scripts.memory_common import get_embedding_function


LAYER_COLLECTIONS = {
    "raw": "memory_raw",
    "semantic": "memory_semantic",
    "architecture": "memory_architecture",
    "event": "memory_event",
}


def collection_safe(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value)[:42].strip("_")
    return safe or "project"


class VectorStore:
    def __init__(self, memory_root: Path) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed. Run setup.ps1 or pip install -r requirements.txt.") from exc
        self.memory_root = memory_root
        self.chroma_root = memory_root / "_server_chroma"
        self.chroma_root.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_root))
        self.embedding_function = get_embedding_function()

    def registry(self) -> Any:
        return self.client.get_or_create_collection(
            name="project_registry",
            embedding_function=self.embedding_function,
            metadata={"purpose": "project_fingerprints"},
        )

    def memory(self, project_id: str, layer: str) -> Any:
        if layer not in LAYER_COLLECTIONS:
            raise ValueError(f"Unknown memory layer: {layer}")
        return self.client.get_or_create_collection(
            name=f"{LAYER_COLLECTIONS[layer]}_{collection_safe(project_id)}",
            embedding_function=self.embedding_function,
            metadata={"project_id": project_id, "layer": layer},
        )
