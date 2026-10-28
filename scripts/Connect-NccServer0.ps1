[CmdletBinding()]
param(
    [ValidateSet('Shell', 'Status', 'Login', 'Smoke')]
    [string]$Mode = 'Shell',
    [string]$CampusAddress
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$sshConfig = Join-Path $env:USERPROFILE '.ssh\config'
if (-not (Test-Path -LiteralPath $sshConfig)) { throw 'Existing SSH config not found.' }
if (-not $CampusAddress) {
    $campusCandidates = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.InterfaceAlias -eq 'WLAN' -and $_.IPAddress -like '10.*' -and $_.AddressState -eq 'Preferred'
    })
    if ($campusCandidates.Count -ne 1) { throw 'Cannot select one campus WLAN address; pass -CampusAddress explicitly.' }
    $CampusAddress = $campusCandidates[0].IPAddress
}
$ip = $null
if (-not [System.Net.IPAddress]::TryParse($CampusAddress, [ref]$ip)) { throw 'Invalid campus IP address.' }
$sshArgs = @('-F', $sshConfig, '-b', $CampusAddress, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
    '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no', '-o', 'ServerAliveInterval=30')
$remoteBase = '/data/duandh/eegfm-stage-a-20261028'
switch ($Mode) {
    'Shell' { & ssh @sshArgs -tt nccserver0 "$remoteBase/bin/enter-workspace" }
    'Status' { & ssh @sshArgs -T nccserver0 "$remoteBase/bin/codex --version; $remoteBase/bin/codex login status" }
    'Login' { & ssh @sshArgs -tt nccserver0 "$remoteBase/bin/codex login --device-auth" }
    'Smoke' { & ssh @sshArgs -T nccserver0 "timeout -k 5s 90s $remoteBase/bin/codex exec --skip-git-repo-check --sandbox read-only -C $remoteBase/smoke 'Reply exactly CODEX_READY. Do not use tools, read files, or run commands.'" }
}
exit $LASTEXITCODE
