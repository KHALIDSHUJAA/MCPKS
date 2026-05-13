from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException

from .config import load_settings
from .schemas import FeedbackRequest, ProjectSnapshot, RetrieveRequest, StoreRequest
from .service import MemoryOS


settings = load_settings()
memory_os = MemoryOS(settings)
executor = ThreadPoolExecutor(max_workers=2)
app = FastAPI(title="AI Memory Operating System", version="0.2.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "memory_root": str(settings.memory_root)}


@app.post("/detect_project")
def detect_project(snapshot: ProjectSnapshot):
    return memory_os.detect_project(snapshot.root)


@app.post("/store")
def store(request: StoreRequest, background_tasks: BackgroundTasks):
    if request.async_store:
        detection = memory_os.detect_project(request.root)
        background_tasks.add_task(memory_os.store, request.model_copy(update={"async_store": False}))
        return {
            "project_id": detection.project_id,
            "indexed_files": 0,
            "removed_files": 0,
            "stored_entries": len(request.entries),
            "queued": True,
        }
    return memory_os.store(request)


@app.post("/retrieve")
def retrieve(request: RetrieveRequest):
    return memory_os.retrieve(request)


@app.get("/summary")
def summary(root: str):
    return memory_os.summary(root)


@app.post("/feedback")
def feedback(request: FeedbackRequest):
    return memory_os.feedback(request)


@app.post("/mcp")
def mcp_json_rpc(payload: dict[str, Any]):
    method = payload.get("method")
    params = payload.get("params") or {}
    request_id = payload.get("id")
    try:
        if method == "tools/list":
            result = {
                "tools": [
                    {"name": "detect_project", "description": "Detect or create an isolated project memory namespace."},
                    {"name": "retrieve_memory", "description": "Retrieve relevant project memory chunks."},
                    {"name": "store_memory", "description": "Store code, semantic, architecture, or event memory."},
                    {"name": "get_summary", "description": "Return project summary and state."},
                ]
            }
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "detect_project":
                result = memory_os.detect_project(args["root"]).model_dump()
            elif name == "retrieve_memory":
                result = memory_os.retrieve(RetrieveRequest(**args)).model_dump()
            elif name == "store_memory":
                result = memory_os.store(StoreRequest(**args)).model_dump()
            elif name == "get_summary":
                result = memory_os.summary(args["root"]).model_dump()
            else:
                raise HTTPException(status_code=404, detail=f"Unknown MCP tool: {name}")
        else:
            raise HTTPException(status_code=404, detail=f"Unknown MCP method: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except HTTPException:
        raise
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}
