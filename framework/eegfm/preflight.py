"""`eegfm preflight`: check everything a run needs before any GPU or model spend.

Default checks are local or read-only: CLI and login, proxy reachability,
writable directories, task files and registry paths, and (for TiONE tasks)
tikit, the trusted helper, notebook STS and one read-only task lookup.
`--live` additionally runs one tiny agent session in a throwaway run, to prove
the agent can run bin/eegfm, write the run and scratch directories, and reach
the network from inside its sandbox.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import yaml

from .common import CODE, ROOT, load_task, task_dir

PROXY = "http://127.0.0.1:17897"


def check(name, ok, detail=""):
    return {"check": name, "ok": bool(ok), "detail": str(detail)[:400]}


def run(argv, timeout=30, env=None):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        return done.returncode, (done.stdout + done.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"{type(exc).__name__}: {exc}"


def agent_checks(agent):
    out = []
    binary = shutil.which(agent)
    out.append(check(f"{agent} CLI on PATH", binary, binary or "not found"))
    if not binary:
        return out
    code, text = run([agent, "--version"])
    out.append(check(f"{agent} --version", code == 0, text.splitlines()[0] if text else ""))
    if agent == "codex":
        code, text = run(["codex", "login", "status"])
        out.append(check("codex login status", code == 0 and "logged in" in text.lower(), text.splitlines()[-1] if text else ""))
    return out


def network_checks():
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    out = [check("HTTPS_PROXY set", proxy, proxy or f"export HTTP_PROXY={PROXY} HTTPS_PROXY={PROXY}")]
    code, text = run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "15",
                      *(["-x", proxy] if proxy else []), "https://chatgpt.com/"], timeout=25)
    out.append(check("internet via proxy (chatgpt.com reachable)", code == 0 and text[-3:].isdigit(), f"http {text[-3:]}"))
    return out


def writable_checks(dirs):
    out = []
    for d in dirs:
        path = Path(d)
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / f".eegfm-preflight-{os.getpid()}"
            probe.write_text("ok")
            probe.unlink()
            out.append(check(f"writable {d}", True))
        except OSError as exc:
            out.append(check(f"writable {d}", False, exc))
    return out


def task_checks(task_id):
    out = []
    try:
        task = load_task(task_id)
    except SystemExit as exc:
        return [check(f"task {task_id} loads", False, exc)]
    out.append(check(f"task {task_id} loads", True, task["title"]))
    source = Path(task["source"]["root"])
    source = source if source.is_absolute() else task_dir(task_id) / source
    out.append(check("task source exists", source.is_dir(), source))
    out.append(check("TASK.md present", (task_dir(task_id) / "TASK.md").exists()))
    datasets = yaml.safe_load((ROOT / "registry" / "datasets.yaml").read_text())
    models = yaml.safe_load((ROOT / "registry" / "models.yaml").read_text())["models"]
    for name in task.get("datasets", []):
        spec = datasets["datasets"].get(name)
        if spec:
            path = Path(datasets["root"]) / spec["release"]
            out.append(check(f"dataset {name}", path.is_dir(), path))
    model = models.get(task.get("model"), {})
    if model.get("weights"):
        out.append(check(f"model {task['model']} weights", Path(model["weights"]).exists(), model["weights"]))
    brief = task_dir(task_id) / "RESEARCH_BRIEF.md"
    out.append(check("approved task brief", True, "present: runs start in working" if brief.exists()
                     else "absent: runs start with the brief stage and stop for human review"))
    if task["compute"]["backend"] == "tione":
        out += tione_checks(task["compute"])
    return out


def tione_checks(compute):
    from .jobs import RECORD_JOB, TIONE_HELPER, TioneBackend

    out = [check("TiONE helper present", TIONE_HELPER.exists(), TIONE_HELPER),
           check("record_job.py present", RECORD_JOB.exists(), RECORD_JOB),
           check("notebook STS env (QCLOUD_CONTAINER_INSTANCE_CREDENTIALS_URL)",
                 os.environ.get("QCLOUD_CONTAINER_INSTANCE_CREDENTIALS_URL"), "required by the helper")]
    try:
        import tikit  # noqa: F401
        out.append(check("tikit importable", True))
    except ImportError as exc:
        out.append(check("tikit importable", False, exc))
        return out
    try:
        helper, client = TioneBackend(compute).client()
        found = helper._find_exact_task(client, "eegfm-preflight-nonexistent-task")
        out.append(check("TiONE read-only lookup", found is None, "client created; no task submitted"))
    except Exception as exc:  # report, never raise: this is a diagnostic
        out.append(check("TiONE read-only lookup", False, f"{type(exc).__name__}: {exc}"))
    return out


def live_check(agent, writable, model=None, extra=()):
    """One tiny real session in a throwaway run; costs one short agent call."""
    from .driver import Adapter

    run_id = f"preflight-{agent}-{int(time.time())}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({"run_id": run_id, "task_id": None}))
    scratch = Path(writable[0]) / run_id if writable else run_dir
    prompt = (f"Preflight check only; do not do research. Run these shell commands exactly and report their output:\n"
              f"1. {CODE / 'bin' / 'eegfm'} --help | head -3\n"
              f"2. echo ok > '{run_dir / 'agent_wrote_run.txt'}'\n"
              f"3. mkdir -p '{scratch}' && echo ok > '{scratch / 'agent_wrote_scratch.txt'}'\n"
              f"4. curl -sS -I -o /dev/null -w '%{{http_code}}' --max-time 15 https://pypi.org/ ; echo\n"
              f"Then end your turn.")
    adapter = Adapter(agent, model, None, list(extra), writable)
    argv = adapter.argv(prompt, run_dir)
    started = time.time()
    code, text = run(argv, timeout=900, env={**os.environ, "PATH": f"{CODE / 'bin'}:{os.environ.get('PATH', '')}"})
    ok, error, summary = adapter.classify(code, text, "", False)
    out = [check(f"live {agent} session completed", ok, f"{round(time.time() - started)} s; {error or ''} "
                 f"{summary.get('total_cost_usd', '')}"),
           check("agent can write the run directory", (run_dir / "agent_wrote_run.txt").exists()),
           check("agent can write the scratch directory", (scratch / "agent_wrote_scratch.txt").exists(), scratch)]
    (run_dir / "preflight_session.log").write_text(text)
    return out, run_dir


def preflight(agent, task_id=None, live=False, model=None, extra=(), writable=None):
    from .driver import WRITABLE_DEFAULTS

    writable = writable if writable is not None else WRITABLE_DEFAULTS
    results = agent_checks(agent) + network_checks() + writable_checks(writable)
    if task_id:
        results += task_checks(task_id)
    log = None
    if live:
        more, log = live_check(agent, writable, model, extra)
        results += more
    return {"ok": all(r["ok"] for r in results), "checks": results, "live_log": str(log) if log else None}
