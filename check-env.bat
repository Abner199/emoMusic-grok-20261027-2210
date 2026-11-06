@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem 一键检测 conda 环境 emotune 是否满足运行条件。可加参数：--strict（版本须与锁定文件一致）、--no-run（不跑识别）
call tools\env_python.bat
if not defined EMOTUNE_PY (
  echo 找不到 conda 环境 emotune。请先双击 tools\setup-conda.bat 创建环境。
  echo 若环境在别处：先 conda activate 你的环境，再运行 python tools\check_env.py
  pause
  exit /b 1
)
"%EMOTUNE_PY%" -X utf8 tools\check_env.py %*
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
