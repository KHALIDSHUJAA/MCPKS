$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonCandidates = @()
if ($env:PYTHON) {
  $PythonCandidates += $env:PYTHON
}
$PythonCandidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
$PythonCandidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
$PythonCandidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
$PathPython = Get-Command python -ErrorAction SilentlyContinue
if ($PathPython) {
  $PythonCandidates += $PathPython.Source
}

function Test-Python($Candidate) {
  if (-not $Candidate -or -not (Test-Path $Candidate)) {
    return $false
  }
  try {
    & $Candidate -c "import sys, importlib.util; raise SystemExit(0 if sys.version_info >= (3, 11) and importlib.util.find_spec('chromadb') and importlib.util.find_spec('fastapi') else 1)" | Out-Null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

$Python = $PythonCandidates | Where-Object { Test-Python $_ } | Select-Object -First 1
if (-not $Python) {
  throw "Python 3.11+ was not found."
}

$Port = if ($env:MEMORY_OS_PORT) { [int]$env:MEMORY_OS_PORT } else { 8765 }
$HostAddress = if ($env:MEMORY_OS_HOST) { $env:MEMORY_OS_HOST } else { "127.0.0.1" }
$HealthUrl = "http://$HostAddress`:$Port/health"

try {
  $Existing = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
  if ($Existing.ok) {
    Write-Host "AI Memory OS already running at $HealthUrl"
    exit 0
  }
} catch {
  # Continue and start the server.
}

if (-not $env:OPENAI_API_KEY -and -not $env:CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS) {
  $env:CODEX_MEMORY_ALLOW_LOCAL_EMBEDDINGS = "1"
}

if (-not $env:MEMORY_OS_ROOT) {
  $env:MEMORY_OS_ROOT = Join-Path $RepoRoot "memory"
}

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLogPath = Join-Path $LogDir "memory-os.out.log"
$ErrLogPath = Join-Path $LogDir "memory-os.err.log"

Start-Process `
  -FilePath $Python `
  -ArgumentList @("scripts\run_server.py", "--host", $HostAddress, "--port", "$Port") `
  -WorkingDirectory $RepoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $OutLogPath `
  -RedirectStandardError $ErrLogPath

Start-Sleep -Seconds 3
try {
  $Result = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10 -ErrorAction Stop
  if ($Result.ok) {
    Write-Host "AI Memory OS started at $HealthUrl"
    exit 0
  }
} catch {
  throw "AI Memory OS did not start. Check $OutLogPath and $ErrLogPath"
}
