#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $taskRoot '.local\nccserver0'
$stateFile = Join-Path $logDir 'proxy-tunnel.state.json'
$lockFile = Join-Path $logDir 'proxy-tunnel.lock'
if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) { Write-Output 'No task tunnel state recorded; no process was stopped.'; return }
$operationLock = $null
try {
    try { $operationLock = [IO.File]::Open($lockFile, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None) }
    catch { throw 'Another tunnel start/stop operation is in progress; retry after it finishes.' }
    $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if ([string]$state.pid -notmatch '^\d+$' -or -not $state.startTime -or -not $state.commandIdentity) { throw 'Incomplete task tunnel identity; refusing to stop a process.' }
    $candidate = Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f [int]$state.pid)
    if ($candidate) {
        if ($candidate.Name -ne 'ssh.exe' -or $candidate.CommandLine -ne $state.commandIdentity -or
            $candidate.CommandLine -notmatch '127\.0\.0\.1:0:127\.0\.0\.1:10808' -or
            $candidate.CommandLine -notmatch '(?:^|[\s"])nccserver0(?:[\s"]|$)') {
            throw 'Recorded PID belongs to a different process; refusing to stop it.'
        }
        $process = Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue
        if ($process) {
            try {
                # Compare instants without DateTime-to-string formatting or precision loss.
                if ($process.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$state.startTime).ToUniversalTime().Ticks) { throw 'Recorded process creation time does not match; refusing to stop it.' }
                if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
            } finally { $process.Dispose() }
        }
    }
    $state.status = 'stopped'
    $state.updatedAt = [DateTime]::UtcNow.ToString('o')
    $temporary = $stateFile + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($state | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
        [IO.File]::Replace($temporary, $stateFile, ($stateFile + '.previous'))
    } finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }
    Write-Output ('Task tunnel stopped (recorded PID {0}, port {1}). Unknown server listeners were left untouched.' -f $state.pid, $state.port)
} finally { if ($operationLock) { $operationLock.Dispose() } }
