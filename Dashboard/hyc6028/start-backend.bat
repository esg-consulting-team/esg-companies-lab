@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%backend"

rem --- Find a real python.exe, skipping the Microsoft Store alias stub ---
rem (that stub sits at %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe and often
rem  shadows the real interpreter on PATH, so we search known install folders first)
set "PYEXE="

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if not defined PYEXE if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)
for /d %%D in ("C:\Program Files\Python3*") do (
    if not defined PYEXE if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)
for /d %%D in ("C:\Program Files (x86)\Python3*") do (
    if not defined PYEXE if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)

if not defined PYEXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /i "WindowsApps" >nul
        if errorlevel 1 if not defined PYEXE set "PYEXE=%%P"
    )
)

if not defined PYEXE (
    echo [ERROR] Python not found ^(or only the Microsoft Store alias was found^).
    echo Install Python 3.11+ from https://www.python.org/downloads/
    echo IMPORTANT: check "Add python.exe to PATH" during install, then run this again.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo venv not found. Creating it with: !PYEXE!
    "!PYEXE!" -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo Installing dependencies...
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\pip.exe install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
    echo Dependencies installed.
    echo.
)

if not exist ".env" (
    if exist ".env.example" (
        echo .env not found, copying .env.example ...
        copy /y ".env.example" ".env" >nul
    )
)

echo Starting ESG console backend (FastAPI)...
echo   http://127.0.0.1:8000
echo   API docs: http://127.0.0.1:8000/docs
echo.
echo Note: --reload is not used because this project may sit inside a OneDrive
echo       sync folder, which can trigger an infinite restart loop.
echo.

venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --host 127.0.0.1

echo.
echo Backend server stopped.
pause
