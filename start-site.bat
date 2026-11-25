@echo off
set "PATH=%PATH%;C:\Program Files\nodejs;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links"
cd /d "%~dp0"
start "stock-api" /min cmd /c "uv run uvicorn api.main:app --port 8000"
cd /d "%~dp0web"
start "stock-web" /min cmd /c "npm run start -- -p 3000"
