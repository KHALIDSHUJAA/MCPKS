from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_IGNORE_DIRS = {
    ".codex",
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}

DEFAULT_IGNORE_SUFFIXES = {
    ".7z",
    ".a",
    ".app",
    ".bin",
    ".bmp",
    ".class",
    ".db",
    ".dll",
    ".dmg",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mp3",
    ".mp4",
    ".o",
    ".obj",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".so",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}

ARCHITECTURE_HINTS = (
    "architecture",
    "design",
    "readme",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "dockerfile",
    "compose",
    "config",
    "settings",
    "router",
    "routes",
    "schema",
    "model",
    "service",
)


@dataclass(frozen=True)
class ProjectContext:
    root: Path
    memory_root: Path
    project_name: str
    project_dir: Path
    chroma_dir: Path
    state_path: Path
    summary_path: Path
    index_path: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def setup_logging(verbose: bool = False) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_common_args(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--project-root",
        default=os.environ.get("CODEX_PROJECT_ROOT"),
        help="Project root to index. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--memory-root",
        default=os.environ.get("CODEX_MEMORY_ROOT"),
        help="Memory root. Defaults to ./memory beside this repository.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def script_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_project_root(value: str | None = None) -> Path:
    root = Path(value).expanduser() if value else Path.cwd()
    return root.resolve()


def sanitize_project_name(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-._")
    return clean or "project"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not read %s: %s", path, exc)
        return default


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def resolve_context(project_root: str | None = None, memory_root: str | None = None) -> ProjectContext:
    root = detect_project_root(project_root)
    mem_root = Path(memory_root).expanduser().resolve() if memory_root else script_repo_root() / "memory"
    base_name = sanitize_project_name(root.name)
    project_dir = mem_root / base_name

    existing_state = load_json(project_dir / "project_state.json", {})
    existing_root = existing_state.get("project_root")
    if existing_root and Path(existing_root).resolve() != root:
        path_hash = hashlib.md5(str(root).encode("utf-8")).hexdigest()[:8]
        project_dir = mem_root / f"{base_name}-{path_hash}"

    project_dir.mkdir(parents=True, exist_ok=True)
    return ProjectContext(
        root=root,
        memory_root=mem_root,
        project_name=project_dir.name,
        project_dir=project_dir,
        chroma_dir=project_dir / "chroma",
        state_path=project_dir / "project_state.json",
        summary_path=project_dir / "summary.md",
        index_path=project_dir / "index.json",
    )


def ensure_project_state(ctx: ProjectContext) -> dict[str, Any]:
    state = load_json(ctx.state_path, {})
    changed = False
    defaults = {
        "project_name": ctx.project_name,
        "project_root": str(ctx.root),
        "last_opened": utc_now(),
        "active_files": [],
        "known_bugs": [],
        "decisions": [],
        "todos": [],
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value
            changed = True
    if state.get("project_root") != str(ctx.root):
        state["project_root"] = str(ctx.root)
        changed = True
    if changed:
        write_json_atomic(ctx.state_path, state)
    return state


def update_project_state(ctx: ProjectContext, **updates: Any) -> dict[str, Any]:
    state = ensure_project_state(ctx)
    for key, value in updates.items():
        if key == "active_files":
            current = [item for item in state.get("active_files", []) if isinstance(item, str)]
            merged = list(dict.fromkeys([*value, *current]))[:25]
            state["active_files"] = merged
        else:
            state[key] = value
    write_json_atomic(ctx.state_path, state)
    return state


def file_md5(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    try:
        sample = path.read_bytes()[:sample_size]
    except OSError:
        return True
    return b"\x00" in sample


def should_skip_path(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    parts = set(rel.parts)
    if parts & DEFAULT_IGNORE_DIRS:
        return True
    if path.suffix.lower() in DEFAULT_IGNORE_SUFFIXES:
        return True
    return False


def read_text_file(path: Path, max_bytes: int = 1_500_000) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            logging.info("Skipping large file %s", path)
            return None
        if is_probably_binary(path):
            logging.debug("Skipping binary file %s", path)
            return None
        raw = path.read_bytes()
    except OSError as exc:
        logging.debug("Skipping unreadable file %s: %s", path, exc)
        return None

    for encoding in ("utf-8", "utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    logging.debug("Skipping undecodable file %s", path)
    return None


def rel_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def stable_doc_id(project_name: str, relative_path: str, chunk_index: int, content_hash: str) -> str:
    seed = f"{project_name}:{relative_path}:{chunk_index}:{content_hash}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def architecture_score(path: str) -> float:
    lower = path.lower()
    return 1.0 if any(hint in lower for hint in ARCHITECTURE_HINTS) else 0.0


def unique_keep_order(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def fail_soft(message: str, code: int = 0) -> None:
    logging.warning(message)
    raise SystemExit(code)


class DeterministicEmbeddingFunction:
    """Local test embedding. Production should use OpenAI via OPENAI_API_KEY."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "codex-memory-deterministic"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "DeterministicEmbeddingFunction":
        return DeterministicEmbeddingFunction(dimensions=int(config.get("dimensions", 1536)))

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions}

    def embed_query(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma API name
        return self.__call__(input)

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma API name
        vectors: list[list[float]] = []
        for text in input:
            values = [0.0] * self.dimensions
            tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
            for token in tokens or [text[:64]]:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                values[idx] += sign
            norm = sum(v * v for v in values) ** 0.5 or 1.0
            vectors.append([v / norm for v in values])
        return vectors


def get_embedding_function() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("CODEX_MEMORY_EMBEDDING_MODEL", "text-embedding-3-small")
    if api_key:
        try:
            from chromadb.utils import embedding_functions
        except ImportError as exc:
            raise RuntimeError("chromadb is installed incorrectly; cannot load OpenAI embedding function") from exc
        return embedding_functions.OpenAIEmbeddingFunction(api_key=api_key, model_name=model)

    if os.environ.get("CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS") == "1":
        return DeterministicEmbeddingFunction()

    raise RuntimeError(
        "OPENAI_API_KEY is required for production embeddings. "
        "Set CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS=1 only for local smoke tests."
    )


def get_collection(ctx: ProjectContext) -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is not installed. Run setup.sh or pip install -r requirements.txt.") from exc

    ctx.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(ctx.chroma_dir))
    return client.get_or_create_collection(
        name="project_memory",
        embedding_function=get_embedding_function(),
        metadata={"project_name": ctx.project_name},
    )


def stdin_json() -> dict[str, Any]:
    if sys.stdin is None or sys.stdin.closed:
        return {}
    try:
        data = sys.stdin.read()
    except OSError:
        return {}
    if not data.strip():
        return {}
    try:
        value = json.loads(data)
    except json.JSONDecodeError:
        return {"prompt": data}
    return value if isinstance(value, dict) else {}
