@echo off
cd /d "%~dp0"
echo Stopping the site...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
set "PATH=%PATH%;C:\Program Files\nodejs"
echo Rebuilding the web page (1-3 minutes)...
cd /d "%~dp0web"
call npm run build
if errorlevel 1 (
  echo BUILD FAILED - please screenshot this window for Claude.
  pause
  exit /b 1
)
cd /d "%~dp0"
call "%~dp0start-site.bat"
echo Waiting 15 seconds for the site to start...
timeout /t 15 >nul
start http://localhost:3000
echo Done.
pause
