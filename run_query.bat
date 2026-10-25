@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo [错误] 未找到 Python: %PY%
  pause
  exit /b 1
)
echo ============================================
echo   校园统筹 Agent - 查询门户启动中...
echo   访问地址: http://localhost:8010
echo   按 Ctrl+C 停止
echo ============================================
"%PY%" query_server.py
pause