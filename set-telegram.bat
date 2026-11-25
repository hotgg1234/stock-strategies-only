@echo off
cd /d "%~dp0"
echo.
echo ==== Set Telegram notification ====
echo 1) In Telegram, talk to @BotFather, send /newbot, copy the bot token.
echo 2) Open your new bot and press Start. Then talk to @userinfobot to get your chat id.
echo.
set /p "TGTOKEN=Bot token: "
set /p "TGCHAT=Chat id: "
if "%TGTOKEN%"=="" goto :empty
if "%TGCHAT%"=="" goto :empty

powershell -NoProfile -Command "$p=(Resolve-Path '.env').Path; $vals=@{'TELEGRAM_BOT_TOKEN'=$env:TGTOKEN.Trim().Trim('\"'); 'TELEGRAM_CHAT_ID'=$env:TGCHAT.Trim().Trim('\"')}; $lines=[IO.File]::ReadAllLines($p); $seen=@{}; $out=@(foreach($l in $lines){ $hit=$null; foreach($k in $vals.Keys){ if($l -match ('^\s*'+$k+'\s*=')){ $hit=$k } }; if($hit){ $seen[$hit]=1; $hit+'='+$vals[$hit] } else { $l } }); foreach($k in $vals.Keys){ if(-not $seen[$k]){ $out+=($k+'='+$vals[$k]) } }; [IO.File]::WriteAllLines($p, $out, (New-Object Text.UTF8Encoding $false)); Write-Host 'Saved to .env'"

echo Sending a test message...
powershell -NoProfile -Command "try { $body=@{chat_id=$env:TGCHAT.Trim(); text='stock-strategies: Telegram OK'} | ConvertTo-Json; Invoke-RestMethod -Method Post -ContentType 'application/json; charset=utf-8' -Uri ('https://api.telegram.org/bot'+$env:TGTOKEN.Trim()+'/sendMessage') -Body ([Text.Encoding]::UTF8.GetBytes($body)) | Out-Null; Write-Host 'Test message sent. Check Telegram.' } catch { Write-Host ('Test failed: '+$_.Exception.Message) }"
pause
exit /b 0

:empty
echo Nothing entered. No changes made.
pause
exit /b 1
