from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.chunker import chunk_text
from scripts.file_indexer import load_index, save_index, scan_changed_files
from scripts.memory_common import (
    architecture_score,
    load_json,
    read_text_file,
    stable_doc_id,
    utc_now,
    write_json_atomic,
)
from scripts.update_summary import write_summary

from .cache import TTLCache
from .config import Settings
from .fingerprint import build_fingerprint
from .registry import ProjectRegistry
from .schemas import (
    FeedbackRequest,
    MemoryEntry,
    ProjectDetectionResult,
    RetrieveRequest,
    RetrieveResponse,
    RetrievedChunk,
    StoreRequest,
    StoreResponse,
    SummaryResponse,
)
from .vector_store import VectorStore


class MemoryOS:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.memory_root.mkdir(parents=True, exist_ok=True)
        self.vector_store = VectorStore(settings.memory_root)
        self.registry = ProjectRegistry(settings.memory_root, self.vector_store, settings.match_threshold)
        self.cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)

    def project_dir(self, project_id: str) -> Path:
        path = self.settings.memory_root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def index_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "index.json"

    def state_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project_state.json"

    def summary_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "summary.md"

    def detect_project(self, root: str) -> ProjectDetectionResult:
        root_path = Path(root).expanduser().resolve()
        fingerprint = build_fingerprint(root_path, max_files=self.settings.max_scan_files)
        result = self.registry.detect(root_path, fingerprint)
        self.ensure_state(result, root_path)
        return result

    def ensure_state(self, detection: ProjectDetectionResult, root: Path) -> dict[str, Any]:
        state_path = self.state_path(detection.project_id)
        state = load_json(state_path, {})
        state.setdefault("project_id", detection.project_id)
        state.setdefault("project_name", detection.project_name)
        state.setdefault("project_root", str(root))
        state.setdefault("last_opened", utc_now())
        state.setdefault("active_files", [])
        state.setdefault("known_bugs", [])
        state.setdefault("decisions", [])
        state.setdefault("todos", [])
        state.setdefault("memory_layers", {"raw": 0, "semantic": 0, "architecture": 0, "event": 0})
        state["last_opened"] = utc_now()
        write_json_atomic(state_path, state)
        return state

    def store(self, request: StoreRequest) -> StoreResponse:
        detection = self.detect_project(request.root)
        root = Path(request.root).expanduser().resolve()
        indexed_files = 0
        removed_files = 0
        stored_entries = 0

        if request.scan_files:
            indexed_files, removed_files = self.store_changed_files(detection, root)
        if request.entries:
            stored_entries += self.store_entries(detection, request.entries, tool=request.tool)
        if request.event or request.tool:
            event_text = request.event or f"Tool action from {request.tool}"
            stored_entries += self.store_entries(
                detection,
                [MemoryEntry(text=event_text, layer="event", metadata={"tool": request.tool or "unknown"})],
                tool=request.tool,
            )

        self.update_summary(detection.project_id)
        self.cache.clear()
        return StoreResponse(
            project_id=detection.project_id,
            indexed_files=indexed_files,
            removed_files=removed_files,
            stored_entries=stored_entries,
            queued=False,
        )

    def delete_existing_chunks(self, collection: Any, file_entry: dict[str, Any] | None, key: str = "ids") -> None:
        ids = (file_entry or {}).get(key, [])
        if ids:
            collection.delete(ids=ids)

    def store_changed_files(self, detection: ProjectDetectionResult, root: Path) -> tuple[int, int]:
        index = load_index(self.index_path(detection.project_id))
        changed, removed = scan_changed_files(root, index)
        raw_collection = self.vector_store.memory(detection.project_id, "raw")
        architecture_collection = self.vector_store.memory(detection.project_id, "architecture")

        for relative in removed:
            old_entry = index["files"].get(relative)
            self.delete_existing_chunks(raw_collection, old_entry)
            self.delete_existing_chunks(architecture_collection, old_entry, key="architecture_ids")
            index["files"].pop(relative, None)

        indexed_paths: list[str] = []
        for file_info in changed:
            text = read_text_file(file_info["path"])
            if text is None:
                continue
            chunks = chunk_text(text)
            old_entry = index["files"].get(file_info["relative_path"])
            self.delete_existing_chunks(raw_collection, old_entry)
            self.delete_existing_chunks(architecture_collection, old_entry, key="architecture_ids")
            ids: list[str] = []
            arch_ids: list[str] = []
            for chunk in chunks:
                content_hash = hashlib.sha1(chunk.text.encode("utf-8")).hexdigest()
                doc_id = stable_doc_id(detection.project_id, file_info["relative_path"], chunk.index, content_hash)
                metadata = {
                    "project_id": detection.project_id,
                    "project_name": detection.project_name,
                    "layer": "raw",
                    "file_path": file_info["relative_path"],
                    "chunk_index": chunk.index,
                    "content_hash": content_hash,
                    "mtime": file_info["mtime"],
                    "indexed_at": utc_now(),
                    "is_architecture": int(architecture_score(file_info["relative_path"])),
                }
                raw_collection.upsert(ids=[doc_id], documents=[chunk.text], metadatas=[metadata])
                ids.append(doc_id)
                if metadata["is_architecture"]:
                    arch_id = f"arch_{doc_id}"
                    architecture_collection.upsert(ids=[arch_id], documents=[chunk.text], metadatas=[{**metadata, "layer": "architecture"}])
                    arch_ids.append(arch_id)
            index["files"][file_info["relative_path"]] = {
                "hash": file_info["hash"],
                "size": file_info["size"],
                "mtime": file_info["mtime"],
                "chunk_count": len(chunks),
                "ids": ids,
                "architecture_ids": arch_ids,
                "last_indexed": utc_now(),
            }
            indexed_paths.append(file_info["relative_path"])

        save_index(self.index_path(detection.project_id), index)
        state = load_json(self.state_path(detection.project_id), {})
        state["active_files"] = list(dict.fromkeys([*indexed_paths, *state.get("active_files", [])]))[:30]
        layers = state.setdefault("memory_layers", {})
        layers["raw"] = self.vector_store.memory(detection.project_id, "raw").count()
        layers["architecture"] = self.vector_store.memory(detection.project_id, "architecture").count()
        write_json_atomic(self.state_path(detection.project_id), state)
        return len(indexed_paths), len(removed)

    def store_entries(self, detection: ProjectDetectionResult, entries: list[MemoryEntry], tool: str | None = None) -> int:
        stored = 0
        for entry in entries:
            collection = self.vector_store.memory(detection.project_id, entry.layer)
            content_hash = hashlib.sha1(entry.text.encode("utf-8")).hexdigest()
            doc_id = hashlib.sha1(f"{detection.project_id}:{entry.layer}:{entry.file_path}:{content_hash}".encode("utf-8")).hexdigest()
            metadata = {
                **entry.metadata,
                "project_id": detection.project_id,
                "project_name": detection.project_name,
                "layer": entry.layer,
                "file_path": entry.file_path or "",
                "chunk_index": 0,
                "content_hash": content_hash,
                "tool": tool or entry.metadata.get("tool", ""),
                "indexed_at": utc_now(),
            }
            collection.upsert(ids=[doc_id], documents=[entry.text], metadatas=[metadata])
            stored += 1
        state = load_json(self.state_path(detection.project_id), {})
        layers = state.setdefault("memory_layers", {})
        for layer in ("raw", "semantic", "architecture", "event"):
            layers[layer] = self.vector_store.memory(detection.project_id, layer).count()
        write_json_atomic(self.state_path(detection.project_id), state)
        return stored

    def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        detection = self.detect_project(request.root)
        cache_key = hashlib.sha1(
            f"{detection.project_id}:{request.query}:{','.join(request.layers)}:{request.top_k}".encode("utf-8")
        ).hexdigest()
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        chunks: list[RetrievedChunk] = []
        seen: set[str] = set()
        for layer in request.layers:
            collection = self.vector_store.memory(detection.project_id, layer)
            count = collection.count()
            if not count:
                continue
            results = collection.query(query_texts=[request.query], n_results=min(max(request.top_k * 3, 10), count))
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] or [1.0] * len(docs)
            for doc, meta, distance in zip(docs, metas, distances):
                meta = meta or {}
                digest = meta.get("content_hash") or hashlib.sha1(doc.encode("utf-8")).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                file_path = meta.get("file_path") or None
                priority = architecture_score(file_path or "") * 0.08
                if file_path and file_path in request.open_files:
                    priority += 0.08
                score = max(0.0, 1.0 - float(distance)) + priority
                chunks.append(
                    RetrievedChunk(
                        layer=layer,
                        file_path=file_path,
                        chunk_index=int(meta.get("chunk_index", 0) or 0),
                        score=round(score, 4),
                        text=doc.strip()[:4000],
                        metadata=meta,
                    )
                )

        chunks.sort(key=lambda item: item.score, reverse=True)
        response = RetrieveResponse(
            project_id=detection.project_id,
            project_name=detection.project_name,
            confidence=detection.confidence,
            summary=self.read_summary(detection.project_id),
            chunks=chunks[: min(request.top_k, self.settings.max_retrieve_chunks)],
        )
        self.cache.set(cache_key, response)
        return response

    def read_summary(self, project_id: str) -> str | None:
        path = self.summary_path(project_id)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def update_summary(self, project_id: str) -> None:
        state = load_json(self.state_path(project_id), {})
        index = load_index(self.index_path(project_id))
        ctx = SimpleNamespace(
            project_name=state.get("project_name", project_id),
            root=Path(state.get("project_root", ".")),
            summary_path=self.summary_path(project_id),
        )
        write_summary(ctx, state, index)

    def summary(self, root: str) -> SummaryResponse:
        detection = self.detect_project(root)
        state = load_json(self.state_path(detection.project_id), {})
        return SummaryResponse(
            project_id=detection.project_id,
            project_name=detection.project_name,
            summary=self.read_summary(detection.project_id),
            state=state,
        )

    def feedback(self, request: FeedbackRequest) -> dict[str, Any]:
        detection = self.detect_project(request.root)
        project_id = request.accepted_project_id or detection.project_id
        return self.registry.feedback(project_id, request.correct, request.notes)
