"""Thin unified study runner built on the existing ResearchRunner."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .backends import backend_public_info, create_chat_client, load_registry
from .ledger import BudgetLedger
from .research import ResearchConfig, ResearchRunner
from .run_manifest import sha256_file
from .study_spec import StudySpec, load_study_spec, resolve, validate_spec, write_study_spec

BACKENDS = "configs/models/backends_20261021.json"


class StudyRuntimeError(RuntimeError):
    """Study configuration or execution problem."""


def study_dir(root: Path, spec: StudySpec) -> Path:
    return root / "studies" / spec.study_id


def _deadline(spec: StudySpec) -> tuple[str, str]:
    if spec.deadline:
        deadline = datetime.fromisoformat(spec.deadline.replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        stop = deadline - timedelta(minutes=30)
        return deadline.astimezone(timezone.utc).isoformat(), stop.astimezone(timezone.utc).isoformat()
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=24)
    return deadline.isoformat(), (deadline - timedelta(minutes=30)).isoformat()


def init_study(study_id: str, root: Path) -> Path:
    target = root / "studies" / study_id
    if target.exists():
        raise StudyRuntimeError(f"study already exists: {target}")
    spec = StudySpec(
        study_id=study_id,
        title=study_id,
        question="Replace this with the study question.",
        task_path=f"studies/{study_id}/task.md",
        material_manifest_path="configs/materials/emotion_state_trait_v1.json",
        material_evidence_dir="archive/experiments/emotion_20261021/runs/flash_emotion_20261021/materials/evidence",
        material_version="emotion_state_trait_v1",
        system_prompt_path="configs/prompts/emotion_research_system.md",
        deliverables=["State competing explanations and one discriminating experiment."],
        arms=[],
    )
    target.mkdir(parents=True)
    write_study_spec(target / "study.json", spec)
    (target / "task.md").write_text("# Task\n\nReplace this with the exact frozen task.\n", encoding="utf-8")
    return target


def load_study(root: Path, study_id: str) -> tuple[Path, StudySpec]:
    path = root / "studies" / study_id / "study.json"
    if not path.exists():
        raise StudyRuntimeError(f"study config not found: {path}")
    return path, load_study_spec(path)


def status(root: Path, study_id: str) -> dict[str, object]:
    path, spec = load_study(root, study_id)
    study_root = path.parent
    runs: list[dict[str, object]] = []
    for state_path in sorted((study_root / "runs").rglob("state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {"error": "unreadable"}
        runs.append(
            {
                "path": str(state_path.parent.relative_to(root)),
                "run_id": state.get("run_id", ""),
                "phase": state.get("phase", ""),
                "accepted": state.get("accepted", False),
                "acceptance": state.get("acceptance", ""),
                "stop_reason": state.get("stop_reason", ""),
            }
        )
    budgets: dict[str, object] = {}
    for ledger_path in sorted((study_root / "budgets").glob("*.json")):
        budgets[ledger_path.stem] = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not budgets and (study_root / "budget.json").exists():
        budgets["study"] = json.loads((study_root / "budget.json").read_text(encoding="utf-8"))
    return {
        "study_id": spec.study_id,
        "study_path": str(path.relative_to(root)),
        "archived": spec.archived,
        "arms": [arm.model_dump(mode="json") for arm in spec.arms],
        "runs": runs,
        "budgets": budgets,
    }


def report(root: Path, study_id: str) -> dict[str, object]:
    payload = status(root, study_id)
    study_root = root / "studies" / study_id
    raw_runs = payload.get("runs")
    runs = raw_runs if isinstance(raw_runs, list) else []
    lines = [
        f"# {study_id}",
        "",
        f"- study config: `studies/{study_id}/study.json`",
        f"- archived: `{payload['archived']}`",
        f"- runs: {len(runs)}",
        "",
        "## Runs",
        "",
        "| run | phase | accepted | stop reason |",
        "|---|---|---|---|",
    ]
    for run in runs:
        if not isinstance(run, dict):
            continue
        lines.append(
            f"| `{run['run_id']}` | {run['phase']} | {run['accepted']} | {run['stop_reason']} |"
        )
    budgets = payload.get("budgets")
    lines.extend(["", "## Budgets", "", "```json", json.dumps(budgets, ensure_ascii=False, indent=2), "```", ""])
    target = study_root / "report.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return {"report": str(target.relative_to(root)), "runs": len(runs)}


def run_study(root: Path, study_id: str, *, confirm_cost: bool = False) -> dict[str, object]:
    path, spec = load_study(root, study_id)
    if spec.archived:
        raise StudyRuntimeError("archived studies are read-only")
    errors = validate_spec(spec, root, load_registry(root / BACKENDS))
    if errors:
        raise StudyRuntimeError("study validation failed: " + "; ".join(errors))
    if not confirm_cost:
        raise StudyRuntimeError(
            "paid run not started: pass --confirm-cost after reviewing budget and model status"
        )
    registry = load_registry(root / BACKENDS)
    study_root = path.parent
    cap = spec.budget
    arm_cap = cap.cap_cny / max(1, len(spec.arms))
    deadline, stop = _deadline(spec)
    manifest_path = resolve(root, spec.material_manifest_path)
    results: list[dict[str, object]] = []
    ledger_snapshots: dict[str, object] = {}
    for arm in spec.arms:
        backend = registry.chat(arm.backend)
        if backend.price is None:
            raise StudyRuntimeError(f"arm {arm.name}: no price configured")
        model_info = backend_public_info(backend)
        ledger = BudgetLedger(
            study_root / "budgets" / f"{arm.name}.json",
            run_id=f"{spec.study_id}__{arm.name}",
            cap_cny=arm_cap,
            wrap_up_reserve_cny=min(cap.wrap_up_reserve_cny, arm_cap / 4),
            model_attempts_limit=cap.model_attempts_cap,
            search_attempts_limit=cap.search_attempts_cap,
            fetch_attempts_limit=cap.fetch_attempts_cap,
            input_tokens_limit=cap.input_tokens_cap,
            output_tokens_limit=cap.output_tokens_cap,
            input_price_cny_per_mtok=backend.price.input_cache_miss_peak_cny_per_mtok,
            output_price_cny_per_mtok=backend.price.output_peak_cny_per_mtok,
            price_source=backend.price.source,
            price_checked_at=backend.price.checked_at,
        )
        for repeat in range(1, arm.repeats + 1):
            run_id = f"{spec.study_id}__{arm.name}__{repeat:02d}"
            run_dir = study_root / "runs" / arm.name / f"repeat_{repeat:02d}"
            state_path = run_dir / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state.get("phase") in {"completed", "completed_unverified"}:
                    results.append({"run_id": run_id, "status": "already_terminal", "path": str(run_dir)})
                    continue
            rule_path = arm.rule_path
            config = ResearchConfig(
                run_id=run_id,
                run_dir=str(run_dir),
                question=spec.question,
                deadline=deadline,
                stop_new_at=stop,
                system_prompt_path=spec.system_prompt_path,
                deliverables=spec.deliverables,
                materials_manifest_path=spec.material_manifest_path,
                material_evidence_dir=spec.material_evidence_dir,
                material_version=spec.material_version,
                material_manifest_sha256=sha256_file(manifest_path),
                rule_text_path=rule_path,
                rule_version=arm.name,
                research_mode="materials_only",
                max_model_calls=spec.limits.max_model_calls,
                max_tool_calls=spec.limits.max_tool_calls,
                max_turns=spec.limits.max_turns,
                max_model_calls_per_turn=spec.limits.max_model_calls_per_turn,
                max_tool_calls_per_turn=spec.limits.max_tool_calls_per_turn,
                max_output_tokens=spec.limits.max_output_tokens,
                max_output_tokens_retry=spec.limits.max_output_tokens_retry,
                context_char_target=spec.limits.context_char_target,
                study_config=spec.model_dump(mode="json"),
                model_info=model_info,
                tool_info={"research_mode": "materials_only"},
                ledger_path=str(study_root / "budgets" / f"{arm.name}.json"),
                code_root=str(root),
            )
            client = create_chat_client(registry, arm.backend, ledger=ledger, attribution=run_id)
            try:
                summary = ResearchRunner(config, model_client=client, tool_client=None, ledger=ledger).run()
                results.append({"run_id": run_id, "status": summary.phase, "accepted": summary.accepted, "path": str(run_dir)})
            except Exception as error:  # noqa: BLE001 - study boundary must preserve failure
                results.append({"run_id": run_id, "status": "error", "error": f"{type(error).__name__}: {error}", "path": str(run_dir)})
        ledger_snapshots[arm.name] = ledger.snapshot()
    return {"study_id": spec.study_id, "results": results, "budgets": ledger_snapshots}
