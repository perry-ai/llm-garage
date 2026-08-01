@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 app.py --replace --open-browser
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python app.py --replace --open-browser
  exit /b %ERRORLEVEL%
)

echo Python 3 was not found. Install Python 3 or add it to PATH, then run this file again.
pause
exit /b 1

