@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ESG] python을 찾을 수 없습니다. Python을 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ESG] 가상환경이 없어 새로 만듭니다...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  echo [ESG] 의존성 설치 중... (처음 한 번만, 수 분 걸릴 수 있습니다)
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
)

if not exist ".env" (
  echo [ESG] .env 파일이 없어 .env.example을 복사합니다. 필요 시 값을 확인하세요.
  copy /y ".env.example" ".env" >nul
)

echo [ESG] FastAPI 백엔드 실행 중... http://127.0.0.1:8000  (Ctrl+C로 종료)
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000

pause
