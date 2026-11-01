"""`eegfm` command line. Agents and humans use the same commands."""
import argparse
import json
import sys

TASK_COMMANDS: dict[str, str] = {
    "driver": "eegfm.agent.driver",
    "episode": "eegfm.eeg.run",
    "reference": "eegfm.eeg.reference",
    "export": "eegfm.eeg.export",
    "prepare-eegmmidb": "eegfm.eeg.eegmmidb",
    "eegmmidb-reference": "eegfm.eeg.eegmmidb_reference",
    "eegmmidb-export": "eegfm.eeg.eegmmidb_export",
    "baselines": "eegfm.eeg.baselines",
    "bootstrap": "eegfm.eeg.bootstrap",
    "replay": "eegfm.eeg.replay",
    "calibrate": "eegfm.evaluation.calibration",
    "legacy-score": "eegfm.evaluation.legacy.__main__",
}


def out(value):
    print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, default=str))


def build():
    p = argparse.ArgumentParser(prog="eegfm", description=__doc__)
    sub = p.add_subparsers(dest="group", required=True)

    run = sub.add_parser("run").add_subparsers(dest="cmd", required=True)
    x = run.add_parser("init"); x.add_argument("--task", required=True); x.add_argument("--run-id", required=True)

    st = sub.add_parser("state").add_subparsers(dest="cmd", required=True)
    x = st.add_parser("show"); x.add_argument("run")
    x = st.add_parser("set"); x.add_argument("run"); x.add_argument("--status", required=True)
    x.add_argument("--job", action="append", default=[]); x.add_argument("--note")

    br = sub.add_parser("brief", help="human review gate").add_subparsers(dest="cmd", required=True)
    for name in ("approve", "reject"):
        x = br.add_parser(name); x.add_argument("run"); x.add_argument("--note", default="")
    x = br.add_parser("submit", help="agent: brief written, request review"); x.add_argument("run")

    at = sub.add_parser("attempt").add_subparsers(dest="cmd", required=True)
    x = at.add_parser("new"); x.add_argument("run"); x.add_argument("--kind", required=True)
    x.add_argument("--title", required=True); x.add_argument("--parent"); x.add_argument("--hypothesis")
    x = at.add_parser("verdict"); x.add_argument("run"); x.add_argument("attempt")
    g = x.add_mutually_exclusive_group(required=True); g.add_argument("--keep", action="store_true")
    g.add_argument("--discard", action="store_true"); x.add_argument("--reason", required=True)
    x = at.add_parser("list"); x.add_argument("run")
    x = at.add_parser("show"); x.add_argument("run"); x.add_argument("attempt")

    ws = sub.add_parser("workspace").add_subparsers(dest="cmd", required=True)
    x = ws.add_parser("checkout", help="restore the workspace to an attempt's code"); x.add_argument("run")
    x.add_argument("attempt")

    x = sub.add_parser("freeze", help="freeze the evaluator after setup"); x.add_argument("run")
    x.add_argument("--note", required=True)

    ev = sub.add_parser("eval").add_subparsers(dest="cmd", required=True)
    x = ev.add_parser("submit"); x.add_argument("run"); x.add_argument("attempt")
    x.add_argument("--phase", choices=["val", "test"], default="val"); x.add_argument("--gpus", type=int)
    x = ev.add_parser("collect"); x.add_argument("run"); x.add_argument("attempt")

    x = sub.add_parser("lock", help="lock a test candidate"); x.add_argument("run"); x.add_argument("attempt")
    x.add_argument("--reason", required=True)

    jb = sub.add_parser("job").add_subparsers(dest="cmd", required=True)
    x = jb.add_parser("status"); x.add_argument("run"); x.add_argument("job")
    x = jb.add_parser("list"); x.add_argument("run")
    x = jb.add_parser("stop"); x.add_argument("run"); x.add_argument("job")

    me = sub.add_parser("memory").add_subparsers(dest="cmd", required=True)
    x = me.add_parser("add"); x.add_argument("--task", required=True); x.add_argument("--run")
    x.add_argument("--kind", required=True); x.add_argument("--applies", action="append", required=True)
    x.add_argument("--evidence", action="append", required=True); x.add_argument("--claim", required=True)
    x.add_argument("--confidence", default="medium"); x.add_argument("--shared", action="store_true")
    x = me.add_parser("promote"); x.add_argument("--task", required=True); x.add_argument("item")
    x.add_argument("--confirmed-by", action="append", default=[])
    x = me.add_parser("dispute"); x.add_argument("--task", required=True); x.add_argument("item")
    x.add_argument("--evidence", action="append", required=True); x.add_argument("--note", required=True)
    x = me.add_parser("index"); x.add_argument("--task")

    rp = sub.add_parser("report").add_subparsers(dest="cmd", required=True)
    x = rp.add_parser("final", help="unseal test results of locked candidates"); x.add_argument("run")

    x = sub.add_parser("status", help="human-readable run summary"); x.add_argument("run")

    x = sub.add_parser("preflight", help="check agent, network, storage, task and compute before a run")
    x.add_argument("--agent", choices=["codex", "claude"], required=True); x.add_argument("--task")
    x.add_argument("--live", action="store_true", help="also run one tiny real agent session")
    x.add_argument("--model"); x.add_argument("--agent-arg", action="append", default=[])
    for name, module in TASK_COMMANDS.items():
        sub.add_parser(name, help=f"dispatch to {module}", add_help=False)
    return p


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in TASK_COMMANDS:
        if "--help" in arguments[1:] or "-h" in arguments[1:]:
            from eegfm.arguments import task_parser
            task_parser(arguments[0]).parse_args(arguments[1:])
        import importlib
        module = importlib.import_module(TASK_COMMANDS[arguments[0]])
        previous = sys.argv
        try:
            sys.argv = ["eegfm " + arguments[0], *arguments[1:]]
            return module.main() or 0
        finally:
            sys.argv = previous
    args = build().parse_args(arguments)
    from eegfm.agent import attempts as A
    from eegfm.agent import evaluation as E
    from eegfm.agent import jobs as J
    from eegfm.improvement import memory as M
    from eegfm.agent import state as S
    from eegfm.common import read_json
    from eegfm.common import read_jsonl
    from eegfm.common import run_dir
    g, c = args.group, getattr(args, "cmd", None)
    if g == "run":
        out(str(A.init_run(args.task, args.run_id)))
    elif g == "state":
        run = run_dir(args.run)
        out(S.get(run) if c == "show" else S.set_state(run, args.status, args.note, args.job))
    elif g == "brief":
        run = run_dir(args.run)
        if c == "submit":
            out(S.set_state(run, "awaiting_review", "brief ready for human review"))
        elif c == "approve":
            if S.get(run).get("status") != "awaiting_review":
                raise SystemExit("No brief is awaiting review")
            brief = run / "RESEARCH_BRIEF.md"
            if not brief.exists():
                raise SystemExit(f"{brief} does not exist")
            # The approved brief becomes the task's standing brief for later runs.
            task_id = read_json(run / "run.json")["task_id"]
            from eegfm.common import task_dir
            (task_dir(task_id) / "RESEARCH_BRIEF.md").write_text(
                f"<!-- approved {args.note!r} from run {run.name} -->\n" + brief.read_text(encoding="utf-8"),
                encoding="utf-8")
            out(S.set_state(run, "working", f"brief approved: {args.note}", actor="human"))
        else:
            out(S.set_state(run, "brief", f"brief rejected: {args.note}", actor="human"))
    elif g == "attempt":
        run = run_dir(args.run)
        if c == "new":
            out(A.new_attempt(run, args.kind, args.title, args.parent, args.hypothesis))
        elif c == "verdict":
            out(A.set_verdict(run, args.attempt, "keep" if args.keep else "discard", args.reason))
        elif c == "list":
            A.write_index(run)
            out((run / "attempts" / "INDEX.md").read_text())
        else:
            out(A.get_attempt(run, args.attempt))
    elif g == "workspace":
        run = run_dir(args.run)
        commit = A.get_attempt(run, args.attempt).get("commit")
        if not commit:
            raise SystemExit("That attempt has no recorded code yet")
        A.git(run / "workspace", "checkout", commit, "--", ".")
        out(f"workspace files restored to {args.attempt} ({commit[:10]}); edit and create a new attempt")
    elif g == "freeze":
        out(E.freeze(run_dir(args.run), args.note))
    elif g == "eval":
        run = run_dir(args.run)
        out(E.submit(run, args.attempt, args.phase, args.gpus) if c == "submit" else E.collect(run, args.attempt))
    elif g == "lock":
        out(E.lock(run_dir(args.run), args.attempt, args.reason))
    elif g == "job":
        run = run_dir(args.run)
        compute = E.task_of(run)["compute"]
        if c == "status":
            out(J.refresh(run, compute, args.job))
        elif c == "list":
            out([{k: r.get(k) for k in ("job_id", "attempt", "phase", "status", "gpus")}
                 for r in (read_json(p) for p in sorted((run / "jobs").glob("*.json")))])
        else:
            record = read_json(J.ledger(run, args.job))
            J.backend(compute).stop(record)
            out(J.refresh(run, compute, args.job))
    elif g == "memory":
        if c == "add":
            run = run_dir(args.run) if args.run else None
            out(str(M.add(args.task, args.kind, args.claim, args.applies, args.evidence, args.confidence,
                          run, args.shared)))
        elif c == "promote":
            out(str(M.promote(args.task, args.item, args.confirmed_by)))
        elif c == "dispute":
            out(str(M.dispute(args.task, args.item, args.evidence, args.note)))
        else:
            M.index(args.task)
            out("memory indexes regenerated")
    elif g == "report":
        out(E.final_report(run_dir(args.run)))
    elif g == "preflight":
        from eegfm.agent.preflight import preflight
        result = preflight(args.agent, args.task, args.live, args.model, args.agent_arg)
        for item in result["checks"]:
            print(f"[{'ok' if item['ok'] else 'FAIL'}] {item['check']}" + (f" -- {item['detail']}" if item["detail"] else ""))
        print("PREFLIGHT " + ("PASSED" if result["ok"] else "FAILED") + (f"; live log: {result['live_log']}" if result["live_log"] else ""))
        return 0 if result["ok"] else 1
    elif g == "status":
        run = run_dir(args.run)
        out({"state": S.get(run), "attempts": json.loads(A.summary(run)),
             "frozen": bool(read_json(run / "freeze.json")), "locks": read_jsonl(run / "locks.jsonl"),
             "recent_events": read_jsonl(run / "events.jsonl")[-8:]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
