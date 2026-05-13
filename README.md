# AI Memory Operating System

This repository contains an IDE-agnostic, agent-agnostic memory system for AI coding tools. It can run locally through Codex hooks or as a centralized Memory OS server shared by Codex, Claude, Antigravity, Cursor, VS Code, and future tools.

Each detected project gets an isolated namespace under `memory/<project_id>/` with:

- `chroma/` persistent ChromaDB vector storage for local hook mode
- `project_state.json` active files, known bugs, decisions, todos, and timestamps
- `summary.md` readable session summary
- `index.json` file hashes and stored chunk ids

The centralized server also maintains:

- `memory/_server_chroma/` shared Chroma collections
- `memory/project_registry.json` project fingerprints, roots, scores, and feedback

## Install

```bash
./setup.sh
```

On Windows PowerShell:

```powershell
.\setup.ps1
```

For production retrieval and storage, set an OpenAI API key before agents start:

```bash
export OPENAI_API_KEY=your_api_key
```

The default embedding model is `text-embedding-3-small`. Override it with:

```bash
export CODEX_MEMORY_EMBEDDING_MODEL=text-embedding-3-large
```

For local smoke tests without network credentials only:

```bash
export CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS=1
```

## Central Server

Start the IDE-agnostic Memory OS server:

```bash
python scripts/run_server.py --host 127.0.0.1 --port 8765
```

Or:

```bash
uvicorn memory_os.server:app --host 127.0.0.1 --port 8765
```

Docker:

```bash
docker compose up --build
```

Production endpoints:

- `POST /detect_project`
- `POST /retrieve`
- `POST /store`
- `GET /summary?root=<path>`
- `POST /feedback`
- `POST /mcp` for JSON-RPC style MCP tool calls

Example:

```bash
curl -X POST http://127.0.0.1:8765/retrieve \
  -H "Content-Type: application/json" \
  -d '{"root":"/path/to/project","query":"How does auth work?","top_k":8}'
```

## Auto Project Detection

No `AGENTS.md`, manual config, or user-defined project id is required.

The detection engine scans a lightweight folder snapshot and builds a fingerprint from:

- file structure and top-level directories
- manifests such as `package.json`, `requirements.txt`, `pubspec.yaml`, `go.mod`
- dependency text
- git remote/root/head when available
- semantic fingerprint embedding

The registry compares candidates using:

```text
score = structure_score + dependency_score + embedding_similarity + git_signal
```

If the score is greater than `0.85`, the existing project namespace is reused. Otherwise a new namespace is created.

## Hooks

`.codex/hooks.json` wires the memory system into the Codex lifecycle:

- `SessionStart` runs `scripts/init_project.py`, creates project memory, and prints `summary.md` when it exists.
- `UserPromptSubmit` runs `scripts/retrieve_memory.py`, queries memory, and emits compact context for the current prompt.
- `PostToolUse` runs `scripts/store_memory.py`, detects changed files, chunks them, and stores only updated chunks.
- `Stop` runs `scripts/update_summary.py`, writing a readable markdown summary for the next session.

To make Codex hooks use the central server instead of local storage, set:

```bash
export MEMORY_OS_SERVER_URL=http://127.0.0.1:8765
```

Then the same hook scripts delegate retrieval and storage to the server.

## Memory Layers

The centralized server stores four isolated memory layers per project:

- Raw memory: code chunks and file diffs
- Semantic memory: decisions, explanations, and reasoning
- Architecture memory: system design and module relationships
- Event memory: file edits, commits, tool actions, and IDE events

## How Storage Works

`scripts/file_indexer.py` recursively scans the project root and skips generated or unsafe paths:

- `node_modules`, `.git`, `dist`, `build`, `venv`, `__pycache__`
- binary and large unreadable files

Every readable file is hashed with MD5. If the hash did not change, the file is not re-indexed. When a file changes, the old chunk ids recorded in `index.json` are deleted from Chroma and replaced with the new chunks.

Metadata includes:

- file path
- project name
- chunk index
- file modification time
- content hash

In server mode, chunks are stored in project-specific Chroma collections by layer, for example:

- `memory_raw_<project_id>`
- `memory_semantic_<project_id>`
- `memory_architecture_<project_id>`
- `memory_event_<project_id>`

## Retrieval

`scripts/retrieve_memory.py "your prompt"` queries the current project's memory. It fetches extra candidates, removes duplicate content, and re-ranks with boosts for recent, open, and architecture-related files.

The output is deliberately compact:

```text
<codex_memory_context>
project: my-project
summary:
...
relevant_chunks:
--- src/app.ts#chunk-0 ---
...
</codex_memory_context>
```

Server retrieval uses a small TTL cache, deduplicates by content hash, and boosts open files plus architecture-related files. The target latency is under 300ms for warm, local queries.

## IDE And Agent Bridges

VS Code:

- `integrations/vscode/` contains a minimal extension.
- On file open it calls `/retrieve`.
- On file save it calls `/store`.
- Memory appears in the `AI Memory` output channel.

Claude Desktop:

- `integrations/claude_desktop_config.json` shows an MCP stdio configuration using `python -m memory_os.mcp_stdio`.

Codex:

- Existing `.codex/hooks.json` works locally.
- `integrations/codex_hooks_server.json` shows server-backed hook usage through `MEMORY_OS_SERVER_URL`.

Antigravity:

- `integrations/antigravity.md` documents HTTP integration.

Cursor and future IDEs:

- Use the same HTTP endpoints or MCP JSON-RPC tool names:
  - `detect_project`
  - `retrieve_memory`
  - `store_memory`
  - `get_summary`

## Self-Learning

`POST /feedback` records whether a project match was correct. The registry stores accepted/rejected feedback and adjusts the per-project threshold:

- accepted matches slightly lower threshold
- rejected matches raise threshold

This creates a feedback loop for project identity matching without requiring configuration files.

## Manual Commands

```bash
python scripts/init_project.py
python scripts/store_memory.py
python scripts/retrieve_memory.py "How does auth work?"
python scripts/update_summary.py
```

Run the server:

```bash
python scripts/run_server.py --port 8765
```

To index another project explicitly:

```bash
python scripts/store_memory.py --project-root /path/to/project
```

To place memory elsewhere:

```bash
CODEX_MEMORY_ROOT=/path/to/memory python scripts/store_memory.py
```

## Extending

Git integration:

- Record branch, commit, author, and changed file status in event memory.
- Bias retrieval toward files changed on the current branch.

Advanced chunking:

- Replace paragraph chunking with AST-aware chunkers for Python, TypeScript, JavaScript, and SQL.
- Store symbol metadata such as class, function, route, and exported names.

UI dashboard:

- Build a small local dashboard that reads `project_registry.json`, `project_state.json`, `summary.md`, and Chroma collection stats.
- Add controls to mark bugs, decisions, and todos without editing JSON by hand.

Cloud deployment:

- Use `Dockerfile` and `docker-compose.yml`.
- Mount durable storage at `MEMORY_OS_ROOT`.
- Swap ChromaDB collections for pgvector behind `memory_os/vector_store.py` if central Postgres is preferred.

## Safety

The scripts never delete project files. They only write inside the configured memory root and only delete stale vector documents from the project's own memory collections. Binary, unreadable, and oversized files are skipped. Cross-project leakage is blocked by per-project ids and separate vector collections.
