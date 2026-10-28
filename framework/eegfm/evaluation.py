"""Evaluation with a frozen evaluator and sealed test results.

- `freeze` hashes the evaluator files (task.yaml source.frozen) after setup.
  Every later evaluation verifies its code snapshot against those hashes and
  that only source.editable files changed since the freeze commit.
- An evaluation may be sharded (evaluation.shards, e.g. one job per target
  dataset). Each shard writes {out}/metrics.json with the primary metric;
  the attempt's primary score is the mean over shards.
- Validation results go to attempts/<A>/eval/score.json and drive every
  decision. Test results go to sealed/<A>/ only, for locked candidates, at
  most evaluation.test.max_candidates of them, once each.
- Every evaluation request and unsealing is appended to audit.jsonl.

Agents run as the same OS user, so the seal is enforced by these tools, the
audit log and PROGRAM.md rather than by file permissions. Tasks that need a
hard guarantee keep test labels only inside the compute job (PROGRAM.md 7).
"""
from pathlib import Path
import shlex
import shutil
import statistics

from . import attempts as A
from . import jobs as J
from .common import append_jsonl, load_task, matches, now, read_json, read_jsonl, sha256, write_json


def task_of(run):
    return load_task(read_json(run / "run.json")["task_id"])


def check_task_unchanged(run, task):
    if sha256(task["_path"]) != read_json(run / "run.json")["task_yaml_sha256"]:
        raise SystemExit("task.yaml changed after the run started; start a new run for a new contract")


def commit_all(workspace, message):
    A.git(workspace, "add", "-A")
    if A.git(workspace, "status", "--porcelain"):
        A.git(workspace, "-c", "user.name=eegfm", "-c", "user.email=eegfm@localhost", "commit", "-q", "-m", message)
    return A.git(workspace, "rev-parse", "HEAD")


def freeze(run, note):
    task = task_of(run)
    check_task_unchanged(run, task)
    if read_json(run / "freeze.json"):
        raise SystemExit("Evaluator already frozen; a new evaluator requires a new run")
    workspace = run / "workspace"
    patterns = task["source"].get("frozen", [])
    files = {}
    for path in sorted(workspace.rglob("*")):
        rel = str(path.relative_to(workspace))
        if path.is_file() and ".git" not in path.relative_to(workspace).parts and matches(rel, patterns):
            files[rel] = sha256(path)
    if not files:
        raise SystemExit(f"No workspace file matches source.frozen {patterns}")
    commit = commit_all(workspace, "freeze: evaluator and setup")
    record = {"frozen_at": now(), "note": note, "files": files, "commit": commit}
    write_json(run / "freeze.json", record)
    append_jsonl(run / "events.jsonl", {"event": "freeze", "files": sorted(files), "commit": commit})
    append_jsonl(run / "audit.jsonl", {"event": "freeze", "files": files, "commit": commit})
    return record


def snapshot(run, attempt, task):
    workspace = run / "workspace"
    commit = commit_all(workspace, f"{attempt['id']}: {attempt['title']}")
    frozen = read_json(run / "freeze.json")
    if frozen:
        changed = [rel for rel in A.git(workspace, "diff", "--name-only", frozen["commit"], "HEAD").splitlines() if rel]
        editable = task["source"].get("editable", [])
        outside = [rel for rel in changed if not matches(rel, editable)]
        if outside:
            raise SystemExit(f"Changed files outside source.editable since the freeze: {outside}. "
                             "Restore them (git -C workspace checkout <freeze commit> -- <file>).")
    code = run / "attempts" / attempt["id"] / "code"
    if code.exists():
        shutil.rmtree(code)
    for rel in A.git(workspace, "ls-files").splitlines():
        (code / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / rel, code / rel)
    if frozen:
        for rel, digest in frozen["files"].items():
            if not (code / rel).exists() or sha256(code / rel) != digest:
                raise SystemExit(f"Frozen evaluator file {rel} differs from freeze.json; restore it")
    return commit, code


def shards(task):
    return task["evaluation"].get("shards") or [None]


def submit(run, attempt_id, phase, gpus=None):
    task = task_of(run)
    check_task_unchanged(run, task)
    attempt = A.get_attempt(run, attempt_id)
    ev = task["evaluation"]
    if phase == "val":
        if attempt["status"] in {"submitted", "evaluated"}:
            raise SystemExit(f"{attempt_id} already has a validation evaluation; create a new attempt")
        command, base = ev["val_command"], run / "attempts" / attempt_id / "eval" / "raw_val"
        # Setup attempts may run a short smoke version of the evaluator; their
        # scores never count (only baseline/iteration attempts are compared).
        if attempt["kind"] == "setup" and ev.get("smoke_command"):
            command = ev["smoke_command"]
        commit, code = snapshot(run, attempt, task)
        attempt["commit"] = commit
    elif phase == "test":
        if not any(x["attempt"] == attempt_id for x in read_jsonl(run / "locks.jsonl")):
            raise SystemExit(f"Test evaluation requires `eegfm lock {run.name} {attempt_id}` first")
        done = {x["attempt"] for x in read_jsonl(run / "audit.jsonl") if x.get("phase") == "test"}
        limit = ev.get("test", {}).get("max_candidates", 2)
        if attempt_id in done:
            raise SystemExit(f"{attempt_id} already has a test evaluation; test runs once per candidate")
        if len(done) >= limit:
            raise SystemExit(f"Test budget used: {len(done)} of {limit} candidates")
        if "test_command" not in ev:
            raise SystemExit("task.yaml has no evaluation.test_command")
        command, base = ev["test_command"], run / "sealed" / attempt_id
        commit, code = attempt["commit"], run / "attempts" / attempt_id / "code"
    else:
        raise SystemExit("phase must be val or test")
    records = []
    for shard in shards(task):
        out = base / shard if shard else base
        out.mkdir(parents=True, exist_ok=True)
        val_out = run / "attempts" / attempt_id / "eval" / "raw_val"
        values = {"out": out, "code": code, "attempt": attempt_id, "phase": phase, "run": run,
                  "shard": shard or "", "val_out": val_out / shard if shard else val_out}
        # Paths contain spaces ("auto research"): every placeholder is shell-quoted.
        rendered = command.format(**{k: shlex.quote(str(v)) for k, v in values.items()})
        record = J.submit(run, task["compute"], attempt_id, phase + (f"-{shard}" if shard else ""), code,
                          rendered, gpus=gpus)
        records.append(record)
        attempt.setdefault("jobs", []).append(record["job_id"])
    if phase == "val":
        attempt["status"] = "submitted"
    A.save_attempt(run, attempt)
    append_jsonl(run / "audit.jsonl", {"event": "evaluation_submitted", "attempt": attempt_id, "phase": phase,
                                        "jobs": [r["job_id"] for r in records], "commit": commit})
    return {"attempt": attempt_id, "phase": phase, "jobs": [r["job_id"] for r in records]}


def _shard_results(run, task, attempt, phase, base):
    """[(shard, job_record, metrics or None)] for the latest job of each shard."""
    out = []
    for shard in shards(task):
        tag = phase + (f"-{shard}" if shard else "")
        ids = [j for j in attempt.get("jobs", []) if (read_json(J.ledger(run, j)) or {}).get("phase") == tag]
        if not ids:
            continue
        record = J.refresh(run, task["compute"], ids[-1])
        path = (base / shard if shard else base) / "metrics.json"
        out.append((shard, record, read_json(path)))
    return out


def collect(run, attempt_id):
    task = task_of(run)
    attempt = A.get_attempt(run, attempt_id)
    metric = task["evaluation"]["metric"]
    message = {"attempt": attempt_id}
    for job in attempt.get("jobs", []):
        J.refresh(run, task["compute"], job)
    ledgers = [read_json(J.ledger(run, j)) for j in attempt.get("jobs", [])]
    pending = [r["job_id"] for r in ledgers if r and r["status"] not in J.TERMINAL]
    if pending:
        return {**message, "pending": pending}
    attempt["gpu_hours"] = round(sum(r.get("gpu_hours", 0) for r in ledgers if r), 3)
    if attempt["status"] == "submitted":
        results = _shard_results(run, task, attempt, "val", run / "attempts" / attempt_id / "eval" / "raw_val")
        errors, per_shard = [], {}
        for shard, record, metrics in results:
            name = shard or "all"
            if record["status"] != "succeeded" or not metrics or not isinstance(metrics.get(metric), (int, float)):
                tail = Path(record["log"]).read_text(errors="replace")[-2500:] if Path(record["log"]).exists() else ""
                errors.append(f"[{name}] job {record['job_id']} status={record['status']}; "
                              f"{'metric missing' if metrics else 'metrics.json missing'}\n{tail}")
            elif any("test" in str(key).lower() for key in metrics):
                errors.append(f"[{name}] validation output contains test keys; the evaluator must not emit test")
            else:
                per_shard[name] = metrics
        if errors or not per_shard:
            (run / "attempts" / attempt_id / "eval").mkdir(parents=True, exist_ok=True)
            (run / "attempts" / attempt_id / "eval" / "error.txt").write_text("\n\n".join(errors) or "no results")
            attempt["status"] = "failed"
            message.update(status="failed", errors=len(errors))
        else:
            primary = statistics.fmean(m[metric] for m in per_shard.values())
            write_json(run / "attempts" / attempt_id / "eval" / "score.json",
                       {"primary": primary, "metric": metric, "aggregate": "mean over shards",
                        "shards": {k: v[metric] for k, v in per_shard.items()}, "metrics": per_shard, "phase": "val"})
            attempt.update(status="evaluated", score={"primary": primary,
                                                      "shards": {k: v[metric] for k, v in per_shard.items()}})
            message.update(status="evaluated", primary=primary)
    if any(r and r["phase"].startswith("test") for r in ledgers):
        attempt["test_sealed"] = True
        message["test"] = "sealed: results are not shown before `eegfm report final`"
    A.save_attempt(run, attempt)
    return message


def lock(run, attempt_id, reason):
    attempt = A.get_attempt(run, attempt_id)
    if attempt["status"] != "evaluated":
        raise SystemExit("Only an attempt with a validation score can be locked")
    if attempt["kind"] not in {"baseline", "iteration"}:
        raise SystemExit("Setup attempts cannot be test candidates")
    if any(x["attempt"] == attempt_id for x in read_jsonl(run / "locks.jsonl")):
        raise SystemExit(f"{attempt_id} is already locked")
    append_jsonl(run / "locks.jsonl", {"attempt": attempt_id, "reason": reason, "commit": attempt["commit"],
                                        "val_primary": attempt["score"]["primary"]})
    append_jsonl(run / "audit.jsonl", {"event": "lock", "attempt": attempt_id})
    return {"locked": attempt_id, "val_primary": attempt["score"]["primary"]}


def final_report(run):
    """Unseal only when every locked candidate's test jobs have finished."""
    task = task_of(run)
    metric = task["evaluation"]["metric"]
    locks = read_jsonl(run / "locks.jsonl")
    if not locks:
        raise SystemExit("No locked candidates")
    rows = []
    for item in locks:
        attempt = A.get_attempt(run, item["attempt"])
        results = _shard_results(run, task, attempt, "test", run / "sealed" / item["attempt"])
        if not results:
            raise SystemExit(f"{item['attempt']} has no test evaluation yet")
        unfinished = [r["job_id"] for _, r, _ in results if r["status"] not in J.TERMINAL]
        if unfinished:
            raise SystemExit(f"Test jobs still running: {unfinished}")
        shard_values = {(s or "all"): (m or {}).get(metric) for s, _, m in results}
        complete = all(isinstance(v, (int, float)) for v in shard_values.values())
        rows.append({"attempt": item["attempt"], "kind": attempt["kind"], "title": attempt["title"],
                     "val_primary": attempt["score"]["primary"],
                     "test_primary": statistics.fmean(shard_values.values()) if complete else None,
                     "test_shards": shard_values,
                     "test_metrics": {(s or "all"): m for s, _, m in results}})
    write_json(run / "final_test.json", {"unsealed_at": now(), "metric": metric, "candidates": rows})
    append_jsonl(run / "audit.jsonl", {"event": "unsealed", "candidates": [r["attempt"] for r in rows]})
    return {"candidates": [{k: r[k] for k in ("attempt", "kind", "title", "val_primary", "test_primary",
                                              "test_shards")} for r in rows],
            "written": str(run / "final_test.json")}
