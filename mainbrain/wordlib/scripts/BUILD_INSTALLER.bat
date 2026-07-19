@echo off
:: ================================================================
:: WORDLIB -- Build the self-extracting installer EXE
:: Run this ONCE to produce WORDLIB_Installer.exe.
:: Requires 7-Zip installed (free: https://7-zip.org).
:: ================================================================
setlocal
cd /d "%~dp0"
title WORDLIB -- Build Installer EXE

:: Locate 7-Zip
set SEVENZIP=
if exist "%ProgramFiles%\7-Zip\7z.exe" set "SEVENZIP=%ProgramFiles%\7-Zip\7z.exe"
if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "SEVENZIP=%ProgramFiles(x86)%\7-Zip\7z.exe"
if "%SEVENZIP%"=="" (
  echo.
  echo   7-Zip not found. Install it first ^(free^):
  echo     https://7-zip.org
  echo   Then run this again.
  echo.
  pause
  exit /b 1
)

:: Locate the SFX module that ships with 7-Zip
set SFXMOD=
if exist "%ProgramFiles%\7-Zip\7zSD.sfx" set "SFXMOD=%ProgramFiles%\7-Zip\7zSD.sfx"
if exist "%ProgramFiles(x86)%\7-Zip\7zSD.sfx" set "SFXMOD=%ProgramFiles(x86)%\7-Zip\7zSD.sfx"
if "%SFXMOD%"=="" (
  echo   7zSD.sfx not found in your 7-Zip folder.
  echo   Download the 'Extra' package from 7-zip.org/download.html,
  echo   copy 7zSD.sfx next to 7z.exe, then run this again.
  pause
  exit /b 1
)

echo   [1/3] Compressing wordlib into archive...
:: Build the archive from the PARENT so the folder name is preserved
pushd "%~dp0.."
if exist "%~dp0wordlib_payload.7z" del "%~dp0wordlib_payload.7z"
"%SEVENZIP%" a -r "%~dp0wordlib_payload.7z" "wordlib\*" >nul
popd

echo   [2/3] Assembling self-extracting EXE...
copy /b "%SFXMOD%" + "%~dp0sfx_config.txt" + "%~dp0wordlib_payload.7z" "%~dp0WORDLIB_Installer.exe" >nul

echo   [3/3] Cleaning up...
del "%~dp0wordlib_payload.7z" >nul 2>&1

echo.
echo   ====================================================
echo    DONE.  Created:  WORDLIB_Installer.exe
echo.
echo    Share THAT single file. The user double-clicks it and
echo    everything unpacks + installs automatically.
echo   ====================================================
echo.
pause
endlocal
