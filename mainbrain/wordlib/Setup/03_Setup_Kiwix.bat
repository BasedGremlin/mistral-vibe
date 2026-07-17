@echo off
:: ================================================================
:: WORDLIB Setup Step 3 -- Kiwix + ZIM files
::
:: Downloads:
::   kiwix-serve.exe         (~10 MB)
::   wikipedia_en_all_mini   (~7-8 GB, full text, no images)
::   devdocs.io ZIM          (~200 MB, programming references)
::   Stack Exchange: Programming subset (~1-2 GB, if available)
::
:: Realistic space use: ~9-10 GB total
:: Must fit alongside Ollama (~5 GB) on 28.7 GB USB.
::
:: NOTE: Full English Wikipedia nopic = 39-50 GB (does NOT fit).
::       Mini = full article text, no images. Still 7 million articles.
::       This is the right choice for a 32 GB USB.
:: ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title WORDLIB Setup -- Kiwix

echo.
echo  =====================================================
echo    WORDLIB Setup [3/4] -- Kiwix Offline Library
echo  =====================================================
echo.

set KIWIX_DIR=%~dp0..\core\kiwix
set DATA_DIR=%KIWIX_DIR%
set EXE=%KIWIX_DIR%\kiwix-serve.exe

:: Create folder
if not exist "%KIWIX_DIR%" mkdir "%KIWIX_DIR%"

:: ── Download kiwix-serve.exe ──────────────────────────────────
if exist "%EXE%" (
    echo  [OK] kiwix-serve.exe already present.
) else (
    echo  Downloading kiwix-serve.exe (~10 MB)...
    powershell -Command "& {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri 'https://download.kiwix.org/release/kiwix-tools/kiwix-tools_win-x64-latest.zip' -OutFile '%KIWIX_DIR%\kiwix-tools.zip'
    }"
    powershell -Command "Expand-Archive '%KIWIX_DIR%\kiwix-tools.zip' '%KIWIX_DIR%\tools_tmp' -Force"
    :: Copy kiwix-serve.exe out of the version subfolder
    for /r "%KIWIX_DIR%\tools_tmp" %%F in (kiwix-serve.exe) do copy "%%F" "%EXE%" >nul
    rd /s /q "%KIWIX_DIR%\tools_tmp" 2>nul
    del "%KIWIX_DIR%\kiwix-tools.zip" 2>nul
    if exist "%EXE%" (
        echo  [OK] kiwix-serve.exe ready.
    ) else (
        echo  [ERR] kiwix-serve.exe not extracted. Manual step required.
        echo        Download from https://download.kiwix.org/release/kiwix-tools/
        echo        Extract kiwix-serve.exe to: %KIWIX_DIR%\
    )
)

echo.
echo  ─────────────────────────────────────────────────
echo   Downloading ZIM files (large, be patient)
echo  ─────────────────────────────────────────────────
echo.
echo  [1] Wikipedia English Mini (all articles, text only, ~7-8 GB)
echo      7 million articles. Full text. No images. Fits USB.
echo.

:: Check if already downloaded (any wikipedia_en_all_mini*.zim)
set WIKI_ZIM=
for %%F in ("%KIWIX_DIR%\wikipedia_en_all_mini*.zim") do set WIKI_ZIM=%%F

if defined WIKI_ZIM (
    echo  [OK] Wikipedia mini ZIM already present: %WIKI_ZIM%
) else (
    echo  Downloading Wikipedia EN mini...
    echo  This is ~7-8 GB and may take 30-90 minutes.
    echo  Do not close this window.
    echo.
    :: Most recent available mini ZIM (check https://download.kiwix.org/zim/wikipedia/ for latest)
    set ZIM_URL=https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_mini_2026-04.zim
    set ZIM_DEST=%KIWIX_DIR%\wikipedia_en_all_mini_2026-04.zim
    powershell -Command "& {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri '!ZIM_URL!' -OutFile '!ZIM_DEST!' -UseBasicParsing
    }"
    if exist "!ZIM_DEST!" (
        echo  [OK] Wikipedia mini downloaded.
    ) else (
        echo  [WARN] Wikipedia mini download may have failed.
        echo         Check https://download.kiwix.org/zim/wikipedia/ for current URL.
    )
)

echo.
echo  [2] Stack Exchange: Programming (smaller, ~300-600 MB)
echo.
set SE_ZIM=
for %%F in ("%KIWIX_DIR%\stack_exchange_en*.zim") do set SE_ZIM=%%F
if defined SE_ZIM (
    echo  [OK] Stack Exchange ZIM present: %SE_ZIM%
) else (
    echo  Downloading Stack Exchange (programming subset)...
    powershell -Command "& {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri 'https://download.kiwix.org/zim/stack_exchange/stack_exchange_en.programming.2026-03.zim' -OutFile '%KIWIX_DIR%\stack_exchange_programming_2026-03.zim' -UseBasicParsing
    }"
    if exist "%KIWIX_DIR%\stack_exchange_programming_2026-03.zim" (
        echo  [OK] Stack Exchange downloaded.
    ) else (
        echo  [WARN] Check https://download.kiwix.org/zim/stack_exchange/ for current URL.
    )
)

:: ── Generate library.xml ─────────────────────────────────────
echo.
echo  Generating Kiwix library.xml...

:: Build library.xml manually (kiwix-manage alternative for portability)
echo ^<?xml version="1.0" encoding="UTF-8"?^> > "%KIWIX_DIR%\library.xml"
echo ^<library^> >> "%KIWIX_DIR%\library.xml"
for %%F in ("%KIWIX_DIR%\*.zim") do (
    echo   ^<book path="%%F"/^> >> "%KIWIX_DIR%\library.xml"
)
echo ^</library^> >> "%KIWIX_DIR%\library.xml"
echo  [OK] library.xml generated.

echo.
echo  =====================================================
echo   Kiwix setup complete.
echo.
echo   ZIM files in: core\kiwix\
echo   Served at:    http://localhost:8080  (when running)
echo.
echo   ZIM URL reference: https://download.kiwix.org/zim/
echo.
echo   Next: run Setup\04_Setup_Godot.bat
echo  =====================================================
echo.
pause
