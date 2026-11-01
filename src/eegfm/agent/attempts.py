"""Runs and attempts: the episodic memory of a research run (a discovery tree).

runs/<run>/
  run.json            task id, created_at, task.yaml hash
  STATE.json          declared lifecycle state (see state.py)
  workspace/          git repo: the editable copy of the task's code base
  attempts/<A#>/      proposal.md, attempt.json, code/ snapshot, eval/score.json (val only)
  attempts/INDEX.md   generated table of every attempt (facts only)
  sealed/             test outputs; not read before finalize (see evaluation.py)
"""
import json
from pathlib import Path
import shutil
import subprocess

from eegfm.common import CODE
from eegfm.common import ROOT
from eegfm.common import append_jsonl
from eegfm.common import load_task
from eegfm.common import now
from eegfm.common import read_json
from eegfm.common import sha256
from eegfm.common import source_files
from eegfm.common import task_dir
from eegfm.common import write_json

KINDS = {"setup", "baseline", "iteration"}
VERDICTS = {"keep", "discard"}


def git(workspace, *args):
    return subprocess.run(["git", "-C", str(workspace), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def init_run(task_id, run_id):
    task = load_task(task_id)
    run = ROOT / "runs" / run_id
    if (run / "run.json").exists():
        raise SystemExit(f"Run {run_id} already exists")
    source = Path(task["source"]["root"])
    if not source.is_absolute():
        source = task_dir(task_id) / source
    files = source_files(source, task["source"].get("include"), task["source"].get("exclude"))
    if not files:
        raise SystemExit(f"No source files found under {source}")
    workspace = run / "workspace"
    for rel in files:
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, target)
    git(workspace, "init", "-q")
    git(workspace, "add", "-A")
    git(workspace, "-c", "user.name=eegfm", "-c", "user.email=eegfm@localhost", "commit", "-q", "-m",
        f"Initial copy of {task_id} source")
    write_json(run / "run.json", {"run_id": run_id, "task_id": task_id, "created_at": now(),
                                  "task_yaml_sha256": sha256(task["_path"]), "source_root": str(source),
                                  "source_files": files})
    for name in ("attempts", "sealed", "jobs", "sessions"):
        (run / name).mkdir(parents=True, exist_ok=True)
    (run / "sealed" / "README.md").write_text(
        "Sealed test outputs. Agents must not read this directory before finalize; "
        "use `eegfm report final`.\n")
    first = "brief" if not (task_dir(task_id) / "RESEARCH_BRIEF.md").exists() else "working"
    from eegfm.agent import state
    state.set_state(run, first, note="run initialised", actor="eegfm")
    write_index(run)
    return run


def attempts(run):
    out = []
    for path in sorted((run / "attempts").glob("A*/attempt.json"), key=lambda p: int(p.parent.name[1:])):
        out.append(read_json(path))
    return out


def get_attempt(run, attempt_id):
    record = read_json(run / "attempts" / attempt_id / "attempt.json")
    if not record:
        raise SystemExit(f"Unknown attempt {attempt_id}")
    return record


def save_attempt(run, record):
    write_json(run / "attempts" / record["id"] / "attempt.json", record)
    write_index(run)


def new_attempt(run, kind, title, parent=None, hypothesis=None):
    # Serialize allocation and budget checks across concurrent CLI processes.
    # This is an operational guard, not isolation from a malicious same-user edit.
    with (run / 'attempts' / '.allocation.lock').open('a+b') as lock:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _new_attempt_locked(run, kind, title, parent, hypothesis)


def _new_attempt_locked(run, kind, title, parent=None, hypothesis=None):
    if kind not in KINDS:
        raise SystemExit(f"kind must be one of {sorted(KINDS)}")
    meta=read_json(run / 'run.json'); task=load_task(meta['task_id'])
    if sha256(task['_path']) != meta['task_yaml_sha256']:
        raise SystemExit('task.yaml changed after the run started; start a new run for a new contract')
    existing = attempts(run)
    limit=task['search'].get('max_attempts')
    if limit is not None and (type(limit) is not int or limit < 0):
        raise SystemExit('search.max_attempts must be a nonnegative integer')
    # Existing reve_isa contract defines this as iterations after the baseline.
    # Proposed and failed iterations consume allocation; setup/baseline do not.
    if kind == 'iteration' and limit is not None and sum(a['kind']=='iteration' for a in existing) >= limit:
        raise SystemExit(f'Iteration budget exhausted: {limit} allocated; finalize or start a separately authorized run')
    if parent and parent not in {a["id"] for a in existing}:
        raise SystemExit(f"Unknown parent attempt {parent}")
    freeze = read_json(run / "freeze.json")
    if kind in {"baseline", "iteration"} and not freeze:
        raise SystemExit("Freeze the evaluator first (`eegfm freeze`); only setup attempts precede it")
    attempt_id = f"A{len(existing) + 1}"
    directory = run / "attempts" / attempt_id
    directory.mkdir(parents=True)
    template = (Path(__file__).resolve().parents[1] / "templates" / "proposal.md").read_text(encoding="utf-8")
    (directory / "proposal.md").write_text(
        template.replace("{{id}}", attempt_id).replace("{{title}}", title)
        .replace("{{parent}}", parent or "-").replace("{{kind}}", kind)
        .replace("{{hypothesis}}", hypothesis or "(fill in)"), encoding="utf-8")
    record = {"id": attempt_id, "kind": kind, "title": title, "parent": parent, "status": "proposed",
              "created_at": now(), "jobs": [], "verdict": None, "reason": None, "score": None,
              "commit": None, "gpu_hours": 0.0}
    save_attempt(run, record)
    append_jsonl(run / "events.jsonl", {"event": "attempt_new", "attempt": attempt_id, "kind": kind,
                                         "parent": parent})
    return record


def set_verdict(run, attempt_id, verdict, reason):
    if verdict not in VERDICTS:
        raise SystemExit("verdict must be keep or discard")
    record = get_attempt(run, attempt_id)
    if verdict == "keep" and record["status"] != "evaluated":
        raise SystemExit("Only an evaluated attempt can be kept")
    record.update(verdict=verdict, reason=reason, decided_at=now())
    save_attempt(run, record)
    append_jsonl(run / "events.jsonl", {"event": "verdict", "attempt": attempt_id, "verdict": verdict})
    return record


def baseline_metric(run):
    for record in attempts(run):
        if record["kind"] == "baseline" and record["status"] == "evaluated":
            return (record.get("score") or {}).get("primary")
    return None


def write_index(run):
    meta = read_json(run / "run.json", {})
    task = load_task(meta["task_id"]) if meta else None
    metric = task["evaluation"]["metric"] if task else "metric"
    base = baseline_metric(run)
    lines = [f"# Attempts of run `{run.name}`", "",
             f"Primary validation metric: `{metric}`"
             + (f" ({task['evaluation']['direction']})" if task else "")
             + (f"; baseline = {base:.4g}" if isinstance(base, (int, float)) else ""), "",
             "Generated from attempt.json and eval/score.json (facts only; read proposal.md for intent).", "",
             "| id | kind | parent | title | status | val primary | vs baseline | verdict | jobs | GPU-h |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for a in attempts(run):
        primary = (a.get("score") or {}).get("primary")
        delta = "" if not isinstance(primary, (int, float)) or not isinstance(base, (int, float)) else f"{primary - base:+.4g}"
        value = "" if not isinstance(primary, (int, float)) else f"{primary:.4g}"
        title = a["title"].replace("|", "/")
        lines.append(f"| {a['id']} | {a['kind']} | {a.get('parent') or ''} | {title} | {a['status']} | {value} "
                     f"| {delta} | {a.get('verdict') or ''} | {len(a.get('jobs', []))} | {a.get('gpu_hours', 0):.2f} |")
    (run / "attempts").mkdir(parents=True, exist_ok=True)
    (run / "attempts" / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def summary(run):
    rows = attempts(run)
    return json.dumps({"attempts": len(rows), "evaluated": sum(a["status"] == "evaluated" for a in rows),
                       "iterations_evaluated": sum(a["kind"] == "iteration" and a["status"] == "evaluated"
                                                    for a in rows)})
