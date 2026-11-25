@echo off
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\nodejs;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
chcp 65001 >nul
echo Daily screening started. First run takes 5-10 minutes - please do not close this window.
echo.
uv run python daily_run.py %*
echo.
echo Finished. Full log: data\logs\daily.log
timeout /t 60
