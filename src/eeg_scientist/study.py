"""Development -> method update -> freeze -> paired holdout study."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .cases import build_public_case, generate_case, load_case_specs
from .experiments import compute_baselines
from .provider import ScientistProvider
from .schema import (
    EpisodeConfig,
    EpisodeState,
    EpisodeSummary,
    MetaResponse,
    ModelRequest,
    ProviderResponse,
    ResearchRule,
    StudyConfig,
    StudyState,
    StudySummary,
)
from .scientist import (
    TOOL_SPECS,
    DecisionParseError,
    build_meta_request,
    build_s1_text,
    collect_event_ids,
    load_rule_text,
    parse_meta,
)
from .splits import build_all_splits
from .storage import (
    append_event,
    atomic_write_json,
    canonical_json,
    ensure_dir,
    load_result,
    sha256_text,
    utc_now,
)

HOLDOUT_MINUTES_PER_EPISODE = 12


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _code_hashes() -> dict[str, str]:
    root = Path(__file__).parent
    return {path.name: _file_hash(path) for path in sorted(root.glob("*.py"))}


def _dependency_versions() -> dict[str, str]:
    import numpy
    import pydantic
    import sklearn

    return {"numpy": numpy.__version__, "scikit-learn": sklearn.__version__, "pydantic": pydantic.__version__}


def _read_episode_summary(config: EpisodeConfig, run_dir: Path) -> EpisodeSummary | None:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        return None
    state = EpisodeState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
    final_path = run_dir / "final.json"
    total = 0
    hit = 0
    status = state.phase
    if final_path.exists():
        final = json.loads(final_path.read_text(encoding="utf-8"))
        total = int(final.get("predictions_total", 0))
        hit = int(final.get("predictions_hit", 0))
        status = str(final.get("status", state.phase))
    return EpisodeSummary(
        episode_id=config.episode_id,
        case_id=config.case_id,
        status=status,
        backend=config.backend,
        model=config.model,
        actions_used=state.actions_used,
        calls_used=state.calls_used,
        attempts_used=state.attempts_used,
        tokens_used=state.tokens_used,
        predictions_total=total,
        predictions_hit=hit,
        stop_reason=state.stop_reason,
        run_dir=str(run_dir),
    )


def _episode_config(
    config: StudyConfig,
    *,
    episode_id: str,
    case_id: str,
    rule_path: Path,
    run_dir: Path,
    shared_facts_path: Path | None,
    provider: ScientistProvider,
) -> EpisodeConfig:
    return EpisodeConfig(
        episode_id=episode_id,
        case_id=case_id,
        case_specs_path=config.case_specs_path,
        rule_path=str(rule_path),
        provider=dict(config.provider),
        backend=provider.backend,  # type: ignore[arg-type]
        model=provider.model_name,
        max_actions=config.max_actions_per_episode,
        max_calls=config.max_calls_per_episode,
        max_attempts=12,
        deadline=config.deadline,
        run_dir=str(run_dir),
        shared_facts_path=str(shared_facts_path) if shared_facts_path else None,
    )


def _run_arm(
    config: StudyConfig,
    provider: ScientistProvider,
    *,
    case_id: str,
    arm: str,
    rule_path: Path,
    shared_facts_path: Path | None,
    study_dir: Path,
) -> EpisodeSummary:
    run_dir = ensure_dir(study_dir / "holdout" / case_id / arm.lower())
    episode_config = _episode_config(
        config,
        episode_id=f"{config.study_id}_{case_id}_{arm.lower()}",
        case_id=case_id,
        rule_path=rule_path,
        run_dir=run_dir,
        shared_facts_path=shared_facts_path,
        provider=provider,
    )
    existing = _read_episode_summary(episode_config, run_dir)
    if existing is not None and existing.status in ("failed", "blocked", "incomplete"):
        return existing
    from .runner import resume_episode

    return resume_episode(episode_config, provider)


def _run_dev_arm(
    config: StudyConfig,
    provider: ScientistProvider,
    *,
    case_id: str,
    study_dir: Path,
) -> EpisodeSummary:
    run_dir = ensure_dir(study_dir / "development" / case_id / "s0")
    episode_config = _episode_config(
        config,
        episode_id=f"{config.study_id}_{case_id}_dev_s0",
        case_id=case_id,
        rule_path=Path("archive/experiments/synthetic_20261019/prompts/S0.md"),
        run_dir=run_dir,
        shared_facts_path=None,
        provider=provider,
    )
    existing = _read_episode_summary(episode_config, run_dir)
    if existing is not None and existing.status in ("failed", "blocked", "incomplete"):
        return existing
    from .runner import resume_episode

    return resume_episode(episode_config, provider)


def _build_development_facts(config: StudyConfig, specs: dict[str, object], summaries: list[EpisodeSummary], study_dir: Path) -> dict[str, object]:
    development_cases: list[dict[str, object]] = []
    trajectories: list[dict[str, object]] = []
    validation_failures: list[dict[str, object]] = []
    for summary in summaries:
        run_dir = Path(summary.run_dir)
        public_path = run_dir / "public_input.json"
        public = json.loads(public_path.read_text(encoding="utf-8")) if public_path.exists() else {}
        development_cases.append(
            {
                "case_id": summary.case_id,
                "baseline": public.get("baseline", {}),
                "structure_summary": public.get("structure_summary", {}),
                "status": summary.status,
            }
        )
        events: list[dict[str, object]] = []
        history_path = run_dir / "history.json"
        if history_path.exists():
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(history, list):
                for index, item in enumerate(history, start=1):
                    if not isinstance(item, dict):
                        continue
                    action_summary = item.get("action", {})
                    action_payload = action_summary.get("action") if isinstance(action_summary, dict) else None
                    if not isinstance(action_payload, dict):
                        continue
                    result = item.get("result", {})
                    score = item.get("prediction_score", {})
                    events.append(
                        {
                            "event_id": f"dev-{summary.case_id}-action-{index}",
                            "tool_id": action_payload.get("tool_id"),
                            "prediction": action_payload.get("prediction"),
                            "result_metrics": result.get("metrics", {}) if isinstance(result, dict) else {},
                            "valid": result.get("valid") if isinstance(result, dict) else None,
                            "score": score,
                        }
                    )
        trajectories.append(
            {
                "episode_id": summary.episode_id,
                "case_id": summary.case_id,
                "status": summary.status,
                "events": events,
                "stop_reason": summary.stop_reason,
            }
        )
        if summary.status != "completed":
            validation_failures.append(
                {"case_id": summary.case_id, "status": summary.status, "stop_reason": summary.stop_reason}
            )
    return {
        "study_id": config.study_id,
        "development_cases": development_cases,
        "trajectories": trajectories,
        "validation_failures": validation_failures,
        "note": "Public development facts only; no generator mechanism, hidden answer, or holdout result.",
    }


def _meta_update(
    config: StudyConfig,
    provider: ScientistProvider,
    facts: dict[str, object],
    s0_text: str,
) -> tuple[MetaResponse, int, int, list[str]]:
    event_ids = collect_event_ids(facts)
    request = build_meta_request(facts, s0_text, event_ids)
    response = provider.decide(request)
    attempts = 1
    tokens = int(response.usage.get("total_tokens", 0) or 0)
    errors: list[str] = []
    if response.status != "ok":
        errors.append(f"provider_{response.status}: {response.error}")
        return MetaResponse(update="no_update", reasoning_summary="Meta provider unavailable"), attempts, tokens, errors
    try:
        return parse_meta(response.visible_text, set(event_ids)), attempts, tokens, errors
    except DecisionParseError as error:
        errors.append(str(error))
        repair = ModelRequest(
            request_id=f"meta_repair_{int(time.time())}",
            stage="meta_repair",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return ONLY valid MetaResponse JSON. Schema: {\"update\":\"rules\"|\"no_update\","
                        "\"rules\":[{\"trigger\":\"...\",\"action\":\"...\",\"boundary\":\"...\","
                        "\"evidence_event_ids\":[\"...\"]}],\"reasoning_summary\":\"...\"}. "
                        "Do not add holdout cases, family codes, or fixed tool choices."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"original_output": response.visible_text, "validation_error": str(error), "available_event_ids": event_ids},
                        ensure_ascii=False,
                    ),
                },
            ],
            model_settings={"temperature": 0.0, "max_output_tokens": 1500, "think": False, "format": "json"},
            rule_hash=sha256_text(s0_text),
            public_input_hash=sha256_text(canonical_json(facts)),
            created_at=utc_now(),
        )
        repaired = provider.decide(repair)
        attempts += 1
        tokens += int(repaired.usage.get("total_tokens", 0) or 0)
        if repaired.status != "ok":
            errors.append(f"repair_provider_{repaired.status}")
            return MetaResponse(update="no_update", reasoning_summary="Meta repair unavailable"), attempts, tokens, errors
        try:
            return parse_meta(repaired.visible_text, set(event_ids)), attempts, tokens, errors
        except DecisionParseError as second_error:
            errors.append(str(second_error))
            return MetaResponse(update="no_update", reasoning_summary="Meta output remained invalid"), attempts, tokens, errors


def freeze_hash(manifest: dict[str, object]) -> str:
    return sha256_text(canonical_json(manifest))


def check_freeze(state: StudyState, manifest: dict[str, object]) -> str:
    current = freeze_hash(manifest)
    if state.freeze_manifest_hash and state.freeze_manifest_hash != current:
        raise RuntimeError("freeze manifest changed after freeze; start a new study version")
    return current


def _pair_order(config: StudyConfig, holdout_ids: list[str]) -> dict[str, list[str]]:
    order: dict[str, list[str]] = {}
    for index, case_id in enumerate(holdout_ids):
        first = "S0" if (index + config.arm_order_seed) % 2 == 0 else "S1"
        second = "S1" if first == "S0" else "S0"
        order[case_id] = [first, second]
    return order


def freeze_study(
    config: StudyConfig,
    provider: ScientistProvider,
    *,
    specs: dict[str, object],
    study_dir: Path,
    facts: dict[str, object],
    s0_text: str,
    s1_text: str,
    meta: MetaResponse,
    meta_attempts: int,
    meta_tokens: int,
    meta_errors: list[str],
) -> dict[str, object]:
    facts_path = study_dir / "shared_development_facts.json"
    atomic_write_json(facts_path, facts)
    s0_path = Path("archive/experiments/synthetic_20261019/prompts/S0.md")
    s1_path = Path("archive/experiments/synthetic_20261019/prompts/S1.md")
    case_specs_path = Path(config.case_specs_path)
    holdout_specs = {case_id: specs[case_id].model_dump(mode="json") for case_id in config.holdout_case_ids if case_id in specs}
    model_info: dict[str, object] = {"provider": provider.provider_name, "model": provider.model_name}
    if hasattr(provider, "describe"):
        try:
            model_info["describe"] = getattr(provider, "describe")()
        except Exception as error:  # noqa: BLE001 - metadata boundary
            model_info["describe_error"] = str(error)
    pair_order = _pair_order(config, list(holdout_specs))
    manifest = {
        "freeze_id": f"freeze_{int(time.time())}",
        "created_at": utc_now(),
        "study_id": config.study_id,
        "generator_version": "1.0",
        "case_specs_sha256": _file_hash(case_specs_path),
        "holdout_specs_sha256": sha256_text(canonical_json(holdout_specs)),
        "dev_case_ids": list(config.dev_case_ids),
        "holdout_case_ids": list(holdout_specs),
        "pair_order": pair_order,
        "arm_order_seed": config.arm_order_seed,
        "model": model_info,
        "s0_sha256": sha256_text(s0_text),
        "s1_sha256": sha256_text(s1_text),
        "shared_development_facts_sha256": sha256_text(canonical_json(facts)),
        "tool_specs_sha256": sha256_text(canonical_json(TOOL_SPECS)),
        "classifier": {"scaler": "StandardScaler", "classifier": "KNeighborsClassifier", "n_neighbors": 1},
        "random_label_seeds": list(range(101, 111)),
        "code_sha256": _code_hashes(),
        "dependency_versions": _dependency_versions(),
        "deadline": config.deadline,
        "report_reserve_minutes": config.report_reserve_minutes,
        "meta": {
            "update": meta.update,
            "n_rules": len(meta.rules),
            "meta_attempts": meta_attempts,
            "meta_tokens": meta_tokens,
            "meta_errors": meta_errors,
        },
    }
    if not s1_path.exists():
        raise RuntimeError("S1 must be written before freezing")
    manifest_path = Path(config.freeze_manifest_path)
    atomic_write_json(manifest_path, manifest)
    atomic_write_json(study_dir / "FREEZE_MANIFEST.json", manifest)
    memory_methods = Path("archive/experiments/synthetic_20261019/memory/research_methods")
    memory_scientific = Path("archive/experiments/synthetic_20261019/memory/scientific_knowledge")
    ensure_dir(memory_methods)
    ensure_dir(memory_scientific)
    atomic_write_json(
        memory_methods / "rules.json",
        {
            "study_id": config.study_id,
            "update": meta.update,
            "rules": [rule.model_dump(mode="json") for rule in meta.rules],
            "source": "shared_development_facts.json",
            "author": "developer_assisted_dsh",
            "reasoning_summary": meta.reasoning_summary,
        },
    )
    (memory_scientific / "dev_facts.md").write_text(
        "# Development facts\n\n" + json.dumps(facts, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def run_study(config: StudyConfig, provider: ScientistProvider) -> StudySummary:
    study_dir = ensure_dir(Path(config.run_root) / config.study_id)
    state_path = study_dir / "study_state.json"
    if state_path.exists():
        state = StudyState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
    else:
        state = StudyState(
            study_id=config.study_id,
            phase="development",
            deadline=config.deadline,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        atomic_write_json(state_path, state.model_dump(mode="json"))
        append_event(study_dir, "study_started", {"study_id": config.study_id, "deadline": config.deadline})
    specs = load_case_specs(Path(config.case_specs_path))
    s0_text = load_rule_text(Path("archive/experiments/synthetic_20261019/prompts/S0.md"))
    deadline = _deadline(config.deadline)
    stop_new = deadline.timestamp() - config.report_reserve_minutes * 60
    freeze_path = Path(config.freeze_manifest_path)

    if not freeze_path.exists():
        summaries: list[EpisodeSummary] = []
        for case_id in config.dev_case_ids:
            if state.attempts_used >= config.max_attempts or state.tokens_used >= config.max_tokens:
                state.stopped_reason = "budget"
                break
            if _now().timestamp() + HOLDOUT_MINUTES_PER_EPISODE * 60 > stop_new:
                state.stopped_reason = "deadline"
                break
            summary = _run_dev_arm(config, provider, case_id=case_id, study_dir=study_dir)
            summaries.append(summary)
            state.attempts_used += summary.attempts_used
            state.tokens_used += summary.tokens_used
            atomic_write_json(state_path, state.model_dump(mode="json"))
            if summary.status not in ("completed",):
                state.stopped_reason = f"development_{summary.status}"
                break
        if len(summaries) < len(config.dev_case_ids):
            state.phase = "development_blocked"
            state.updated_at = utc_now()
            atomic_write_json(state_path, state.model_dump(mode="json"))
            return StudySummary(
                study_id=config.study_id,
                phase=state.phase,
                pairs_completed=0,
                pairs_total=len(config.holdout_case_ids),
                stopped_reason=state.stopped_reason,
                study_dir=str(study_dir),
            )
        facts = _build_development_facts(config, specs, summaries, study_dir)
        meta, meta_attempts, meta_tokens, meta_errors = _meta_update(config, provider, facts, s0_text)
        s1_text = build_s1_text(s0_text, meta)
        Path("archive/experiments/synthetic_20261019/prompts/S1.md").write_text(s1_text, encoding="utf-8")
        manifest = freeze_study(
            config,
            provider,
            specs=specs,
            study_dir=study_dir,
            facts=facts,
            s0_text=s0_text,
            s1_text=s1_text,
            meta=meta,
            meta_attempts=meta_attempts,
            meta_tokens=meta_tokens,
            meta_errors=meta_errors,
        )
        state.freeze_manifest_hash = sha256_text(canonical_json(manifest))
        state.phase = "frozen"
        state.attempts_used += meta_attempts
        state.tokens_used += meta_tokens
        state.updated_at = utc_now()
        atomic_write_json(state_path, state.model_dump(mode="json"))
        append_event(study_dir, "freeze_created", {"freeze_hash": state.freeze_manifest_hash, "update": meta.update})
    else:
        manifest = json.loads(freeze_path.read_text(encoding="utf-8"))
        state.freeze_manifest_hash = check_freeze(state, manifest)
        facts_path = study_dir / "shared_development_facts.json"
        if not facts_path.exists():
            raise RuntimeError("shared development facts missing after freeze")

    manifest = json.loads(freeze_path.read_text(encoding="utf-8"))
    pair_order = manifest.get("pair_order", _pair_order(config, list(config.holdout_case_ids)))
    facts_path = study_dir / "shared_development_facts.json"
    s0_path = Path("archive/experiments/synthetic_20261019/prompts/S0.md")
    s1_path = Path("archive/experiments/synthetic_20261019/prompts/S1.md")
    for case_id in config.holdout_case_ids:
        pair = state.pairs.setdefault(case_id, {})
        if pair.get("paired"):
            continue
        if _now().timestamp() + 2 * HOLDOUT_MINUTES_PER_EPISODE * 60 > stop_new:
            state.stopped_reason = "deadline"
            break
        if state.attempts_used >= config.max_attempts or state.tokens_used >= config.max_tokens:
            state.stopped_reason = "budget"
            break
        for arm in pair_order.get(case_id, ["S0", "S1"]):
            if pair.get(arm, {}).get("status") in ("completed", "failed", "blocked", "incomplete"):
                continue
            rule_path = s0_path if arm == "S0" else s1_path
            summary = _run_arm(
                config,
                provider,
                case_id=case_id,
                arm=arm,
                rule_path=rule_path,
                shared_facts_path=facts_path,
                study_dir=study_dir,
            )
            pair[arm] = summary.model_dump(mode="json")
            state.attempts_used += summary.attempts_used
            state.tokens_used += summary.tokens_used
            state.current = f"{case_id}:{arm}"
            state.updated_at = utc_now()
            atomic_write_json(state_path, state.model_dump(mode="json"))
            append_event(
                study_dir,
                "arm_finished",
                {"case_id": case_id, "arm": arm, "status": summary.status, "run_dir": summary.run_dir},
            )
            if summary.status != "completed":
                state.stopped_reason = f"arm_{summary.status}"
        both = pair.get("S0", {}).get("status") == "completed" and pair.get("S1", {}).get("status") == "completed"
        pair["paired"] = both
        if both:
            pair["paired_at"] = utc_now()
        state.updated_at = utc_now()
        atomic_write_json(state_path, state.model_dump(mode="json"))
        append_event(study_dir, "pair_finished", {"case_id": case_id, "paired": both})

    completed = sum(1 for pair in state.pairs.values() if pair.get("paired"))
    state.phase = "complete" if completed >= len(config.holdout_case_ids) else "partial"
    state.updated_at = utc_now()
    atomic_write_json(state_path, state.model_dump(mode="json"))
    append_event(study_dir, "study_finished", {"phase": state.phase, "pairs_completed": completed})
    return StudySummary(
        study_id=config.study_id,
        phase=state.phase,
        pairs_completed=completed,
        pairs_total=len(config.holdout_case_ids),
        stopped_reason=state.stopped_reason,
        study_dir=str(study_dir),
    )
