"""Scripted offline agent for the synthetic demo: one protocol step per session.

It uses only eegfm and files, exactly like a real agent, so the driver,
tools, freeze, sealing and memory are exercised end to end without an LLM.
Behaviour switches (environment): FAKE_AGENT_MODE=idle (do nothing),
overloaded (exit like an overloaded backend once), crash (fail with an ordinary error).
"""
import json
import os
from pathlib import Path
import subprocess
import sys

CODE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("EEGFM_ROOT") or CODE)
BIN = [sys.executable, "-m", "eegfm"]


def eegfm(*args):
    done = subprocess.run([*BIN, *args], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"eegfm {' '.join(args)} failed: {done.stdout}{done.stderr}")
    return done.stdout


def main(run_id):
    run = ROOT / "runs" / run_id
    mode = os.environ.get("FAKE_AGENT_MODE", "")
    marker = run / "fake_overloaded_once"
    if mode == "idle":
        return 0
    if mode == "crash":
        print("Traceback (most recent call last):\nKeyError: 'attempts'", file=sys.stderr)
        return 1
    if mode == "overloaded" and not marker.exists():
        marker.write_text("x")
        print("API Error: 529 overloaded_error", file=sys.stderr)
        return 1
    state = json.loads((run / "STATE.json").read_text())
    notes = run / "NOTES.md"
    if state["status"] == "brief":
        (run / "RESEARCH_BRIEF.md").write_text("# brief\n\n## 4. 候选假设\n### H1 lower lr\n")
        eegfm("brief", "submit", run_id)
        return 0
    attempts = [json.loads(p.read_text()) for p in sorted((run / "attempts").glob("A*/attempt.json"),
                                                           key=lambda p: int(p.parent.name[1:]))]
    for a in attempts:  # collect anything that finished
        if a["status"] == "submitted" or (a.get("test_sealed") and not (run / "final_test.json").exists()):
            eegfm("eval", "collect", run_id, a["id"])
    attempts = [json.loads(p.read_text()) for p in sorted((run / "attempts").glob("A*/attempt.json"),
                                                           key=lambda p: int(p.parent.name[1:]))]
    workspace = run / "workspace"
    if not (run / "freeze.json").exists():
        eegfm("freeze", run_id, "--note", "synthetic evaluator inspected")
        notes.open("a").write("## fake\n- froze evaluator\n")
        return 0
    baseline = [a for a in attempts if a["kind"] == "baseline"]
    iterations = [a for a in attempts if a["kind"] == "iteration"]
    locks = (run / "locks.jsonl").read_text().splitlines() if (run / "locks.jsonl").exists() else []

    def submit(record):
        out = json.loads(eegfm("eval", "submit", run_id, record["id"], "--phase", "val"))
        eegfm("state", "set", run_id, "--status", "waiting_job", *sum((["--job", j] for j in out["jobs"]), []))

    if not baseline:
        submit(json.loads(eegfm("attempt", "new", run_id, "--kind", "baseline", "--title", "initial config")))
        return 0
    evaluated = [a for a in iterations if a["status"] == "evaluated"]
    if len(iterations) < 2:
        best = max([a for a in baseline + evaluated if a["status"] == "evaluated"],
                   key=lambda a: a["score"]["primary"])
        eegfm("workspace", "checkout", run_id, best["id"])
        cfg = (workspace / "method.yaml").read_text().splitlines()
        lr = float(next(l for l in cfg if l.startswith("posttrain_lr_log10")).split(":")[1].split("#")[0])
        cfg = [f"posttrain_lr_log10: {lr + 0.2:.2f}" if l.startswith("posttrain_lr_log10") else l for l in cfg]
        (workspace / "method.yaml").write_text("\n".join(cfg) + "\n")
        submit(json.loads(eegfm("attempt", "new", run_id, "--kind", "iteration", "--parent", best["id"],
                                "--title", f"lr {lr + 0.2:.2f}")))
        return 0
    for a in iterations:
        if a["status"] == "evaluated" and not a.get("verdict"):
            keep = a["score"]["primary"] > baseline[0]["score"]["primary"]
            eegfm("attempt", "verdict", run_id, a["id"], "--keep" if keep else "--discard", "--reason", "val vs baseline")
    if not locks:
        best = max(evaluated, key=lambda a: a["score"]["primary"])
        jobs = []
        for candidate in (baseline[0], best):
            eegfm("lock", run_id, candidate["id"], "--reason", "final selection on validation")
            jobs += json.loads(eegfm("eval", "submit", run_id, candidate["id"], "--phase", "test"))["jobs"]
        eegfm("state", "set", run_id, "--status", "waiting_job", *sum((["--job", j] for j in jobs), []))
        return 0
    report = json.loads(eegfm("report", "final", run_id))
    (run / "FINAL_REPORT.md").write_text("# final\n\n" + json.dumps(report, indent=2))
    eegfm("memory", "add", "--task", "synthetic_demo", "--run", run_id, "--kind", "observation",
          "--applies", "method:lr_sweep", "--evidence", f"run:{run_id}/attempt:{best_id(attempts)}",
          "--claim", "Raising the synthetic post-training lr from the initial value changed validation accuracy.")
    eegfm("state", "set", run_id, "--status", "done", "--note", "synthetic loop complete")
    return 0


def best_id(attempts):
    good = [a for a in attempts if a["status"] == "evaluated"]
    return max(good, key=lambda a: a["score"]["primary"])["id"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
