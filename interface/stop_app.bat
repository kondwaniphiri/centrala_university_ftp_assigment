@echo off
REM Stop Flask backend started by start_app.bat using stored PID.
SETLOCAL
set PID_FILE=flask_app.pid

if not exist %PID_FILE% (
  echo No PID file (%PID_FILE%) found. Nothing to stop.
  goto :EOF
)

for /f "usebackq tokens=*" %%p in ("%PID_FILE%") do set TARGET=%%p
echo Attempting to stop PID %TARGET% ...

taskkill /PID %TARGET% /T /F >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Stopped Flask backend (PID %TARGET%).
  del %PID_FILE%
) else (
  echo Could not terminate PID %TARGET%. It may have already exited.
  del %PID_FILE%
)
ENDLOCAL
