# Start the Awardline web UI
# Usage: .\start_web.ps1
#        .\start_web.ps1 -Port 8080

param(
    [int]$Port = 8000,
    [switch]$Reload
)

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    # Fallback to system Python if the venv launcher is broken (path moved)
    $python = "C:\Python312\python.exe"
}

$reloadFlag = if ($Reload) { "--reload" } else { "" }

Write-Host "Starting Awardline web UI on http://localhost:$Port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop.`n"

& $python -m uvicorn web.app:app --host 0.0.0.0 --port $Port $reloadFlag
