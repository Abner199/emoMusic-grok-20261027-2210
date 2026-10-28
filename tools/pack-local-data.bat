@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
call "%~dp0env_python.bat"
if not defined EMOTUNE_PY set "EMOTUNE_PY=python"
"%EMOTUNE_PY%" tools\pack_local_data.py
echo.
echo 把 data\emotune-local-data.zip 拷到新电脑的项目目录，再运行 tools\unpack-local-data.bat
pause
