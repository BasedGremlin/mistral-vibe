@echo off
:: ================================================================
:: WORDLIB -- Backup Before Ventoy
:: Copies the entire wordlib folder to your hard drive so nothing
:: is lost when Ventoy reformats the USB.
::
:: Run this BEFORE following docs\VENTOY_LINUX_MINT_SETUP.txt
:: ================================================================
setlocal
cd /d "%~dp0.."
title WORDLIB -- Backup Before Ventoy

echo.
echo  =====================================================
echo    WORDLIB -- Backup Before Ventoy
echo  =====================================================
echo.
echo  This copies your entire wordlib folder to your hard drive.
echo  Do this BEFORE installing Ventoy (which erases the USB).
echo.

set SOURCE=%~dp0..
set DEST=%USERPROFILE%\wordlib_backup

echo  Source : %SOURCE%
echo  Backup : %DEST%
echo.
echo  WARNING: If models are present, this may be several GB
echo           and take a while. That is normal.
echo.
set /p GO=  Type YES to start the backup:  

if /i not "%GO%"=="YES" (
    echo  Cancelled.
    pause
    exit /b 0
)

echo.
echo  Copying... please wait. Do not close this window.
echo.

robocopy "%SOURCE%" "%DEST%" /E /COPY:DAT /R:2 /W:3 /NFL /NDL /NP

if errorlevel 8 (
    echo.
    echo  [ERR] Backup had errors. Check available disk space.
    pause
    exit /b 1
)

echo.
echo  =====================================================
echo   [OK] Backup complete.
echo.
echo   Backup location: %DEST%
echo.
echo   Verify the folder size looks right, then proceed with
echo   docs\VENTOY_LINUX_MINT_SETUP.txt
echo  =====================================================
echo.
pause
