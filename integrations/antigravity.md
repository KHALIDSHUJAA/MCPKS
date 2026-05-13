# Antigravity Integration

Run the Memory OS server once:

```powershell
python -m uvicorn memory_os.server:app --host 127.0.0.1 --port 8765
```

Configure Antigravity custom hooks or agent startup commands to call:

```text
POST http://127.0.0.1:8765/retrieve
POST http://127.0.0.1:8765/store
```

Use the current workspace folder as `root`. The server detects the project automatically and shares the same namespace with Codex, Claude, Cursor, and VS Code.
