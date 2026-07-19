@echo off
:: ================================================================
:: WORDLIB -- ONE-HIT INSTALL  (Windows)
:: First time using this USB? Just double-click THIS file.
:: It sets up everything automatically and opens ETHER AI.
:: ================================================================
setlocal
cd /d "%~dp0"
title WORDLIB -- One-Hit Install

:: Unblock USB files silently (first run)
powershell -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File" >nul 2>&1

:: Find Python using the RELIABLE errorlevel pattern (same as RUN_ME.bat)
set PYTHON=
if exist "%~dp0python\python.exe" ( set "PYTHON=%~dp0python\python.exe" & goto :RUN )
py --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=py" & goto :RUN )
python --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python" & goto :RUN )
python3 --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python3" & goto :RUN )

:: No Python found
echo.
echo  ====================================================
echo   Python is not installed yet.
echo.
echo   1. Go to https://python.org/downloads
echo   2. Download Python 3 and install it
echo   3. IMPORTANT: tick "Add Python to PATH" during install
echo   4. Then double-click this INSTALL.bat again
echo  ====================================================
echo.
pause
exit /b 1

:RUN
echo.
echo  Starting one-hit install with: %PYTHON%
echo  This needs internet and runs 15-30 min on first install.
echo.
%PYTHON% "%~dp0launcher.py" install
set EXITCODE=%errorlevel%
echo.
if %EXITCODE% NEQ 0 (
  echo  ====================================================
  echo   Install did not finish cleanly ^(exit %EXITCODE%^).
  echo   Double-click TROUBLESHOOT.bat for the exact fix.
  echo  ====================================================
) else (
  echo  Install finished. ETHER AI should be open in your browser.
  echo  Next time, just double-click RUN_ME.bat
)
echo.
pause
endlocal
