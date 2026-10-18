"""Episode state machine: public input -> decision -> sealed experiment -> update."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .cases import build_public_case, generate_case, hash_dataset, load_case_specs
from .experiments import (
    ExperimentError,
    compute_baselines,
    run_sealed_experiment,
    score_prediction,
    validate_request_against_tool,
)
from .provider import ScientistProvider
from .schema import (
    Decision,
    EpisodeConfig,
    EpisodeState,
    EpisodeSummary,
    ExperimentContext,
    ExperimentResult,
    ProviderResponse,
)
from .scientist import (
    DecisionParseError,
    build_repair_request,
    build_request,
    load_rule_text,
    parse_decision,
    summarize_decision,
    summarize_result,
)
from .splits import build_all_splits
from .storage import (
    append_event,
    atomic_write_json,
    cache_key,
    canonical_json,
    ensure_dir,
    load_result,
    read_cache,
    seal_prediction,
    sha256_text,
    utc_now,
    write_cache,
    write_state,
)

RANDOM_LABEL_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _redacted(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if any(token in key.lower() for token in ("key", "secret", "token")) else _redacted(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    return value


def _usage_tokens(response: ProviderResponse) -> int:
    total = response.usage.get("total_tokens", 0)
    if isinstance(total, (int, float)) and total > 0:
        return int(total)
    prompt = response.usage.get("prompt_tokens", 0)
    completion = response.usage.get("completion_tokens", 0)
    return int(prompt if isinstance(prompt, (int, float)) else 0) + int(
        completion if isinstance(completion, (int, float)) else 0
    )


def _call_model(
    provider: ScientistProvider,
    request: object,
    run_dir: Path,
    counter: int,
    state: EpisodeState,
) -> tuple[ProviderResponse, bool]:
    key = cache_key(
        {
            "rule_hash": getattr(request, "rule_hash", ""),
            "messages": getattr(request, "messages", []),
            "stage": getattr(request, "stage", ""),
            "model_settings": getattr(request, "model_settings", {}),
            "model": provider.model_name,
            "backend": provider.backend,
        }
    )
    cached = read_cache(run_dir, key)
    if cached is not None:
        response = ProviderResponse.model_validate(cached)
        return response, True
    response = provider.decide(request)  # type: ignore[arg-type]
    if response.status == "ok":
        write_cache(run_dir, key, response.model_dump(mode="json"))
    atomic_write_json(run_dir / f"response_{counter:03d}.json", response.model_dump(mode="json"))
    return response, False


def _summary_from_state(
    config: EpisodeConfig,
    run_dir: Path,
    state: EpisodeState,
    status: str,
    predictions_total: int,
    predictions_hit: int,
) -> EpisodeSummary:
    return EpisodeSummary(
        episode_id=config.episode_id,
        case_id=config.case_id,
        status=status,
        backend=config.backend,
        model=config.model or state.model,
        actions_used=state.actions_used,
        calls_used=state.calls_used,
        attempts_used=state.attempts_used,
        tokens_used=state.tokens_used,
        predictions_total=predictions_total,
        predictions_hit=predictions_hit,
        stop_reason=state.stop_reason,
        run_dir=str(run_dir),
    )


def run_episode(config: EpisodeConfig, provider: ScientistProvider, *, resume: bool = False) -> EpisodeSummary:
    run_dir = ensure_dir(Path(config.run_dir))
    specs = load_case_specs(Path(config.case_specs_path))
    if config.case_id not in specs:
        raise ValueError(f"unknown case {config.case_id}")
    spec = specs[config.case_id]
    dataset = generate_case(spec)
    splits = build_all_splits(dataset, spec.split_seed)
    baseline = compute_baselines(dataset, splits)
    public_case = build_public_case(dataset, baseline)
    rule_text = load_rule_text(Path(config.rule_path))
    rule_version = Path(config.rule_path).stem
    context = ExperimentContext(
        splits=splits,
        random_label_seeds=list(RANDOM_LABEL_SEEDS),
        tool_version="1.0",
        timeout_seconds=300,
        data_hash=hash_dataset(dataset),
        seed=spec.model_seed,
    )
    facts: dict[str, object] | None = None
    if config.shared_facts_path and Path(config.shared_facts_path).exists():
        facts = json.loads(Path(config.shared_facts_path).read_text(encoding="utf-8"))

    atomic_write_json(run_dir / "public_input.json", public_case.model_dump(mode="json"))
    atomic_write_json(
        run_dir / "config_snapshot.json",
        {
            "episode": _redacted(config.model_dump(mode="json")),
            "rule_sha256": sha256_text(rule_text),
            "data_hash": context.data_hash,
            "case_id": public_case.case_id,
        },
    )
    state_path = run_dir / "state.json"
    existing = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    if existing is not None:
        state = EpisodeState.model_validate(existing)
        resume = True
    else:
        state = EpisodeState(
            episode_id=config.episode_id,
            case_id=config.case_id,
            rule_version=rule_version,
            phase="running",
            backend=provider.backend,  # type: ignore[arg-type]
            provider=provider.provider_name,
            model=provider.model_name,
            started_at=utc_now(),
            updated_at=utc_now(),
        )
    history_path = run_dir / "history.json"
    history: list[dict[str, object]] = []
    executed_request_ids: set[str] = set()
    executed_action_keys: set[str] = set()
    scores: list[dict[str, object]] = []
    predictions_total = 0
    predictions_hit = 0
    if resume and history_path.exists():
        loaded_history = json.loads(history_path.read_text(encoding="utf-8"))
        if isinstance(loaded_history, list):
            history = [item for item in loaded_history if isinstance(item, dict)]
            for item in history:
                action_summary = item.get("action", {})
                action_payload = action_summary.get("action") if isinstance(action_summary, dict) else None
                if isinstance(action_payload, dict) and isinstance(action_payload.get("request_id"), str):
                    executed_request_ids.add(action_payload["request_id"])
                    executed_action_keys.add(
                        sha256_text(
                            canonical_json(
                                {"tool_id": action_payload.get("tool_id"), "parameters": action_payload.get("parameters", {})}
                            )
                        )
                    )
                score = item.get("prediction_score")
                if isinstance(score, dict):
                    if score.get("status") == "scored":
                        predictions_total += 1
                        if bool(score.get("hit")):
                            predictions_hit += 1
                    scores.append(
                        {
                            "request_id": action_payload.get("request_id") if isinstance(action_payload, dict) else "",
                            "tool_id": action_payload.get("tool_id") if isinstance(action_payload, dict) else "",
                            "score": score,
                            "result": item.get("result", {}),
                        }
                    )
    if resume:
        append_event(run_dir, "episode_resumed", {"episode_id": config.episode_id, "at": utc_now()})
        state.phase = "running"
        state.updated_at = utc_now()
        write_state(run_dir, state)
    else:
        append_event(
            run_dir,
            "episode_started",
            {
                "episode_id": config.episode_id,
                "case_id": config.case_id,
                "rule_version": rule_version,
                "backend": provider.backend,
                "provider": provider.provider_name,
                "model": provider.model_name,
            },
        )
        state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        write_state(run_dir, state)

    force_stop = state.actions_used >= config.max_actions
    stage = "final" if force_stop else ("initial" if state.actions_used == 0 else f"after_action_{state.actions_used}")
    stop_reason = ""
    status = "incomplete"
    existing_requests = [int(path.stem.split("_")[1]) for path in run_dir.glob("request_*.json") if path.stem.split("_")[-1].isdigit()]
    counter = max(existing_requests, default=0)
    deadline = _deadline(config.deadline)

    while state.calls_used < config.max_calls:
        if _now() >= deadline:
            stop_reason = "deadline"
            state.stop_reason = stop_reason
            state.updated_at = utc_now()
            append_event(run_dir, "episode_stopped", {"reason": "deadline"})
            write_state(run_dir, state)
            break
        if state.attempts_used >= config.max_attempts:
            stop_reason = "attempt_budget"
            state.stop_reason = stop_reason
            state.updated_at = utc_now()
            append_event(run_dir, "episode_stopped", {"reason": "attempt_budget"})
            write_state(run_dir, state)
            break
        request = build_request(
            public_case,
            rule_text,
            history=history,
            development_facts=facts,
            stage=stage,
            force_stop=force_stop,
        )
        counter += 1
        atomic_write_json(run_dir / f"request_{counter:03d}.json", request.model_dump(mode="json"))
        append_event(
            run_dir,
            "model_request",
            {"request_id": request.request_id, "stage": stage, "counter": counter},
        )
        state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        response, reused = _call_model(provider, request, run_dir, counter, state)
        state.calls_used += 1
        state.attempts_used += 1
        state.tokens_used += _usage_tokens(response)
        state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        append_event(
            run_dir,
            "model_response_reused" if reused else "model_response",
            {
                "request_id": request.request_id,
                "status": response.status,
                "model": response.model_id,
                "usage": response.usage,
                "latency_ms": response.latency_ms,
                "reused": reused,
            },
        )
        state.updated_at = utc_now()
        write_state(run_dir, state)
        if response.status != "ok":
            stop_reason = f"provider_{response.status}"
            state.phase = "blocked"
            state.stop_reason = stop_reason
            append_event(run_dir, "episode_blocked", {"reason": stop_reason, "error": response.error})
            write_state(run_dir, state)
            status = "blocked"
            break
        try:
            decision = parse_decision(response.visible_text)
            decision_text = response.visible_text
        except DecisionParseError as error:
            repair = build_repair_request(
                response.visible_text,
                str(error),
                rule_text=rule_text,
                public_input_hash=request.public_input_hash,
            )
            counter += 1
            atomic_write_json(run_dir / f"request_{counter:03d}.json", repair.model_dump(mode="json"))
            append_event(run_dir, "format_repair_request", {"request_id": repair.request_id, "error": str(error)})
            repaired, repair_reused = _call_model(provider, repair, run_dir, counter, state)
            state.attempts_used += 1
            state.tokens_used += _usage_tokens(repaired)
            append_event(
                run_dir,
                "format_repair_response",
                {
                    "request_id": repair.request_id,
                    "status": repaired.status,
                    "reused": repair_reused,
                    "usage": repaired.usage,
                },
            )
            if repaired.status != "ok":
                stop_reason = f"repair_provider_{repaired.status}"
                state.phase = "blocked"
                state.stop_reason = stop_reason
                write_state(run_dir, state)
                status = "blocked"
                break
            try:
                decision = parse_decision(repaired.visible_text)
                decision_text = repaired.visible_text
            except DecisionParseError as second_error:
                stop_reason = "invalid_decision_after_repair"
                state.phase = "failed"
                state.stop_reason = stop_reason
                append_event(run_dir, "episode_failed", {"reason": stop_reason, "error": str(second_error)})
                write_state(run_dir, state)
                status = "failed"
                break
        if force_stop and decision.decision_type != "stop":
            repair = build_repair_request(
                decision_text,
                "force_stop=True requires decision_type='stop'. Do not request another action. "
                "Use the evidence already in history and return a final stop decision.",
                rule_text=rule_text,
                public_input_hash=request.public_input_hash,
            )
            counter += 1
            atomic_write_json(run_dir / f"request_{counter:03d}.json", repair.model_dump(mode="json"))
            append_event(run_dir, "constraint_repair_request", {"request_id": repair.request_id})
            repaired, repair_reused = _call_model(provider, repair, run_dir, counter, state)
            state.attempts_used += 1
            state.tokens_used += _usage_tokens(repaired)
            append_event(
                run_dir,
                "constraint_repair_response",
                {"request_id": repair.request_id, "status": repaired.status, "reused": repair_reused, "usage": repaired.usage},
            )
            if repaired.status != "ok":
                stop_reason = f"constraint_repair_provider_{repaired.status}"
                state.phase = "blocked"
                state.stop_reason = stop_reason
                write_state(run_dir, state)
                status = "blocked"
                break
            try:
                repaired_decision = parse_decision(repaired.visible_text)
            except DecisionParseError as error:
                stop_reason = "invalid_constraint_repair"
                state.phase = "failed"
                state.stop_reason = stop_reason
                append_event(run_dir, "episode_failed", {"reason": stop_reason, "error": str(error)})
                write_state(run_dir, state)
                status = "failed"
                break
            if repaired_decision.decision_type != "stop":
                stop_reason = "force_stop_action_rejected"
                state.phase = "failed"
                state.stop_reason = stop_reason
                append_event(run_dir, "episode_failed", {"reason": stop_reason})
                write_state(run_dir, state)
                status = "failed"
                break
            decision = repaired_decision
        if decision.decision_type == "stop":
            final = {
                "episode_id": config.episode_id,
                "case_id": config.case_id,
                "rule_version": rule_version,
                "backend": provider.backend,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "decision": decision.model_dump(mode="json"),
                "scores": scores,
                "predictions_total": predictions_total,
                "predictions_hit": predictions_hit,
                "stop_reason": decision.stop.reason if decision.stop else "model_stop",
                "created_at": utc_now(),
            }
            atomic_write_json(run_dir / "final.json", final)
            append_event(run_dir, "decision_final", {"request_id": request.request_id, "reason": final["stop_reason"]})
            atomic_write_json(history_path, history)
            state.phase = "completed"
            state.stop_reason = str(final["stop_reason"])
            state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
            write_state(run_dir, state)
            status = "completed"
            stop_reason = state.stop_reason
            break
        if decision.action is None:
            stop_reason = "decision_without_action_or_stop"
            state.phase = "failed"
            state.stop_reason = stop_reason
            status = "failed"
            append_event(run_dir, "episode_failed", {"reason": stop_reason})
            write_state(run_dir, state)
            break
        action = decision.action
        if state.actions_used >= config.max_actions:
            stop_reason = "action_budget_exceeded"
            state.phase = "failed"
            state.stop_reason = stop_reason
            status = "failed"
            append_event(run_dir, "episode_failed", {"reason": stop_reason})
            write_state(run_dir, state)
            break
        try:
            validate_request_against_tool(action)
        except ExperimentError as error:
            stop_reason = f"invalid_action: {error}"
            state.phase = "failed"
            state.stop_reason = stop_reason
            status = "failed"
            append_event(run_dir, "episode_failed", {"reason": stop_reason})
            write_state(run_dir, state)
            break
        if action.request_id in executed_request_ids or sha256_text(
            canonical_json({"tool_id": action.tool_id, "parameters": action.parameters})
        ) in executed_action_keys:
            append_event(run_dir, "duplicate_action", {"request_id": action.request_id, "tool_id": action.tool_id})
            history.append(
                {
                    "action": summarize_decision(decision),
                    "result": {"duplicate": True, "reason": "the same experiment request was already executed"},
                }
            )
            state.actions_used += 1
            if state.actions_used >= config.max_actions:
                force_stop = True
                stage = "final"
            state.updated_at = utc_now()
            write_state(run_dir, state)
            continue
        sealed = seal_prediction(run_dir, action)
        state.last_event_sequence = sealed.event_sequence
        append_event(run_dir, "experiment_started", {"request_id": action.request_id, "tool_id": action.tool_id})
        existing_result = load_result(run_dir, action.request_id)
        if existing_result is not None:
            result = existing_result
            append_event(run_dir, "experiment_result_reused", {"request_id": action.request_id, "tool_id": action.tool_id})
        else:
            started = time.perf_counter()
            try:
                result = run_sealed_experiment(dataset, sealed, context)
            except Exception as error:  # noqa: BLE001 - experiment boundary
                stop_reason = f"experiment_failed: {error}"
                state.phase = "failed"
                state.stop_reason = stop_reason
                status = "failed"
                append_event(run_dir, "episode_failed", {"reason": stop_reason})
                write_state(run_dir, state)
                break
            elapsed = time.perf_counter() - started
            if elapsed > context.timeout_seconds:
                result = result.model_copy(update={"valid": False, "invalid_reason": "experiment timeout"})
            atomic_write_json(run_dir / f"result_{counter:03d}.json", result.model_dump(mode="json"))
            append_event(
                run_dir,
                "experiment_result",
                {"request_id": action.request_id, "tool_id": action.tool_id, "valid": result.valid, "result_path": f"result_{counter:03d}.json"},
            )
        score = score_prediction(action.prediction, result)
        scores.append({"request_id": action.request_id, "tool_id": action.tool_id, "score": score, "result": result.model_dump(mode="json")})
        if score.get("status") == "scored":
            predictions_total += 1
            if bool(score.get("hit")):
                predictions_hit += 1
        atomic_write_json(run_dir / f"score_{counter:03d}.json", scores[-1])
        executed_request_ids.add(action.request_id)
        executed_action_keys.add(sha256_text(canonical_json({"tool_id": action.tool_id, "parameters": action.parameters})))
        state.actions_used += 1
        history.append(
            {
                "action": summarize_decision(decision),
                "result": summarize_result(result),
                "prediction_score": score,
            }
        )
        atomic_write_json(history_path, history)
        state.updated_at = utc_now()
        state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        write_state(run_dir, state)
        if state.actions_used >= config.max_actions:
            force_stop = True
            stage = "final"
        else:
            stage = f"after_action_{state.actions_used}"

    if status == "incomplete":
        final = {
            "episode_id": config.episode_id,
            "case_id": config.case_id,
            "rule_version": rule_version,
            "backend": provider.backend,
            "provider": provider.provider_name,
            "model": provider.model_name,
            "status": "incomplete",
            "scores": scores,
            "predictions_total": predictions_total,
            "predictions_hit": predictions_hit,
            "stop_reason": stop_reason or "call_budget",
            "created_at": utc_now(),
        }
        atomic_write_json(run_dir / "final.json", final)
        append_event(run_dir, "episode_incomplete", {"reason": final["stop_reason"]})
        atomic_write_json(history_path, history)
        state.phase = "incomplete"
        state.stop_reason = str(final["stop_reason"])
        state.last_event_sequence = len(Path(run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        write_state(run_dir, state)

    summary = _summary_from_state(config, run_dir, state, status, predictions_total, predictions_hit)
    lines = [
        f"# Episode {config.episode_id}",
        "",
        f"- case: {config.case_id}",
        f"- rule: {rule_version}",
        f"- backend: {provider.backend} / {provider.provider_name} / {provider.model_name}",
        f"- status: {status}",
        f"- actions: {state.actions_used}; calls: {state.calls_used}; attempts: {state.attempts_used}; tokens: {state.tokens_used}",
        f"- predictions: {predictions_hit}/{predictions_total}",
        f"- stop reason: {state.stop_reason}",
        "",
        "## Scores",
        "",
    ]
    for item in scores:
        lines.append(f"- `{item['tool_id']}`: {json.dumps(item['score'], ensure_ascii=False)}")
    lines.append("")
    (run_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def resume_episode(config: EpisodeConfig, provider: ScientistProvider) -> EpisodeSummary:
    run_dir = Path(config.run_dir)
    state_path = run_dir / "state.json"
    if not state_path.exists():
        return run_episode(config, provider)
    state = EpisodeState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))
    if state.phase == "completed":
        final_path = run_dir / "final.json"
        total = 0
        hit = 0
        if final_path.exists():
            final = json.loads(final_path.read_text(encoding="utf-8"))
            total = int(final.get("predictions_total", 0))
            hit = int(final.get("predictions_hit", 0))
        return _summary_from_state(config, run_dir, state, "completed", total, hit)
    return run_episode(config, provider, resume=True)
