@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [ESG] 백엔드 / 프론트엔드를 각각 새 창에서 띄웁니다...
start "ESG Backend (http://127.0.0.1:8000)" cmd /k "chcp 65001 >nul && call "%~dp0backend\start-backend.bat""
timeout /t 2 /nobreak >nul
start "ESG Frontend (http://localhost:5173)" cmd /k "chcp 65001 >nul && call "%~dp0frontend\start-frontend.bat""

echo.
echo   Backend : http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo.
echo 두 창을 각각 닫거나 Ctrl+C로 서버를 종료할 수 있습니다.
echo (stop-all.bat 을 실행하면 포트 8000/5173을 한 번에 정리합니다.)