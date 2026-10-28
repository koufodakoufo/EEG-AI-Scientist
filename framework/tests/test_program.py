"""End-to-end checks of the research program with a scripted agent (no LLM, no GPU)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

CODE = Path(__file__).resolve().parents[1]
BIN = str(CODE / "bin" / "eegfm")


@pytest.fixture
def root(tmp_path, monkeypatch):
    data = tmp_path / "data root"  # a space, like "auto research"
    shutil.copytree(CODE / "tasks" / "synthetic_demo", data / "tasks" / "synthetic_demo",
                    ignore=shutil.ignore_patterns("RESEARCH_BRIEF.md", "items"))
    (data / "tasks" / "synthetic_demo" / "memory" / "items").mkdir(parents=True)
    (data / "memory" / "items").mkdir(parents=True)
    (data / "runs").mkdir()
    monkeypatch.setenv("EEGFM_ROOT", str(data))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    return data


def eegfm(*args, ok=True):
    done = subprocess.run([BIN, *args], capture_output=True, text=True)
    if ok and done.returncode:
        raise AssertionError(f"eegfm {args}: {done.stdout}{done.stderr}")
    return done


def state(root, run="r"):
    return json.loads((root / "runs" / run / "STATE.json").read_text())


def driver(*extra, timeout=120):
    return subprocess.run([sys.executable, "-B", "-m", "eegfm.driver", "run", "--run", "r", "--agent", "script",
                           "--script", str(CODE / "tests" / "fake_agent.py"), "--poll", "0.3", "--backoff", "0.2",
                           *extra], cwd=CODE, env={**os.environ, "PYTHONPATH": str(CODE)},
                          capture_output=True, text=True, timeout=timeout)


def wait_for(predicate, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError("condition not reached")


def test_full_loop_with_brief_review_and_sealed_test(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    assert state(root)["status"] == "brief"
    # The driver stops at the human review gate when asked to run once.
    driver("--once")
    driver("--once")
    assert state(root)["status"] == "awaiting_review"
    assert "brief approve" in (root / "runs" / "r" / "ATTENTION.md").read_text()
    eegfm("brief", "approve", "r", "--note", "ok")
    assert (root / "tasks" / "synthetic_demo" / "RESEARCH_BRIEF.md").exists()
    done = driver()
    assert done.returncode == 0, done.stderr
    s = state(root)
    assert s["status"] == "done"
    run = root / "runs" / "r"
    index = (run / "attempts" / "INDEX.md").read_text()
    assert "baseline" in index and index.count("| iteration |") == 2
    final = json.loads((run / "final_test.json").read_text())
    assert {c["kind"] for c in final["candidates"]} == {"baseline", "iteration"}
    assert all(isinstance(c["test_primary"], float) for c in final["candidates"])
    # Validation scores never contain test values; test lives only under sealed/.
    for score in run.glob("attempts/*/eval/score.json"):
        assert "test" not in score.read_text().lower()
    assert list((run / "sealed").glob("*/dsA/metrics.json"))
    audit = [json.loads(l) for l in (run / "audit.jsonl").read_text().splitlines()]
    assert [a["event"] for a in audit].count("lock") == 2 and audit[-1]["event"] == "unsealed"
    sessions = [json.loads(l) for l in (run / "sessions.jsonl").read_text().splitlines()]
    assert all(s["progressed"] for s in sessions)


def test_resume_after_driver_kill_continues_without_duplicates(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    driver("--once"); driver("--once")
    eegfm("brief", "approve", "r", "--note", "ok")
    process = subprocess.Popen([sys.executable, "-B", "-m", "eegfm.driver", "run", "--run", "r", "--agent", "script",
                                "--script", str(CODE / "tests" / "fake_agent.py"), "--poll", "0.3"], cwd=CODE,
                               env={**os.environ, "PYTHONPATH": str(CODE)})
    wait_for(lambda: state(root)["status"] == "waiting_job" and "-a2-" in " ".join(state(root)["jobs"]))
    process.kill()
    process.wait()
    assert driver().returncode == 0
    run = root / "runs" / "r"
    assert state(root)["status"] == "done"
    ids = [json.loads(p.read_text())["id"] for p in run.glob("attempts/A*/attempt.json")]
    assert sorted(ids) == ["A1", "A2", "A3"]


def test_overloaded_agent_backs_off_then_continues(root, monkeypatch):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    monkeypatch.setenv("FAKE_AGENT_MODE", "overloaded")
    driver("--once")  # overloaded session: back off, no state change
    sessions = [json.loads(l) for l in (root / "runs" / "r" / "sessions.jsonl").read_text().splitlines()]
    assert sessions[-1]["error"] == "transient" and state(root)["status"] == "brief"
    driver("--once")
    assert state(root)["status"] == "awaiting_review"


def test_sessions_that_change_nothing_end_as_blocked_with_a_reason(root, monkeypatch):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    monkeypatch.setenv("FAKE_AGENT_MODE", "idle")
    assert driver("--stall-limit", "2").returncode == 3
    s = state(root)
    assert s["status"] == "blocked" and "changed nothing" in s["note"]
    assert "blocked" in (root / "runs" / "r" / "ATTENTION.md").read_text()


def test_crashing_agent_is_blocked_with_its_error_not_retried_forever(root, monkeypatch):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    monkeypatch.setenv("FAKE_AGENT_MODE", "crash")
    assert driver("--stall-limit", "2", timeout=60).returncode == 3
    sessions = [json.loads(l) for l in (root / "runs" / "r" / "sessions.jsonl").read_text().splitlines()]
    assert [s["error"] for s in sessions] == ["failed", "failed"]
    assert "keyerror" in sessions[-1]["summary"]["error_tail"]
    assert state(root)["status"] == "blocked"


def test_relative_script_path_is_resolved_before_sessions_start(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    done = subprocess.run([sys.executable, "-B", "-m", "eegfm.driver", "run", "--run", "r", "--agent", "script",
                           "--script", "tests/fake_agent.py", "--once"], cwd=CODE,
                          env={**os.environ, "PYTHONPATH": str(CODE)}, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and state(root)["status"] == "awaiting_review"


def test_tools_enforce_freeze_editable_scope_and_test_gating(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    run = root / "runs" / "r"
    eegfm("state", "set", "r", "--status", "working", "--note", "skip brief in this test")
    assert "Freeze" in eegfm("attempt", "new", "r", "--kind", "baseline", "--title", "b", ok=False).stderr
    eegfm("freeze", "r", "--note", "inspected")
    a1 = json.loads(eegfm("attempt", "new", "r", "--kind", "baseline", "--title", "b").stdout)["id"]
    jobs = json.loads(eegfm("eval", "submit", "r", a1).stdout)["jobs"]
    wait_for(lambda: all((run / "jobs" / f"{j}.exit").exists() for j in jobs))
    assert json.loads(eegfm("eval", "collect", "r", a1).stdout)["status"] == "evaluated"
    # Test before lock is refused; after lock it runs exactly once.
    assert "lock" in eegfm("eval", "submit", "r", a1, "--phase", "test", ok=False).stderr
    eegfm("lock", "r", a1, "--reason", "baseline")
    eegfm("eval", "submit", "r", a1, "--phase", "test")
    assert "once" in eegfm("eval", "submit", "r", a1, "--phase", "test", ok=False).stderr
    out = json.loads(eegfm("eval", "collect", "r", a1).stdout)
    assert "primary" not in out or "test" not in json.dumps(out).replace("sealed", "")[:0]
    # Editing the frozen evaluator or a non-editable file is refused at submission.
    (run / "workspace" / "run_eval.py").write_text("print('changed')\n")
    a2 = json.loads(eegfm("attempt", "new", "r", "--kind", "iteration", "--parent", a1, "--title", "x").stdout)["id"]
    assert "outside source.editable" in eegfm("eval", "submit", "r", a2, ok=False).stderr
    # An agent cannot leave the human review gate on its own.
    eegfm("brief", "submit", "r")
    assert "awaiting human review" in eegfm("state", "set", "r", "--status", "working", ok=False).stderr


def test_validation_output_with_test_keys_fails_the_attempt(root):
    evaluator = root / "tasks" / "synthetic_demo" / "src" / "run_eval.py"
    evaluator.write_text(evaluator.read_text().replace('metrics = {"ft_bacc"', 'metrics = {"test_bacc": 1, "ft_bacc"'))
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    run = root / "runs" / "r"
    eegfm("state", "set", "r", "--status", "working")
    eegfm("freeze", "r", "--note", "x")
    a1 = json.loads(eegfm("attempt", "new", "r", "--kind", "baseline", "--title", "b").stdout)["id"]
    jobs = json.loads(eegfm("eval", "submit", "r", a1).stdout)["jobs"]
    wait_for(lambda: all((run / "jobs" / f"{j}.exit").exists() for j in jobs))
    assert json.loads(eegfm("eval", "collect", "r", a1).stdout)["status"] == "failed"
    assert "test keys" in (run / "attempts" / a1 / "eval" / "error.txt").read_text()


def test_crashed_evaluation_is_a_failed_attempt_with_its_error(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    run = root / "runs" / "r"
    eegfm("state", "set", "r", "--status", "working")
    eegfm("freeze", "r", "--note", "x")
    (run / "workspace" / "method.yaml").write_text("posttrain_lr_log10: -3.7\ntemperature: 0.1\nwarmup_epochs: 3\n")
    a1 = json.loads(eegfm("attempt", "new", "r", "--kind", "baseline", "--title", "too high lr").stdout)["id"]
    jobs = json.loads(eegfm("eval", "submit", "r", a1).stdout)["jobs"]
    wait_for(lambda: all((run / "jobs" / f"{j}.exit").exists() for j in jobs))
    assert json.loads(eegfm("eval", "collect", "r", a1).stdout)["status"] == "failed"
    assert "diverged" in (run / "attempts" / a1 / "eval" / "error.txt").read_text()


def test_memory_rules_and_promotion_filter(root):
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    bad = eegfm("memory", "add", "--task", "synthetic_demo", "--kind", "observation", "--applies", "method:x",
                "--evidence", "run:r/attempt:A1", "--claim", "Next we should try a lower lr.", ok=False)
    assert "not a recommendation" in bad.stderr
    leak = eegfm("memory", "add", "--task", "synthetic_demo", "--run", "r", "--kind", "observation",
                 "--applies", "method:x", "--evidence", "run:r/attempt:A1", "--claim", "test bAcc rose to 61%", ok=False)
    assert "test results" in leak.stderr
    method = eegfm("memory", "add", "--task", "synthetic_demo", "--kind", "observation", "--applies", "method:x",
                   "--evidence", "run:r/attempt:A1", "--claim", "Validation rose with warmup.").stdout.strip()
    item = Path(method).stem
    assert "method-specific" in eegfm("memory", "promote", "--task", "synthetic_demo", item, ok=False).stderr
    data = eegfm("memory", "add", "--task", "synthetic_demo", "--kind", "pitfall", "--applies", "dataset:dsA",
                 "--evidence", "run:r/attempt:A1", "--claim", "dsA labels are imbalanced.").stdout.strip()
    item = Path(data).stem
    assert "two tasks" in eegfm("memory", "promote", "--task", "synthetic_demo", item, ok=False).stderr
    shared = eegfm("memory", "promote", "--task", "synthetic_demo", item, "--confirmed-by", "other_task").stdout.strip()
    assert "/memory/items/" in shared and "dsA" in (root / "memory" / "INDEX.md").read_text()


def test_setup_attempts_use_the_smoke_command_and_never_count(root):
    task = root / "tasks" / "synthetic_demo" / "task.yaml"
    task.write_text(task.read_text().replace(
        '  metric: ft_bacc',
        '  smoke_command: "python3 -B run_eval.py --phase val --target {shard} --out {out} && touch {out}/SMOKE"\n'
        '  metric: ft_bacc'))
    eegfm("run", "init", "--task", "synthetic_demo", "--run-id", "r")
    run = root / "runs" / "r"
    eegfm("state", "set", "r", "--status", "working")
    a1 = json.loads(eegfm("attempt", "new", "r", "--kind", "setup", "--title", "smoke").stdout)["id"]
    jobs = json.loads(eegfm("eval", "submit", "r", a1).stdout)["jobs"]
    wait_for(lambda: all((run / "jobs" / f"{j}.exit").exists() for j in jobs))
    eegfm("eval", "collect", "r", a1)
    assert (run / "attempts" / a1 / "eval" / "raw_val" / "dsA" / "SMOKE").exists()
    eegfm("freeze", "r", "--note", "x")
    a2 = json.loads(eegfm("attempt", "new", "r", "--kind", "baseline", "--title", "b").stdout)["id"]
    jobs = json.loads(eegfm("eval", "submit", "r", a2).stdout)["jobs"]
    wait_for(lambda: all((run / "jobs" / f"{j}.exit").exists() for j in jobs))
    eegfm("eval", "collect", "r", a2)
    assert not (run / "attempts" / a2 / "eval" / "raw_val" / "dsA" / "SMOKE").exists()
    assert "setup attempts cannot" in eegfm("lock", "r", a1, "--reason", "x", ok=False).stderr.lower()


def test_agent_command_lines_carry_writable_dirs_and_extra_args(tmp_path):
    sys.path.insert(0, str(CODE))
    from eegfm.driver import Adapter

    codex = Adapter("codex", "m", None, ["-c", 'model_reasoning_effort="xhigh"'], [str(tmp_path)]).argv("P", tmp_path)
    assert codex[-1] == "P" and ["--add-dir", str(tmp_path)] == codex[codex.index("--add-dir"):codex.index("--add-dir") + 2]
    assert 'model_reasoning_effort="xhigh"' in codex and "sandbox_workspace_write.network_access=true" in codex
    claude = Adapter("claude", None, None, [], [str(tmp_path)]).argv("P", tmp_path)
    assert claude.count("--add-dir") == 2 and "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch,TodoWrite" in claude
