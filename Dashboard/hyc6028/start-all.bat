@echo off
setlocal
set "ROOT=%~dp0"

echo Starting ESG console (backend + frontend, each in its own window)
echo.

start "ESG Backend (FastAPI :8000)" cmd /k call "%ROOT%start-backend.bat"

timeout /t 3 /nobreak >nul

start "ESG Frontend (Vite :5173)" cmd /k call "%ROOT%start-frontend.bat"

echo.
echo Two windows were opened:
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo.
echo Press Ctrl+C in each window to stop that server.
pause
