# FiverrScout Local Development Startup Script
# Run from project root: .\start_local.ps1

$ErrorActionPreference = "Stop"
$PYTHON = "C:\Users\HP\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "=== FiverrScout Local Dev Launcher ===" -ForegroundColor Cyan
Write-Host ""

# ── Check MongoDB ─────────────────────────────────────────────────────────────
Write-Host "Checking MongoDB connection..." -ForegroundColor Yellow
$mongoCheck = & $PYTHON -c "
import os
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv('$ROOT\backend\.env')
url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
try:
    c = MongoClient(url, serverSelectionTimeoutMS=4000)
    c.list_database_names()
    print('OK')
except Exception as e:
    print('FAIL: ' + str(e)[:120])
" 2>&1

if ($mongoCheck -match "OK") {
    Write-Host "  MongoDB connection verified successfully!" -ForegroundColor Green
} else {
    Write-Host "  WARNING: MongoDB check reported: $mongoCheck" -ForegroundColor Yellow
    Write-Host "  Check your MONGO_URL in backend\.env" -ForegroundColor Yellow
}

# ── Start Backend ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting backend (FastAPI on port 8000)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($python, $root)
    Set-Location "$root\backend"
    & $python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $PYTHON, $ROOT

Start-Sleep -Seconds 3
Write-Host "  Backend started (PID: $($backendJob.Id))" -ForegroundColor Green

# ── Start Frontend ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting frontend (React on port 3000)..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\frontend"
    npm start
} -ArgumentList $ROOT

Write-Host ""
Write-Host "=== Both services starting ===" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Login credentials:" -ForegroundColor Yellow
Write-Host "  Pro user:  pro@fiverrscout.example.com / Pro1234!"
Write-Host "  Demo user: demo@fiverrscout.example.com / Demo1234!"
Write-Host ""
Write-Host "Press Ctrl+C to stop both services." -ForegroundColor Yellow

try {
    while ($true) {
        $backendJob | Receive-Job -ErrorAction SilentlyContinue | Write-Host
        $frontendJob | Receive-Job -ErrorAction SilentlyContinue | Write-Host
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    Stop-Job $backendJob, $frontendJob
    Remove-Job $backendJob, $frontendJob
}

