"""Installation, workspace isolation and lightweight command entrypoints."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import pytest

REPO = Path(__file__).resolve().parents[1]

def test_help_outside_checkout_without_science_dependencies(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    completed = subprocess.run([sys.executable, "-S", "-m", "eegfm", "--help"],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "run" in completed.stdout and "memory" in completed.stdout

def test_explicit_workspace_does_not_use_current_directory(tmp_path: Path) -> None:
    selected = tmp_path / "research workspace"
    selected.mkdir()
    env = {**os.environ, "PYTHONPATH": str(REPO / "src"), "EEGFM_ROOT": str(selected)}
    completed = subprocess.run([sys.executable, "-c",
        "from eegfm.common import ROOT; print(ROOT)"], cwd=tmp_path, env=env,
        capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout.strip()) == selected


@pytest.mark.parametrize("command, option", [
    ("reference", "--resources"), ("export", "--public"),
    ("prepare-eegmmidb", "--parent"), ("eegmmidb-reference", "--prepared"),
    ("eegmmidb-export", "--private"), ("baselines", "--reference"),
    ("bootstrap", "--report"), ("episode", "--config"),
])
def test_scientific_help_without_installed_dependencies(tmp_path: Path, command: str, option: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    completed = subprocess.run([sys.executable, "-S", "-m", "eegfm", command, "--help"],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert option in completed.stdout
    assert ".[science]" in completed.stdout


def test_resumer_prompt_uses_current_available_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eegfm.agent import driver
    monkeypatch.setattr(driver, "CODE", tmp_path)
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    required = [tmp_path / name for name in ("README.md", "AGENTS.md", "PROGRAM.md",
        "tasks/synthetic_demo/TASK.md", "runs/replay/STATE.json")]
    for path in required:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    runner = driver.Driver("replay", driver.Adapter("script"), run_path=tmp_path / "runs/replay",
        task={"task_id": "synthetic_demo"})
    assert hasattr(runner, "prompt"), "The session context must be rendered from current workspace files"
    prompt = runner.prompt({"status": "working", "note": "Retain negative results"})
    assert all(str(path) in prompt for path in required)
    assert "memory/INDEX.md" not in prompt and "section 9" not in prompt
    assert "Retain negative results" in prompt
    assert "eegfm state set replay --status waiting_job" in prompt
    assert "eegfm brief submit replay" in prompt
    assert "eegfm state set replay --status done" in prompt
    notes = tmp_path / "runs/replay/NOTES.md"
    assert str(notes) not in prompt
    notes.write_text("Task-owned findings", encoding="utf-8")
    assert str(notes) in runner.prompt({"status": "working"})
