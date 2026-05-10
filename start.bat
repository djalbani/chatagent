@echo off
echo.
echo  ================================================
echo   Danish's Support Chat Agent  (Groq Edition)
echo  ================================================
echo.
echo  Stopping any existing server on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo  Starting backend on http://localhost:8000
echo  Health check: http://localhost:8000/health
echo  Press Ctrl+C to stop.
echo.
cd /d "%~dp0backend"
call venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
