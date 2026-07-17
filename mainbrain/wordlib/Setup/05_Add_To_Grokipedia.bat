@echo off
:: ================================================================
:: WORDLIB -- Add to Grokipedia (RAG Knowledge Base)
::
:: Copies files or folders into the correct storage/ subfolder
:: then triggers a RAG index rebuild via the ETHER AI API.
::
:: Usage:
::   Drag a .md or .txt file onto this .bat file, OR
::   Run it and follow the prompts.
::
:: Supported storage folders:
::   strategy/   -- game strategy, EU4, planning notes
::   recovery/   -- health, supplements, protocols
::   research/   -- business, solar, ecommerce, anything
::   kb/         -- general knowledge base entries
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title WORDLIB -- Add to Grokipedia

echo.
echo  =====================================================
echo    WORDLIB -- Add to Grokipedia (RAG)
echo  =====================================================
echo.

:: If a file was dragged onto the bat, use it. Else prompt.
set SOURCE=%~1

if not defined SOURCE (
    echo  Drag a .md or .txt file onto this bat file to add it,
    echo  or paste the full path here:
    echo.
    set /p SOURCE=  File path: 
)

if not defined SOURCE (
    echo  No file specified. Exiting.
    pause & exit /b 1
)

if not exist "%SOURCE%" (
    echo  [ERR] File not found: %SOURCE%
    pause & exit /b 1
)

echo.
echo  Which Grokipedia folder should this go into?
echo.
echo    1. strategy   (game strategy, EU4, planning)
echo    2. recovery   (health, supplements, protocols)
echo    3. research   (business, solar, ecommerce)
echo    4. kb         (general knowledge)
echo.
set /p CHOICE=  Enter 1-4: 

if "%CHOICE%"=="1" set FOLDER=strategy
if "%CHOICE%"=="2" set FOLDER=recovery
if "%CHOICE%"=="3" set FOLDER=research
if "%CHOICE%"=="4" set FOLDER=kb

if not defined FOLDER (
    echo  Invalid choice. Exiting.
    pause & exit /b 1
)

set DEST_DIR=%~dp0..\storage\%FOLDER%
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

copy "%SOURCE%" "%DEST_DIR%\" >nul
if errorlevel 1 (
    echo  [ERR] Copy failed.
    pause & exit /b 1
)

echo  [OK] Copied to storage\%FOLDER%\%~nx1

:: Trigger RAG rebuild if ETHER AI is running
echo.
echo  Triggering RAG index rebuild...
curl -s -X POST http://localhost:5757/api/rag/rebuild >nul 2>&1
if errorlevel 1 (
    echo  [NOTE] ETHER AI not running -- RAG will rebuild on next start.
) else (
    echo  [OK] RAG rebuild triggered. Check ETHER AI for new chunks.
)

echo.
echo  =====================================================
echo   Done. File added to Grokipedia.
echo   The AI will now reference it in chat answers.
echo  =====================================================
echo.
pause
