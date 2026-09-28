@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
set "HOST=127.0.0.1"
set "PORT=5000"
set "URL=http://%HOST%:%PORT%"
set "HEALTH=%URL%/api/health"
set "ERRMSG="

title Personal Notes Launcher

echo ==========================================
echo   Personal Notes - one click start
echo ==========================================
echo.

rem ---------- 1. python environment ----------
if not exist "%PY%" (
  set "ERRMSG=Virtualenv not found. Create it first with: python -m venv .venv"
  goto :fail
)

rem ---------- 2. dependencies ----------
"%PY%" -c "import flask, dotenv, requests" >nul 2>&1
if errorlevel 1 (
  set "ERRMSG=Dependencies missing. Install with: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
  goto :fail
)

rem ---------- 3. already running ----------
call :health_ok
if not errorlevel 1 (
  echo [OK] Service is already running. Opening the browser.
  goto :open
)

rem ---------- 4. port busy ----------
set "BUSY="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /c:":%PORT% " ^| findstr /c:"LISTENING"') do set "BUSY=%%P"
if defined BUSY (
  set "ERRMSG=Port %PORT% is used by PID !BUSY! but the service is not responding. Stop it with: taskkill /PID !BUSY! /F"
  goto :fail
)

rem ---------- 5. start the server ----------
echo [..] Starting the server in a new window ...
ver >nul
start "Notes Server" /D "%ROOT%" "%ComSpec%" /k ""%PY%" app.py"
if errorlevel 1 (
  set "ERRMSG=Failed to launch the server process."
  goto :fail
)

rem ---------- 6. wait until ready ----------
echo [..] Waiting for the service to be ready ...
set /a TRIES=0
:poll
call :health_ok
if not errorlevel 1 goto :ready
set /a TRIES+=1
if !TRIES! GEQ 60 (
  set "ERRMSG=Service was not ready after 120 seconds. Check the server window for the log."
  goto :fail
)
ping -n 3 127.0.0.1 >nul
goto :poll

:ready
echo [OK] Service is ready.

:open
echo [..] Opening %URL%
start "" "%URL%"
echo.
echo Done. The server keeps running in the server window.
echo To stop it later: close that window, or press Ctrl+C inside it.
ping -n 6 127.0.0.1 >nul
endlocal
exit /b 0

:fail
echo.
echo [ERROR] %ERRMSG%
echo.
echo Startup failed. Press any key to close this window.
pause >nul
endlocal
exit /b 1

:health_ok
"%PY%" -c "import urllib.request,sys;p=urllib.request.urlopen('%HEALTH%',timeout=3).read().decode('utf-8');sys.exit(0 if 'OK' in p else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0
