$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StartScript = Join-Path $RepoRoot "scripts\start_memory_os.ps1"
$TaskName = "AI Memory OS"
$ServerUrl = "http://127.0.0.1:8765"

if (-not (Test-Path $StartScript)) {
  throw "Missing start script: $StartScript"
}

$InstalledVia = "ScheduledTask"
try {
  $Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`""

  $Trigger = New-ScheduledTaskTrigger -AtLogOn
  $Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Starts the local AI Memory OS server for all IDEs and AI coding agents." `
    -Force | Out-Null
} catch {
  $InstalledVia = "StartupFolder"
  $Startup = [Environment]::GetFolderPath("Startup")
  $CmdPath = Join-Path $Startup "AI Memory OS.cmd"
  $Cmd = "@echo off`r`nstart `"`" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`"`r`n"
  Set-Content -Path $CmdPath -Value $Cmd -Encoding ASCII
}

[Environment]::SetEnvironmentVariable("MEMORY_OS_SERVER_URL", $ServerUrl, "User")
[Environment]::SetEnvironmentVariable("MEMORY_OS_AUTOSTART_SCRIPT", $StartScript, "User")

& $StartScript

Write-Host "Installed Windows autostart via: $InstalledVia"
Write-Host "Set user MEMORY_OS_SERVER_URL=$ServerUrl"
