@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
call "%~dp0env_python.bat"
if not defined EMOTUNE_PY set "EMOTUNE_PY=python"
if exist "data\emotune-local-data.zip" (
  "%EMOTUNE_PY%" tools\pack_local_data.py --unpack data\emotune-local-data.zip
) else if exist "emotune-local-data.zip" (
  "%EMOTUNE_PY%" tools\pack_local_data.py --unpack emotune-local-data.zip
) else (
  echo 请把 emotune-local-data.zip 放到项目根目录或 data\ 下再运行本脚本。
)
pause
