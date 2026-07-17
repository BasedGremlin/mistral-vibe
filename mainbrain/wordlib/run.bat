@echo off
REM ETHER AI / WORDLIB -- one-click launcher
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python was not found. Please install Python 3.9 or newer from python.org
  echo and tick "Add Python to PATH" during install, then run this again.
  echo.
  pause
  exit /b 1
)

python main.py
pause
