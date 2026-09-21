@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python environment is missing. Create .venv and install requirements.txt first.
    pause
    exit /b 1
)
echo Open http://localhost:8000/login in your browser.
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
if errorlevel 1 pause
