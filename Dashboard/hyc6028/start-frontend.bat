@echo off
setlocal
set "ROOT=%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

cd /d "%ROOT%frontend"

if not exist "node_modules" (
    echo node_modules not found, installing dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
)

echo Starting ESG console frontend (Vite)...
echo   http://localhost:5173
echo.

call npm run dev

echo.
echo Frontend server stopped.
pause
