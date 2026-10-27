@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 心弦 EmoTune 正在启动…
python app.py
pause
