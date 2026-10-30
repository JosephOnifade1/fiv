# FiverrScout Local Development Startup Script
# Run from project root: .\start_local.ps1

$ErrorActionPreference = "Stop"
$PYTHON = "C:\Users\HP\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "=== FiverrScout Local Dev Launcher ===" -ForegroundColor Cyan
Write-Host ""

# ── Check MongoDB ─────────────────────────────────────────────────────────────
Write-Host "Checking MongoDB..." -ForegroundColor Yellow
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect("localhost", 27017)
    $tcpClient.Close()
    Write-Host "  MongoDB is running on localhost:27017" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "  ERROR: MongoDB is not running on localhost:27017" -ForegroundColor Red
    Write-Host ""
    Write-Host "  You need MongoDB to run the backend. Choose one option:" -ForegroundColor Yellow
    Write-Host "  1. Install MongoDB Community: https://www.mongodb.com/try/download/community"
    Write-Host "  2. Use MongoDB Atlas (free): https://www.mongodb.com/cloud/atlas"
    Write-Host "     Then update MONGO_URL in backend\.env"
    Write-Host ""
    Write-Host "  After installing MongoDB locally, start it with:" -ForegroundColor Yellow
    Write-Host '  net start MongoDB'
    Write-Host "  or run: mongod --dbpath C:\data\db"
    Write-Host ""
    $choice = Read-Host "Continue anyway without MongoDB? (y/N)"
    if ($choice -ne "y" -and $choice -ne "Y") { exit 1 }
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

