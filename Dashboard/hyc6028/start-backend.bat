@echo off
setlocal
set "ROOT=%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

cd /d "%ROOT%backend"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Run this first:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting ESG console backend (FastAPI)...
echo   http://127.0.0.1:8000
echo   API docs: http://127.0.0.1:8000/docs
echo.
echo Note: --reload is not used because this project is inside a OneDrive
echo       sync folder, which can trigger an infinite restart loop.
echo.

venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --host 127.0.0.1

echo.
echo Backend server stopped.
pause
