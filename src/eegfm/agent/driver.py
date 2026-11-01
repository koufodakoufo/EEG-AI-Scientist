"""Resumer: keeps one research run moving across agent sessions.

It never does research itself. Each loop it reads STATE.json and either
  - stops (done / blocked),
  - waits for the human brief review (awaiting_review),
  - polls the run's jobs without any agent running (waiting_job), or
  - launches one agent session with a fixed prompt (brief / working).
Agent errors (overload, network) back off; sessions that change nothing are
counted and, after `stall_limit`, the run is marked blocked with a reason.

Agents are interchangeable: every adapter gets the same prompt and the same
files; only the command line differs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

from eegfm.agent import jobs as J
from eegfm.agent import state as S
from eegfm.common import CODE, SOURCE_ROOT
from eegfm.common import ROOT
from eegfm.common import append_jsonl
from eegfm.common import now
from eegfm.common import read_json
from eegfm.common import read_jsonl
from eegfm.common import run_dir
from eegfm.common import write_json
from eegfm.agent.evaluation import task_of

PROMPT = """You are the research agent for run `{run}` of EEG RSI Scientist at {root}.
Read the current instructions, task definition and available run context:
{context}

Current state: {status}. Note from the last transition: {note}

Follow the task's fixed scope, editable files, evaluation boundary and budget. Consult only knowledge,
memory and skills explicitly permitted by its protocol; a fresh run may have none. Historical notes
and private evaluation answers are not automatically part of this researcher's context.

Work autonomously within the authorized scope. Preserve failures and negative findings, decide on
validation, and freeze the selected candidate before the trusted final test. Record uncertainty in
this run's notes. Use `eegfm --help` for available commands. At a natural stopping point:
- evaluation jobs submitted: eegfm state set {run} --status waiting_job --job <id> ...
- research brief written: eegfm brief submit {run}
- research finished: complete the task's required report, then eegfm state set {run} --status done
Do not wait inside the session for long jobs; the resumer polls them and starts a fresh session.
If progress requires changing the task or resource boundary, or a human must act, record the exact
reason and set --status blocked. Lifecycle completion alone is not evidence of scientific success."""

# Matched only against error text (stderr and the agent's own error fields), never
# the whole transcript, so ordinary output cannot be mistaken for an outage.
TRANSIENT = ("overloaded", "rate limit", "rate_limit", " 429", " 529", " 503", "temporarily unavailable",
             "timed out", "connection reset", "connection refused", "connection error", "network error",
             "econnreset", "stream disconnected", "serveroverloaded", "internal server error")
# Additional writable locations are explicit per-run grants.
WRITABLE_DEFAULTS: list[str] = []
FATAL = ("unauthorized", " 401", "not logged in", "please log in", "invalid api key", "authentication failed")


class Adapter:
    def __init__(self, name, model=None, script=None, extra=None, writable=()):
        self.name, self.model, self.extra = name, model, list(extra or [])
        # Directories outside the repository the agent must write to (scratch,
        # caches, the TiONE job index). Codex's sandbox blocks them otherwise.
        self.writable = [str(Path(d).resolve()) for d in writable]
        # Sessions start in the data root; resolve the script against the caller's directory.
        self.script = str(Path(script).resolve()) if script else None

    def argv(self, prompt, run):
        if self.name == "claude":
            argv = ["claude", "-p", prompt, "--output-format", "json", "--permission-mode", "acceptEdits",
                    "--allowedTools", "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch,TodoWrite",
                    "--add-dir", str(run), *sum((["--add-dir", d] for d in self.writable), [])]
            return argv + (["--model", self.model] if self.model else []) + self.extra
        if self.name == "codex":
            argv = ["codex", "exec", "--json", "-C", str(ROOT), "-s", "workspace-write",
                    "-c", "sandbox_workspace_write.network_access=true", "-c", 'web_search="live"',
                    "-c", "shell_environment_policy.inherit=all",
                    *sum((["--add-dir", d] for d in self.writable), [])]
            return argv + (["-m", self.model] if self.model else []) + self.extra + [prompt]
        if self.name == "script":  # offline tests
            return [sys.executable, self.script, run.name]
        raise SystemExit(f"Unknown agent {self.name}")

    def classify(self, code, stdout, stderr, timed_out):
        """Return (ok, error_kind, summary); error_kind is None, transient, fatal or failed.

        transient: outage-like errors, retried with backoff and not counted as stalls.
        fatal: authentication; only a human can fix it.
        failed: any other unsuccessful session; counted towards the stall limit.
        """
        errors, summary = [stderr[-4000:]], {}
        if timed_out:
            return False, "transient", {"reason": "session timeout"}
        if self.name == "claude":
            try:
                result = json.loads(stdout.strip().splitlines()[-1])
                summary = {k: result.get(k) for k in ("subtype", "is_error", "session_id", "num_turns",
                                                       "total_cost_usd", "duration_ms")}
                summary["result_tail"] = str(result.get("result", ""))[-600:]
                if not result.get("is_error") and code == 0:
                    return True, None, summary
                errors.append(str(result.get("result", "")))
            except (ValueError, IndexError):
                errors.append(stdout[-2000:])
        elif self.name == "codex":
            events, malformed = [], 0
            for line in stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("Codex event must be an object")
                    events.append(event)
                except ValueError:
                    malformed += 1
            failed = [event for event in events if event.get("type") in {"turn.failed", "error"}]
            summary["failed_events"] = len(failed)
            summary["malformed_events"] = malformed
            summary["completed_turns"] = sum(event.get("type") == "turn.completed" for event in events)
            summary["last_event"] = stdout.strip().splitlines()[-1][-600:] if stdout.strip() else ""
            if code == 0 and not failed and not malformed and summary["completed_turns"]:
                return True, None, summary
            errors.extend(json.dumps(event) for event in failed[-5:])
            if malformed or not summary["completed_turns"]:
                errors.append("Malformed or incomplete Codex event stream")
        elif code == 0:
            return True, None, summary
        text = " " + "\n".join(errors).lower()
        if any(word in text for word in FATAL):
            return False, "fatal", {**summary, "reason": "authentication"}
        if any(word in text for word in TRANSIENT):
            return False, "transient", summary
        return False, "failed", {**summary, "reason": f"exit {code}", "error_tail": text[-600:]}


def fingerprint(run):
    digest = hashlib.sha256()
    for name in ("STATE.json", "NOTES.md", "attempts/INDEX.md"):
        path = run / name
        digest.update(path.read_bytes() if path.exists() else b"-")
    digest.update(str(len(read_jsonl(run / "events.jsonl"))).encode())
    try:
        status = subprocess.run(["git", "-C", str(run / "workspace"), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        head = subprocess.run(["git", "-C", str(run / "workspace"), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout
        digest.update((status + head).encode())
    except OSError:
        pass
    return digest.hexdigest()


def attention(run, reason):
    (run / "ATTENTION.md").write_text(f"# Attention: run {run.name}\n\n{now()}\n\n{reason}\n", encoding="utf-8")


class Driver:
    def __init__(self, run_id, adapter, poll=60.0, session_timeout=4 * 3600, max_sessions=100,
                 stall_limit=3, backoff=60.0, outage_max=6 * 3600, once=False,
                 run_path=None, task=None):
        self.run = Path(run_path) if run_path is not None else run_dir(run_id)
        self.task = task if task is not None else task_of(self.run)
        self.adapter = adapter
        self.poll, self.session_timeout, self.max_sessions = poll, session_timeout, max_sessions
        self.stall_limit, self.backoff, self.outage_max, self.once = stall_limit, backoff, outage_max, once
        self.stop = False

    def heartbeat(self, phase, **extra):
        write_json(self.run / "driver.json", {"pid": os.getpid(), "agent": self.adapter.name,
                                              "model": self.adapter.model, "phase": phase,
                                              "heartbeat": now(), **extra})

    def sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self.stop:
            time.sleep(min(2.0, max(0.0, end - time.time())))

    def prompt(self, state: dict[str, Any]) -> str:
        """Render current files without treating historical or absent memory as input."""
        context = [CODE / name for name in ("README.md", "AGENTS.md", "PROGRAM.md")]
        context.extend((ROOT / "tasks" / self.task["task_id"] / "TASK.md", self.run / "STATE.json"))
        context.extend(path for path in (self.run / "NOTES.md", self.run / "attempts/INDEX.md") if path.is_file())
        return PROMPT.format(run=self.run.name, root=ROOT, task=self.task["task_id"],
            context="\n".join(f"- {path}" for path in context),
            status=state.get("status"), note=state.get("note") or "-")

    def session(self, state):
        sessions = read_jsonl(self.run / "sessions.jsonl")
        prompt = self.prompt(state)
        argv = self.adapter.argv(prompt, self.run)
        number = len(sessions) + 1
        log = self.run / "sessions" / f"session_{number:03d}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        before, started = fingerprint(self.run), time.time()
        self.heartbeat("agent_running", session=number)
        env = {**os.environ, "EEGFM_RUN": self.run.name, "PATH": os.environ.get("PATH", ""),
               "PYTHONPATH": str(SOURCE_ROOT)}
        process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=self.session_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        log.write_text(f"$ {' '.join(argv[:3])} ...\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
                       encoding="utf-8")
        ok, error, summary = self.adapter.classify(process.returncode, stdout or "", stderr or "", timed_out)
        progressed = fingerprint(self.run) != before
        record = {"session": number, "agent": self.adapter.name, "model": self.adapter.model,
                  "started": started, "seconds": round(time.time() - started, 1), "exit": process.returncode,
                  "ok": ok, "error": error, "progressed": progressed, "summary": summary,
                  "state_before": state.get("status"), "state_after": S.get(self.run).get("status"),
                  "log": str(log)}
        append_jsonl(self.run / "sessions.jsonl", record)
        return record

    def review_ready(self, state: dict[str, Any]) -> bool:
        """Trusted integrations may perform their pre-authorized protocol review."""
        return False

    def refresh_jobs(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return [J.refresh(self.run, self.task["compute"], job) for job in state.get("jobs", [])]

    def jobs_finished(self, records: list[dict[str, Any]]) -> None:
        self.transition("working", "jobs finished: " + ", ".join(
            f"{r['job_id']}={r['status']}" for r in records) + "; collect them with eegfm eval collect",
            actor="driver")

    def transition(self, status: str, note: str, actor: str = "driver") -> dict[str, Any]:
        return S.set_state(self.run, status, note, actor=actor)

    def validate_done(self) -> None:
        """Legacy runs retain their declaration semantics; trusted adapters override."""
        return None

    def loop(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        stalls, transient_since, failures = 0, None, 0
        while not self.stop:
            state = S.get(self.run)
            status = state.get("status")
            if status == "done":
                self.validate_done()
                self.heartbeat("finished")
                return 0
            if status == "blocked":
                attention(self.run, f"Run blocked: {state.get('note')}")
                self.heartbeat("blocked", reason=state.get("note"))
                return 3
            if status == "awaiting_review":
                if self.review_ready(state):
                    continue
                attention(self.run, "The research brief is ready for review: runs/"
                          f"{self.run.name}/RESEARCH_BRIEF.md\n\nApprove: eegfm brief approve {self.run.name} "
                          f"--note \"...\"\nReject with feedback: eegfm brief reject {self.run.name} --note \"...\"")
                self.heartbeat("awaiting_review")
                if self.once:
                    return 0
                self.sleep(self.poll)
                continue
            (self.run / "ATTENTION.md").unlink(missing_ok=True)
            if status == "waiting_job":
                records = self.refresh_jobs(state)
                pending = [r["job_id"] for r in records if r["status"] not in J.TERMINAL]
                self.heartbeat("waiting_job", pending=pending)
                if pending:
                    if self.once:
                        return 0
                    self.sleep(self.poll)
                    continue
                self.jobs_finished(records)
                continue
            if len(read_jsonl(self.run / "sessions.jsonl")) >= self.max_sessions:
                self.transition("blocked", f"session budget {self.max_sessions} used", actor="driver")
                continue
            record = self.session(state)
            if record["error"] == "fatal":
                self.transition("blocked", f"agent cannot run: {record['summary'].get('reason')}", actor="driver")
                continue
            if record["error"] == "transient" and not record["progressed"]:
                transient_since = transient_since or record["started"]
                failures += 1
                if time.time() - transient_since > self.outage_max:
                    self.transition("blocked", "agent backend unavailable beyond the outage window",
                                actor="driver")
                    continue
                wait = min(900.0, self.backoff * 2 ** (failures - 1))
                self.heartbeat("backing_off", retry_in=wait, failures=failures)
                if self.once:
                    return 0
                self.sleep(wait)
                continue
            transient_since, failures = None, 0
            stalls = 0 if record["progressed"] else stalls + 1
            if stalls >= self.stall_limit:
                self.transition("blocked", f"{stalls} consecutive sessions changed nothing; inspect "
                            f"runs/{self.run.name}/sessions/", actor="driver")
                continue
            if self.once:
                return 0
        return 0


def main(argv=None):
    from eegfm.arguments import task_parser
    p = task_parser('driver', description=__doc__)
    args = p.parse_args(argv)
    run = run_dir(args.run)
    if args.command == "start":
        log = run / "driver.log"
        argv = [sys.executable, "-B", "-m", "eegfm.agent.driver", "run"] + [a for a in (argv or sys.argv[1:]) if a != "start"]
        with log.open("ab") as handle:
            process = subprocess.Popen(argv, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(SOURCE_ROOT)},
                                       stdin=subprocess.DEVNULL, stdout=handle, stderr=handle,
                                       start_new_session=True)
        print(json.dumps({"started": True, "pid": process.pid, "log": str(log)}))
        return 0
    lock = open(run / "driver.lock", "w")
    try:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another driver is already running for this run")
    writable = args.writable if args.writable is not None else [d for d in WRITABLE_DEFAULTS if Path(d).exists()]
    driver = Driver(args.run, Adapter(args.agent, args.model, args.script, args.agent_arg, writable), poll=args.poll,
                    session_timeout=args.session_timeout, max_sessions=args.max_sessions,
                    stall_limit=args.stall_limit, backoff=args.backoff, once=args.once)
    return driver.loop()


if __name__ == "__main__":
    sys.exit(main())
