"""Run one ordinary two-session EEG research episode, or inspect its durable state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from eegfm.common import ROOT, append_jsonl, read_json, read_jsonl, sha256, write_json
from eegfm.eeg import objective_pilot as pilot

EPISODES = ROOT / ".local/research-episodes"
QUESTION = "What pretraining objectives are most suitable for EEG foundation models?"
READINGS = [
    "SpecBraM, arXiv:2610.07484v1 §§5–7: authors compared tokenizer and target at matched training budget. They found benefits of band-power prediction in scarce-label sleep staging; this need not transfer to EEGMAT. https://arxiv.org/html/2610.07484v1",
    "EEG-JEPA, arXiv:2608.00114v1 table 6: authors report improvements in a progressive ablation of latent targets, masking and supervision at multiple levels; the complete package changes more than one factor. https://arxiv.org/html/2608.00114v1",
]
RESOURCES = """This is an exploratory CPU experiment on the public EEGMAT mental arithmetic recordings.
The executor updates all trainable CBraMod encoder and original waveform-head weights from a common public checkpoint.
Only train (24 people, 192 windows) and previously exposed validation (6 people, 48 windows) are available.
Records are before vs during arithmetic, in fixed order. Five seconds per window, 19 scalp electrodes,
200 Hz, 1-second patches. Frozen linear ridge readouts trained on train people, fixed alpha 100:
occipital_alpha = O1/O2 log 8-13 Hz power R2, central_beta = C3/C4 log 13-30 Hz power R2,
condition = recording condition balanced accuracy. The latter can reflect order. All three will be returned.
There are two chosen arms A and B plus unchanged init. Same two paired training seeds 42/43, batch 4,
AdamW, norm clipping at 1; choose 8-32 equal steps. Uniform masked channel-time positions are paired
within seed (nested selections if fractions differ). Waveform reconstruction and/or frequency supervision
use the same predicted waveform and masked positions. Loss = (1-spectral_mix)*waveform MSE +
spectral_mix*MSE between log band energies of predicted and original waveforms. Units and gradients differ.
Choose each arm's spectral_mix in [0,1], 1–8 ordered non-overlapping integer frequency intervals inside
[1,100] Hz (upper bound excluded; [] is permitted for pure waveform), mask_fraction in [0.1,0.9], lr
in [1e-7,1e-3]. Primary endpoint is your choice; effects are B minus A in R2 or fractional BA.
Intervals resample people conditional on the fitted models. Both seeds use the same people. Maximum four
short fits, CPU only, no new data, internet fetch, shell or arbitrary Python by the researcher. The trusted
executor will do the experiment you select. No validation tuning, no final-test access; no forced winner."""
PLAN_FIELDS = ("question", "rationale", "alternative", "prediction", "controls", "decision_rule")
DECISION_FIELDS = (
    "evidence",
    "interpretation",
    "unresolved",
    "next_decision",
    "alternative_rejected",
    "limits",
)


def episode_path(name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,64}", name):
        raise ValueError("use a short lower-case episode name without directories")
    return EPISODES / name


def stage(run: Path) -> str:
    if (run / "decision.json").is_file():
        return "closed"
    if (run / "results.json").is_file():
        return "interpret"
    if (run / "plan.json").is_file():
        return "experiment"
    return "design"


def history() -> str:
    # Only the public study description and table: do not hand the researcher's predecessor's advice to it.
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("### CBraMod 小试")
    end = text.index("\n\n", text.index("| 心算前后平衡准确率", start))
    return text[start:end]


def freeze_brief(run: Path, parent: str | None) -> dict:
    path = run / "brief.json"
    if path.is_file():
        brief = read_json(path)
        if parent is not None and parent != brief["parent"]:
            raise ValueError("this episode already has a different parent")
        return brief
    prior = None
    if parent is not None:
        source = episode_path(parent)
        if source == run or stage(source) != "closed":
            raise ValueError("parent must be a different completed research episode")
        verify_milestones(source)
        prior = {key: read_json(source / f"{key}.json") for key in ("plan", "results", "decision")}
    brief = {
        "question": QUESTION,
        "resources": RESOURCES,
        "literature": READINGS,
        "previous_pilot": history(),
        "parent": parent,
        "parent_record": prior,
    }
    write_json(path, brief)
    code = [
        Path(__file__),
        Path(pilot.__file__),
        ROOT / "src/eegfm/agent/actor.py",
        ROOT / "src/eegfm/eeg/data.py",
        ROOT / "src/eegfm/eeg/statistics.py",
    ]
    append_jsonl(
        run / "trajectory.jsonl",
        {
            "action": "brief_frozen",
            "brief_sha256": sha256(path),
            "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in code},
            "context": "ordinary research: public pilot table, two literature notes, declared parent, service instructions",
        },
    )
    return brief


def require_text(value: dict, fields: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or any(
        not isinstance(value.get(k), str) or not value[k].strip() or len(value[k]) > 5000 for k in fields
    ):
        raise ValueError(f"expected nonempty text fields: {', '.join(fields)}")


def execute_bounded(run: Path, plan: dict) -> dict:
    """A hard wall timeout surrounds the CPU process, including data preparation and evaluation."""
    if read_json(run / "plan.json") != plan:
        raise ValueError("worker requires the frozen plan")
    code = (
        "from pathlib import Path; import sys; from eegfm.common import read_json, write_json; "
        "from eegfm.eeg.objective_pilot import execute_research_plan; "
        "run=Path(sys.argv[1]); write_json(run/'results.json', "
        "execute_research_plan(run,read_json(run/'plan.json')))"
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "CUDA_VISIBLE_DEVICES": "-1",
        "OMP_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "4",
        "OPENBLAS_NUM_THREADS": "4",
    }
    with (run / "executor.log").open("ab") as log:
        subprocess.run(
            [sys.executable, "-B", "-c", code, str(run)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=True,
        )
    return read_json(run / "results.json")


def verify_milestones(run: Path) -> None:
    """Detect accidental changes to a completed plan or aggregate before the next researcher sees it."""
    identities = {
        "brief_frozen": ("brief.json", "brief_sha256"),
        "plan_frozen": ("plan.json", "sha256"),
        "experiment_returned": ("results.json", "results_sha256"),
        "decision_recorded": ("decision.json", "sha256"),
    }
    recorded = set()
    for row in read_jsonl(run / "trajectory.jsonl"):
        if row.get("action") in identities:
            name, key = identities[row["action"]]
            if sha256(run / name) != row[key]:
                raise ValueError(f"frozen milestone changed: {name}")
            recorded.add(name)
    for name, _ in identities.values():
        if (run / name).is_file() and name not in recorded:
            raise ValueError(
                f"unrecorded milestone after an interrupted write: {name}; review before resuming"
            )


def validate_plan(value: dict) -> None:
    if value.get("action") == "decline":
        require_text(value, ("rationale",))
        return
    if value.get("action") != "experiment":
        raise ValueError("action must be experiment or decline")
    require_text(value, PLAN_FIELDS)
    if value.get("primary") not in (*pilot.TARGETS, "condition"):
        raise ValueError(
            "primary must be exactly one string: occipital_alpha, central_beta, or condition. Put explanations in the other fields."
        )
    pilot.validate_research_plan(value)


def validate_decision(value: dict) -> None:
    require_text(value, DECISION_FIELDS)
    if value.get("verdict") not in ("continue", "redirect", "stop"):
        raise ValueError("verdict must be continue, redirect or stop")


def request_text(role: str, brief: dict, run: Path) -> str:
    common = (
        "You are the scientific decision maker for an ordinary EEG study. Work in Chinese. "
        "Use only the material in this message. Treat history and papers as evidence; you may disagree. "
        "Return one JSON object, no tool calls. This is an exploratory research workflow, not a capability test.\n"
    )
    if role == "design":
        instruction = (
            "Choose your own scientific comparison. Name a serious competing explanation and a different "
            "experiment you rejected, specify direction and decision rule before execution. Do not try to fill "
            "a preselected topic. You may decline if no meaningful comparison is possible. JSON fields: "
            "action (experiment or decline), question, rationale, alternative, prediction, controls, "
            "decision_rule (per-seed rule including inconclusive cases). Each of the previous six explanatory "
            "fields is a single string. primary is exactly one of occipital_alpha, central_beta, condition. steps "
            "(integer), arms (two objects in order: name A/B, spectral_mix, bands, mask_fraction, lr). "
            "For decline only action and rationale are needed."
        )
        inputs = {"admitted_brief": brief}
    else:
        instruction = (
            "An earlier independent researcher selected the frozen plan. Your responsibility is to interpret "
            "the actual returned results. Compare the predeclared prediction and thresholds with the measured "
            "B minus A and evidence from each seed. Mention any controls or physical interpretations that "
            "remain unresolved. Choose the next action yourself (it will be recorded, not executed). "
            "Return text fields evidence, interpretation, unresolved, next_decision, alternative_rejected, "
            "limits, and verdict (continue, redirect or stop)."
        )
        inputs = {
            "admitted_brief": brief,
            "frozen_plan": {
                k: v for k, v in read_json(run / "plan.json").items() if k != "researcher_session"
            },
            "executor_results": read_json(run / "results.json"),
        }
    return common + instruction + "\n" + json.dumps(inputs, ensure_ascii=False, sort_keys=True)


def choose(
    run: Path, role: str, prompt: str, validate: Callable[[dict], None], launch: Callable[..., dict]
) -> tuple[dict, str]:
    previous = ""
    events = [r for r in read_jsonl(run / "trajectory.jsonl") if r.get("role") == role]
    requested = {r["attempt"]: r["input_sha256"] for r in events if r["action"] == "session_requested"}
    logged = {
        r.get("attempt")
        for r in events
        if r.get("action") == "invalid_response"
    }
    for attempt in (1, 2, 3):
        folder = run / f"{role}-{attempt}"
        submitted = prompt + previous
        if folder.exists():
            receipt = read_json(folder / "receipt.json")
            if not receipt or receipt.get("status") not in ("completed", "failed"):
                raise RuntimeError(
                    f"review interrupted provider session in {folder.name}; do not silently duplicate it"
                )
            if receipt.get("status") == "failed":
                if attempt == 3:
                    raise RuntimeError(f"provider attempts exhausted; see {folder/'receipt.json'}")
                continue
            calls = receipt.get("calls", [])
            if (not calls or calls[-1].get("phase") != "research" or not requested.get(attempt)
                    or calls[-1].get("prompt_sha256") != requested[attempt]):
                raise ValueError(f"native receipt does not match the recorded request for {folder.name}")
        else:
            append_jsonl(
                run / "trajectory.jsonl",
                {
                    "action": "session_requested",
                    "role": role,
                    "attempt": attempt,
                    "input_sha256": hashlib.sha256(submitted.encode("utf-8")).hexdigest(),
                },
            )
            receipt = launch(folder, submitted)
        raw = receipt["text"].strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("response must be an object")
            validate(value)
            return value, receipt["thread_id"]
        except (ValueError, TypeError, KeyError) as exc:
            if attempt not in logged:
                append_jsonl(
                    run / "trajectory.jsonl",
                    {
                        "action": "invalid_response",
                        "role": role,
                        "attempt": attempt,
                        "thread_id": receipt["thread_id"],
                        "error": str(exc),
                    },
                )
            previous = (
                "\nYour predecessor submitted the following invalid response. Fix only the contract error "
                + str(exc)
                + ".\n"
                + raw
            )
    raise ValueError(f"{role}: no response satisfied the contract in three attempts")


def advance(
    run: Path,
    *,
    parent: str | None = None,
    through: str = "interpret",
    launch: Callable[..., dict] | None = None,
    execute: Callable[..., dict] | None = None,
) -> str:
    if launch is None:
        from eegfm.agent.actor import ordinary_session

        launch = ordinary_session
    if execute is None:
        execute = execute_bounded
    run.mkdir(parents=True, exist_ok=True)
    with pilot.exclusive(run):
        verify_milestones(run)
        brief = freeze_brief(run, parent)
        for role in ("design", "experiment", "interpret"):
            if stage(run) == role:
                if role == "experiment":
                    try:
                        results = execute(run, read_json(run / "plan.json"))
                    except Exception as exc:
                        append_jsonl(
                            run / "trajectory.jsonl", {"action": "experiment_failed", "error": str(exc)}
                        )
                        raise
                    if not (run / "results.json").exists():
                        write_json(run / "results.json", results)
                    append_jsonl(
                        run / "trajectory.jsonl",
                        {"action": "experiment_returned", "results_sha256": sha256(run / "results.json")},
                    )
                else:
                    value, identity = choose(
                        run,
                        role,
                        request_text(role, brief, run),
                        validate_plan if role == "design" else validate_decision,
                        launch,
                    )
                    if (
                        role == "interpret"
                        and identity == read_json(run / "plan.json")["researcher_session"]
                    ):
                        raise RuntimeError("continuation must start a different native thread")
                    answer = dict(value, researcher_session=identity)
                    path = run / ("plan.json" if role == "design" else "decision.json")
                    write_json(path, answer)
                    append_jsonl(
                        run / "trajectory.jsonl",
                        {
                            "action": "plan_frozen" if role == "design" else "decision_recorded",
                            "session": identity,
                            "sha256": sha256(path),
                        },
                    )
                    if role == "design" and value["action"] == "decline":
                        write_json(
                            run / "decision.json",
                            {
                                "verdict": "declined_without_training",
                                "rationale": value["rationale"],
                                "researcher_session": identity,
                            },
                        )
                        append_jsonl(
                            run / "trajectory.jsonl",
                            {
                                "action": "decision_recorded",
                                "session": identity,
                                "sha256": sha256(run / "decision.json"),
                            },
                        )
            if role == through:
                break
    return stage(run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "status"))
    parser.add_argument("episode", help="new scientific episode ID or one to continue")
    parser.add_argument(
        "--parent", help="optionally admit an earlier completed episode's scientific record"
    )
    parser.add_argument(
        "--through",
        choices=("design", "experiment", "interpret"),
        default="interpret",
        help="stop after this milestone; default runs through the second decision",
    )
    args = parser.parse_args()
    run = episode_path(args.episode)
    if args.command == "status" and not (run / "brief.json").exists():
        parser.error("no such episode")
    state = (
        advance(run, parent=args.parent, through=args.through) if args.command == "run" else stage(run)
    )
    print(
        json.dumps(
            {
                "episode": args.episode,
                "next_stage": state,
                "private_directory": str(run),
                "decision": read_json(run / "decision.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
