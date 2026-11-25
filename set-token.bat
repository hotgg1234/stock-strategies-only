@echo off
cd /d "%~dp0"
echo.
echo ==== Set FinMind token ====
echo Paste your FinMind token (right-click to paste), then press Enter.
echo.
set /p "TOKEN=Token: "
if "%TOKEN%"=="" (
  echo No token entered. Nothing changed.
  pause
  exit /b 1
)

powershell -NoProfile -Command "$t=$env:TOKEN.Trim().Trim('\"'); $p=(Resolve-Path '.env').Path; $lines=[IO.File]::ReadAllLines($p); $found=$false; $out=@(foreach($l in $lines){ if($l -match '^\s*FINMIND_TOKEN\s*='){ $found=$true; 'FINMIND_TOKEN='+$t } else { $l } }); if(-not $found){ $out+=('FINMIND_TOKEN='+$t) }; [IO.File]::WriteAllLines($p, $out, (New-Object Text.UTF8Encoding $false)); Write-Host ('Saved. Token length: '+$t.Length)"

echo.
echo Restarting the site...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000 " ^| findstr LISTENING') do taskkill /PID %%p /T /F >nul 2>&1
timeout /t 2 >nul
call "%~dp0start-site.bat"
timeout /t 15 >nul
start http://localhost:3000

echo.
echo Done. Refresh the page and press the screening button.
pause
