@echo off
title AgriVyaan Mission Studio Launcher
echo ==========================================================
echo   AgriVyaan Mission Studio - Visual Multi-Drone Simulator
echo ==========================================================

set STUDIO_DIR=%~dp0..
set BACKEND_DIR=%STUDIO_DIR%\backend
set FRONTEND_DIR=%STUDIO_DIR%\frontend
set VENV_PYTHON=%STUDIO_DIR%\..\.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" set VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe

echo Starting FastAPI Backend on http://localhost:8000...
start "AgriVyaan Studio Backend" /d "%BACKEND_DIR%" "%VENV_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo Starting React Frontend on http://localhost:5173...
start "AgriVyaan Studio Frontend" /d "%FRONTEND_DIR%" cmd /c "npm run dev"

echo.
echo AgriVyaan Mission Studio has launched in separate windows!
echo Web UI: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
pause
