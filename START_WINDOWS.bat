@echo off
setlocal
cd /d "%~dp0"
title MIKEIZU TradeLab PRO - Research and Demo
cls
echo ======================================================
echo        MIKEIZU TRADELAB PRO - RESEARCH AND DEMO
echo ======================================================
echo.
echo Local simulator + broker DEMO. LIVE EXECUTION DISABLED.
echo.
set "PY="
where py >nul 2>nul
if not errorlevel 1 (
 for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  if not defined PY (
   py -%%V -c "import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
   if not errorlevel 1 set "PY=py -%%V"
  )
 )
)
if not defined PY (
 where python >nul 2>nul
 if not errorlevel 1 (
  python -c "import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
 )
)
if not defined PY (
 echo ERROR: Python 3.10 or newer is required. Install from python.org
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 echo Creating private virtual environment...
 %PY% -m venv .venv
 if errorlevel 1 goto :fail
)
echo Installing the official WebSocket client dependency (internet needed on first run)...
".venv\Scripts\python.exe" -m pip install --require-hashes -r requirements.lock -q
if errorlevel 1 goto :fail
echo Starting localhost app...
".venv\Scripts\python.exe" deriv_server.py %*
if errorlevel 1 goto :fail
exit /b 0
:fail
echo Failed to start. Check your internet connection and Python installation.
pause
exit /b 1
