"""Run lifecycle state (STATE.json). The agent declares it; the driver reads it.

status values:
  brief            write or revise RESEARCH_BRIEF.md
  awaiting_review  brief written; a human approves with `eegfm brief approve`
  working          agent has work to do now (setup, iterate, finalize)
  waiting_job      agent submitted jobs and ended its session; driver polls them
  done             final report written, memory consolidated
  blocked          only a human can unblock (reason in note); driver stops
"""
from .common import append_jsonl, now, read_json, write_json

STATUSES = {"brief", "awaiting_review", "working", "waiting_job", "done", "blocked"}


def path(run):
    return run / "STATE.json"


def get(run):
    return read_json(path(run), {})


def set_state(run, status, note=None, jobs=None, actor="agent", **extra):
    if status not in STATUSES:
        raise SystemExit(f"Unknown status {status!r}; use one of {sorted(STATUSES)}")
    state = get(run)
    previous = state.get("status")
    if previous == "awaiting_review" and status not in {"awaiting_review", "blocked"} and actor == "agent":
        raise SystemExit("The brief is awaiting human review; only `eegfm brief approve/reject` can move on")
    if previous == "done" and status != "done":
        raise SystemExit("Run is done")
    if status == "waiting_job" and not jobs:
        raise SystemExit("waiting_job requires at least one --job id")
    state.update(status=status, note=note, jobs=list(jobs or []), updated_at=now(),
                 updated_by=actor, **extra)
    write_json(path(run), state)
    append_jsonl(run / "events.jsonl", {"event": "state", "from": previous, "to": status,
                                         "note": note, "jobs": list(jobs or []), "actor": actor})
    return state
