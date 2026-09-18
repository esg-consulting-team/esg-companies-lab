@echo off
setlocal
set "ROOT=%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

cd /d "%ROOT%frontend-design-preview-wanted"

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js/npm not found on PATH.
    echo Install Node.js LTS from https://nodejs.org/ ^(this also installs npm^),
    echo then run this again.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo node_modules not found, installing dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
    echo Dependencies installed.
    echo.
)

echo Starting ESG console frontend - WANTED DESIGN PREVIEW copy (Vite)...
echo   http://localhost:5175
echo.
echo (Backend must be running too - use start-backend.bat)
echo.

call npm run dev

echo.
echo Frontend server stopped.
pause
