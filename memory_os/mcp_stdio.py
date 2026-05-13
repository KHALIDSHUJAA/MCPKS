from __future__ import annotations

import json
import sys
from typing import Any

from .config import load_settings
from .schemas import RetrieveRequest, StoreRequest
from .service import MemoryOS


def response(request_id: Any, result: Any = None, error: str | None = None) -> dict[str, Any]:
    if error:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": error}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    service = MemoryOS(load_settings())
    for line in sys.stdin:
        if not line.strip():
            continue
        payload = json.loads(line)
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}
        try:
            if method == "tools/list":
                result = {
                    "tools": [
                        {"name": "detect_project", "description": "Detect project namespace from a folder snapshot."},
                        {"name": "retrieve_memory", "description": "Retrieve project memory."},
                        {"name": "store_memory", "description": "Store project memory."},
                        {"name": "get_summary", "description": "Get project summary."},
                    ]
                }
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments") or {}
                if name == "detect_project":
                    result = service.detect_project(args["root"]).model_dump()
                elif name == "retrieve_memory":
                    result = service.retrieve(RetrieveRequest(**args)).model_dump()
                elif name == "store_memory":
                    result = service.store(StoreRequest(**args)).model_dump()
                elif name == "get_summary":
                    result = service.summary(args["root"]).model_dump()
                else:
                    raise ValueError(f"Unknown tool: {name}")
            else:
                result = {}
            print(json.dumps(response(request_id, result), ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps(response(request_id, error=str(exc))), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
