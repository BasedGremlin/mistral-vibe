@echo off
:: ================================================================
:: WORDLIB -- START HERE
:: This is the ONLY file you click the first time.
:: It runs the polished auto-installer. Hands-off after this click.
:: ================================================================
setlocal
cd /d "%~dp0"
title WORDLIB -- Auto Installer

:: Make the console big enough for the UI
mode con: cols=66 lines=40 >nul 2>&1

:: Unblock USB files silently (first run)
powershell -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File" >nul 2>&1

:: Find Python (reliable errorlevel pattern)
set PYTHON=
if exist "%~dp0python\python.exe" ( set "PYTHON=%~dp0python\python.exe" & goto :RUN )
py --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=py" & goto :RUN )
python --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python" & goto :RUN )
python3 --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python3" & goto :RUN )

cls
echo.
echo   ====================================================
echo    Python is not installed yet -- one quick step first.
echo   ====================================================
echo.
echo    1. Go to https://python.org/downloads
echo    2. Download and install Python 3
echo    3. IMPORTANT: tick "Add Python to PATH"
echo    4. Double-click START_HERE.bat again
echo.
pause
exit /b 1

:RUN
%PYTHON% "%~dp0start_here.py"
set EXITCODE=%errorlevel%
if %EXITCODE% NEQ 0 (
  echo.
  echo   If anything failed, double-click scripts\TROUBLESHOOT.bat for exact fixes.
)
echo.
pause
endlocal
