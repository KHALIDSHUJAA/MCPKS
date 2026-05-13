$ErrorActionPreference = "Stop"

function Test-Python($candidate) {
  if (-not $candidate) {
    return $false
  }
  try {
    & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" | Out-Null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

$candidates = @()
if ($env:PYTHON) {
  $candidates += $env:PYTHON
}
$pathPython = Get-Command python -ErrorAction SilentlyContinue
if ($pathPython) {
  $candidates += $pathPython.Source
}
$candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
$candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
$candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"

$python = $candidates | Where-Object { Test-Path $_ } | Where-Object { Test-Python $_ } | Select-Object -First 1
if (-not $python) {
  throw "Python 3.11+ was not found. Install Python 3.11+ and rerun setup."
}

& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python scripts/init_project.py

Write-Host ""
Write-Host "Codex memory setup complete."
Write-Host "Set OPENAI_API_KEY for production embeddings."
Write-Host "Run central server: python scripts/run_server.py --host 127.0.0.1 --port 8765"
