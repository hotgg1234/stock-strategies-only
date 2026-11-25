@echo off
set "PATH=%PATH%;C:\Program Files\nodejs;%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links"
cd /d "C:\Users\a0912\Documents\stock-strategies-only"
start "stock-api" /min cmd /c "uv run uvicorn api.main:app --port 8000"
cd /d "C:\Users\a0912\Documents\stock-strategies-only\web"
start "stock-web" /min cmd /c "npm run start -- -p 3000"
