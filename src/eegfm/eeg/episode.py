"""Trusted native episode wiring. Never expose this module or config to Actor.

Actual launches use ResearchDriver.loop and launch_actor; tests may patch those
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

from eegfm.agent.actor import prepare_control
from eegfm.agent.actor import launch_actor
from eegfm.agent.actor import profile_template_sha256
from eegfm.agent.actor import readonly_transport_sha256
from eegfm.agent.actor import validate_isolation_gate
from eegfm.agent.budget import BudgetExceeded
from eegfm.agent.budget import mark_call
from eegfm.agent.budget import reserve_call
from eegfm.agent.budget import write_atomic
from eegfm.agent.provider import supported_native_identity, MAX_DELEGATED_SESSION_SECONDS, MAX_DELEGATED_EPISODE_SECONDS
from eegfm.evaluation.bundle import canonical_bytes
from eegfm.evaluation.bundle import create_public_bundle
from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.bundle import safe_relative
from eegfm.evaluation.bundle import verify_public_bundle
from eegfm.agent.controller import ResearchController
from eegfm.agent.controller import ResearchDriver
from eegfm.agent.controller import EvaluationSpec
from eegfm.agent.controller import RECOVERY_POLICIES
from eegfm.agent.controller import ControllerAlreadyRunning
from eegfm.agent.driver import Adapter
from eegfm.evaluation.worker import FileBinding
from eegfm.evaluation.worker import RuntimeConfig
from eegfm.evaluation.worker import SandboxedWorkerEvaluator
from eegfm.evaluation.worker import SplitInputs
from eegfm.improvement.trace import collect_visible_trace
from eegfm.improvement.trace import cli_usage
from eegfm.eeg.evidence_policy import SESSION_GUIDANCE, validate_policy, validation_evidence_status

MODEL = "gpt-6.1-sol"
DEFAULT_TASK = "eegmat-representation-analysis-v1"
READOUT_TASK = "eegmmidb-readout-bottleneck-v1"
RESIDUAL_RECOVERY_TASK = "eegmat-residual-recovery-v1"
SCOPE = {"task": "eegmat-arithmetic-background", "public_resources_only": True,
         "backbone_frozen": True, "head_frozen": True, "selection_split": "validation",
         "test_after_lock_only": True, "gpu": 0}
DOCS = ("TASK.md", "INTERFACE.md", "API_README.md", "PUBLIC_RESULT_SCHEMA.md")
PAPER_TASK_RESOURCE = "resources/PAPER_TASK.json"
PAPER_TASK_MAX_BYTES = 1024 * 1024
POLICY_HASH = hashlib.sha256(canonical_bytes({"scope": SCOPE, "review": "scope-json-and-substantive-plan-v1"})).hexdigest()
TASKS = {
    DEFAULT_TASK: ("representation_analysis", "eegmat-arithmetic-background"),
    "eegmat-attribute-dependence-v1": ("representation_analysis", "eegmat-arithmetic-background"),
    "eegmmidb-attribute-dependence-v1": ("eegmmidb", "eegmmidb-eyes-open-closed-baseline"),
    "eegmat-attribute-dependence-v2": ("eegmat_attribute_dependence_v2", "eegmat-arithmetic-background"),
    "eegmmidb-attribute-dependence-v2": ("eegmmidb_attribute_dependence_v2", "eegmmidb-eyes-open-closed-baseline"),
    READOUT_TASK: ("readout_bottleneck", "eegmmidb-cached-readout-bottleneck"),
    RESIDUAL_RECOVERY_TASK: ("residual_recovery", "eegmat-cached-residual-recovery"),
}
EVIDENCE_TASKS = frozenset({"eegmat-attribute-dependence-v2", "eegmmidb-attribute-dependence-v2"})


def task_scope(task_id: str = DEFAULT_TASK) -> dict[str, Any]:
    if not isinstance(task_id, str) or task_id not in TASKS:
        raise ValueError("Unregistered public task identity")
    scope = {**SCOPE, "task": TASKS[task_id][1]}
    if task_id in {READOUT_TASK, RESIDUAL_RECOVERY_TASK}:
        scope.update(cached_inputs_only=True, train_only_readouts=True)
    return scope


def review_policy_hash(task_id: str = DEFAULT_TASK, *, session_guidance: str = "fixed_stages_v1") -> str:
    policy = {"scope": task_scope(task_id), "review": "scope-json-and-substantive-plan-v1"}
    policy.update(evidence_guidance_identity({"task_id": task_id, "session_guidance": session_guidance}))
    return hashlib.sha256(canonical_bytes(policy)).hexdigest()


def task_evidence_policy(task_id: str) -> dict[str, Any] | None:
    task_scope(task_id)
    if task_id not in EVIDENCE_TASKS:
        return None
    from eegfm.common import ROOT
    return validate_policy(read_json(ROOT / "tasks" / TASKS[task_id][0] / "EVIDENCE_POLICY.json"))


def evidence_guidance_identity(config: dict[str, Any], public_root: Path | None = None) -> dict[str, Any]:
    """Freeze the one guidance switch and canonical task-policy bytes."""
    task_id = config.get("task_id", DEFAULT_TASK)
    policy = task_evidence_policy(task_id)
    guidance = config.get("session_guidance", "fixed_stages_v1")
    if (not isinstance(guidance, str) or guidance not in SESSION_GUIDANCE
            or (policy is None and guidance != "fixed_stages_v1")):
        raise ValueError("Unsupported task session guidance")
    if policy is None:
        return {}  # Preserve historical enrollment identity and default behavior.
    maximum = config.get("max_attempts", 2)
    if type(maximum) is not int or not 1 <= maximum <= 2:
        raise ValueError("Evidence tasks permit at most two scientific iterations")
    if config.get("recovery_policy", "validation-recovery-v1") != "validation-recovery-v1":
        raise ValueError("Evidence task recovery policy must match validation-recovery-v1")
    if public_root is not None:
        manifest = verify_public_bundle(public_root)
        if manifest["task_id"] != task_id or canonical_bytes(validate_policy(
                read_json(public_root / "EVIDENCE_POLICY.json"))) != canonical_bytes(policy):
            raise ValueError("Public evidence policy differs from frozen task policy")
    return {"session_guidance": guidance,
            "evidence_policy_sha256": hashlib.sha256(canonical_bytes(policy)).hexdigest(),
            "evidence_feedback_source_sha256": digest_file(Path(__file__).with_name("evidence_policy.py"))}


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


def validate_residual_qualification(config: dict[str, Any]) -> dict[str, Any]:
    """Match the eight attested roles to actual enrolled files before launch."""
    from eegfm.eeg.residual_recovery import validate_qualification
    if config.get("task_id") != RESIDUAL_RECOVERY_TASK:
        raise ValueError("Residual qualification requires its registered task")
    if (set(config["truth_by_split"]) != {"validation", "test"}
            or set(config["inference_by_split"]) != {"validation", "test"}):
        raise ValueError("Residual private roles require exactly validation/test")
    expected = {"truth_train": binding(config["train_truth"]).sha256,
                "split_manifest": binding(config["split_manifest"]).sha256,
                **{f"truth_{s}": binding(v).sha256 for s, v in config["truth_by_split"].items()},
                **{f"inference_{s}": binding(v).sha256 for s, v in config["inference_by_split"].items()}}
    if config.get("schema_version") == "ssh_residual_recovery_worker_v1":
        public = Path(config["public_root"])
        manifest = verify_public_bundle(public)
        if manifest["task_id"] != RESIDUAL_RECOVERY_TASK:
            raise ValueError("Residual public task mismatch")
        files = {item["path"]: item["sha256"] for item in manifest["files"]}
        expected.update({f"public_{s}": files[f"{s}.npz"] for s in ("train", "validation")})
    else:
        expected.update(public_train=binding(config["train_input"]).sha256,
                        public_validation=binding(config["public_validation_input"]).sha256)
        if (binding(config["validation_input"]).sha256 != expected["inference_validation"]
                or binding(config["test_input"]).sha256 != expected["inference_test"]):
            raise ValueError("Residual worker inputs differ from enrolled inference")
    receipt = read_json(binding(config["residual_data_qualification"]).path, maximum_bytes=64 * 1024)
    return validate_qualification(receipt, expected)


def residual_baseline_identity_sha(result: dict[str, Any]) -> str:
    """Read only the trusted successful validation manifest, never actor files."""
    if not isinstance(result, dict) or result.get("status") != "succeeded" or result.get("split") != "validation":
        raise ValueError("Successful residual validation result required")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Residual baseline identity artifact required")
    matches = []
    for item in artifacts:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str) or not isinstance(item["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None):
            raise ValueError("Malformed residual artifact")
        safe_relative(item["path"])
        if Path(item["path"]).name == "baseline_identity.json":
            if item["path"] != "baseline_identity.json":
                raise ValueError("Alternate baseline identity path forbidden")
            matches.append(item["sha256"])
    if len(matches) != 1:
        raise ValueError("Exactly one trusted baseline identity artifact required")
    return matches[0]


def load_aggregator(config: dict[str, Any], *, public_root: Path | None = None,
                    verify_runtime: bool = False) -> Any:
    """Dispatch only enrolled scientific tasks, identically on both machines."""
    task_id = config.get("task_id", DEFAULT_TASK)
    task_scope(task_id)
    truth = {name: binding(value) for name, value in config["truth_by_split"].items()}
    train_truth = binding(config["train_truth"])
    if task_id in {READOUT_TASK, RESIDUAL_RECOVERY_TASK}:
        from eegfm.evaluation.ssh_worker import readout_runtime_record, verify_readout_runtime
        runtime = readout_runtime_record(config.get("aggregate_runtime"))
        if verify_runtime:
            verify_readout_runtime(runtime)
        public = public_root if public_root is not None else Path(config["public_root"])
        manifest = verify_public_bundle(public)
        if manifest["task_id"] != task_id:
            raise ValueError("Readout scorer requires its actual enrolled public task bundle")
        if (config.get("public_manifest_sha256") is not None
                and digest_file(public / "PUBLIC_MANIFEST.json") != config["public_manifest_sha256"]):
            raise ValueError("Readout public manifest differs from enrollment")
        files = {item["path"]: item["sha256"] for item in manifest["files"]}
        public_inputs = {name: FileBinding(public / f"{name}.npz", files[f"{name}.npz"])
                         for name in ("train", "validation")}
        inference = {name: binding(value) for name, value in config["inference_by_split"].items()}
        if task_id == RESIDUAL_RECOVERY_TASK:
            from eegfm.eeg.residual_recovery_aggregation import ResidualRecoveryAggregator
            if "bootstrap_resamples" in config or "seed" in config:
                raise ValueError("Residual statistics have fixed seeds and resamples")
            validate_residual_qualification(config)
            return ResidualRecoveryAggregator(truth, train_truth, inference,
                public_by_split=public_inputs, qualification=binding(config["residual_data_qualification"]),
                runtime_identity=runtime,
                verify_runtime=(lambda: verify_readout_runtime(runtime)) if verify_runtime else None)
        from eegfm.eeg.readout_aggregation import ReadoutAggregator
        return ReadoutAggregator(truth, train_truth, inference,
            test_cohort=binding(config["test_cohort"]),
            public_by_split=public_inputs,
            runtime_identity=runtime,
            verify_runtime=(lambda: verify_readout_runtime(runtime)) if verify_runtime else None,
            bootstrap_resamples=config.get("bootstrap_resamples", 10000), seed=config.get("seed", 161803))
    from eegfm.eeg.aggregation import ScientificAggregator
    return ScientificAggregator(truth, train_truth, bootstrap_resamples=config.get("bootstrap_resamples", 2000))


def aggregator_source_sha256(task_id: str = DEFAULT_TASK) -> str:
    task_scope(task_id)
    name = {READOUT_TASK: "readout_aggregation.py", RESIDUAL_RECOVERY_TASK: "residual_recovery_aggregation.py"}.get(task_id, "aggregation.py")
    return digest_file(Path(__file__).with_name(name))


def episode_time_limits(config: dict[str, Any]) -> tuple[int, int]:
    task_id = config.get("task_id", DEFAULT_TASK)
    task_scope(task_id)
    wall_cap, session_cap = (2700, 600) if task_id == READOUT_TASK else (5400, 900)
    wall_default, session_default = wall_cap, session_cap
    if task_id == RESIDUAL_RECOVERY_TASK:
        wall_cap, session_cap = MAX_DELEGATED_EPISODE_SECONDS, MAX_DELEGATED_SESSION_SECONDS
        # Existing callers retain their allocation unless a new config declares it.
        wall_default, session_default = 2700, 240
    wall = config.get("episode_timeout_seconds", wall_default)
    session = config.get("session_timeout_seconds", session_default)
    if (type(wall) is not int or not 0 < wall <= wall_cap
            or type(session) is not int or not 0 < session <= session_cap):
        raise ValueError("Invalid episode/session timeout")
    return wall, session


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


def validate_scope(value: Any, task_id: str = DEFAULT_TASK) -> None:
    if not isinstance(value, dict) or any(type(value.get(key)) is not type(expected) or value.get(key) != expected
                                           for key, expected in task_scope(task_id).items()):
        raise ValueError("Protocol scope differs from frozen public task")


class EpisodeController(ResearchController):
    def __init__(self, *, task_id: str = DEFAULT_TASK,
                 session_guidance: str = "fixed_stages_v1", **kwargs: Any) -> None:
        task_scope(task_id)
        self.task_id = task_id
        self.session_guidance = session_guidance
        self.evidence_policy = task_evidence_policy(task_id)
        if task_id == RESIDUAL_RECOVERY_TASK:
            kwargs.setdefault("max_attempts", 1)
            if (type(kwargs["max_attempts"]) is not int or kwargs["max_attempts"] != 1
                    or kwargs.get("recovery_policy", "strict-v1") != "strict-v1"):
                raise ValueError("Residual recovery permits one iteration and no retries")
        if self.evidence_policy is not None:
            kwargs.setdefault("max_attempts", 2)
            kwargs.setdefault("recovery_policy", "validation-recovery-v1")
        guidance_identity = evidence_guidance_identity({"task_id": task_id, "session_guidance": session_guidance,
                                                       "max_attempts": kwargs.get("max_attempts", 2),
                                                       "recovery_policy": kwargs.get("recovery_policy", "strict-v1")})
        if task_id == RESIDUAL_RECOVERY_TASK:
            guidance_identity = {"validation_identity_release": "residual_baseline_identity_hash_v1"}
        # A separate task-bound enrollment preserves the base controller's v1
        # journal format while rejecting treatment drift even in direct use.
        guidance_path = Path(kwargs["trusted_root"]) / "runs" / kwargs["run_id"] / "EVIDENCE_GUIDANCE.json"
        if guidance_path.exists() and read_json(guidance_path) != {"task_id": task_id, **guidance_identity}:
            raise ValueError("Frozen evidence guidance identity changed")
        super().__init__(**kwargs)
        if guidance_identity:
            try:
                with guidance_path.open("xb") as handle:
                    handle.write(canonical_bytes({"task_id": task_id, **guidance_identity}))
            except FileExistsError:
                if read_json(guidance_path) != {"task_id": task_id, **guidance_identity}:
                    raise ValueError("Frozen evidence guidance identity changed")

    def projection(self) -> dict[str, Any]:
        projection = super().projection()
        if self.session_guidance == "adaptive_evidence_v1":
            with self._transaction() as db:
                maximum = self._load(db)["identity"]["max_attempts"]
            projection["evidence_status"] = validation_evidence_status(
                self.evidence_policy, projection, max_iterations=maximum)
        return projection

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if isinstance(request, dict) and request.get("operation") == "contract":
            payload = request.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("Contract payload must be an object")
            validate_scope(payload.get("protocol"), self.task_id)
        return super().handle(request)

    def _completion_ready(self, state: dict[str, Any]) -> None:
        super()._completion_ready(state)
        locked = next(attempt for attempt in state["attempts"] if attempt["id"] == state["lock"]["attempt_id"])
        final = state["jobs"][state["test_job"]].get("result", {}).get("metrics", {})
        if self.task_id == RESIDUAL_RECOVERY_TASK:
            self._residual_parity(state, state["lock"])
            if locked["kind"] != "iteration" or not self._residual_model_schema(final, 4):
                raise ValueError("Residual completion requires the final four-model test schema")
            return
        if self.task_id == READOUT_TASK:
            if (locked["kind"] != "iteration" or any(
                    metrics.get("readout_count", 0) < 2 or metrics.get("representation_readouts", 0) < 1
                    for metrics in (locked.get("metrics", {}), final))):
                raise ValueError("Completion requires multiple readouts including representation in locked validation and final test")
            return
        if (locked["kind"] != "iteration" or locked.get("metrics", {}).get("q1_groups", 0) <= 0
                or final.get("q1_groups", 0) <= 0):
            raise ValueError("Completion requires Q1 evidence from the locked validation iteration and final test")

    @staticmethod
    def _residual_model_schema(metrics: dict[str, Any], count: int) -> bool:
        return (metrics.get("model_count") == count and metrics.get("view_count") == 5
                and metrics.get("target_count") == 6 and metrics.get("baseline_only") == (count == 2)
                and metrics.get("numeric_scope_complete") == (count == 4))

    def _residual_parity(self, state: dict[str, Any], payload: Any) -> None:
        if not isinstance(payload, dict):
            raise ValueError("Residual lock payload required")
        baseline = [a for a in state["attempts"] if a["kind"] == "baseline"]
        selected = [a for a in state["attempts"] if a["id"] == payload.get("attempt_id") and a["kind"] == "iteration"]
        if len(baseline) != 1 or len(selected) != 1:
            raise ValueError("Residual lock requires baseline and final iteration")
        fingerprints = []
        for attempt, count in ((baseline[0], 2), (selected[0], 4)):
            if not self._validated_attempt(state, attempt):
                raise ValueError("Successful actual residual validation job required")
            keys = [key for key in attempt["jobs"] if state["jobs"][key]["split"] == "validation"]
            key = keys[0]
            job = state["jobs"][key]
            result = job["result"]
            if (job["job_id"] != key or job["attempt_id"] != attempt["id"]
                    or any(result.get(name) != job[name] for name in ("job_id", "candidate_digest", "split"))
                    or not self._residual_model_schema(result.get("metrics", {}), count)):
                raise ValueError("Residual fingerprint must belong to the actual matching validation job")
            fingerprints.append(residual_baseline_identity_sha(result))
        if selected[0]["candidate_digest"] != payload.get("candidate_digest") or fingerprints[0] != fingerprints[1]:
            raise ValueError("Residual baseline fingerprint parity required before lock")

    def _dispatch(self, state: dict[str, Any], operation: str, payload: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if self.task_id == RESIDUAL_RECOVERY_TASK and operation == "lock":
            self._residual_parity(state, payload)
        return super()._dispatch(state, operation, payload)

    def validate_done(self) -> None:
        # Base validation invokes this class's stricter _completion_ready on the
        # authoritative journal, including when resuming an already-done run.
        super().validate_done()


def review_brief(controller: EpisodeController, projection: dict[str, Any]) -> dict[str, Any]:
    if projection["episode_id"] != controller.episode_id:
        raise ValueError("Review episode mismatch")
    content = (controller.run / "RESEARCH_BRIEF.md").read_text(encoding="utf-8")
    match = re.match(r"\s*```json\s*\n(.*?)\n```\s*(.*)", content, flags=re.S)
    approved = False
    try:
        if match and len(match.group(2).strip()) >= 40:
            validate_scope(json.loads(match.group(1), object_pairs_hook=_unique_object), controller.task_id)
            approved = True
    except (ValueError, TypeError):
        pass
    return {"approved": approved, "reviewer_id": "frozen-scope-reviewer",
            "policy_sha256": review_policy_hash(controller.task_id, session_guidance=controller.session_guidance)}


def validate_residual_paper_public_task(value: Any) -> None:
    from eegfm.evaluation.paper import PUBLIC_FIELDS, VERSION

    def text(item: Any) -> bool:
        return isinstance(item, str) and bool(item.strip()) and "\x00" not in item

    if (not isinstance(value, dict) or set(value) != {"schema_version", "task_id", "revision"} | PUBLIC_FIELDS
            or value["schema_version"] != VERSION):
        raise ValueError("Expected the paper public task schema and fields")
    if not all(text(value[key]) for key in ("task_id", "revision", "question")) or any(
            not isinstance(value[key], list) or not value[key] or not all(map(text, value[key]))
            for key in ("resources", "constraints", "report_contract")):
        raise ValueError("Expected paper public question, identity and lists of public text")
    budget = value["budget"]
    if not isinstance(budget, dict) or not budget or any(type(cap) not in (int, float) or cap <= 0 for cap in budget.values()):
        raise ValueError("Expected paper public numeric budget")
    canonical_bytes(value)  # Also reject nonfinite numbers and invalid Unicode escapes.


def prepare_public(config: dict[str, Any], case: Path, private: Path) -> Path:
    """Export the explicit task allowlist and its enrolled optional resources."""
    task_id = config.get("task_id", DEFAULT_TASK)
    task_scope(task_id)
    evidence_guidance_identity(config)
    source, public = Path(config["public_source"]), case / "public"
    condition = config["condition"]
    if condition not in {"no_skill", "skill"} or (condition == "skill") != bool(config.get("skill")):
        raise ValueError("Condition requires exactly its matching optional skill")
    names = config["public_files"]
    if not isinstance(names, list) or len(set(names)) != len(names):
        raise ValueError("Explicit unique public allowlist required")
    paper_enabled = PAPER_TASK_RESOURCE in names
    if paper_enabled and task_id != RESIDUAL_RECOVERY_TASK:
        raise ValueError("The frozen paper task resource is reserved for residual recovery")
    if task_id in {READOUT_TASK, RESIDUAL_RECOVERY_TASK}:
        required = {"train.npz", "validation.npz", "eeg_api.py", "resources/CACHE_SCHEMA.json"}
        if paper_enabled:
            required.add(PAPER_TASK_RESOURCE)
        if set(names) != required:
            raise ValueError("Unexpected resource in the readout public allowlist")
    for name in names:
        safe_relative(name)
        if name not in {"train.npz", "validation.npz", "eeg_api.py"} and not name.startswith("resources/"):
            raise ValueError("Only sanitized data/API resources can be exported")
        if any(word in name.lower() for word in ("test", "reference", "private", "gold", "score")):
            raise ValueError("Private/reference material cannot be exported")
    if not {"train.npz", "validation.npz", "eeg_api.py"} <= set(names):
        raise ValueError("Missing train/validation/API public resources")
    from eegfm.common import ROOT
    docs = ROOT / "tasks" / TASKS[task_id][0]
    task_docs = DOCS + (("EVIDENCE_POLICY.json",) if task_id in EVIDENCE_TASKS else ())
    expected = {name: digest_file(source / name) for name in names if name != PAPER_TASK_RESOURCE}
    if paper_enabled:
        paper_path = source / PAPER_TASK_RESOURCE
        _regular(paper_path)
        with paper_path.open("rb") as stream:
            paper_bytes = stream.read(PAPER_TASK_MAX_BYTES + 1)
        if len(paper_bytes) > PAPER_TASK_MAX_BYTES:
            raise ValueError("Paper public task byte limit exceeded")
        validate_residual_paper_public_task(json.loads(paper_bytes.decode("utf-8"), object_pairs_hook=_unique_object))
        expected[PAPER_TASK_RESOURCE] = hashlib.sha256(paper_bytes).hexdigest()
    expected.update({name: digest_file(docs / name) for name in task_docs})
    if condition == "skill":
        expected["SKILL.md"] = binding(config["skill"]).sha256
    if public.exists():
        manifest = verify_public_bundle(public)
        if manifest["task_id"] != task_id:
            raise ValueError("Existing public task identity differs from enrollment")
        if {item["path"]: item["sha256"] for item in manifest["files"]} != expected:
            raise ValueError("Existing public bundle differs from frozen enrollment")
        return public
    stage = private / "public-staging"
    stage.mkdir(parents=True, exist_ok=False)
    for name in names:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == PAPER_TASK_RESOURCE:
            target.write_bytes(paper_bytes)
        else:
            _regular(source / name)
            shutil.copyfile(source / name, target)
    for name in task_docs:
        shutil.copyfile(docs / name, stage / name)
    if condition == "skill":
        shutil.copyfile(binding(config["skill"]).path, stage / "SKILL.md")
    if any(digest_file(stage / name) != value for name, value in expected.items()):
        raise ValueError("Public source changed during export")
    create_public_bundle(stage, public, expected, task_id=task_id, tier="real_eeg")
    return public


def frozen_skill_context(config: dict[str, Any], public: Path) -> tuple[str, str | None]:
    """Bind actual treatment bytes into the model prompt for the new protocol."""
    delivery = config.get("skill_delivery", "mounted-only-v1")
    if delivery not in {"mounted-only-v1", "inline-frozen-v1"}:
        raise ValueError("Unknown skill delivery policy")
    if delivery == "mounted-only-v1" or config["condition"] == "no_skill":
        return "", None
    source = binding(config["skill"])
    source.verify()
    raw = (public / "SKILL.md").read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != source.sha256:
        raise ValueError("Frozen skill prompt bytes differ from enrollment")
    return ("\nFROZEN_OPTIONAL_SKILL_SHA256 " + source.sha256 +
            "\nBEGIN_FROZEN_OPTIONAL_SKILL\n" + raw.decode("utf-8") +
            "\nEND_FROZEN_OPTIONAL_SKILL\n", source.sha256)


def session_prompt(projection: dict[str, Any], number: int, scientific_python: Path,
                   history: list[dict[str, Any]], *, task_id: str = DEFAULT_TASK,
                   session_guidance: str = "fixed_stages_v1") -> str:
    task_scope(task_id)
    evidence_guidance_identity({"task_id": task_id, "session_guidance": session_guidance})
    if not 1 <= number <= 6:
        raise ValueError("Session limit exceeded")
    docs_advice = "Read public/EVIDENCE_POLICY.json. " if task_id in EVIDENCE_TASKS else ""
    flow = ("The five-stage flow is brief; contract+baseline; attempt; lock+test; report. "
            "The sixth session is a correction allowance. ")
    if session_guidance == "adaptive_evidence_v1":
        flow = "Follow the trusted journal state. "
        if not projection.get("lock") and projection["state"]["status"] not in {"done", "blocked"}:
            flow += ("After iteration validation, inspect evidence_status and remaining iterations; "
                     "consider a useful revision before freezing within the same budget. "
                     "If evidence cannot be produced, report the limitation. ")
        flow += ("After lock, complete the frozen lifecycle and report without changing scientific choices or refitting. "
                "Coverage is advisory and does not establish scientific validity. ")
    return (f"You are the isolated research Actor for this single EEG episode ({task_id}). "
            "Read public/TASK.md, public/INTERFACE.md, public/API_README.md and "
            "public/PUBLIC_RESULT_SCHEMA.md; read public/SKILL.md if present. "
            "Use only these materials and your own case/output history. No other conversation is available.\n"
            f"Scientific Python: {scientific_python}\nSession: {number}/6. "
            f"Write requests to output/requests-session-{number:02d}.json and end the session. "
            + docs_advice + flow + "Keep research notes in output/. "
            "No request is executed before this session ends.\n"
            "TRUSTED_OWN_EPISODE_PROJECTION_JSON\n" + canonical_bytes(projection).decode()
            + "OWN_SESSION_RECEIPTS_JSON\n" + canonical_bytes(history).decode())


class NativeEpisodeLaunch:
    """One reservation and one fresh control home per actual native invocation."""
    def __init__(self, config: dict[str, Any], controller: ResearchController, private: Path,
                 public: Path, started_at: float) -> None:
        self.config, self.controller, self.private, self.public = config, controller, private, public
        self.wall_seconds, self.session_seconds = episode_time_limits(config)
        self.started_at = started_at
        self.history_path = private / "own-session-receipts.json"
        self.history = read_json(self.history_path) if self.history_path.exists() else []

    def __call__(self, projection: dict[str, Any]) -> dict[str, Any]:
        config = self.config
        sessions = [json.loads(line) for line in (self.controller.run / "sessions.jsonl").read_text().splitlines()]
        number = len(sessions)
        if not 1 <= number <= min(6, len(config["call_ids"])):
            raise BudgetExceeded("Episode call allocation exhausted")
        remaining = int(self.started_at + self.wall_seconds - time.time()) - 30
        if remaining < 1:
            raise BudgetExceeded("Episode wall deadline reached")
        timeout = min(self.session_seconds, remaining)
        call_id = config["call_ids"][number - 1]
        budget = Path(config["budget_path"])
        skill_context, injected_skill_sha256 = frozen_skill_context(config, self.public)
        prompt = session_prompt(projection, number, Path(config["scientific_python"]), self.history,
                                task_id=config.get("task_id", DEFAULT_TASK),
                                session_guidance=config.get("session_guidance", "fixed_stages_v1")) + skill_context
        reserve_call(budget, call_id, "actor", timeout)
        output = self.private / "launches" / f"session-{number:02d}-{call_id}"
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
                read_only_roots=tuple(Path(path) for path in config["scientific_roots"]),
                auth_mode="readonly_bind")
            validate_isolation_gate(metadata, gate)
            mark_call(budget, call_id, "running", episode_id=self.controller.episode_id,
                      session=number, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                      injected_skill_sha256=injected_skill_sha256)
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
        usage = cli_usage(report["stdout"])
        mark_call(budget, call_id, status if running else "blocked", evidence=str(output),
                  episode_id=self.controller.episode_id, session=number, usage=usage)
        self.history.append({"session": number, "status": status, "actual_native_invocation": invoked,
                             "injected_skill_sha256": injected_skill_sha256,
                             "verified_model_turn": verified_turn and clean,
                             "usage": usage,
                             "request_count": len(report["requests"]),
                             "feedback": report["stderr"] if report["stderr"].startswith("Trusted launch/") else ""})
        write_atomic(self.history_path, self.history)
        write_atomic(self.private / "launch-receipts" / f"session-{number:02d}.json",
                     {key: value for key, value in report.items() if key not in {"stdout", "stderr"}})
        return report


def validate_cloud_bindings(remote: dict[str, Any], train: FileBinding,
                            validation: FileBinding, test: FileBinding,
                            expected_identity: dict[str, Any], aggregate_source_sha256: str) -> None:
    """Cloud paths may differ; the data and trusted aggregation must not."""
    expected = {"validation": validation, "test": test}
    try:
        worker = remote["worker"]
        matches = all(worker["inputs"][name]["train"]["sha256"] == train.sha256
                      and worker["inputs"][name]["evaluation"]["sha256"] == value.sha256
                      for name, value in expected.items())
        matches = (matches and all(remote[key] == value for key, value in expected_identity.items())
                   and worker["aggregate_source_sha256"] == aggregate_source_sha256)
        if expected_identity.get("task_id") in {READOUT_TASK, RESIDUAL_RECOVERY_TASK}:
            matches = matches and worker["aggregate_policy_sha256"] == expected_identity["aggregate_policy_sha256"]
        if expected_identity.get("task_id") == RESIDUAL_RECOVERY_TASK:
            matches = matches and worker.get("validation_identity_release") == "residual_baseline_identity_hash_v1"
    except (KeyError, TypeError):
        matches = False
    if not matches:
        raise ValueError("Trusted cloud data/aggregation differs from episode enrollment")


def validate_private_boundaries(case: Path, protected: list[Path], roots: tuple[Path, ...]) -> None:
    case = case.resolve()
    roots = tuple(root.resolve(strict=True) for root in roots)
    for path in protected:
        path = path.resolve()
        if path == case or case in path.parents:
            raise ValueError("Private bindings cannot be mounted inside Actor case")
        if any(root == path or root in path.parents or path in root.parents for root in roots):
            raise ValueError("Private bindings cannot overlap Actor scientific runtime")


class DeadlineEvaluator:
    sandboxed = True

    def __init__(self, evaluator: Any, started_at: float, *, timeout_seconds: int = 5400,
                 deadline_epoch: float | None = None) -> None:
        if type(timeout_seconds) is not int or not 0 < timeout_seconds <= 5400:
            raise ValueError("Invalid episode timeout")
        self.evaluator, self.started_at = evaluator, started_at
        self.deadline_epoch = started_at + timeout_seconds if deadline_epoch is None else deadline_epoch
        if (type(self.deadline_epoch) not in (int, float)
                or not started_at < self.deadline_epoch <= started_at + timeout_seconds):
            raise ValueError("Invalid absolute episode deadline")
        if hasattr(evaluator, "deadline_epoch"):
            evaluator.deadline_epoch = self.deadline_epoch

    def submit(self, spec: EvaluationSpec) -> dict[str, Any]:
        operation_timeout = getattr(self.evaluator, "operation_timeout_seconds", self.evaluator.timeout)
        if time.time() + operation_timeout + 30 > self.deadline_epoch:
            raise BudgetExceeded("Insufficient episode time for allocated worker")
        return self.evaluator.submit(spec)

    def poll(self, job_id: str) -> dict[str, Any]:
        return self.evaluator.poll(job_id)


class EpisodeDriver(ResearchDriver):
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
    if config.get('schema_version') == 'audited_coding_episode_v1':
        return run_delegated_episode(config)
    if config.get('task_id') == RESIDUAL_RECOVERY_TASK:
        raise ValueError("Residual recovery requires the audited delegated route")
    if os.name != "posix":
        raise RuntimeError("Native isolated episodes require Linux")
    if config.get("schema_version") != "real_episode_config_v1":
        raise ValueError("Unsupported episode enrollment")
    if config.get("auth_mode", "readonly_bind") != "readonly_bind":
        raise ValueError("Research episodes require read-only authentication binding")
    task_id = config.get("task_id", DEFAULT_TASK)
    scope = task_scope(task_id)
    evidence_guidance_identity(config)
    wall_seconds, _ = episode_time_limits(config)
    recovery_policy = config.get("recovery_policy", "validation-recovery-v1" if task_id in EVIDENCE_TASKS else "strict-v1")
    if not isinstance(recovery_policy, str) or recovery_policy not in RECOVERY_POLICIES:
        raise ValueError("Unsupported recovery policy")
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
    roots = tuple(Path(path).resolve(strict=True) for path in config["scientific_roots"])
    if not roots:
        raise ValueError("The read-only scientific runtime must be explicit")
    native_binary = Path(config["native_binary"])
    live_report = read_json(gate.path)
    validate_isolation_gate({"native_binary_sha256": digest_file(native_binary),
        "code_mode_host_sha256": digest_file(native_binary.parent / "codex-code-mode-host"),
        "bwrap_sha256": digest_file(Path(config["bwrap"])),
        "profile_template_sha256": profile_template_sha256(MODEL, read_only_roots=roots),
        "read_only_roots": [str(path) for path in roots],
        "auth_mode": "readonly_bind",
        "transport_template_sha256": readonly_transport_sha256()}, live_report)
    if any(live_report.get("probes", {}).get(name, {}).get("allowed") is not False
           for name in ("test_features", "split_manifest", "driver_state")):
        raise ValueError("Live certificate lacks sealed-test/controller denial evidence")
    aggregate = load_aggregator(config, public_root=public, verify_runtime=not bool(config.get("cloud_worker")))
    truth, train_truth = aggregate.truth, aggregate.train_truth
    readout_private = []
    if task_id == READOUT_TASK:
        readout_private = [*(value.path for value in aggregate.inference.values()), aggregate.test_cohort.path]
        if (aggregate.inference["validation"].sha256 != validation.sha256
                or aggregate.inference["test"].sha256 != test.sha256):
            raise ValueError("Readout scorer inference differs from worker inputs")
    validate_private_boundaries(case, [private, split.path, validation.path, test.path, runtime_manifest.path,
                      gate.path, Path(config["auth_source"]), Path(config["budget_path"]),
                      *(value.path for value in truth.values()), train_truth.path, *readout_private], roots)
    if train.sha256 != digest_file(public / "train.npz"):
        raise ValueError("Worker training view differs from Actor training view")
    public_hash = digest_file(public / "PUBLIC_MANIFEST.json")
    if config.get("cloud_worker"):
        from eegfm.evaluation.ssh_worker import SshWorkerEvaluator, scientific_identity
        cloud = config["cloud_worker"]
        remote_config = cloud["config"]
        if set(remote_config) != {"path", "sha256"} or not Path(remote_config["path"]).is_absolute():
            raise ValueError("Explicit absolute cloud config binding required")
        worker = SshWorkerEvaluator(host=cloud["host"], port=cloud["port"], user=cloud["user"],
            known_hosts=binding(cloud["known_hosts"]), remote_python=Path(cloud["python"]),
            remote_code=Path(cloud["code"]),
            remote_config=FileBinding(Path(remote_config["path"]), remote_config["sha256"]),
            journal_root=private / "cloud-worker-journal")
        expected_identity = scientific_identity(config, aggregate=aggregate,
            public_manifest_sha256=public_hash, split_manifest_sha256=split.sha256)
        validate_cloud_bindings(worker.identity, train, validation, test, expected_identity,
                                aggregator_source_sha256(task_id))
    else:
        runtime = RuntimeConfig(bwrap=Path(config["bwrap"]), python=Path(config["scientific_python"]),
            environment_roots=tuple(Path(path) for path in config["scientific_roots"]), manifest=runtime_manifest)
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
                "model": MODEL, "effort": "medium", "session_limit": len(call_ids), "wall_seconds": wall_seconds,
                "auth_mode": "readonly_bind",
                "task_id": task_id, "task_scope": scope,
                "review_policy_sha256": review_policy_hash(task_id, session_guidance=config.get("session_guidance", "fixed_stages_v1")),
                "runner_sha256": digest_file(Path(__file__)),
                "actor_source_sha256": digest_file(Path(__file__).resolve().parents[1] / "agent/actor.py"),
                "bridge_source_sha256": digest_file(Path(__file__).resolve().parents[1] / "agent/controller.py"),
                "science_source_sha256": digest_file(Path(__file__).with_name("statistics.py")),
                "data_source_sha256": digest_file(Path(__file__).with_name("data.py")),
                "live_isolation_report_sha256": gate.sha256}
    identity.update(evidence_guidance_identity(config, public))
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
        split_manifest_sha256=split.sha256, evaluator=DeadlineEvaluator(worker, enrolled["started_at_epoch"], timeout_seconds=wall_seconds),
        max_attempts=config.get("max_attempts", 2),
        recovery_policy=recovery_policy, task_id=task_id,
        session_guidance=config.get("session_guidance", "fixed_stages_v1"))
    launcher = NativeEpisodeLaunch(config, controller, private, public, enrolled["started_at_epoch"])
    driver = EpisodeDriver(controller, launch=launcher, reviewer=lambda projection: review_brief(controller, projection),
                          max_sessions=len(call_ids), poll=1.0)
    driver.episode_deadline = enrolled["started_at_epoch"] + wall_seconds
    try:
        exit_code = driver.loop()
    except ControllerAlreadyRunning:
        # A second observer must not block or overwrite the healthy owner's run.
        raise
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


def validate_delegated_config(config: dict[str, Any]) -> dict[str, Any]:
    """Explicit historical-readout admission; never inspect native credentials."""
    if (config.get('schema_version') != 'audited_coding_episode_v1' or config.get('task_id') not in {READOUT_TASK, RESIDUAL_RECOVERY_TASK}
            or not supported_native_identity(config.get('model'), config.get('reasoning_effort'))):
        raise ValueError('Explicit audited historical-readout provider required')
    if any(name in config for name in ('auth_source', 'auth_mode', 'native_binary', 'isolation_report', 'proxy_url', 'bwrap')):
        raise ValueError('Audited provider config must not carry native authentication/isolation fields')
    wall, timeout = episode_time_limits(config)
    if not 180 <= timeout <= MAX_DELEGATED_SESSION_SECONDS or wall > MAX_DELEGATED_EPISODE_SECONDS:
        raise ValueError('Audited session allocation must be 180-480 seconds within 4200 seconds')
    if 'episode_deadline_epoch' in config and (type(config['episode_deadline_epoch']) is not int
                                               or config['episode_deadline_epoch'] <= 0):
        raise ValueError('Absolute episode deadline must be a positive integer epoch')
    timing = config.get('provider', {}).get('native_timing')
    if timing is not None and (not isinstance(timing, dict) or 'episode_deadline_epoch' not in config
                               or timing.get('episode_deadline_epoch') != config['episode_deadline_epoch']):
        raise ValueError('Native timing must retain the exact episode deadline')
    calls = config.get('call_ids')
    if (not isinstance(calls, list) or not 1 <= len(calls) <= 6 or len(set(calls)) != len(calls)
            or any(not isinstance(item, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', item) is None for item in calls)):
        raise ValueError('One to six unique declared model calls required')
    if config['task_id'] == RESIDUAL_RECOVERY_TASK:
        if (type(config.get('max_attempts', 1)) is not int or config.get('max_attempts', 1) != 1
                or config.get('recovery_policy', 'strict-v1') != 'strict-v1'):
            raise ValueError('Residual recovery permits one iteration and no retries')
        return validate_residual_qualification(config)
    proof_binding = binding(config['historical_data_qualification'])
    proof = read_json(proof_binding.path)
    if (proof.get('status') != 'exact_historical_readout_inputs_qualified_for_development_replay'
            or proof.get('not_project_unseen_confirmation') is not True or not proof.get('previous_successful_test_job')):
        raise ValueError('A successful exact historical test provenance receipt is required')
    roles = {row['role']: row['sha256'] for row in proof['bindings']}
    expected = {'public_train': config['train_input'], 'public_validation': config['public_validation_input'],
                **{'inference_' + name: item for name, item in config['inference_by_split'].items()},
                'truth_train': config['train_truth'], **{'truth_' + name: item for name, item in config['truth_by_split'].items()},
                'cohort': config['test_cohort'], 'split_manifest': config['split_manifest']}
    if len(roles) != len(proof['bindings']) or set(roles) != set(expected):
        raise ValueError('Historical data roles are incomplete or duplicated')
    for role, value in expected.items():
        if binding(value).sha256 != roles[role]:
            raise ValueError('Episode data differs from exact historical role: ' + role)
    if (binding(config['validation_input']).sha256 != roles['inference_validation']
            or binding(config['test_input']).sha256 != roles['inference_test']):
        raise ValueError('Worker inference differs from historical replay inputs')
    return proof


def delegated_deadline(config: dict[str, Any], started_at: float) -> float:
    """Bind a prospective deadline to the original enrollment and model budget."""
    wall, _ = episode_time_limits(config)
    if 'episode_deadline_epoch' not in config:
        return started_at + wall
    deadline = config['episode_deadline_epoch']
    if type(deadline) is not int or not started_at < deadline <= started_at + wall:
        raise ValueError('Absolute episode deadline is outside the original allocation')
    budget = read_json(Path(config['budget_path']))
    try:
        end = datetime.fromisoformat(budget['deadline_at'])
        cutoff = datetime.fromisoformat(budget['stop_new_research_at'])
        if (end.utcoffset() is None or cutoff.utcoffset() is None
                or end.timestamp() != deadline or cutoff.timestamp() > deadline):
            raise ValueError('Model budget differs from the fixed episode deadline')
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Model budget must bind the same absolute deadline') from error
    return deadline


def run_delegated_episode(config: dict[str, Any]) -> dict[str, Any]:
    """Opt-in audited model provider; retain existing scientific lifecycle gates."""
    from eegfm.agent.provider import PROVIDER, ProviderMailbox, ProviderLaunch, read_trusted_receipt
    from eegfm.evaluation.public_workbench import PublicWorkbench
    from eegfm.evaluation.ssh_worker import SshWorkerEvaluator, scientific_identity
    validate_delegated_config(config)
    task_id = config['task_id']
    residual = task_id == RESIDUAL_RECOVERY_TASK
    if os.name != 'posix':
        raise RuntimeError('The trusted ResearchDriver controller remains on Linux')
    case, private = Path(config['case_root']), Path(config['trusted_root'])
    if not case.is_absolute() or not private.is_absolute() or case == private or case in private.parents or private in case.parents:
        raise ValueError('Absolute disjoint provider case and trusted roots required')
    if case.exists() and any(case.iterdir()) and not (private / 'ENROLLMENT.json').is_file():
        raise ValueError('Fresh provider enrollment requires a fresh case')
    for path in (case, private):
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Provider roots cannot contain links')
        path.mkdir(parents=True, exist_ok=True)
    (case / 'output').mkdir(exist_ok=True)
    public = prepare_public(config, case, private)
    train, validation, test = (binding(config[name]) for name in ('train_input', 'validation_input', 'test_input'))
    split = binding(config['split_manifest'])
    aggregate = load_aggregator(config, public_root=public, verify_runtime=False)
    public_hash = digest_file(public / 'PUBLIC_MANIFEST.json')
    if digest_file(public / 'train.npz') != train.sha256 or digest_file(public / 'validation.npz') != binding(config['public_validation_input']).sha256:
        raise ValueError('Provider public resources differ from bound historical data')
    protected = [private, split.path, validation.path, test.path, Path(config['budget_path']),
                 aggregate.train_truth.path, *(item.path for item in aggregate.truth.values()),
                 *(item.path for item in aggregate.inference.values()),
                 aggregate.qualification.path if residual else aggregate.test_cohort.path,
                 *(item.path for item in aggregate.source_bindings)]
    validate_private_boundaries(case, protected, ())

    def cloud_worker(value: dict, journal: Path) -> SshWorkerEvaluator:
        remote = value['config']
        if set(remote) != {'path', 'sha256'} or not Path(remote['path']).is_absolute():
            raise ValueError('Fixed remote worker config required')
        return SshWorkerEvaluator(host=value['host'], port=value['port'], user=value['user'],
            known_hosts=binding(value['known_hosts']), remote_python=Path(value['python']), remote_code=Path(value['code']),
            remote_config=FileBinding(Path(remote['path']), remote['sha256']), journal_root=journal)

    worker = cloud_worker(config['cloud_worker'], private / 'cloud-worker-journal')
    expected = scientific_identity(config, aggregate=aggregate, public_manifest_sha256=public_hash, split_manifest_sha256=split.sha256)
    validate_cloud_bindings(worker.identity, train, validation, test, expected, aggregator_source_sha256(task_id))
    fit_worker = cloud_worker(config['public_fit_worker'], private / 'public-fit-worker-journal')
    from eegfm.evaluation.public_workbench import MODE
    fit_identity = fit_worker.identity
    if (fit_identity.get('episode_id') != config['episode_id'] or fit_identity.get('run_id') != config['run_id']
            or fit_identity.get('public_manifest_sha256') != public_hash
            or fit_identity.get('worker', {}).get('public_artifact_mode') != MODE
            or fit_identity.get('worker', {}).get('allowed_splits') != ['validation']
            or ('episode_deadline_epoch' in config
                and fit_identity.get('episode_deadline_epoch') != config['episode_deadline_epoch'])):
        raise ValueError('Public fit worker is not bound to this case/public-only capability')
    if worker.timeout > (120 if residual else 180) or fit_worker.timeout > (90 if residual else 120):
        raise ValueError('Audited scientific/public fit timeout exceeds task allocation')
    identity = {'schema_version': 'audited_coding_enrollment_v1', 'config_sha256': hashlib.sha256(canonical_bytes(config)).hexdigest(),
                'execution_mode': PROVIDER, 'public_manifest_sha256': public_hash, 'worker': worker._enrollment(),
                'public_fit_worker': fit_worker._enrollment(), 'runner_sha256': digest_file(Path(__file__)),
                'controller_source_sha256': digest_file(Path(__file__).resolve().parents[1] / 'agent/controller.py'),
                **({'residual_qualification_sha256': config['residual_data_qualification']['sha256']} if residual else
                   {'historical_provenance_sha256': config['historical_data_qualification']['sha256']}),
                **evidence_guidance_identity(config, public)}
    enrollment_path = private / 'ENROLLMENT.json'
    if enrollment_path.exists():
        enrollment = read_json(enrollment_path, maximum_bytes=8 * 1024**2)
        if enrollment['identity'] != identity:
            raise ValueError('Audited coding enrollment drift')
    else:
        enrollment = {'identity': identity, 'started_at_epoch': time.time()}
        if 'episode_deadline_epoch' in config:
            enrollment['deadline_epoch'] = delegated_deadline(config, enrollment['started_at_epoch'])
        with enrollment_path.open('xb') as stream:
            stream.write(canonical_bytes(enrollment))
    wall, timeout = episode_time_limits(config)
    deadline = delegated_deadline(config, enrollment['started_at_epoch'])
    if 'episode_deadline_epoch' in config and enrollment.get('deadline_epoch') != deadline:
        raise ValueError('Original enrollment deadline changed')
    if time.time() >= deadline:
        raise BudgetExceeded('Original episode deadline reached')
    controller = EpisodeController(trusted_root=private / 'controller', case_root=case,
        episode_id=config['episode_id'], run_id=config['run_id'], public_manifest_sha256=public_hash,
        split_manifest_sha256=split.sha256, evaluator=DeadlineEvaluator(worker, enrollment['started_at_epoch'],
                                                                       timeout_seconds=wall, deadline_epoch=deadline),
        max_attempts=config.get('max_attempts', 1 if residual else 2), task_id=task_id,
        recovery_policy=config.get('recovery_policy', 'strict-v1'), session_guidance=config.get('session_guidance', 'fixed_stages_v1'))

    def workbench(pending_case: Path) -> PublicWorkbench:
        relative = pending_case.resolve().relative_to((controller.run / 'provider/sessions').resolve())
        if len(relative.parts) != 2 or relative.parts[-1] != 'case':
            raise ValueError('Public fitting belongs to a declared provider session')
        fit_worker.deadline_epoch = deadline
        return PublicWorkbench(evaluator=fit_worker, private_root=controller.run / 'provider/fit-journals' / relative.parts[0],
            case_root=pending_case, episode_id=config['episode_id'], run_id=config['run_id'],
            public_manifest_sha256=public_hash, split_manifest_sha256=fit_worker.identity['split_manifest_sha256'])

    provider = config['provider']
    provider_enrollment = {**provider, 'episode_id': config['episode_id'], 'run_id': config['run_id'],
        'model': config['model'], 'effort': config['reasoning_effort'], 'session_limit': len(config['call_ids']),
        'session_timeout_seconds': timeout,
        'study_disclosure': 'Historical readout train/validation/test bytes have previously been used by this project. Test is withheld from this researcher until lock for workflow replay only; it is not project-unseen confirmation. Common inherited project history may include high-level prior readout findings. No blind capability or research-gain claim follows.'}
    if residual:
        provider_enrollment['study_disclosure'] = ('Cached EEGMAT residual inputs include six final-test participants and prior project test exposure. '
            'Test is withheld from this researcher until lock, not project-unseen confirmation. Common project history is inherited. '
            'Additional recovery beyond the finite affine comparator does not establish intrinsic nonlinearity, causal reliance, method gain or RSI.')
    mailbox = ProviderMailbox(root=controller.run / 'provider', case_root=case, public_root=public,
                              enrollment=provider_enrollment, workbench_factory=workbench)
    service = {'schema_version': 'audited_provider_service_v1', 'mailbox_root': str(mailbox.root),
               'case_root': str(case), 'public_root': str(public), 'enrollment': provider_enrollment,
               'public_fit_worker': config['public_fit_worker'], 'public_fit_journal': str(private / 'public-fit-worker-journal'),
               'episode_deadline_epoch': deadline}
    service_path = mailbox.root / 'SERVICE.json'
    if service_path.exists() and read_json(service_path) != service:
        raise ValueError('Frozen provider service changed')
    if not service_path.exists():
        write_atomic(service_path, service)
    launcher = ProviderLaunch(mailbox, budget_path=Path(config['budget_path']), call_ids=config['call_ids'])
    driver = EpisodeDriver(controller, launch=launcher, reviewer=lambda projection: review_brief(controller, projection),
        max_sessions=len(config['call_ids']), session_provider=PROVIDER, provider_model=config['model'], provider_timeout_seconds=timeout, poll=1.)
    driver.episode_deadline = deadline
    try:
        exit_code = driver.loop()
    except ControllerAlreadyRunning:
        raise
    except Exception as error:
        if controller.projection()['state']['status'] != 'done':
            controller.block('Audited provider orchestration stopped: ' + type(error).__name__)
        write_atomic(private / 'orchestration-error.json', {'error_type': type(error).__name__})
        exit_code = 3
    projection = controller.projection()
    write_atomic(private / 'FINAL_PUBLIC_PROJECTION.json', projection)
    result = {'schema_version': 'audited_coding_result_v1', 'execution_mode': PROVIDER,
              'episode_id': config['episode_id'], 'run_id': config['run_id'], 'exit_code': exit_code,
              'state': projection['state'], 'actual_native_isolated_invocations': 0,
              'historical_development_replay': True,
              'scientific_completion': 'Existing full lifecycle gates retained; source/refit/prediction/claim review remains separate.',
              'boundary': 'Audited delegated context with declared inherited history, separate scientific Docker; not native model OS isolation or blind confirmation.'}
    write_atomic(private / 'EPISODE_RESULT.json', result)
    return result
