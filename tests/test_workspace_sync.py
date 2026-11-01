"""Publishing must verify the deployed checkout, not only its main ref."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
ROOT = Path(__file__).resolve().parents[1]


def run_publish(tmp_path: Path, scenario: str) -> subprocess.CompletedProcess[str]:
    """Use fake transports so rejection is tested without any network mutation."""
    script = str(ROOT / "scripts" / "sync-workspaces.ps1").replace("'", "''")
    wrapper = tmp_path / "check-sync.ps1"
    wrapper.write_text(
        r"""
$global:LASTEXITCODE = 0
$global:pushes = 0
$global:reads = 0
$commit = 'ffffffffffffffffffffffffffffffffffffffff'
function git {
    $global:LASTEXITCODE = 0
    if ($args -contains 'branch') { return 'main' }
    if ($args -contains 'rev-parse') { return $commit }
    if ($args -contains 'status') { return }
    if ($args -contains 'get-url') { return 'https://github.com/koufodakoufo/EEG-AI-Scientist.git' }
    if ($args -contains 'push') { $global:pushes++; return }
    if ($args -contains 'ls-remote') { return "$commit`trefs/heads/main" }
    throw ('Unexpected git command: ' + ($args -join ' '))
}
function ssh {
    $global:LASTEXITCODE = 0
    $global:reads++
    $command = [string]$args[-1]
    if ($command -match '--abbrev-ref') {
        if ($scenario -eq 'already-wrong' -or $global:reads -gt 1) { 'feat/unpublished' } else { 'main' }
        $commit
    } else { $commit }
}
"""
        + f"\n$scenario = '{scenario}'\ntry {{\n & '{script}' -Publish -Target huoshanyun\n"
        + " throw 'UNSAFE_SUCCESS'\n} catch {\n"
        + " if ($_.Exception.Message -notmatch 'checkout.*main|branch.*main') { Write-Output $_; exit 7 }\n"
        + " if ($scenario -eq 'already-wrong' -and $global:pushes -ne 0) { exit 8 }\n"
        + " Write-Output 'CHECKOUT_REJECTED'; exit 0\n}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-File", str(wrapper)],
        capture_output=True, text=True, timeout=30, check=False,
    )


@pytest.mark.parametrize("scenario", ["already-wrong", "changed-after-push"])
def test_publish_rejects_non_main_remote_checkout(tmp_path: Path, scenario: str) -> None:
    result = run_publish(tmp_path, scenario)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CHECKOUT_REJECTED" in result.stdout
