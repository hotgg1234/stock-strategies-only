# Create/replace the "StockDaily" task: Mon-Fri 15:30, and catch up later if the PC was off/asleep at that time.
$ErrorActionPreference = 'Stop'
try {
    $bat = Join-Path $PSScriptRoot 'run-daily.bat'
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "' + $bat + '"') -WorkingDirectory $PSScriptRoot
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At '15:30'
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName 'StockDaily' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host 'OK. StockDaily runs Mon-Fri 15:30.'
    Write-Host 'If the PC was off or asleep at 15:30, it will run as soon as the PC is back on.'
}
catch {
    Write-Host ('FAILED: ' + $_.Exception.Message)
}
