@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo [错误] 未找到 Python: %PY%
  echo 请先安装 Python 3.12，或修改本脚本中的 PY 路径。
  pause
  exit /b 1
)
echo ============================================
echo   校园统筹 Agent  启动中...
echo   访问地址: http://localhost:8501
echo   按 Ctrl+C 停止
echo ============================================
"%PY%" -m streamlit run app.py --server.headless true --server.port 8501
pause