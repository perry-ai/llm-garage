@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set PID_FILE=data\llmgarage.pid
set LLMGARAGE_PORT=58001
set LLMGARAGE_URL=http://127.0.0.1:58001/api/shutdown
set SHUTDOWN_REQUESTED=0

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Method POST -Uri '%LLMGARAGE_URL%' -Body '{}' -ContentType 'application/json' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if %ERRORLEVEL% EQU 0 set SHUTDOWN_REQUESTED=1
ping -n 3 127.0.0.1 >nul
netstat -ano | findstr ":58001" | findstr "LISTENING" >nul
if %ERRORLEVEL% NEQ 0 (
  del "%PID_FILE%" >nul 2>nul
  if "%SHUTDOWN_REQUESTED%"=="1" (
    echo LLMGarage stopped.
  ) else (
    echo No LLMGarage process was found on port %LLMGARAGE_PORT%.
  )
  exit /b 0
)

if exist "%PID_FILE%" (
  set /p LLMGARAGE_PID=<"%PID_FILE%"
  del "%PID_FILE%" >nul 2>nul
  if defined LLMGARAGE_PID (
    echo Stopping LLMGarage process PID !LLMGARAGE_PID!...
    taskkill /PID !LLMGARAGE_PID! /T /F >nul 2>nul
    if !ERRORLEVEL! EQU 0 exit /b 0
  )
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":58001" ^| findstr "LISTENING"') do (
  echo Stopping LLMGarage process on port %LLMGARAGE_PORT%, PID %%P...
  taskkill /PID %%P /T /F
  exit /b %ERRORLEVEL%
)

echo No LLMGarage process was found on port %LLMGARAGE_PORT%.
exit /b 0

