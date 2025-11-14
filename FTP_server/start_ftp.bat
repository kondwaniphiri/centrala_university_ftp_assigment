@echo off
REM Start the Node-based FTP server (server.js) and record PID.
SETLOCAL ENABLEDELAYEDEXPANSION
set PID_FILE=ftp_server.pid
set NODE_SCRIPT=server.js

if exist %PID_FILE% (
  for /f "usebackq tokens=*" %%p in ("%PID_FILE%") do set OLD=%%p
  for /f "skip=3 tokens=1" %%a in ('tasklist /FI "PID eq !OLD!"') do (
    if "%%a" NEQ "INFO:" (
      echo FTP server already running with PID !OLD!.
      echo If stale, run stop_ftp.bat then start again.
      goto :EOF
    )
  )
  echo Stale PID file found. Removing.
  del %PID_FILE%
)

echo Starting FTP server (node %NODE_SCRIPT%)...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Start-Process -FilePath node -ArgumentList '%NODE_SCRIPT%' -PassThru).Id"`) do set NEWPID=%%i
echo !NEWPID!> %PID_FILE%
echo FTP server started with PID !NEWPID! (logged in %PID_FILE%).
echo To stop it, run stop_ftp.bat
ENDLOCAL
