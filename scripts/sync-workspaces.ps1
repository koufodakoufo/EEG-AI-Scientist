param(
    [ValidateSet('all', 'huoshanyun', 'nccserver0')][string]$Target = 'all',
    [switch]$Publish,
    [string]$CampusAddress
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $projectRoot 'config/workspaces.json') -Raw | ConvertFrom-Json
$hosts = if ($Target -eq 'all') { @('huoshanyun', 'nccserver0') } else { @($Target) }
# Git for Windows may find its bundled SSH instead of the client used above.
# Resolve the system application so both paths use the same keys and SSH agent.
$sshExecutable = (Get-Command ssh -CommandType Application | Select-Object -First 1).Source.Replace('\', '/')

function Invoke-CheckedGit([string[]]$GitArguments) {
    & git -C $projectRoot @GitArguments
    if ($LASTEXITCODE -ne 0) { throw ('Git failed: ' + ($GitArguments -join ' ')) }
}

$branch = & git -C $projectRoot branch --show-current
if ($LASTEXITCODE -ne 0) { throw 'Not a Git checkout' }
$commit = & git -C $projectRoot rev-parse HEAD
Write-Output "local: $branch $commit"
if ($Publish) {
    if ($branch -ne $settings.branch) { throw "Publish requires branch $($settings.branch)" }
    $dirty = & git -C $projectRoot status --porcelain
    if ($dirty) { throw 'Commit or preserve local changes before publishing' }
    $configuredRemote = & git -C $projectRoot remote get-url $settings.remote
    if ($configuredRemote -ne $settings.repository) { throw 'Unexpected authoritative Git remote' }
}

foreach ($machine in $hosts) {
    $workspace = $settings.workspaces.$machine
    $sshArguments = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes')
    if ($machine -eq 'nccserver0') {
        if (-not $CampusAddress) {
            $addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
                $_.AddressState -eq 'Preferred' -and $_.InterfaceAlias -match 'WLAN|Wi-Fi' -and $_.IPAddress -match '^10\.'
            })
            if ($addresses.Count -eq 0) {
                $addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
                    $_.AddressState -eq 'Preferred' -and $_.IPAddress -match '^10\.'
                })
            }
            if ($addresses.Count -ne 1) { throw 'Pass the current campus IPv4 using -CampusAddress' }
            $CampusAddress = $addresses[0].IPAddress
        }
        $parsedAddress = $null
        if (-not [Net.IPAddress]::TryParse($CampusAddress, [ref]$parsedAddress)) { throw 'Invalid campus IP address' }
        $sshArguments += @('-b', $CampusAddress)
    }
    # Paths come from this repository's reviewed configuration, not user command text.
    if ($workspace.code -notmatch '^/[A-Za-z0-9_./-]+$' -or $workspace.code -match '/\.\.?(/|$)') { throw 'Unsafe configured code path' }
    $remoteState = @(& ssh @sshArguments $machine "git -C '$($workspace.code)' rev-parse --abbrev-ref HEAD && git -C '$($workspace.code)' rev-parse HEAD && git -C '$($workspace.code)' status --porcelain")
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect $machine" }
    Write-Output ($machine + ': ' + ($remoteState -join ' | '))
    if ($Publish -and ($remoteState.Count -lt 2 -or $remoteState[0] -ne $settings.branch)) { throw "Remote checkout is not on main: $machine" }
    if ($Publish -and $remoteState.Count -ne 2) { throw "Remote checkout has changes: $machine" }
}

if (-not $Publish) { exit 0 }
Invoke-CheckedGit @('push', $settings.remote, $settings.branch, '--follow-tags')
foreach ($machine in $hosts) {
    $workspace = $settings.workspaces.$machine
    $previousSshCommand = $env:GIT_SSH_COMMAND
    try {
        $env:GIT_SSH_COMMAND = '"' + $sshExecutable + '" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes'
        if ($machine -eq 'nccserver0') { $env:GIT_SSH_COMMAND += " -b $CampusAddress" }
        # Git's updateInstead refuses dirty server checkouts; no force/reset/copy overlay.
        Invoke-CheckedGit @('push', ('ssh://' + $machine + $workspace.code), ($settings.branch + ':' + $settings.branch), '--follow-tags')
        $verificationSshArguments = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes')
        if ($machine -eq 'nccserver0') { $verificationSshArguments += @('-b', $CampusAddress) }
        $deployed = @(& ssh @verificationSshArguments $machine "git -C '$($workspace.code)' rev-parse --abbrev-ref HEAD && git -C '$($workspace.code)' rev-parse HEAD && git -C '$($workspace.code)' status --porcelain")
        if ($LASTEXITCODE -ne 0) { throw "Cannot verify deployed checkout on $machine" }
        if ($deployed.Count -lt 2 -or $deployed[0] -ne $settings.branch) { throw "Deployed checkout is not on main: $machine" }
        if ($deployed.Count -ne 2 -or $deployed[1] -ne $commit) { throw "Deployed checkout version or cleanliness mismatch on $machine" }
        Write-Output "verified: $machine $commit"
    } finally {
        $env:GIT_SSH_COMMAND = $previousSshCommand
    }
}
