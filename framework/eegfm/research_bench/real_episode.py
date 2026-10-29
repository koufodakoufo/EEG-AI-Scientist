"""Trusted native episode wiring. Never expose this module or config to Actor.

Actual launches use BridgeDriver.loop and launch_actor; tests may patch those
boundaries but such scripted tests are explicitly not live model evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
from typing import Any

from .actor import prepare_control, launch_actor, profile_template_sha256, validate_isolation_gate
from .budget import BudgetExceeded, mark_call, reserve_call, write_atomic
from .bundle import canonical_bytes, create_public_bundle, digest_file, safe_relative, verify_public_bundle
from .driver_bridge import BridgeController, BridgeDriver, EvaluationSpec
from eegfm.driver import Adapter
from .real_worker import FileBinding, RuntimeConfig, SandboxedWorkerEvaluator, SplitInputs
from .trace import collect_visible_trace

MODEL = "gpt-6.1-sol"
SCOPE = {"task": "eegmat-arithmetic-background", "public_resources_only": True,
         "backbone_frozen": True, "head_frozen": True, "selection_split": "validation",
         "test_after_lock_only": True, "gpu": 0}
DOCS = ("TASK.md", "INTERFACE.md", "API_README.md", "PUBLIC_RESULT_SCHEMA.md")
POLICY_HASH = hashlib.sha256(canonical_bytes({"scope": SCOPE, "review": "scope-json-and-substantive-plan-v1"})).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path, maximum_bytes: int = 1024 * 1024) -> Any:
    _regular(path)
    if path.stat().st_size > maximum_bytes:
        raise ValueError("JSON byte limit exceeded")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _regular(path: Path) -> None:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("Links forbidden")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Expected a single-link regular file")


def binding(value: dict[str, str]) -> FileBinding:
    if set(value) != {"path", "sha256"} or not Path(value["path"]).is_absolute():
        raise ValueError("Explicit absolute FileBinding required")
    result = FileBinding(Path(value["path"]), value["sha256"])
    result.verify()
    return result


def parse_requests(path: Path, episode_id: str) -> list[dict[str, Any]]:
    requests = read_json(path)
    if not isinstance(requests, list) or len(requests) > 16:
        raise ValueError("Expected at most 16 requests")
    for request in requests:
        if not isinstance(request, dict) or set(request) != {"request_id", "episode_id", "operation", "payload"}:
            raise ValueError("Invalid request envelope")
        if request["episode_id"] != episode_id or len(canonical_bytes(request)) > 64 * 1024:
            raise ValueError("Wrong episode or oversized request")
    return requests


def validate_scope(value: Any) -> None:
    if not isinstance(value, dict) or any(type(value.get(key)) is not type(expected) or value.get(key) != expected
                                           for key, expected in SCOPE.items()):
        raise ValueError("Protocol scope differs from frozen public task")


class EpisodeController(BridgeController):
    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if isinstance(request, dict) and request.get("operation") == "contract":
            payload = request.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("Contract payload must be an object")
            validate_scope(payload.get("protocol"))
        return super().handle(request)

    def _completion_ready(self, state: dict[str, Any]) -> None:
        super()._completion_ready(state)
        locked = next(attempt for attempt in state["attempts"] if attempt["id"] == state["lock"]["attempt_id"])
        final = state["jobs"][state["test_job"]].get("result", {}).get("metrics", {})
        if (locked["kind"] != "iteration" or locked.get("metrics", {}).get("q1_groups", 0) <= 0
                or final.get("q1_groups", 0) <= 0):
            raise ValueError("Completion requires Q1 evidence from the locked validation iteration and final test")

    def validate_done(self) -> None:
        # Base validation invokes this class's stricter _completion_ready on the
        # authoritative journal, including when resuming an already-done run.
        super().validate_done()


def review_brief(controller: BridgeController, projection: dict[str, Any]) -> dict[str, Any]:
    if projection["episode_id"] != controller.episode_id:
        raise ValueError("Review episode mismatch")
    content = (controller.run / "RESEARCH_BRIEF.md").read_text(encoding="utf-8")
    match = re.match(r"\s*```json\s*\n(.*?)\n```\s*(.*)", content, flags=re.S)
    approved = False
    try:
        if match and len(match.group(2).strip()) >= 40:
            validate_scope(json.loads(match.group(1), object_pairs_hook=_unique_object))
            approved = True
    except (ValueError, TypeError):
        pass
    return {"approved": approved, "reviewer_id": "frozen-scope-reviewer", "policy_sha256": POLICY_HASH}


def prepare_public(config: dict[str, Any], case: Path, private: Path) -> Path:
    """Explicit public export; only an optional skill changes condition content."""
    source, public = Path(config["public_source"]), case / "public"
    condition = config["condition"]
    if condition not in {"no_skill", "skill"} or (condition == "skill") != bool(config.get("skill")):
        raise ValueError("Condition requires exactly its matching optional skill")
    names = config["public_files"]
    if not isinstance(names, list) or len(set(names)) != len(names):
        raise ValueError("Explicit unique public allowlist required")
    for name in names:
        safe_relative(name)
        if name not in {"train.npz", "validation.npz", "eeg_api.py"} and not name.startswith("resources/"):
            raise ValueError("Only sanitized data/API resources can be exported")
        if any(word in name.lower() for word in ("test", "reference", "private", "gold", "score")):
            raise ValueError("Private/reference material cannot be exported")
    if not {"train.npz", "validation.npz", "eeg_api.py"} <= set(names):
        raise ValueError("Missing train/validation/API public resources")
    docs = Path(__file__).resolve().parents[2] / "benchmarks" / "brainpec_real"
    expected = {name: digest_file(source / name) for name in names}
    expected.update({name: digest_file(docs / name) for name in DOCS})
    if condition == "skill":
        expected["SKILL.md"] = binding(config["skill"]).sha256
    if public.exists():
        manifest = verify_public_bundle(public)
        if {item["path"]: item["sha256"] for item in manifest["files"]} != expected:
            raise ValueError("Existing public bundle differs from frozen enrollment")
        return public
    stage = private / "public-staging"
    stage.mkdir(parents=True, exist_ok=False)
    for name in names:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _regular(source / name)
        shutil.copyfile(source / name, target)
    for name in DOCS:
        shutil.copyfile(docs / name, stage / name)
    if condition == "skill":
        shutil.copyfile(binding(config["skill"]).path, stage / "SKILL.md")
    if any(digest_file(stage / name) != value for name, value in expected.items()):
        raise ValueError("Public source changed during export")
    create_public_bundle(stage, public, expected, task_id="eegmat-representation-analysis-v1", tier="real_eeg")
    return public


def session_prompt(projection: dict[str, Any], number: int, scientific_python: Path,
                   history: list[dict[str, Any]]) -> str:
    if not 1 <= number <= 6:
        raise ValueError("Session limit exceeded")
    return ("You are the isolated research Actor for this single EEGMAT episode. "
            "Read public/TASK.md, public/INTERFACE.md, public/API_README.md and "
            "public/PUBLIC_RESULT_SCHEMA.md; read public/SKILL.md if present. "
            "Use only these materials and your own case/output history. No other conversation is available.\n"
            f"Scientific Python: {scientific_python}\nSession: {number}/6. "
            f"Write requests to output/requests-session-{number:02d}.json and end the session. "
            "The five-stage flow is brief; contract+baseline; attempt; lock+test; report. "
            "The sixth session is a correction allowance. Keep research notes in output/. "
            "No request is executed before this session ends.\n"
            "TRUSTED_OWN_EPISODE_PROJECTION_JSON\n" + canonical_bytes(projection).decode()
            + "OWN_SESSION_RECEIPTS_JSON\n" + canonical_bytes(history).decode())


class NativeEpisodeLaunch:
    """One reservation and one fresh control home per actual native invocation."""
    def __init__(self, config: dict[str, Any], controller: BridgeController, private: Path,
                 public: Path, started_at: float) -> None:
        self.config, self.controller, self.private, self.public = config, controller, private, public
        self.started_at = started_at
        self.history_path = private / "own-session-receipts.json"
        self.history = read_json(self.history_path) if self.history_path.exists() else []

    def __call__(self, projection: dict[str, Any]) -> dict[str, Any]:
        config = self.config
        sessions = [json.loads(line) for line in (self.controller.run / "sessions.jsonl").read_text().splitlines()]
        number = len(sessions)
        if not 1 <= number <= min(6, len(config["call_ids"])):
            raise BudgetExceeded("Episode call allocation exhausted")
        remaining = int(self.started_at + 5400 - time.time()) - 30
        if remaining < 1:
            raise BudgetExceeded("Episode wall deadline reached")
        timeout = min(900, remaining)
        call_id = config["call_ids"][number - 1]
        budget = Path(config["budget_path"])
        reserve_call(budget, call_id, "actor", timeout)
        output = self.private / "launches" / f"session-{number:02d}-{call_id}"
        prompt = session_prompt(projection, number, Path(config["scientific_python"]), self.history)
        report: dict[str, Any] = {"status": "failed", "exit_code": -1, "stdout": "", "stderr": "",
                                  "process_cleanup": {"surviving_owned_pids": []}, "requests": []}
        running, invoked, verified_turn = False, False, False
        try:
            gate = read_json(binding(config["isolation_report"]).path)
            runtime_manifest = binding(config["runtime_manifest"])
            runtime_manifest.verify()
            metadata = prepare_control(case=self.controller.case, public=self.public,
                control_home=self.private / "controls" / f"session-{number:02d}-{call_id}",
                native_binary=Path(config["native_binary"]), bwrap_dir=Path(config["bwrap"]).parent,
                auth_source=Path(config["auth_source"]), model=MODEL,
                read_only_roots=tuple(Path(path) for path in config["scientific_roots"]))
            validate_isolation_gate(metadata, gate)
            mark_call(budget, call_id, "running", episode_id=self.controller.episode_id,
                      session=number, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
            running = True
            invoked = True
            native = launch_actor(metadata, prompt, output_dir=output, timeout_seconds=timeout,
                bwrap_dir=Path(config["bwrap"]).parent, proxy_url=config["proxy_url"], role="actor",
                isolation_report=gate, prompt_via_stdin=True,
                case_storage_limit_bytes=10 * 1024**3)
            report.update({key: native.get(key) for key in ("status", "exit_code", "process_cleanup")})
            report["stdout"] = (output / "stdout.jsonl").read_text(encoding="utf-8")
            report["stderr"] = (output / "stderr.log").read_text(encoding="utf-8")
            if report["process_cleanup"].get("surviving_owned_pids") != []:
                raise ValueError("Owned model processes survived cleanup")
            trace = collect_visible_trace(Path(metadata["control_home"]), output / "trace")
            contexts = trace["turn_metadata"]
            if not contexts or any(row.get("model") != MODEL or row.get("effort") != "medium" for row in contexts):
                raise ValueError("Actual model identity differs from enrollment")
            verified_turn = True
            verify_public_bundle(self.public)
            if report["status"] == "completed" and report["exit_code"] == 0 and report["process_cleanup"].get("surviving_owned_pids") == []:
                report["requests"] = parse_requests(self.controller.case / "output" / f"requests-session-{number:02d}.json", self.controller.episode_id)
        except Exception as error:
            report.update(status="failed", requests=[], stderr="Trusted launch/ingestion failure: " + type(error).__name__)
            write_atomic(self.private / "launch-errors" / f"session-{number:02d}.json",
                         {"error_type": type(error).__name__, "session": number, "call_id": call_id})
        clean, _, _ = Adapter("codex").classify(report["exit_code"], report["stdout"], report["stderr"], report["status"] == "timed_out")
        status = "timed_out" if report["status"] == "timed_out" else "completed" if report["status"] == "completed" and clean else "failed"
        mark_call(budget, call_id, status if running else "blocked", evidence=str(output),
                  episode_id=self.controller.episode_id, session=number)
        self.history.append({"session": number, "status": status, "actual_native_invocation": invoked,
                             "verified_model_turn": verified_turn and clean,
                             "request_count": len(report["requests"]),
                             "feedback": report["stderr"] if report["stderr"].startswith("Trusted launch/") else ""})
        write_atomic(self.history_path, self.history)
        write_atomic(self.private / "launch-receipts" / f"session-{number:02d}.json",
                     {key: value for key, value in report.items() if key not in {"stdout", "stderr"}})
        return report


class DeadlineEvaluator:
    sandboxed = True

    def __init__(self, evaluator: SandboxedWorkerEvaluator, started_at: float) -> None:
        self.evaluator, self.started_at = evaluator, started_at

    def submit(self, spec: EvaluationSpec) -> dict[str, Any]:
        if time.time() + self.evaluator.timeout + 30 > self.started_at + 5400:
            raise BudgetExceeded("Insufficient episode time for allocated worker")
        return self.evaluator.submit(spec)

    def poll(self, job_id: str) -> dict[str, Any]:
        return self.evaluator.poll(job_id)


class EpisodeDriver(BridgeDriver):
    """Keep the inherited scheduler; cap its outage/job sleeps at the wall end."""
    episode_deadline: float

    def sleep(self, seconds: float) -> None:
        remaining = self.episode_deadline - time.time()
        if remaining <= 0:
            self.controller.block("Episode wall deadline reached")
            return
        super().sleep(min(seconds, remaining))
        if time.time() >= self.episode_deadline:
            self.controller.block("Episode wall deadline reached")


def run_episode(config: dict[str, Any]) -> dict[str, Any]:
    """Linux native entrypoint; no production scripted-hook or synthetic mode."""
    if os.name != "posix":
        raise RuntimeError("Native isolated episodes require Linux")
    from .real_aggregate import ScientificAggregator

    if config.get("schema_version") != "real_episode_config_v1":
        raise ValueError("Unsupported episode enrollment")
    if config.get("model", MODEL) != MODEL or config.get("reasoning_effort", "medium") != "medium":
        raise ValueError("Frozen model/effort required")
    call_ids = config["call_ids"]
    if not isinstance(call_ids, list) or not 1 <= len(call_ids) <= 6 or len(set(call_ids)) != len(call_ids) or any(not re.fullmatch(r"R[0-9]{2,}", value) for value in call_ids):
        raise ValueError("One to six unique R-series call IDs required")
    case, private = Path(config["case_root"]), Path(config["trusted_root"])
    if not case.is_absolute() or not private.is_absolute() or case == private or case in private.parents or private in case.parents:
        raise ValueError("Absolute disjoint case and trusted roots required")
    if case.exists() and any(case.iterdir()) and not (private / "ENROLLMENT.json").is_file():
        raise ValueError("Fresh enrollment requires a fresh case; no unrelated episode history")
    for path in (case, private):
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError("Episode roots cannot contain links")
        path.mkdir(parents=True, exist_ok=True)
    for directory in ("output", "home", "tmp"):
        (case / directory).mkdir(exist_ok=True)
    public = prepare_public(config, case, private)
    # Bind every private source and source implementation before model enrollment.
    train = binding(config["train_input"])
    validation, test = binding(config["validation_input"]), binding(config["test_input"])
    split = binding(config["split_manifest"])
    runtime_manifest = binding(config["runtime_manifest"])
    gate = binding(config["isolation_report"])
    # Fail before enrollment or a model reservation when live certification is
    # absent/stale. prepare_control and launch_actor independently check again.
    roots = tuple(Path(path) for path in config["scientific_roots"])
    if not roots:
        raise ValueError("The read-only scientific runtime must be explicit")
    native_binary = Path(config["native_binary"])
    live_report = read_json(gate.path)
    validate_isolation_gate({"native_binary_sha256": digest_file(native_binary),
        "code_mode_host_sha256": digest_file(native_binary.parent / "codex-code-mode-host"),
        "bwrap_sha256": digest_file(Path(config["bwrap"])),
        "profile_template_sha256": profile_template_sha256(MODEL, read_only_roots=roots),
        "read_only_roots": [str(path) for path in roots]}, live_report)
    if any(live_report.get("probes", {}).get(name, {}).get("allowed") is not False
           for name in ("test_features", "split_manifest", "driver_state")):
        raise ValueError("Live certificate lacks sealed-test/controller denial evidence")
    truth = {name: binding(value) for name, value in config["truth_by_split"].items()}
    train_truth = binding(config["train_truth"])
    for protected in (private, split.path, validation.path, test.path, runtime_manifest.path,
                      gate.path, Path(config["auth_source"]), Path(config["budget_path"]),
                      *(value.path for value in truth.values()), train_truth.path):
        if protected == case or case in protected.parents:
            raise ValueError("Private bindings cannot be mounted inside Actor case")
    if train.sha256 != digest_file(public / "train.npz"):
        raise ValueError("Worker training view differs from Actor training view")
    aggregate = ScientificAggregator(truth, train_truth, bootstrap_resamples=config.get("bootstrap_resamples", 2000))
    runtime = RuntimeConfig(bwrap=Path(config["bwrap"]), python=Path(config["scientific_python"]),
        environment_roots=tuple(Path(path) for path in config["scientific_roots"]), manifest=runtime_manifest)
    public_hash = digest_file(public / "PUBLIC_MANIFEST.json")
    worker = SandboxedWorkerEvaluator(private_root=private / "worker-evidence", public_root=public,
        public_manifest_sha256=public_hash, split_manifest_path=split.path, split_manifest_sha256=split.sha256,
        inputs_by_split={"validation": SplitInputs(train, validation), "test": SplitInputs(train, test)},
        runtime=runtime, aggregate=aggregate, released_metrics=aggregate.released_metrics,
        aggregate_bindings=aggregate.bindings, aggregate_policy_sha256=aggregate.policy_sha256,
        timeout_seconds=config.get("worker_timeout_seconds", 900))
    if worker.timeout > 900:
        raise ValueError("Episode worker limit is 900 seconds")
    identity = {"config_sha256": hashlib.sha256(canonical_bytes(config)).hexdigest(),
                "public_manifest_sha256": public_hash, "worker_enrollment": worker._enrollment(),
                "model": MODEL, "effort": "medium", "session_limit": len(call_ids), "wall_seconds": 5400,
                "review_policy_sha256": POLICY_HASH,
                "runner_sha256": digest_file(Path(__file__)),
                "actor_source_sha256": digest_file(Path(__file__).with_name("actor.py")),
                "bridge_source_sha256": digest_file(Path(__file__).with_name("driver_bridge.py")),
                "science_source_sha256": digest_file(Path(__file__).with_name("real_science.py")),
                "data_source_sha256": digest_file(Path(__file__).with_name("real_data.py")),
                "live_isolation_report_sha256": gate.sha256}
    enrollment_path = private / "ENROLLMENT.json"
    if enrollment_path.exists():
        enrolled = read_json(enrollment_path, maximum_bytes=8 * 1024**2)
        if enrolled["identity"] != identity:
            raise ValueError("Frozen episode enrollment changed")
    else:
        enrolled = {"schema_version": "real_episode_enrollment_v1", "identity": identity,
                    "started_at_epoch": time.time(), "started_at": datetime.now(timezone.utc).isoformat(),
                    "execution_mode": "native_isolated_model"}
        with enrollment_path.open("xb") as handle:
            handle.write(canonical_bytes(enrolled))
    controller = EpisodeController(trusted_root=private / "controller", case_root=case,
        episode_id=config["episode_id"], run_id=config["run_id"], public_manifest_sha256=public_hash,
        split_manifest_sha256=split.sha256, evaluator=DeadlineEvaluator(worker, enrolled["started_at_epoch"]),
        max_attempts=config.get("max_attempts", 2))
    launcher = NativeEpisodeLaunch(config, controller, private, public, enrolled["started_at_epoch"])
    driver = EpisodeDriver(controller, launch=launcher, reviewer=lambda projection: review_brief(controller, projection),
                          max_sessions=len(call_ids), poll=1.0)
    driver.episode_deadline = enrolled["started_at_epoch"] + 5400
    try:
        exit_code = driver.loop()
    except Exception as error:
        if controller.projection()["state"]["status"] != "done":
            controller.block("Trusted orchestration stopped: " + type(error).__name__)
        write_atomic(private / "orchestration-error.json", {"error_type": type(error).__name__})
        exit_code = 3
    projection = controller.projection()
    # Only the same filtered projection is retained as a publication artifact.
    write_atomic(private / "FINAL_PUBLIC_PROJECTION.json", projection)
    result = {"schema_version": "real_episode_result_v1", "episode_id": controller.episode_id,
              "run_id": controller.run_id, "exit_code": exit_code, "state": projection["state"],
              "enrollment_sha256": digest_file(enrollment_path),
              "actual_native_invocations": sum(bool(row.get("actual_native_invocation")) for row in launcher.history),
              "actual_model_run": any(row.get("verified_model_turn") for row in launcher.history),
              "scientific_completion": "requires independent evidence review; lifecycle completion alone is insufficient"}
    write_atomic(private / "EPISODE_RESULT.json", result)
    return result
