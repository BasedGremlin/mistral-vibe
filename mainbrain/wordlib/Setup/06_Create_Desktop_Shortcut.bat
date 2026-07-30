@echo off
:: ================================================================
:: WORDLIB Setup Step 6 -- Create Desktop Shortcut (thin door)
:: Runs 06_Create_Desktop_Shortcut.ps1. One-time, zero manual steps.
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
title WORDLIB Setup -- Desktop Shortcut

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0\06_Create_Desktop_Shortcut.ps1"
if errorlevel 1 (
    echo.
    echo [ERR] Shortcut creation failed. See message above.
    echo       Try TROUBLESHOOT.bat if this keeps happening.
    pause
    exit /b 1
)

echo.
pause
