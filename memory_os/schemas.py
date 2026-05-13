from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryLayer = Literal["raw", "semantic", "architecture", "event"]


class ProjectSnapshot(BaseModel):
    root: str
    open_files: list[str] = Field(default_factory=list)
    prompt: str | None = None
    tool: str | None = None


class ProjectDetectionResult(BaseModel):
    project_id: str
    project_name: str
    confidence: float
    is_new: bool
    scores: dict[str, float]
    root: str


class MemoryEntry(BaseModel):
    text: str
    layer: MemoryLayer = "semantic"
    file_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreRequest(BaseModel):
    root: str
    entries: list[MemoryEntry] = Field(default_factory=list)
    scan_files: bool = True
    tool: str | None = None
    event: str | None = None
    async_store: bool = True


class StoreResponse(BaseModel):
    project_id: str
    indexed_files: int
    removed_files: int
    stored_entries: int
    queued: bool = False


class RetrieveRequest(BaseModel):
    root: str
    query: str
    layers: list[MemoryLayer] = Field(default_factory=lambda: ["raw", "semantic", "architecture", "event"])
    top_k: int = 8
    open_files: list[str] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    layer: MemoryLayer
    file_path: str | None = None
    chunk_index: int = 0
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    project_id: str
    project_name: str
    confidence: float
    summary: str | None = None
    chunks: list[RetrievedChunk]


class SummaryResponse(BaseModel):
    project_id: str
    project_name: str
    summary: str | None
    state: dict[str, Any]


class FeedbackRequest(BaseModel):
    root: str
    accepted_project_id: str | None = None
    correct: bool = True
    notes: str | None = None
