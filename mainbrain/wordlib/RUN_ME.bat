@echo off
:: ================================================================
:: WORDLIB (D:) -- Windows Entry Point
:: Thin door: finds Python, runs launcher.py. All logic is in Python.
:: ================================================================
cd /d "%~dp0"
title WORDLIB -- USB AI Master

:: Unblock USB files silently (first run)
powershell -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File" >nul 2>&1

:: Find Python: embedded > py launcher > python > python3
set PYTHON=
if exist "%~dp0python\python.exe" ( set PYTHON=%~dp0python\python.exe & goto :RUN )
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=py & goto :RUN )
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=python & goto :RUN )
python3 --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=python3 & goto :RUN )

echo.
echo  ERROR: Python not found. Install from https://python.org/downloads
echo  Check "Add Python to PATH" during install, then re-run.
echo.
pause
exit /b 1

:RUN
%PYTHON% "%~dp0launcher.py"
pause
