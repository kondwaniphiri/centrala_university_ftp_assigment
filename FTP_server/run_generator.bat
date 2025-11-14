@echo off
REM Run the CSV generator (generate_csv_data.py) and show live output.
REM Pass through any arguments supplied to this script.

SETLOCAL
set PY_FILE=generate_csv_data.py

if not exist %PY_FILE% (
  echo Cannot find %PY_FILE% in current directory.
  exit /b 1
)

echo Running generator: python %PY_FILE% %*
python %PY_FILE% %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Generator finished with exit code %EXITCODE%.
ENDLOCAL & exit /b %EXITCODE%
