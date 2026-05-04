# Airpoint — Quick Run Script (after installation)
# Run: .\run.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Airpoint — Touchless Cursor Control     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Check if venv exists
if (-not (Test-Path "$ProjectDir\venv")) {
    Write-Host "No virtual environment found." -ForegroundColor Red
    Write-Host "Run the installer first:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1"
    Write-Host ""
    exit 1
}

# Activate and run
& "$ProjectDir\venv\Scripts\Activate.ps1"

Write-Host "Starting Airpoint..." -ForegroundColor Green
Write-Host ""
python "$ProjectDir\app\main.py"
