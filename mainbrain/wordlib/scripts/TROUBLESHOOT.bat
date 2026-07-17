@echo off
:: WORDLIB -- Troubleshooter. Diagnoses problems, gives exact fixes.
setlocal
cd /d "%~dp0"
title WORDLIB Troubleshoot
set PYTHON=
if exist "%~dp0python\python.exe" ( set "PYTHON=%~dp0python\python.exe" & goto :RUN )
py --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=py" & goto :RUN )
python --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python" & goto :RUN )
python3 --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python3" & goto :RUN )
echo  Python not found. Install from https://python.org/downloads
pause
exit /b 1
:RUN
%PYTHON% "%~dp0src\troubleshoot.py"
pause
endlocal
