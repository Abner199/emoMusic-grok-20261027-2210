@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0tools\env_python.bat"
if not defined EMOTUNE_PY (
  echo 未找到 conda 环境 emotune（Python 3.12）。
  echo 请先双击 tools\setup-conda.bat，或打开 Anaconda Prompt 按 SETUP.md 创建环境。
  pause
  exit /b 1
)
echo 心弦 EmoTune 正在启动…
"%EMOTUNE_PY%" -c "import sys; print('Python', sys.version.split()[0], '|', sys.prefix)"
"%EMOTUNE_PY%" app.py
pause
