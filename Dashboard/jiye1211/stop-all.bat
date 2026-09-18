@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo [ESG] 8000(backend), 5173(frontend) 포트를 쓰는 프로세스를 종료합니다...

for %%P in (8000 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo   - 포트 %%P 사용 중인 PID %%A 종료 (하위 프로세스 포함)
    taskkill /PID %%A /T /F >nul 2>nul
  )
)

echo [ESG] 완료.
pause
