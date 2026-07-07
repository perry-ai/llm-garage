@echo off
setlocal
cd /d "%~dp0"

set LLMGARAGE_URL=http://127.0.0.1:58001

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "" "%LLMGARAGE_URL%"
  py -3 app.py
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "" "%LLMGARAGE_URL%"
  python app.py
  exit /b %ERRORLEVEL%
)

echo Python 3 was not found. Install Python 3 or add it to PATH, then run this file again.
pause
exit /b 1

