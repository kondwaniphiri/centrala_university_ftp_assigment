@echo off
REM Start Flask backend (app.py) detached and record PID.
REM Working directory: interface\

SETLOCAL ENABLEDELAYEDEXPANSION

set PY_FILE=ftp_client_backend\app.py
set PID_FILE=flask_app.pid

if exist %PID_FILE% (
  echo Found existing %PID_FILE%. Checking process...
  for /f "usebackq tokens=*" %%p in ("%PID_FILE%") do set OLD_PID=%%p
  REM Check if process exists (tasklist filter). If exists, don't start another.
  for /f "skip=3 tokens=1" %%a in ('tasklist /FI "PID eq !OLD_PID!"') do (
    if "%%a" NEQ "INFO:" (
      echo Flask backend already running with PID !OLD_PID!.
      echo If it's stale, run stop_app.bat then start again.
      goto :EOF
    )
  )
  echo Stale PID file found. Removing.
  del %PID_FILE%
)

REM Launch python in a new window, capture PID using PowerShell (more reliable)
echo Starting Flask backend...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Start-Process -FilePath python -ArgumentList '%PY_FILE%' -PassThru).Id"`) do set NEWPID=%%i
echo !NEWPID!> %PID_FILE%
echo Flask backend started with PID !NEWPID! (recorded in %PID_FILE%).
echo To stop it, run stop_app.bat
ENDLOCAL
