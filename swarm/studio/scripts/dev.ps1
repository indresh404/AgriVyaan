# AgriVyaan Mission Studio - Concurrent Development Launcher
# Starts FastAPI backend on :8000 and Vite React frontend on :5173

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StudioDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $StudioDir "backend"
$FrontendDir = Join-Path $StudioDir "frontend"
$SwarmVenvPython = Join-Path $StudioDir "..\.venv\Scripts\python.exe"
$BackendVenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (Test-Path $SwarmVenvPython) {
    $VenvPython = $SwarmVenvPython
} elseif (Test-Path $BackendVenvPython) {
    $VenvPython = $BackendVenvPython
} else {
    Write-Host "Virtual environment not found at $SwarmVenvPython or $BackendVenvPython!" -ForegroundColor Red
    exit 1
}

Write-Host "Starting FastAPI Backend on http://localhost:8000..." -ForegroundColor Yellow
$BackendProcess = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory $BackendDir -PassThru

Write-Host "Starting React Frontend on http://localhost:5173..." -ForegroundColor Yellow
$FrontendProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory $FrontendDir -PassThru

Write-Host ""
Write-Host "AgriVyaan Mission Studio is now running!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "Backend API & Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C or close this console to terminate processes." -ForegroundColor Gray

try {
    Wait-Process -Id $FrontendProcess.Id
} finally {
    Write-Host "Shutting down processes..." -ForegroundColor Yellow
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
}
