@echo off
cd /d "%~dp0"
echo Restarting the stock site...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
timeout /t 2 >nul
call "%~dp0start-site.bat"
echo Waiting 15 seconds for the site to start...
timeout /t 15 >nul
start http://localhost:3000
