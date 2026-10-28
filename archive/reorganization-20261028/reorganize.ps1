[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = 'X:\projects\EEG-AI-Scientist'
$temporaryRoot = 'C:\Users\14090\Documents\ChatGPT\EEG-FM-RSI'
$recordRoot = Join-Path $projectRoot 'archive\reorganization-20261028'
$evidenceRoot = Join-Path $projectRoot 'archive\setup-20261028\evidence'
$legacyRoot = Join-Path $projectRoot 'archive\legacy-harness-20261028'
$records = [System.Collections.Generic.List[object]]::new()

function Assert-Within([string]$Path, [string]$Root) {
    $absolute = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $boundary = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ($absolute -eq $boundary -or -not $absolute.StartsWith($boundary + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not a descendant of the intended boundary: $absolute"
    }
    return $absolute
}
function Hash-File([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Ensure-Parent([string]$Path) {
    $parent = Split-Path -Parent $Path
    [void][IO.Directory]::CreateDirectory($parent)
}
function Copy-VerifiedFile([string]$Source, [string]$Target) {
    [void](Assert-Within $Source $temporaryRoot)
    [void](Assert-Within $Target $projectRoot)
    if (Test-Path -LiteralPath $Target) { throw "Destination already exists: $Target" }
    if ((Get-Item -LiteralPath $Source -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing link: $Source" }
    $before = Hash-File $Source
    Ensure-Parent $Target
    Copy-Item -LiteralPath $Source -Destination $Target
    $after = Hash-File $Target
    if ($before -ne $after -or $before -ne (Hash-File $Source)) { throw "Copy verification failed: $Source" }
    $records.Add([pscustomobject]@{action='copy_verified';source=$Source;target=$Target;sha256=$after})
}
function Copy-VerifiedTree([string]$Source, [string]$Target, [string]$ExcludedPrefix='') {
    [void](Assert-Within $Source $temporaryRoot)
    [void](Assert-Within $Target $projectRoot)
    if (Test-Path -LiteralPath $Target) { throw "Destination already exists: $Target" }
    [void][IO.Directory]::CreateDirectory($Target)
    foreach ($entry in Get-ChildItem -LiteralPath $Source -Force -Recurse) {
        $relative = $entry.FullName.Substring($Source.Length).TrimStart('\')
        if ($ExcludedPrefix -and ($relative -eq $ExcludedPrefix -or $relative.StartsWith($ExcludedPrefix + '\',[StringComparison]::OrdinalIgnoreCase))) { continue }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing link: $($entry.FullName)" }
        $destination = Join-Path $Target $relative
        if ($entry.PSIsContainer) { [void][IO.Directory]::CreateDirectory($destination) }
        else { Copy-VerifiedFile $entry.FullName $destination }
    }
}
function Move-LocalEntry([string]$Name, [string]$Destination) {
    $source = Assert-Within (Join-Path $projectRoot $Name) $projectRoot
    $target = Assert-Within $Destination $projectRoot
    if (-not (Test-Path -LiteralPath $source)) { throw "Missing migration source: $source" }
    if (Test-Path -LiteralPath $target) { throw "Migration destination exists: $target" }
    if ((Get-Item -LiteralPath $source -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked migration source: $source" }
    Ensure-Parent $target
    Move-Item -LiteralPath $source -Destination $target
    if ((Test-Path -LiteralPath $source) -or -not (Test-Path -LiteralPath $target)) { throw "Move did not complete: $source" }
    $records.Add([pscustomobject]@{action='same_volume_move';source=$source;target=$target})
    $records | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $recordRoot 'migration-in-progress.json') -Encoding utf8
}

if (Test-Path -LiteralPath (Join-Path $recordRoot 'completed.json')) { throw 'Migration already recorded; inspect instead of rerunning.' }
foreach ($newPath in @($legacyRoot, $evidenceRoot, (Join-Path $projectRoot 'framework'), (Join-Path $projectRoot 'materials'), (Join-Path $projectRoot 'scripts'))) {
    if (Test-Path -LiteralPath $newPath) { throw "Expected new destination: $newPath" }
}
$indexHash = Hash-File (Join-Path $projectRoot '.git\index')
$configHash = Hash-File (Join-Path $projectRoot '.git\config')
$head = (& git --no-optional-locks -c safe.directory=X:/projects/EEG-AI-Scientist -C $projectRoot rev-parse HEAD).Trim()
$beforeStatus = & git --no-optional-locks -c safe.directory=X:/projects/EEG-AI-Scientist -C $projectRoot status --porcelain=v1
$beforeStatus | Set-Content -LiteralPath (Join-Path $recordRoot 'status-before.txt') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $projectRoot '.gitignore') -Destination (Join-Path $recordRoot 'gitignore-before.txt')

# Verify the previously captured business snapshot against the current source before any move.
$snapshot = Get-Content -Raw -LiteralPath (Join-Path $temporaryRoot 'reports\environment-20261028\local-archive\manifest.json') | ConvertFrom-Json
foreach ($item in $snapshot.entries) {
    $source = Join-Path $projectRoot $item.path
    if (-not (Test-Path -LiteralPath $source) -or (Hash-File $source) -ne $item.sha256) { throw "Source changed since recovery snapshot: $($item.path)" }
}
if ($indexHash -ne $snapshot.index_sha256) { throw 'Original Git index changed since snapshot; stop before migration.' }

# Preserve all setup evidence except the redundant restore-check clone; its verified bundle/ZIP/results remain.
$reportSource = Join-Path $temporaryRoot 'reports\environment-20261028'
Copy-VerifiedTree $reportSource $evidenceRoot 'local-archive\restore-check'
$bundle = Join-Path $evidenceRoot 'source-provenance\eeg-fm-research-source-snapshot-corrected.bundle'
if ((Hash-File $bundle) -ne 'a0e2131f29ec3ae176887fe69c71149563b593de08aa5d3e366d52fcf0cc13fd') { throw 'Source Git history bundle mismatch.' }

# Import only the original framework files, without the accidental nested repository.
$sourceManifest = Get-Content -Raw -LiteralPath (Join-Path $evidenceRoot 'source-provenance\source-file-manifest.json') | ConvertFrom-Json
$frameworkRoot = Join-Path $projectRoot 'framework'
[void][IO.Directory]::CreateDirectory($frameworkRoot)
foreach ($item in $sourceManifest) {
    $source = Join-Path (Join-Path $temporaryRoot 'workspaces\eeg-fm-research') $item.path
    $target = Join-Path $frameworkRoot $item.path
    if ($item.path -match '(^|[/\\])\.git([/\\]|$)' -or (Hash-File $source) -ne $item.sha256) { throw "Unexpected source entry: $($item.path)" }
    Copy-VerifiedFile $source $target
}
if (Test-Path -LiteralPath (Join-Path $frameworkRoot '.git')) { throw 'Framework must not contain a nested repository.' }

# Same-volume moves retain original bytes; existing archive and credentials are not touched.
$legacyNames = @('.venv','.vscode','audit_20261022','configs','docs','src','studies','tests','.python-version','ENVIRONMENT.md','HANDOFF.md','pyproject.toml','pyrightconfig.json','README.md','uv.lock')
foreach ($name in $legacyNames) { Move-LocalEntry $name (Join-Path $legacyRoot $name) }
Move-LocalEntry 'group-meeting' (Join-Path $projectRoot 'materials\meetings')
Move-LocalEntry 'ref' (Join-Path $projectRoot 'materials\references')
Move-LocalEntry '火山引擎资源利用与规范惯例规定_page_printed.pdf' (Join-Path $projectRoot 'materials\infrastructure\火山引擎资源利用与规范惯例规定_page_printed.pdf')
Move-LocalEntry 'EEG_FM_Codex_Handoff_2026-10-28.md' (Join-Path $projectRoot 'docs\handoffs\EEG_FM_Codex_Handoff_2026-10-28.md')
Move-LocalEntry 'EEG_AI_Scientist_Review_20261022.zip' (Join-Path $projectRoot 'archive\review-packages\EEG_AI_Scientist_Review_20261022.zip')
foreach ($name in @('eeg-fm-research_20261022_e6f6e50','eeg-fm-research_20261022_e6f6e50.tar','eeg-fm-research_20261022_e6f6e50.tar.gz')) {
    Move-LocalEntry $name (Join-Path (Join-Path $projectRoot 'archive\sources\wzf-20261022') $name)
}

Copy-VerifiedTree (Join-Path $temporaryRoot 'docs\environment-20261028') (Join-Path $projectRoot 'docs\environment-20261028')
Copy-VerifiedTree (Join-Path $temporaryRoot 'docs\superpowers') (Join-Path $projectRoot 'archive\setup-20261028\historical-plans')
Copy-VerifiedTree (Join-Path $temporaryRoot 'scripts') (Join-Path $projectRoot 'scripts')
Copy-VerifiedFile (Join-Path $temporaryRoot 'workspaces\AGENTS.md') (Join-Path $projectRoot 'archive\setup-20261028\retired-c-workspaces-AGENTS.md')

# Verify every original business file through the old-to-new mapping before retiring C copies.
$moves = @($records | Where-Object action -eq 'same_volume_move' | Sort-Object { $_.source.Length } -Descending)
$mapped = [System.Collections.Generic.List[object]]::new()
foreach ($item in $snapshot.entries) {
    $original = Join-Path $projectRoot $item.path
    $current = $original
    foreach ($move in $moves) {
        if ($original -eq $move.source) { $current = $move.target; break }
        if ($original.StartsWith($move.source + '\',[StringComparison]::OrdinalIgnoreCase)) { $current = $move.target + $original.Substring($move.source.Length); break }
    }
    if ((Hash-File $current) -ne $item.sha256) { throw "Post-move original content mismatch: $original" }
    $mapped.Add([pscustomobject]@{original=$original;current=$current;sha256=$item.sha256})
}
$mapped | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $recordRoot 'original-files-map.json') -Encoding utf8
if ((Hash-File (Join-Path $projectRoot '.git\index')) -ne $indexHash -or (Hash-File (Join-Path $projectRoot '.git\config')) -ne $configHash) { throw 'Original Git metadata changed.' }

# Only these exact task-created C paths may be removed, after verified copies and Git bundles exist.
$retirePaths = @(
    (Join-Path $temporaryRoot 'reports\environment-20261028'),
    (Join-Path $temporaryRoot 'workspaces'),
    (Join-Path $temporaryRoot 'docs'),
    (Join-Path $temporaryRoot 'scripts')
)
$expectedWorkspaces = @('AGENTS.md','eeg-fm-research')
if (@(Get-ChildItem -LiteralPath (Join-Path $temporaryRoot 'workspaces') -Force | Where-Object Name -notin $expectedWorkspaces).Count) { throw 'Unexpected C workspace contents; do not retire.' }
foreach ($path in $retirePaths) {
    $resolved = Assert-Within $path $temporaryRoot
    if ((Get-Item -LiteralPath $resolved -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing recursive removal of a link: $resolved" }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    if (Test-Path -LiteralPath $resolved) { throw "Retirement incomplete: $resolved" }
    $records.Add([pscustomobject]@{action='retire_verified_task_created_C_copy';source=$resolved;target='Preserved in X project; Git histories preserved as verified bundles'})
}
$records | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $recordRoot 'migration.json') -Encoding utf8
[pscustomobject]@{original_business_files_verified=$mapped.Count;framework_files=$sourceManifest.Count;index_sha256=$indexHash;config_sha256=$configHash;head=$head;c_active_git_repositories_removed=2;new_commits=0;pushes=0;original_credentials_touched=$false} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $recordRoot 'completed.json') -Encoding utf8
Write-Output "Migration verified: $($mapped.Count) original business files, $($sourceManifest.Count) framework files. C task-created working directories retired. Original Git index/config preserved."
