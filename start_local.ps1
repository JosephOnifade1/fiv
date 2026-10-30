# FiverrScout Local Development Startup Script
# Run from project root: .\start_local.ps1

$ROOT = $PSScriptRoot
$PYTHON = "C:\Users\HP\AppData\Local\Python\pythoncore-3.14-64\python.exe"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    FiverrScout Local Dev Launcher      " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check MongoDB Atlas Connection ─────────────────────────────────────────
Write-Host "Checking MongoDB Atlas connection..." -ForegroundColor Yellow
$backendEnv = Join-Path $ROOT "backend\.env"

$mongoCheck = & $PYTHON -c "
import os, certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(r'$backendEnv')
url = os.getenv('MONGO_URL', '')
try:
    c = MongoClient(url, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    c.admin.command('ping')
    print('OK')
except Exception as e:
    print('FAIL: ' + str(e)[:100])
" 2>&1

if ($mongoCheck -match "OK") {
    Write-Host "  [OK] MongoDB Atlas connection verified!" -ForegroundColor Green
} else {
    Write-Host "  [!] MongoDB check note: $mongoCheck" -ForegroundColor Yellow
}

# ── 2. Launch Backend (FastAPI on port 8000) ──────────────────────────────────
Write-Host ""
Write-Host "Starting Backend on http://localhost:8000 ..." -ForegroundColor Yellow
$backendCmd = "Set-Location '$ROOT\backend'; & '$PYTHON' -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal

# ── 3. Launch Frontend (React on port 3000) ───────────────────────────────────
Write-Host "Starting Frontend on http://localhost:3000 ..." -ForegroundColor Yellow
$frontendCmd = "Set-Location '$ROOT\frontend'; npm start"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Both services launched in new windows! " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend App: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your Pro Account Credentials:" -ForegroundColor Yellow
Write-Host "  Email:    onifadejosp@gmail.com" -ForegroundColor White
Write-Host "  Password: Joseph" -ForegroundColor White
Write-Host ""
