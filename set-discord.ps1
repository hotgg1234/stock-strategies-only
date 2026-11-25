# Save a Discord webhook URL into .env and send a test message.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host ''
Write-Host '==== Set Discord notification ===='
Write-Host '1) Discord channel settings (gear icon) > Integrations > Webhooks > New Webhook'
Write-Host '2) Click "Copy Webhook URL", then paste it below (right-click or Ctrl+V) and press Enter.'
Write-Host ''
try {
    $u = (Read-Host 'Webhook URL').Trim().Trim('"').Trim("'")
    if (-not $u) { Write-Host 'Nothing entered. No changes made.'; return }
    if ($u -notmatch '^https://(canary\.|ptb\.)?discord(app)?\.com/api/webhooks/') {
        Write-Host 'This does not look like a Discord webhook URL (should start with https://discord.com/api/webhooks/). Nothing saved.'
        return
    }
    $p = Join-Path $PSScriptRoot '.env'
    $lines = @()
    if (Test-Path -LiteralPath $p) { $lines = [IO.File]::ReadAllLines($p) }
    $found = $false
    $out = @(foreach ($l in $lines) {
        if ($l -match '^\s*DISCORD_WEBHOOK_URL\s*=') { $found = $true; 'DISCORD_WEBHOOK_URL=' + $u } else { $l }
    })
    if (-not $found) { $out += ('DISCORD_WEBHOOK_URL=' + $u) }
    [IO.File]::WriteAllLines($p, $out, (New-Object Text.UTF8Encoding $false))
    Write-Host 'Saved to .env'

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $body = '{"content":"stock-strategies: Discord OK"}'
    Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri $u -Body $body | Out-Null
    Write-Host 'Test message sent. Check your Discord channel.'
}
catch {
    Write-Host ('Error: ' + $_.Exception.Message)
}
