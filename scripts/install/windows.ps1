# Airpoint — Windows Installation Script
# Run in PowerShell: powershell -ExecutionPolicy Bypass -File scripts\install\windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Airpoint — Windows Installer              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Get project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

# Check for Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Host "Python not found. Installing via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.12
    Write-Host "Please restart your terminal and run this script again." -ForegroundColor Yellow
    exit 0
}

$PythonVersion = python --version 2>&1
Write-Host "Python found: $PythonVersion" -ForegroundColor Green

# Create virtual environment
Write-Host "[1/2] Setting up virtual environment..." -ForegroundColor Green
Set-Location $ProjectDir
python -m venv venv
.\venv\Scripts\Activate.ps1

# Upgrade pip
pip install --upgrade pip --quiet

# Install dependencies
Write-Host "[2/2] Installing Python packages..." -ForegroundColor Green
pip install -r requirements.txt --quiet

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Installation Complete!                  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "To start Airpoint:"
Write-Host "  cd $ProjectDir"
Write-Host "  .\run.ps1"
