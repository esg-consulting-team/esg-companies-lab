@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  if exist "C:\Program Files\nodejs\node.exe" (
    set "PATH=%PATH%;C:\Program Files\nodejs"
  ) else (
    echo [ESG] node를 찾을 수 없습니다. Node.js LTS를 설치한 뒤 다시 실행하세요.
    echo        https://nodejs.org
    pause
    exit /b 1
  )
)

if not exist "node_modules" (
  echo [ESG] npm install 실행 중... (처음 한 번만, 수 분 걸릴 수 있습니다)
  call npm install
)

if not exist ".env" (
  echo VITE_API_BASE=http://127.0.0.1:8000> ".env"
)

echo [ESG] Vite 개발서버 실행 중... http://localhost:5173  (Ctrl+C로 종료)
call npm run dev

pause
