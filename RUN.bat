@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 && set PY=py -3 || set PY=python
%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/ and enable "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Creating a local environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create .venv
    pause
    exit /b 1
  )
)
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency install failed.
  pause
  exit /b 1
)
set PYTHONPATH=src
call .venv\Scripts\python.exe -m autoclicker
endlocal
