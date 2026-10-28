@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0\.."

echo 心弦 EmoTune：创建 conda 环境 emotune（Python 3.12）并安装依赖
echo.

set "CONDA_EXE="
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" set "CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\Anaconda3\Scripts\conda.exe" set "CONDA_EXE=%USERPROFILE%\Anaconda3\Scripts\conda.exe"
if exist "%USERPROFILE%\miniforge3\Scripts\conda.exe" set "CONDA_EXE=%USERPROFILE%\miniforge3\Scripts\conda.exe"
if exist "%LOCALAPPDATA%\miniconda3\Scripts\conda.exe" set "CONDA_EXE=%LOCALAPPDATA%\miniconda3\Scripts\conda.exe"
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" set "CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe"
if exist "C:\ProgramData\Miniconda3\Scripts\conda.exe" set "CONDA_EXE=C:\ProgramData\Miniconda3\Scripts\conda.exe"
if exist "C:\ProgramData\anaconda3\Scripts\conda.exe" set "CONDA_EXE=C:\ProgramData\anaconda3\Scripts\conda.exe"
if exist "C:\Miniconda3\Scripts\conda.exe" set "CONDA_EXE=C:\Miniconda3\Scripts\conda.exe"
if exist "C:\Anaconda3\Scripts\conda.exe" set "CONDA_EXE=C:\Anaconda3\Scripts\conda.exe"

if not defined CONDA_EXE (
  where conda.exe >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where conda.exe') do (
      set "CONDA_EXE=%%I"
      goto :have_conda
    )
  )
)

:have_conda
if not defined CONDA_EXE (
  echo 找不到 conda.exe。
  echo 请先安装 Miniconda3（Windows 64 位）：https://docs.conda.io/en/latest/miniconda.html
  echo 安装完成后打开「Anaconda Prompt」或「Miniconda Prompt」，进入本项目目录再运行本脚本。
  echo 也可在安装时勾选 Add Miniconda3 to PATH。
  pause
  exit /b 1
)

echo 使用 conda：%CONDA_EXE%
echo.

call :env_exists
if "%ENV_OK%"=="1" (
  echo 已有环境 emotune，跳过创建，直接安装 / 更新依赖。
) else (
  echo 正在创建环境 emotune，Python 3.12 …
  "%CONDA_EXE%" create -n emotune python=3.12 pip -y
  if errorlevel 1 (
    echo 创建失败。若提示 Terms of Service，请先执行：
    echo   conda tos accept
    echo 然后再运行本脚本。
    pause
    exit /b 1
  )
)

call "%~dp0env_python.bat"
if not defined EMOTUNE_PY (
  echo 环境已创建，但还找不到 python.exe。请关闭窗口，重新打开后再运行本脚本。
  pause
  exit /b 1
)

echo 使用 Python：%EMOTUNE_PY%
"%EMOTUNE_PY%" --version
echo.
echo 先卸掉可能存在的 GPU 版 onnxruntime（本项目只用 CPU）…
"%EMOTUNE_PY%" -m pip uninstall -y onnxruntime-gpu onnxruntime-directml 2>nul
"%CONDA_EXE%" remove -n emotune onnxruntime --yes 2>nul
"%EMOTUNE_PY%" -m pip uninstall -y onnxruntime 2>nul
echo.
echo 正在安装依赖（清华源，onnxruntime 为 pip CPU 包）…
"%EMOTUNE_PY%" -m pip install -U pip --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple
"%EMOTUNE_PY%" -m pip install --default-timeout=300 --retries 10 -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
  echo 清华源失败，改用官方 PyPI …
  "%EMOTUNE_PY%" -m pip install --default-timeout=300 --retries 10 -r requirements.txt
)
if errorlevel 1 (
  echo pip 仍失败，改用 conda-forge 安装 Flask / OpenCV / NumPy（不要装 conda 的 onnxruntime，那是 GPU 大包）。
  "%CONDA_EXE%" install -n emotune -c conda-forge flask numpy scipy pillow requests opencv -y
  "%EMOTUNE_PY%" -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime 2>nul
  "%EMOTUNE_PY%" -m pip install --default-timeout=300 --retries 10 "onnxruntime>=1.16,<2"
  if errorlevel 1 (
    echo 依赖安装失败。请检查网络、关掉代理后再试。不要执行 conda install onnxruntime。
    pause
    exit /b 1
  )
)
echo.
echo 核对 onnxruntime 是 CPU 包…
"%EMOTUNE_PY%" tools\verify_cpu.py
if errorlevel 1 (
  echo onnxruntime 不是 CPU 包。请执行：
  echo   python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime
  echo   python -m pip install "onnxruntime>=1.16,<2"
  pause
  exit /b 1
)

echo.
echo 完成。请双击 run.bat，或在已激活的环境里执行：
echo   conda activate emotune
echo   python app.py
pause
exit /b 0

:env_exists
set "ENV_OK="
call "%~dp0env_python.bat"
if defined EMOTUNE_PY set "ENV_OK=1"
exit /b 0
