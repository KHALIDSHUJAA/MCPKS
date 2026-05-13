#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/init_project.py

cat <<'MSG'

Codex memory setup complete.

Required for production embeddings:
  export OPENAI_API_KEY=your_api_key

Local smoke tests only:
  export CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS=1

Run the central server:
  python scripts/run_server.py --host 127.0.0.1 --port 8765
MSG
