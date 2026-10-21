"""Controlled emotion state-vs-trait study with a Meta rule comparison.

The study is intentionally small: one Meta decision, two baseline research runs,
and only if Meta accepts a rule, two independent rule-augmented runs.  Every run
uses the same frozen material package, model backend, prompts, and per-run
limits.  No real EEG data are read or trained on.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .backends import (
    BackendRegistry,
    backend_public_info,
    create_chat_client,
    load_registry,
)
from .ledger import BudgetExceeded, BudgetLedger, LedgerError
from .meta import run_meta
from .research import ResearchConfig, ResearchRunner
from .run_manifest import sha256_file, sha256_text
from .storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now

STUDY_CONFIG = Path("archive/experiments/emotion_20261021/configs/study.json")
BACKENDS_CONFIG = Path("configs/models/backends_20261021.json")
LOCK_PATH = Path("archive/experiments/emotion_20261021/runs/flash_emotion_20261021/study_lock.json")


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    run_id: str
    arm: Literal["baseline", "meta_rule"]
    repeat: int
    run_dir: str
    phase: str
    accepted: bool
    acceptance: str
    stop_reason: str
    model_calls: int
    tool_calls: int
    final_path: str
    cost_cny: float = 0.0
    retry_of: str = ""


class StudyState(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    study_id: str
    phase: str = "pending"
    meta_decision: dict[str, object] | None = None
    runs: list[RunRecord] = Field(default_factory=list)
    stop_reason: str = ""
    started_at: str = ""
    updated_at: str = ""


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_study(path: Path = STUDY_CONFIG) -> dict[str, object]:
    return _read_json(path)


def make_ledger(study: dict[str, object], registry: BackendRegistry) -> BudgetLedger:
    budget = study["budget"]
    backend = registry.chat(str(study["model_backend"]))
    if backend.price is None:
        raise RuntimeError("selected chat backend has no price config")
    return BudgetLedger(
        Path(str(study["paths"]["budget_ledger"])),
        run_id=str(study["run_id"]),
        cap_cny=float(budget["project_api_cost_cny_cap"]),
        wrap_up_reserve_cny=float(budget["wrap_up_reserve_cny"]),
        model_attempts_limit=int(budget["model_attempts_cap"]),
        search_attempts_limit=int(budget["search_attempts_cap"]),
        fetch_attempts_limit=int(budget["fetch_attempts_cap"]),
        input_tokens_limit=int(budget["input_tokens_cap"]),
        output_tokens_limit=int(budget["output_tokens_cap"]),
        input_price_cny_per_mtok=backend.price.input_cache_miss_peak_cny_per_mtok,
        output_price_cny_per_mtok=backend.price.output_peak_cny_per_mtok,
        tool_price_cny_per_request=backend.price.search_cny_per_success,
        price_source=backend.price.source,
        price_checked_at=backend.price.checked_at,
    )


def _assert_lock(study: dict[str, object]) -> None:
    lock = _read_json(LOCK_PATH)
    checks = {
        "question_sha256": hashlib.sha256(str(study["question"]).encode("utf-8")).hexdigest(),
        "material_manifest_sha256": sha256_file(Path(str(study["materials"]["manifest_path"]))),
        "rubric_sha256": sha256_file(Path("configs/eval/emotion_rubric_v1.json")),
        "baseline_rule_sha256": sha256_file(Path(str(study["rules"]["baseline"]["path"]))),
        "system_prompt_sha256": sha256_file(Path(str(study["prompt"]["system_prompt_path"]))),
    }
    for key, value in checks.items():
        if lock.get(key) != value:
            raise RuntimeError(f"frozen study artifact changed: {key}")


def _state_path(study: dict[str, object]) -> Path:
    return Path(str(study["paths"]["run_root"])) / "study_state.json"


def _load_state(study: dict[str, object]) -> StudyState:
    path = _state_path(study)
    if path.exists():
        return StudyState.model_validate_json(path.read_text(encoding="utf-8"))
    return StudyState(study_id=str(study["study_id"]), started_at=utc_now(), updated_at=utc_now())


def _save_state(study: dict[str, object], state: StudyState) -> None:
    state.updated_at = utc_now()
    atomic_write_json(_state_path(study), state.model_dump(mode="json"))


def _review_files(study: dict[str, object]) -> list[Path]:
    return [Path(item) for item in study["rules"]["meta"]["allowed_review_files"]]


def run_meta_stage(
    study: dict[str, object],
    registry: BackendRegistry,
    ledger: BudgetLedger,
) -> dict[str, object]:
    meta_dir = ensure_dir(Path(str(study["paths"]["meta_dir"])))
    decision_path = meta_dir / "meta_decision.json"
    if decision_path.exists():
        return _read_json(decision_path)
    old_run = Path(str(study["rules"]["meta"]["source_run"]))
    client = create_chat_client(
        registry,
        str(study["meta"]["model_backend"]),
        ledger=ledger,
        attribution="meta",
    )
    try:
        decision = run_meta(
            client,
            old_run_dir=old_run,
            review_files=_review_files(study),
            out_dir=meta_dir,
            allowed_source_ids=[
                "literature_v1:final_answer",
                "literature_v1:final_json",
                "review:EVIDENCE_AUDIT",
                "review:REASONING_REVIEW",
            ],
            max_output_tokens=int(study["meta"]["max_output_tokens"]),
        )
    except (BudgetExceeded, LedgerError) as error:
        decision = {
            "accepted": False,
            "decision": "blocked",
            "reason": f"Meta budget/ledger error: {type(error).__name__}: {error}",
            "rule_text": "",
            "created_at": utc_now(),
        }
        atomic_write_json(decision_path, decision)
    return decision


def _rule_text_for_run(study: dict[str, object], meta_decision: dict[str, object], arm: str) -> tuple[Path, str]:
    baseline_path = Path(str(study["rules"]["baseline"]["path"]))
    baseline = baseline_path.read_text(encoding="utf-8")
    if arm == "baseline":
        return baseline_path, str(study["rules"]["baseline"]["version"])
    rule_text = str(meta_decision.get("rule_text", "")).strip()
    if not rule_text:
        raise RuntimeError("meta_rule arm requested without an accepted rule text")
    combined = (
        baseline.rstrip()
        + "\n\n## Frozen Meta rule (only addition)\n\n"
        + rule_text.strip()
        + "\n"
    )
    digest = sha256_text(combined)[:10]
    version = f"{study['rules']['baseline']['version']}+meta_{digest}"
    combined_dir = ensure_dir(Path(str(study["paths"]["meta_dir"])) / "rule_snapshots")
    target = combined_dir / f"{version}.md"
    if target.exists() and target.read_text(encoding="utf-8") != combined:
        raise RuntimeError(f"combined rule snapshot changed: {target}")
    atomic_write_text(target, combined)
    return target, version


def _run_config(
    study: dict[str, object],
    *,
    arm: str,
    repeat: int,
    rule_path: Path,
    rule_version: str,
    registry: BackendRegistry,
) -> ResearchConfig:
    limits = study["run_limits"]
    run_id = f"{study['run_id']}__{arm}__{repeat:02d}"
    run_dir = Path(str(study["paths"]["runs_dir"])) / arm / f"repeat_{repeat:02d}"
    return ResearchConfig(
        run_id=run_id,
        run_dir=str(run_dir),
        question=str(study["question"]),
        deadline=str(study["deadline"]),
        stop_new_at=str(study["stop_new_at"]),
        system_prompt_path=str(study["prompt"]["system_prompt_path"]),
        deliverables=[str(item) for item in study["deliverables"]],
        materials_manifest_path=str(study["materials"]["manifest_path"]),
        material_evidence_dir=str(study["materials"]["evidence_dir"]),
        material_version=str(study["materials"]["version"]),
        material_manifest_sha256=str(study["materials"]["freeze_sha256"]),
        rule_text_path=str(rule_path),
        rule_version=rule_version,
        research_mode="materials_only",
        max_model_calls=int(limits["max_model_calls"]),
        max_tool_calls=int(limits["max_tool_calls"]),
        max_turns=int(limits["max_turns"]),
        max_model_calls_per_turn=int(limits["max_model_calls_per_turn"]),
        max_tool_calls_per_turn=int(limits["max_tool_calls_per_turn"]),
        max_output_tokens=int(limits["max_output_tokens"]),
        max_output_tokens_retry=int(limits["max_output_tokens_retry"]),
        context_char_target=int(limits["context_char_target"]),
        study_config=study,
        model_info=backend_public_info(registry.chat(str(study["model_backend"]))),
        tool_info=backend_public_info(registry.tool(str(study["tool_backend"]))),
        ledger_path=str(study["paths"]["budget_ledger"]),
        code_root=".",
    )


def _assert_active_study(study: dict[str, object]) -> None:
    if bool(study.get("archive")) or str(study.get("paths", {}).get("run_root", "")).startswith("archive/"):
        raise RuntimeError(
            "this study is archived and read-only; do not run, retry, or rewrite it. "
            "Use the new `study` entry point for new work."
        )


def run_study(study_path: Path = STUDY_CONFIG) -> dict[str, object]:
    study = load_study(study_path)
    _assert_active_study(study)
    _assert_lock(study)
    registry = load_registry(BACKENDS_CONFIG)
    ledger = make_ledger(study, registry)
    state = _load_state(study)
    if state.phase in {"completed", "blocked"}:
        return state.model_dump(mode="json")
    state.phase = "running"
    state.started_at = state.started_at or utc_now()
    _save_state(study, state)

    if state.meta_decision is None:
        try:
            state.meta_decision = run_meta_stage(study, registry, ledger)
        except Exception as error:  # noqa: BLE001 - Meta failure must not fabricate a rule
            state.meta_decision = {
                "accepted": False,
                "decision": "blocked",
                "reason": f"Meta stage error: {type(error).__name__}: {error}",
                "rule_text": "",
                "created_at": utc_now(),
            }
        _save_state(study, state)

    arms: list[tuple[str, int]] = [("baseline", 1), ("baseline", 2)]
    meta_decision = state.meta_decision or {}
    if bool(meta_decision.get("accepted")):
        arms.extend([("meta_rule", 1), ("meta_rule", 2)])

    for arm, repeat in arms:
        existing = next((item for item in state.runs if item.run_id.endswith(f"{arm}__{repeat:02d}")), None)
        if existing is not None and existing.phase in {"completed", "completed_unverified"}:
            continue
        rule_path, rule_version = _rule_text_for_run(study, meta_decision, arm)
        config = _run_config(
            study,
            arm=arm,
            repeat=repeat,
            rule_path=rule_path,
            rule_version=rule_version,
            registry=registry,
        )
        try:
            client = create_chat_client(
                registry,
                str(study["model_backend"]),
                ledger=ledger,
                attribution=config.run_id,
            )
            runner = ResearchRunner(config, model_client=client, tool_client=None, ledger=ledger)
            summary = runner.run()
            record = RunRecord(
                run_id=config.run_id,
                arm=arm,  # type: ignore[arg-type]
                repeat=repeat,
                run_dir=config.run_dir,
                phase=summary.phase,
                accepted=summary.accepted,
                acceptance=summary.acceptance,
                stop_reason=summary.stop_reason,
                model_calls=summary.model_calls,
                tool_calls=summary.tool_calls,
                final_path=summary.final_path,
                cost_cny=float(ledger.cost_by_attribution().get(config.run_id, 0.0)),
            )
        except Exception as error:  # noqa: BLE001 - preserve the block
            record = RunRecord(
                run_id=config.run_id,
                arm=arm,  # type: ignore[arg-type]
                repeat=repeat,
                run_dir=config.run_dir,
                phase="blocked",
                accepted=False,
                acceptance="rejected",
                stop_reason=f"{type(error).__name__}: {error}",
                model_calls=0,
                tool_calls=0,
                final_path="",
                cost_cny=float(ledger.cost_by_attribution().get(config.run_id, 0.0)),
            )
        state.runs = [item for item in state.runs if item.run_id != record.run_id] + [record]
        _save_state(study, state)
        if record.phase == "blocked" and ("Budget" in record.stop_reason or "budget" in record.stop_reason):
            state.phase = "blocked"
            state.stop_reason = record.stop_reason
            _save_state(study, state)
            return state.model_dump(mode="json")

    state.phase = "completed"
    state.stop_reason = "all_planned_runs_finished"
    _save_state(study, state)
    return state.model_dump(mode="json")


def retry_failed_runs(study_path: Path = STUDY_CONFIG) -> dict[str, object]:
    """One bounded retry for arms that do not yet have two accepted runs."""

    study = load_study(study_path)
    _assert_active_study(study)
    _assert_lock(study)
    registry = load_registry(BACKENDS_CONFIG)
    ledger = make_ledger(study, registry)
    state = _load_state(study)
    groups: dict[tuple[str, int], list[RunRecord]] = {}
    for record in state.runs:
        groups.setdefault((record.arm, record.repeat), []).append(record)
    for (arm, repeat), records in sorted(groups.items()):
        accepted = [item for item in records if item.phase in {"completed", "completed_unverified"} and item.accepted]
        if accepted:
            continue
        failed = [item for item in records if item.phase not in {"completed", "completed_unverified"}]
        if not failed:
            continue
        latest = failed[-1]
        retry_number = sum(1 for item in records if "__retry" in item.run_id) + 1
        max_retries = int(study.get("retry", {}).get("max_extra_attempts_per_cell", 1))
        if retry_number > max_retries:
            continue
        retry_id = latest.run_id.split("__retry", 1)[0] + f"__retry{retry_number}"
        retry_dir = latest.run_dir.split("__retry", 1)[0] + f"__retry{retry_number}"
        if any(item.run_id == retry_id and item.phase in {"completed", "completed_unverified"} for item in state.runs):
            continue
        manifest_path = Path(latest.run_dir) / "run_manifest.json"
        manifest = _read_json(manifest_path) if manifest_path.exists() else {}
        rule = manifest.get("rule", {}) if isinstance(manifest, dict) else {}
        rule_path = Path(str(rule.get("path", study["rules"]["baseline"]["path"])))
        rule_version = str(rule.get("version", study["rules"]["baseline"]["version"]))
        base_config = _run_config(
            study,
            arm=arm,
            repeat=repeat,
            rule_path=rule_path,
            rule_version=rule_version,
            registry=registry,
        )
        config = base_config.model_copy(update={"run_id": retry_id, "run_dir": retry_dir})
        try:
            client = create_chat_client(
                registry,
                str(study["model_backend"]),
                ledger=ledger,
                attribution=retry_id,
            )
            runner = ResearchRunner(config, model_client=client, tool_client=None, ledger=ledger)
            summary = runner.run()
            new_record = RunRecord(
                run_id=retry_id,
                arm=arm,  # type: ignore[arg-type]
                repeat=repeat,
                run_dir=retry_dir,
                phase=summary.phase,
                accepted=summary.accepted,
                acceptance=summary.acceptance,
                stop_reason=summary.stop_reason,
                model_calls=summary.model_calls,
                tool_calls=summary.tool_calls,
                final_path=summary.final_path,
                cost_cny=float(ledger.cost_by_attribution().get(retry_id, 0.0)),
                retry_of=latest.run_id,
            )
        except Exception as error:  # noqa: BLE001 - preserve retry failure
            new_record = RunRecord(
                run_id=retry_id,
                arm=arm,  # type: ignore[arg-type]
                repeat=repeat,
                run_dir=retry_dir,
                phase="blocked",
                accepted=False,
                acceptance="rejected",
                stop_reason=f"{type(error).__name__}: {error}",
                model_calls=0,
                tool_calls=0,
                final_path="",
                cost_cny=float(ledger.cost_by_attribution().get(retry_id, 0.0)),
                retry_of=latest.run_id,
            )
        state.runs.append(new_record)
        _save_state(study, state)
    state.phase = "completed" if not any(item.phase == "blocked" for item in state.runs) else "completed_with_blocked_retries"
    _save_state(study, state)
    return state.model_dump(mode="json")


def evaluate_study(study_path: Path = STUDY_CONFIG) -> dict[str, object]:
    study = load_study(study_path)
    _assert_active_study(study)
    registry = load_registry(BACKENDS_CONFIG)
    ledger = make_ledger(study, registry)
    state = _load_state(study)
    reviews_dir = ensure_dir(Path(str(study["paths"]["reviews_dir"])))
    blinded_dir = ensure_dir(reviews_dir / "blinded")
    for stale in blinded_dir.glob("proposal_*.md"):
        stale.unlink()
    groups: dict[tuple[str, int], list[RunRecord]] = {}
    for record in state.runs:
        groups.setdefault((record.arm, record.repeat), []).append(record)
    primary: list[RunRecord] = []
    for key in sorted(groups):
        records = groups[key]
        accepted = [item for item in records if item.phase in {"completed", "completed_unverified"} and item.accepted]
        # Frozen selection rule: first accepted attempt per arm/repeat cell.
        # Later accepted retries are secondary and never replace it.
        primary.append(accepted[0] if accepted else records[-1])

    proposals: list[dict[str, object]] = []
    material_ids = {str(item["evidence_id"]) for item in _read_json(Path(str(study["materials"]["manifest_path"])))["materials"]}
    for record in primary:
        final_path = Path(record.final_path) if record.final_path else Path(record.run_dir) / "final.json"
        answer_path = Path(record.run_dir) / "final_answer.md"
        final = _read_json(final_path) if final_path.exists() else {}
        answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        cited = sorted(set(final.get("inline_evidence_ids", final.get("evidence_ids", []))))
        checks = {
            "accepted": record.accepted,
            "citation_integrity": bool(cited) and set(cited).issubset(material_ids),
            "two_competing_explanations": sum(term in answer.lower() for term in ("解释", "hypothesis", "explanation", "机制")) >= 2,
            "within_between": any(term in answer for term in ("同一人", "不同人", "within", "between", "被试间", "个体间", "状态", "特质")),
            "discriminating_experiment": any(term in answer for term in ("实验", "对照", "反例", "falsif", "预测")),
            "executability": any(term in answer for term in ("数据", "session", "试次", "评分", "样本", "数据集")),
            "limits": any(term in answer for term in ("限制", "无法", "不能区分", "limitation")),
        }
        proposals.append(
            {
                "run_id": record.run_id,
                "arm": record.arm,
                "repeat": record.repeat,
                "accepted": record.accepted,
                "cost_cny": float(ledger.cost_by_attribution().get(record.run_id, 0.0)),
                "cited_ids": cited,
                "material_ids": sorted(material_ids),
                "checks": checks,
                "answer_chars": len(answer),
                "answer_path": str(answer_path),
                "run_dir": record.run_dir,
            }
        )

    # Deterministic blinded order independent of arm/run labels.
    order = sorted(proposals, key=lambda item: hashlib.sha256(str(item["run_id"]).encode("utf-8")).hexdigest())
    key: dict[str, object] = {}
    for index, proposal in enumerate(order, start=1):
        label = f"proposal_{index:02d}"
        target = blinded_dir / f"{label}.md"
        answer = Path(str(proposal["answer_path"])).read_text(encoding="utf-8") if Path(str(proposal["answer_path"])).exists() else "(missing answer)"
        atomic_write_text(
            target,
            f"# {label}\n\n"
            "The model, rule group, run ID, and review scores are intentionally withheld from this file.\n\n"
            + answer,
        )
        key[label] = {
            "run_id": proposal["run_id"],
            "arm": proposal["arm"],
            "repeat": proposal["repeat"],
            "accepted": proposal["accepted"],
            "cost_cny": proposal["cost_cny"],
            "source_answer": proposal["answer_path"],
        }
    atomic_write_json(reviews_dir / "KEY.json", key)
    atomic_write_text(
        reviews_dir / "README.md",
        "# Blinded proposal review\n\n"
        "Read only `blinded/proposal_*.md`. The model/rule-group/run metadata is in `KEY.json`; do not open it until after scoring.\n\n"
        "Use the frozen criteria in `configs/eval/emotion_rubric_v1.json`: citation support, reasoning errors, discriminability, executability, cost.\n\n"
        "The automated file `FORMAT_INTEGRITY_CHECK.md` checks only format/trace integrity; it is not a scientific score.\n\n"
        "This is a human review packet. dsh's manual review is separate and is not a scientific truth score.\n",
    )

    arm_cost: dict[str, float] = {}
    for record in state.runs:
        arm_cost[record.arm] = round(arm_cost.get(record.arm, 0.0) + float(ledger.cost_by_attribution().get(record.run_id, 0.0)), 6)
    summary = {
        "study_id": study["study_id"],
        "meta_decision": state.meta_decision,
        "runs": [item.model_dump(mode="json") for item in state.runs],
        "primary_runs": [item.model_dump(mode="json") for item in primary],
        "proposals": proposals,
        "attempts": len(state.runs),
        "accepted_runs": sum(1 for item in state.runs if item.accepted),
        "arm_total_cost_cny": arm_cost,
        "blinded_key": key,
        "ledger": ledger.snapshot(),
        "note": "dsh initial review; n=2 per arm at most; no statistical significance claim.",
    }
    atomic_write_json(reviews_dir / "evaluation.json", summary)
    lines = [
        "# FORMAT / INTEGRITY CHECK — not a scientific score",
        "",
        "This file records only programmatic format and trace-integrity checks. It is not a scientific quality score, not an independent expert review, and not evidence that a proposal is correct.",
        "",
        f"- Meta decision: `{(state.meta_decision or {}).get('decision', 'not_run')}`; accepted: `{(state.meta_decision or {}).get('accepted', False)}`",
        f"- Attempts: {len(state.runs)}; accepted: {summary['accepted_runs']}; primary proposals: {len(primary)}",
        f"- Baseline attempts: {sum(1 for r in state.runs if r.arm == 'baseline')}; meta-rule attempts: {sum(1 for r in state.runs if r.arm == 'meta_rule')}",
        f"- Total cost by arm: {json.dumps(arm_cost, ensure_ascii=False)}",
        "",
        "| run | arm | accepted | cited IDs | format checks passed | cost CNY |",
        "|---|---|---|---:|---:|---:|",
    ]
    for item in proposals:
        checks = item["checks"]
        passed = sum(1 for value in checks.values() if value is True)
        lines.append(
            f"| `{item['run_id']}` | {item['arm']} | {item['accepted']} | {len(item['cited_ids'])} | "
            f"{passed}/{len(checks)} | {item['cost_cny']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## What this check can and cannot say",
            "",
            "- It checks format and trace integrity: accepted status, citation ID validity, and presence of required proposal elements.",
            "- It cannot establish that a proposal is scientifically correct or that the proposed experiment would identify a mechanism.",
            "- With at most two runs per arm, differences are descriptive only; no p-value or population claim is warranted.",
            "- The blinded files in `blinded/` omit model/rule labels for human reading; `KEY.json` is the separate key.",
            "",
        ]
    )
    atomic_write_text(reviews_dir / "FORMAT_INTEGRITY_CHECK.md", "\n".join(lines))
    # Keep the historical filename as an exact copy for older links.
    atomic_write_text(reviews_dir / "INITIAL_REVIEW.md", "\n".join(lines))
    return summary
