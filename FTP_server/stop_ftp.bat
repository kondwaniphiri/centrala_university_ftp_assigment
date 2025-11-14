@echo off
REM Stop the Node-based FTP server using stored PID.
SETLOCAL
set PID_FILE=ftp_server.pid

if not exist %PID_FILE% (
  echo No PID file (%PID_FILE%) present. Nothing to stop.
  goto :EOF
)

for /f "usebackq tokens=*" %%p in ("%PID_FILE%") do set TARGET=%%p
echo Attempting to stop FTP server PID %TARGET% ...
taskkill /PID %TARGET% /T /F >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Stopped FTP server (PID %TARGET%).
  del %PID_FILE%
) else (
  echo Could not terminate PID %TARGET%. It may have already exited.
  del %PID_FILE%
)
ENDLOCAL
