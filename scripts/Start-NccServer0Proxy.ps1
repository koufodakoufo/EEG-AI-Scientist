#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$CampusAddress,
    [ValidateRange(0, 2147483647)]
    [int]$VerifyOnlySeconds = 0
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $taskRoot '.local\nccserver0'
[void][IO.Directory]::CreateDirectory($logDir)
$stateFile = Join-Path $logDir 'proxy-tunnel.state.json'
$lockFile = Join-Path $logDir 'proxy-tunnel.lock'
$sshConfig = Join-Path $env:USERPROFILE '.ssh\config'
$sshExe = (Get-Command ssh.exe -ErrorAction Stop).Source
$configureScript = Join-Path $PSScriptRoot 'Set-NccServer0Proxy.py'
if (-not (Test-Path -LiteralPath $sshConfig -PathType Leaf)) { throw 'Existing SSH config not found.' }
if (-not (Test-Path -LiteralPath $configureScript -PathType Leaf)) { throw 'Set-NccServer0Proxy.py is missing.' }

function Join-NativeArguments {
    param([string[]]$Values)
    # Start-Process joins ArgumentList itself; quote for Windows argv explicitly.
    return (($Values | ForEach-Object {
        '"' + [regex]::Replace([regex]::Replace($_, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
    }) -join ' ')
}

function Write-TunnelState {
    param($Value)
    $temporary = $stateFile + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        $Value.updatedAt = [DateTime]::UtcNow.ToString('o')
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($stateFile)) { [IO.File]::Replace($temporary, $stateFile, ($stateFile + '.previous')) }
        else { [IO.File]::Move($temporary, $stateFile) }
    } finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }
}

function Read-SharedLog {
    param([string]$Path)
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $reader = $null
    try {
        $reader = New-Object IO.StreamReader($stream)
        return $reader.ReadToEnd()
    } finally {
        if ($reader) { $reader.Dispose() } else { $stream.Dispose() }
    }
}

function Get-OwnedTunnelProcess {
    param($Recorded)
    if (-not $Recorded -or [string]$Recorded.pid -notmatch '^\d+$' -or -not $Recorded.startTime -or -not $Recorded.commandIdentity) { return $null }
    $candidate = Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f [int]$Recorded.pid)
    if (-not $candidate -or $candidate.Name -ne 'ssh.exe' -or $candidate.CommandLine -ne $Recorded.commandIdentity -or
        $candidate.CommandLine -notmatch '127\.0\.0\.1:0:127\.0\.0\.1:10808' -or
        $candidate.CommandLine -notmatch '(?:^|[\s"])nccserver0(?:[\s"]|$)') { return $null }
    try { $process = Get-Process -Id ([int]$Recorded.pid) -ErrorAction Stop } catch { return $null }
    # PowerShell 7 may deserialize ISO JSON dates into DateTime; string casts lose precision.
    if ($process.StartTime.ToUniversalTime().Ticks -ne ([DateTime]$Recorded.startTime).ToUniversalTime().Ticks) { $process.Dispose(); return $null }
    return $process
}

function Invoke-SshCommand {
    param([string]$RemoteCommand, [string]$InputText, [int]$TimeoutSeconds = 35)
    # Process streams bypass PowerShell 5.1 NativeCommandError handling of stderr.
    $arguments = @('-F', $sshConfig, '-b', $CampusAddress, '-T', '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=8', '-o', 'ConnectionAttempts=1', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'UpdateHostKeys=no', '-o', 'ClearAllForwardings=yes', '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
        'nccserver0', $RemoteCommand)
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $sshExe
    $info.Arguments = Join-NativeArguments $arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.RedirectStandardInput = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    $started = $false
    try {
        $started = $process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        # .NET Framework has no ProcessStartInfo.StandardInputEncoding property.
        $inputWriter = New-Object IO.StreamWriter($process.StandardInput.BaseStream, (New-Object Text.UTF8Encoding($false)))
        $timer = [Diagnostics.Stopwatch]::StartNew()
        if ($InputText) {
            $inputTask = $inputWriter.WriteAsync($InputText)
            while (-not $inputTask.IsCompleted -and -not $process.HasExited) {
                if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) { throw 'SSH stdin delivery timed out.' }
                Start-Sleep -Milliseconds 100
            }
            $inputTask.GetAwaiter().GetResult()
        }
        $inputWriter.Close()
        while (-not $process.HasExited) {
            if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) { throw ('SSH command timed out: {0}' -f $RemoteCommand) }
            Start-Sleep -Milliseconds 100
        }
        $process.WaitForExit()
        return [pscustomobject]@{ ExitCode = $process.ExitCode; StdOut = $stdout.GetAwaiter().GetResult(); StdErr = $stderr.GetAwaiter().GetResult() }
    } finally {
        if ($started -and -not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        $process.Dispose()
    }
}

function Test-Tunnel {
    param([int]$Port)
    if ($Port -lt 1 -or $Port -gt 65535) { return $false }
    $listener = Invoke-SshCommand -RemoteCommand ("ss -H -ltn 'sport = :{0}'" -f $Port)
    if ($listener.ExitCode -ne 0) { return $false }
    $lines = @($listener.StdOut -split '\r?\n' | Where-Object { $_.Trim() })
    if ($lines.Count -ne 1) { return $false }
    $fields = $lines[0].Trim() -split '\s+'
    if ($fields.Count -lt 4 -or $fields[3] -ne ('127.0.0.1:{0}' -f $Port)) { return $false }
    $response = Invoke-SshCommand -RemoteCommand ("curl --noproxy '' --proxy http://127.0.0.1:{0} --connect-timeout 5 --max-time 12 -sS -o /dev/null -w '%{{http_code}}' https://auth.openai.com/.well-known/openid-configuration" -f $Port)
    return ($response.ExitCode -eq 0 -and $response.StdOut.Trim() -eq '200')
}

$addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' })
if (-not $CampusAddress) {
    $candidates = @($addresses | Where-Object { $_.InterfaceAlias -eq 'WLAN' -and $_.IPAddress -like '10.*' })
    if ($candidates.Count -ne 1) { throw 'Cannot select one campus WLAN address; pass -CampusAddress explicitly.' }
    $CampusAddress = $candidates[0].IPAddress
}
$parsedAddress = $null
if (-not [Net.IPAddress]::TryParse($CampusAddress, [ref]$parsedAddress) -or
    $parsedAddress.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or
    -not @($addresses | Where-Object { $_.IPAddress -eq $CampusAddress }).Count) {
    throw 'CampusAddress must be an IPv4 address currently assigned to this computer.'
}

$ownedProcess = $null
$ownedState = $null
$startupLock = $null
try {
    try { $startupLock = [IO.File]::Open($lockFile, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None) }
    catch { throw 'Another tunnel start/stop operation is in progress; retry after it finishes.' }
    if (Test-Path -LiteralPath $stateFile) {
        $recorded = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $existing = Get-OwnedTunnelProcess $recorded
        if ($existing) {
            try {
                $healthy = $false
                if ($recorded.campusAddress -eq $CampusAddress) {
                    try { $healthy = Test-Tunnel -Port ([int]$recorded.port) } catch { $healthy = $false }
                }
                if ($healthy -and -not $existing.HasExited) {
                    Write-Output ('Existing task tunnel verified (PID {0}, port {1}, HTTP 200). Keep its original PowerShell window open.' -f $recorded.pid, $recorded.port)
                    return
                }
                # Identify by both command line and creation time before stopping.
                if (-not $existing.HasExited) { $existing.Kill(); $existing.WaitForExit() }
                $recorded.status = 'stopped'
                Write-TunnelState $recorded
            } finally { $existing.Dispose() }
        }
    }
    $localProxy = New-Object Net.Sockets.TcpClient
    try {
        $probe = $localProxy.ConnectAsync('127.0.0.1', 10808)
        if (-not $probe.Wait(2000) -or -not $localProxy.Connected) { throw 'The existing local proxy on 127.0.0.1:10808 is unavailable.' }
    } finally { $localProxy.Dispose() }

    $runId = [Guid]::NewGuid().ToString('N')
    $stdoutLog = Join-Path $logDir ('proxy-tunnel.{0}.stdout.log' -f $runId)
    $stderrLog = Join-Path $logDir ('proxy-tunnel.{0}.stderr.log' -f $runId)
    $arguments = @('-F', $sshConfig, '-b', $CampusAddress, '-N', '-T', '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'UpdateHostKeys=no', '-o', 'ExitOnForwardFailure=yes', '-o', 'LogLevel=INFO',
        '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
        '-R', '127.0.0.1:0:127.0.0.1:10808', 'nccserver0')
    $ownedProcess = Start-Process -FilePath $sshExe -ArgumentList (Join-NativeArguments $arguments) -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
    $identity = Get-CimInstance Win32_Process -Filter ('ProcessId={0}' -f $ownedProcess.Id)
    if (-not $identity -or -not $identity.CommandLine) { throw ('Cannot establish new SSH process identity; inspect {0}' -f $stderrLog) }
    $ownedState = [pscustomobject][ordered]@{
        version = 1; runId = $runId; status = 'starting'; pid = $ownedProcess.Id
        startTime = $ownedProcess.StartTime.ToUniversalTime().ToString('o'); port = 0
        campusAddress = $CampusAddress; commandIdentity = $identity.CommandLine
        stdoutLog = $stdoutLog; stderrLog = $stderrLog; updatedAt = ''
    }
    Write-TunnelState $ownedState
    $allocationTimer = [Diagnostics.Stopwatch]::StartNew()
    while ($allocationTimer.Elapsed.TotalSeconds -lt 25) {
        if ($ownedProcess.HasExited) { throw ('SSH exited with code {0}; inspect {1}' -f $ownedProcess.ExitCode, $stderrLog) }
        $logText = Read-SharedLog -Path $stderrLog
        $allocation = [regex]::Match($logText, '(?m)^Allocated port (\d+) for remote forward to 127\.0\.0\.1:10808\r?$')
        if ($allocation.Success) { $ownedState.port = [int]$allocation.Groups[1].Value; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ownedState.port) { throw ('SSH did not report an allocated remote port; inspect {0}' -f $stderrLog) }
    if (-not (Test-Tunnel -Port $ownedState.port)) { throw 'New tunnel failed loopback-listener or authentication-endpoint HTTP 200 verification.' }
    if ($ownedProcess.HasExited) { throw 'SSH exited before the scoped proxy configuration could be updated.' }
    $configuration = Invoke-SshCommand -RemoteCommand ('python3 - {0}' -f $ownedState.port) -InputText ([IO.File]::ReadAllText($configureScript))
    if ($configuration.ExitCode -ne 0) { throw ('Scoped proxy configuration failed (SSH exit {0}): {1}' -f $configuration.ExitCode, $configuration.StdErr.Trim()) }
    if ($ownedProcess.HasExited) { throw 'SSH exited while updating the scoped proxy configuration.' }
    $ownedState.status = 'ready'
    Write-TunnelState $ownedState
    $startupLock.Dispose()
    $startupLock = $null
    Write-Output ('Task tunnel ready: PID {0}; server 127.0.0.1:{1} -> Windows 127.0.0.1:10808; authentication HTTP 200. Scoped proxy configuration updated.' -f $ownedProcess.Id, $ownedState.port)
    Write-Output 'Keep this PowerShell window open. Press Ctrl+C to stop this tunnel. Existing remote sessions must reload their environment.'
    $sessionTimer = [Diagnostics.Stopwatch]::StartNew()
    while (-not $ownedProcess.HasExited) {
        if ($VerifyOnlySeconds -gt 0 -and $sessionTimer.Elapsed.TotalSeconds -ge $VerifyOnlySeconds) {
            Write-Output ('Verification interval ({0} seconds) completed; stopping this test tunnel.' -f $VerifyOnlySeconds)
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if ($ownedProcess.HasExited) {
        # Stop writes its final state after ending SSH; allow that atomic write to finish.
        for ($stopCheck = 0; $stopCheck -lt 20; $stopCheck++) {
            try {
                $stopRecord = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
                if ($stopRecord.runId -eq $ownedState.runId -and $stopRecord.status -eq 'stopped') {
                    Write-Output 'Task tunnel stopped normally by Stop-NccServer0Proxy.ps1.'
                    return
                }
            } catch { }
            Start-Sleep -Milliseconds 100
        }
        throw ('Tunnel ended (SSH exit {0}); rerun after checking the campus connection and local proxy. Log: {1}' -f $ownedProcess.ExitCode, $stderrLog)
    }
} finally {
    if ($startupLock) { $startupLock.Dispose() }
    if ($ownedProcess) {
        try {
            if (-not $ownedProcess.HasExited) { $ownedProcess.Kill(); $ownedProcess.WaitForExit() }
        } finally {
            $ownedProcess.Dispose()
            if ($ownedState) {
                $cleanupLock = $null
                try {
                    $cleanupLock = [IO.File]::Open($lockFile, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
                    $current = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
                    if ($current.runId -eq $ownedState.runId) { $ownedState.status = 'stopped'; Write-TunnelState $ownedState }
                } catch { Write-Warning ('Tunnel stopped, but its local state could not be updated: {0}' -f $_.Exception.Message) }
                finally { if ($cleanupLock) { $cleanupLock.Dispose() } }
            }
        }
    }
}
