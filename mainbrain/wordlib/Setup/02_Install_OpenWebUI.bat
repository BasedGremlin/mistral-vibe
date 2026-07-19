@echo off
:: ================================================================
:: WORDLIB Setup Step 2 -- Install Open WebUI into core\venv\
:: One-time run. Requires internet + Python installed on the PC.
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title WORDLIB Setup -- Open WebUI

echo.
echo  =====================================================
echo    WORDLIB Setup [2/4] -- Open WebUI
echo  =====================================================
echo.

set VENV=%~dp0..\core\venv
set VENV_PY=%VENV%\Scripts\python.exe
set VENV_PIP=%VENV%\Scripts\pip.exe
set DATA_DIR=%~dp0..\core\open-webui\data
set CACHE=%~dp0..\.pip_cache

:: Create venv if missing
if not exist "%VENV_PY%" (
    echo  Creating Python virtual environment in core\venv\...
    py -m venv "%VENV%"
    if errorlevel 1 (
        python -m venv "%VENV%"
        if errorlevel 1 (
            echo  [ERR] Could not create venv. Install Python from python.org
            pause & exit /b 1
        )
    )
    echo  [OK] Venv created.
)

echo  Installing Open WebUI (may take 5-10 minutes, ~1.5 GB)...
echo.
"%VENV_PIP%" install --upgrade pip --quiet --cache-dir "%CACHE%"
"%VENV_PIP%" install open-webui --quiet --cache-dir "%CACHE%"

if errorlevel 1 (
    echo  [ERR] Open WebUI install failed. Check internet and disk space.
    pause & exit /b 1
)

echo  [OK] Open WebUI installed.
echo.
echo  =====================================================
echo   Next step: run Setup\03_Setup_Kiwix.bat
echo  =====================================================
echo.
pause
