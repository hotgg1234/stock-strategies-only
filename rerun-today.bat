@echo off
cd /d "%~dp0"
echo Re-running today's screening with the latest bot features (and sending Discord)...
call "%~dp0run-daily.bat" --force
