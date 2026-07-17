@echo off
:: WORDLIB -- Deployment Check. Verifies USB readiness, installs nothing.
setlocal
cd /d "%~dp0"
title WORDLIB Deploy Check
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
%PYTHON% "%~dp0deploy_check.py"
pause
endlocal
