"""Thin unified study runner built on the existing ResearchRunner."""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .backends import backend_public_info, create_chat_client, load_registry
from .ledger import BudgetLedger
from .research import (
    GENERIC_SYSTEM_PROMPT,
    ResearchConfig,
    ResearchRunner,
    compose_system_prompt,
    compose_user_prompt,
    load_base_system_prompt,
    load_task_text,
)
from .run_manifest import sha256_file, sha256_text
from .storage import ensure_dir
from .study_spec import StudySpec, load_study_spec, resolve, validate_spec, write_study_spec

BACKENDS = "configs/models/backends_20261021.json"
PREFLIGHT_TIME = "<runtime local time>"
PREFLIGHT_DEADLINE = "2099-01-01T00:00:00+00:00"


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


def _starter_system_prompt() -> str:
    return (
        GENERIC_SYSTEM_PROMPT
        + "\n\nThis is a closed-material study: only evidence listed in this study's material manifest is available. "
        "The user message contains the frozen task body from task.md; it is the authoritative task, not a summary.\n"
    )


def init_study(study_id: str, root: Path, *, template: str = "generic") -> Path:
    """Create a draft study.

    ``generic`` is self-contained and does not reference any old experiment.
    Old material is available only through the explicit ``emotion_20261021``
    template; a new study never silently points at an archived run.
    """

    target = root / "studies" / study_id
    if target.exists():
        raise StudyRuntimeError(f"study already exists: {target}")
    if template not in {"generic", "emotion_20261021"}:
        raise StudyRuntimeError(f"unknown study template: {template}")
    if template == "emotion_20261021":
        material_manifest_path = "configs/materials/emotion_state_trait_v1.json"
        material_evidence_dir = (
            "archive/experiments/emotion_20261021/runs/flash_emotion_20261021/materials/evidence"
        )
        material_version = "emotion_state_trait_v1"
        system_prompt_path = "configs/prompts/emotion_research_system.md"
    else:
        material_manifest_path = f"studies/{study_id}/materials/manifest.json"
        material_evidence_dir = f"studies/{study_id}/materials/evidence"
        material_version = "starter_v1"
        system_prompt_path = f"studies/{study_id}/system_prompt.md"
    spec = StudySpec(
        study_id=study_id,
        title=study_id,
        question="",
        task_path=f"studies/{study_id}/task.md",
        material_manifest_path=material_manifest_path,
        material_evidence_dir=material_evidence_dir,
        material_version=material_version,
        system_prompt_path=system_prompt_path,
        deliverables=["State competing explanations and one discriminating experiment."],
        arms=[],
    )
    target.mkdir(parents=True)
    write_study_spec(target / "study.json", spec)
    (target / "task.md").write_text(
        "# Task\n\n"
        "Replace this with the exact task sent to the model. This file is read as the authoritative task body; "
        "the `question` field in study.json is metadata only.\n\n"
        "## Deliverable\n\n"
        "One research proposal with competing explanations, a discriminating experiment, predictions, and limits.\n",
        encoding="utf-8",
    )
    if template == "generic":
        (target / "system_prompt.md").write_text(_starter_system_prompt(), encoding="utf-8")
        ensure_dir(target / "materials" / "evidence")
        (target / "materials" / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "version": "starter_v1",
                    "materials": [],
                    "note": "Add registered source items with evidence_id/title/read_scope before running.",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    template_note = (
        "Uses the explicitly selected `emotion_20261021` template: archived material and the old system prompt."
        if template == "emotion_20261021"
        else "Self-contained generic template; no archived material is referenced."
    )
    (target / "README.md").write_text(
        f"# {study_id}\n\n"
        f"{template_note}\n\n"
        "- `task.md` — authoritative task body; edit this, not `question` in `study.json`.\n"
        f"- `system_prompt.md` — base system prompt for generic studies; explicit old-material "
        f"templates use their configured prompt.\n"
        "- `materials/manifest.json` — registered evidence IDs; the evidence files live under `materials/evidence/`.\n"
        "- `runs/<arm>/repeat_XX/` — one ResearchRunner run per arm/repeat.\n"
        "- `study.json` — arms, repeats, limits, budget, material version.\n\n"
        "Add arms with a verified backend after filling at least one material item. "
        "`study validate` and `study preflight` are offline.\n",
        encoding="utf-8",
    )
    return target


def load_study(root: Path, study_id: str) -> tuple[Path, StudySpec]:
    path = root / "studies" / study_id / "study.json"
    if not path.exists():
        raise StudyRuntimeError(f"study config not found: {path}")
    return path, load_study_spec(path)


def _read_rule(path: Path) -> str:
    if not path.is_file():
        raise StudyRuntimeError(f"rule file missing: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise StudyRuntimeError(f"rule file unreadable: {path} ({type(error).__name__})") from error
    if not text.strip():
        raise StudyRuntimeError(f"rule file is empty: {path}")
    return text


def _prompt_config(root: Path, spec: StudySpec) -> ResearchConfig:
    return ResearchConfig(
        run_id=f"{spec.study_id}__preflight",
        run_dir=str(root / "studies" / spec.study_id / "preflight"),
        question=spec.question,
        deadline=PREFLIGHT_DEADLINE,
        stop_new_at=PREFLIGHT_DEADLINE,
        task_text_path=str(resolve(root, spec.task_path)) if spec.task_path else None,
        system_prompt_path=str(resolve(root, spec.system_prompt_path)) if spec.system_prompt_path else "",
        deliverables=spec.deliverables,
        materials_manifest_path=str(resolve(root, spec.material_manifest_path)) if spec.material_manifest_path else None,
        material_evidence_dir=str(resolve(root, spec.material_evidence_dir)) if spec.material_evidence_dir else None,
        material_version=spec.material_version,
        research_mode="materials_only",
        max_output_tokens=spec.limits.max_output_tokens,
    )


def _prompt_diff(first: str, current: str, first_name: str, current_name: str) -> list[str]:
    diff = difflib.unified_diff(
        first.splitlines(),
        current.splitlines(),
        fromfile=first_name,
        tofile=current_name,
        lineterm="",
        n=3,
    )
    lines: list[str] = []
    for index, line in enumerate(diff):
        if index >= 160:
            lines.append("... diff truncated at 160 lines ...")
            break
        lines.append(line)
    return lines


def preflight(root: Path, study_id: str) -> dict[str, object]:
    """Show exactly what each arm would send, without calling a model.

    This is the control check required before a rule contrast: hashes for the
    task, material, effective rule, system/user prompt, and the actual prompt
    diff.  Two distinct rule files with identical effective text are rejected
    because the claimed intervention would be absent.
    """

    path, spec = load_study(root, study_id)
    if spec.archived:
        raise StudyRuntimeError("archived studies are read-only")
    config = _prompt_config(root, spec)
    task_text, task_source = load_task_text(config)
    base_system, base_source = load_base_system_prompt(config)
    task_hash = sha256_text(task_text)
    material_path = resolve(root, spec.material_manifest_path)
    if not material_path.is_file():
        raise StudyRuntimeError(f"material manifest missing: {material_path}")
    material_hash = sha256_file(material_path)
    registry = load_registry(root / BACKENDS)
    arms: list[dict[str, object]] = []
    rule_hashes: dict[str, str] = {}
    for arm in spec.arms:
        rule_path = resolve(root, arm.rule_path) if arm.rule_path else None
        rule_text = _read_rule(rule_path) if rule_path is not None else ""
        rule_version = (
            (re.sub(r"[^A-Za-z0-9._-]", "_", rule_path.stem)[:60] or "rule") if rule_path is not None else "baseline"
        )
        rule_hash = sha256_text(rule_text)
        rule_hashes[arm.name] = rule_hash
        system_text = compose_system_prompt(base_system, rule_text, rule_version)
        user_text = compose_user_prompt(config, task_text, task_source, local_time=PREFLIGHT_TIME)
        prompt_text = "SYSTEM\n" + system_text + "\nUSER\n" + user_text
        try:
            backend = registry.chat(arm.backend)
            model_info = backend_public_info(backend)
        except Exception as error:  # noqa: BLE001 - preflight reports configuration errors
            model_info = {"id": arm.backend, "error": f"{type(error).__name__}: {error}"}
        arms.append(
            {
                "name": arm.name,
                "backend": arm.backend,
                "repeats": arm.repeats,
                "model": model_info,
                "rule_path": arm.rule_path,
                "rule_version": rule_version,
                "rule_sha256": rule_hash,
                "rule_chars": len(rule_text),
                "system_sha256": sha256_text(system_text),
                "user_sha256": sha256_text(user_text),
                "prompt_sha256": sha256_text(prompt_text),
                "system_text": system_text,
                "user_text": user_text,
            }
        )
    first_arm = arms[0] if arms else None
    for arm in arms:
        if first_arm is not None:
            arm["prompt_diff_vs_first"] = _prompt_diff(
                str(first_arm["system_text"]) + "\nUSER\n" + str(first_arm["user_text"]),
                str(arm["system_text"]) + "\nUSER\n" + str(arm["user_text"]),
                f"arm:{first_arm['name']}",
                f"arm:{arm['name']}",
            )
    distinct_rule_paths = {arm.rule_path or "" for arm in spec.arms}
    rule_contrast_requested = len(distinct_rule_paths) > 1
    distinct_rule_hashes = sorted(set(rule_hashes.values()))
    rule_contrast_valid = not (rule_contrast_requested and len(distinct_rule_hashes) == 1)
    rule_contrast_reason = (
        "arms claim a rule contrast using distinct rule files, but effective rule text is identical"
        if not rule_contrast_valid
        else "no identical-text rule contrast detected"
    )
    # Recompute prompt hashes per rule group to detect accidental prompt drift.
    consistency_ok = True
    consistency_reason = "arms with identical effective rules have identical prompts"
    groups: dict[str, set[tuple[str, str]]] = {}
    for arm in arms:
        groups.setdefault(str(arm["rule_sha256"]), set()).add((str(arm["system_sha256"]), str(arm["user_sha256"])))
    for rule_hash, variants in groups.items():
        if len(variants) > 1:
            consistency_ok = False
            consistency_reason = f"arms sharing rule hash {rule_hash[:12]} have different prompts"
            break
    return {
        "study_id": spec.study_id,
        "study_path": str(path.relative_to(root)),
        "task": {"path": spec.task_path, "sha256": task_hash, "chars": len(task_text), "source": task_source},
        "material": {"path": spec.material_manifest_path, "sha256": material_hash, "version": spec.material_version},
        "system": {"path": spec.system_prompt_path, "source": base_source},
        "arms": arms,
        "rule_contrast": {
            "requested": rule_contrast_requested,
            "distinct_rule_hashes": distinct_rule_hashes,
            "valid": rule_contrast_valid,
            "reason": rule_contrast_reason,
        },
        "prompt_consistency": {"valid": consistency_ok, "reason": consistency_reason},
        "ok": rule_contrast_valid and consistency_ok,
    }


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
                "arm": state.get("arm", ""),
                "repeat": state.get("repeat", 0),
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
        "- `accepted` means local protocol checks passed (finish_study with matching cited evidence); "
        "it is not a scientific quality score.",
        "",
        "## Runs",
        "",
        "| run | arm | repeat | phase | accepted | acceptance | stop reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        if not isinstance(run, dict):
            continue
        lines.append(
            f"| `{run['run_id']}` | {run['arm']} | {run['repeat']} | {run['phase']} | "
            f"{run['accepted']} | {run['acceptance']} | {run['stop_reason']} |"
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
    registry = load_registry(root / BACKENDS)
    errors = validate_spec(spec, root, registry)
    if errors:
        raise StudyRuntimeError("study validation failed: " + "; ".join(errors))
    checks = preflight(root, study_id)
    if not checks["ok"]:
        raise StudyRuntimeError(
            "study preflight rejected the contrast: "
            + "; ".join(
                str(part.get("reason"))
                for part in (checks["rule_contrast"], checks["prompt_consistency"])
                if isinstance(part, dict) and not part.get("valid")
            )
        )
    if not confirm_cost:
        raise StudyRuntimeError(
            "paid run not started: pass --confirm-cost after reviewing budget and model status"
        )
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
            rule_path = resolve(root, arm.rule_path) if arm.rule_path else None
            if rule_path is not None:
                rule_version = re.sub(r"[^A-Za-z0-9._-]", "_", rule_path.stem)[:60] or "rule"
            else:
                rule_version = "baseline"
            config = ResearchConfig(
                run_id=run_id,
                run_dir=str(run_dir),
                question=spec.question,
                task_text_path=str(resolve(root, spec.task_path)) if spec.task_path else None,
                study_id=spec.study_id,
                arm=arm.name,
                repeat=repeat,
                deadline=deadline,
                stop_new_at=stop,
                system_prompt_path=str(resolve(root, spec.system_prompt_path)) if spec.system_prompt_path else "",
                deliverables=spec.deliverables,
                materials_manifest_path=str(resolve(root, spec.material_manifest_path)),
                material_evidence_dir=str(resolve(root, spec.material_evidence_dir)),
                material_version=spec.material_version,
                material_manifest_sha256=sha256_file(manifest_path),
                rule_text_path=str(rule_path) if rule_path is not None else None,
                rule_version=rule_version,
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
