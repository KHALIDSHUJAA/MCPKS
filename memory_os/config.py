from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    memory_root: Path
    match_threshold: float
    cache_ttl_seconds: int
    max_retrieve_chunks: int
    max_scan_files: int


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[1]
    return Settings(
        memory_root=Path(os.environ.get("MEMORY_OS_ROOT", repo_root / "memory")).expanduser().resolve(),
        match_threshold=float(os.environ.get("MEMORY_OS_MATCH_THRESHOLD", "0.85")),
        cache_ttl_seconds=int(os.environ.get("MEMORY_OS_CACHE_TTL", "45")),
        max_retrieve_chunks=int(os.environ.get("MEMORY_OS_MAX_RETRIEVE_CHUNKS", "10")),
        max_scan_files=int(os.environ.get("MEMORY_OS_MAX_SCAN_FILES", "600")),
    )
