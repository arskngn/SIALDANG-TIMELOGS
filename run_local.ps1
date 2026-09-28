# Sialdang Timelogs - Local Run Script (PowerShell)
# Usage:
#   .\run_local.ps1          - Starts both Backend and Frontend in separate windows
#   .\run_local.ps1 -Backend - Starts only Backend
#   .\run_local.ps1 -Frontend- Starts only Frontend

param (
    [switch]$Backend,
    [switch]$Frontend
)

$RootDir = $PSScriptRoot

if (-not $Backend -and -not $Frontend) {
    $Backend = $true
    $Frontend = $true
}

if ($Backend -and $Frontend) {
    Write-Host "=================================================" -ForegroundColor Cyan
    Write-Host "  Starting Sialdang Timelogs (Backend + Frontend) " -ForegroundColor Green
    Write-Host "=================================================" -ForegroundColor Cyan
    
    # Launch Backend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\backend'; & .\venv\Scripts\python.exe main.py"
    Write-Host "-> Backend launched on http://localhost:8000" -ForegroundColor Yellow
    
    # Launch Frontend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootDir\Frontend'; npm run dev"
    Write-Host "-> Frontend launched on http://localhost:5173" -ForegroundColor Yellow
    
    Write-Host "Both services are running in separate terminal windows." -ForegroundColor Green
    exit 0
}

if ($Backend) {
    Write-Host "Starting Backend on http://localhost:8000 ..." -ForegroundColor Cyan
    Set-Location "$RootDir\backend"
    & .\venv\Scripts\python.exe main.py
}

if ($Frontend) {
    Write-Host "Starting Frontend on http://localhost:5173 ..." -ForegroundColor Cyan
    Set-Location "$RootDir\Frontend"
    npm run dev
}
