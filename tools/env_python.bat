@echo off
rem 定位 conda 环境 emotune 的 python.exe，结果写入 EMOTUNE_PY（优先用户目录）。
set "EMOTUNE_PY="
if exist "%USERPROFILE%\.conda\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\.conda\envs\emotune\python.exe"
  goto :eof
)
if exist "%USERPROFILE%\miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "%USERPROFILE%\Miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\Miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "%USERPROFILE%\anaconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\anaconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "%USERPROFILE%\Anaconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\Anaconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "%USERPROFILE%\miniforge3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%USERPROFILE%\miniforge3\envs\emotune\python.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\conda\conda\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%LOCALAPPDATA%\conda\conda\envs\emotune\python.exe"
  goto :eof
)
if exist "%LOCALAPPDATA%\miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=%LOCALAPPDATA%\miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "C:\ProgramData\miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=C:\ProgramData\miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "C:\ProgramData\Miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=C:\ProgramData\Miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "C:\ProgramData\anaconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=C:\ProgramData\anaconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "C:\Miniconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=C:\Miniconda3\envs\emotune\python.exe"
  goto :eof
)
if exist "C:\Anaconda3\envs\emotune\python.exe" (
  set "EMOTUNE_PY=C:\Anaconda3\envs\emotune\python.exe"
  goto :eof
)
