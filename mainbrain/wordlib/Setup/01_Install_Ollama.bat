@echo off
:: ================================================================
:: WORDLIB Setup Step 1 -- Install Ollama to USB
:: Downloads ollama.exe into core\ollama\
:: One-time run. Requires internet.
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title WORDLIB Setup -- Ollama

echo.
echo  =====================================================
echo    WORDLIB Setup [1/4] -- Ollama AI Runtime
echo  =====================================================
echo.

set DEST=%~dp0..\core\ollama\ollama.exe
set MODEL_DIR=%~dp0..\core\ollama\models

:: Check if already installed
if exist "%DEST%" (
    echo  [OK] ollama.exe already present.
    echo       To update, delete core\ollama\ollama.exe and re-run.
    goto :CHECK_MODEL
)

echo  Downloading ollama.exe to core\ollama\ ...
echo  (Requires internet. File size ~60 MB.)
echo.

powershell -Command "& {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri 'https://ollama.com/download/ollama-windows-amd64.exe' -OutFile '%DEST%'
}"

if exist "%DEST%" (
    echo.
    echo  [OK] ollama.exe downloaded.
) else (
    echo  [ERR] Download failed. Check internet connection and try again.
    pause
    exit /b 1
)

:CHECK_MODEL
echo.
echo  =====================================================
echo    Checking for dolphin3 model...
echo  =====================================================
echo.

:: Point Ollama at USB model storage
set OLLAMA_MODELS=%MODEL_DIR%
set OLLAMA_HOST=127.0.0.1:11434

:: Start Ollama temporarily to pull model
echo  Starting Ollama temporarily...
start "" /b "%DEST%" serve
ping 127.0.0.1 -n 8 >nul 2>&1

:: Check if dolphin3 is already pulled
"%DEST%" list 2>nul | findstr "dolphin3" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] dolphin3 already in model library.
    goto :DONE
)

echo  Pulling dolphin3:8b-llama3.1-q4_K_M (~4.9 GB)...
echo  This downloads once and stays on the USB stick.
echo  Estimated time: 5-15 minutes depending on connection.
echo.
"%DEST%" pull dolphin3:8b-llama3.1-q4_K_M

echo.
echo  Pulling nomic-embed-text (274 MB, needed for RAG)...
"%DEST%" pull nomic-embed-text

:DONE
:: Stop temporary Ollama instance
taskkill /F /IM ollama.exe >nul 2>&1

echo.
echo  =====================================================
echo   [OK] Ollama setup complete.
echo.
echo   Models stored in: core\ollama\models\
echo   Models travel with the USB stick.
echo.
echo   Next step: run Setup\02_Install_OpenWebUI.bat
echo  =====================================================
echo.
pause
