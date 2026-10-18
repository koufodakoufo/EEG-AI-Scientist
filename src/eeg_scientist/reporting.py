"""Generate the morning-facing reports and the review bundle from saved records."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import cast

from .schema import ReportPaths
from .storage import ensure_dir


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001 - report boundary
        return default


def _record_from_dir(
    scope: str,
    case_id: str,
    arm: str,
    arm_dir: Path,
    specs: dict[str, object],
) -> dict[str, object]:
    state = _read_json(arm_dir / "state.json", {})
    final = _read_json(arm_dir / "final.json", {})
    public = _read_json(arm_dir / "public_input.json", {})
    history = _read_json(arm_dir / "history.json", [])
    if not isinstance(state, dict):
        state = {}
    if not isinstance(final, dict):
        final = {}
    if not isinstance(public, dict):
        public = {}
    if not isinstance(history, list):
        history = []
    scores: list[dict[str, object]] = []
    for score_path in sorted(arm_dir.glob("score_*.json")):
        score = _read_json(score_path, {})
        if isinstance(score, dict):
            scores.append(score)
    event_reason = ""
    events_path = arm_dir / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("event_type") in {
                "episode_failed",
                "episode_blocked",
                "episode_stopped",
                "episode_incomplete",
            }:
                payload = event.get("payload", {})
                if isinstance(payload, dict) and payload.get("reason"):
                    event_reason = str(payload["reason"])
    spec = specs.get(case_id, {}) if isinstance(specs.get(case_id, {}), dict) else {}
    return {
        "scope": scope,
        "case_id": case_id,
        "arm": arm,
        "run_dir": str(arm_dir),
        "status": final.get("status", state.get("phase", "unknown")),
        "backend": final.get("backend", state.get("backend", "")),
        "provider": final.get("provider", state.get("provider", "")),
        "model": final.get("model", state.get("model", "")),
        "rule_version": final.get("rule_version", state.get("rule_version", "")),
        "actions_used": int(state.get("actions_used", 0)),
        "calls_used": int(state.get("calls_used", 0)),
        "attempts_used": int(state.get("attempts_used", 0)),
        "tokens_used": int(state.get("tokens_used", 0)),
        "predictions_total": int(final.get("predictions_total", 0)),
        "predictions_hit": int(final.get("predictions_hit", 0)),
        "stop_reason": final.get("stop_reason", state.get("stop_reason", "")),
        "event_reason": event_reason,
        "baseline": public.get("baseline", {}),
        "scores": scores,
        "history": history,
        "final": final,
        "family_review_only": spec.get("family") if isinstance(spec, dict) else None,
        "data_seed_review_only": spec.get("data_seed") if isinstance(spec, dict) else None,
    }


def _preflight_model_info(output_dir: Path, model_name: str) -> dict[str, object]:
    path = output_dir / "PREFLIGHT.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    info: dict[str, object] = {}
    digest = re.search(
        r'"name":\s*"' + re.escape(model_name) + r'".{0,1200}?"digest":\s*"([0-9a-f]{64})"',
        text,
        flags=re.DOTALL,
    )
    if digest:
        info["digest"] = digest.group(1)
    context = re.search(
        r'"name":\s*"' + re.escape(model_name) + r'".{0,1600}?"context_length":\s*(\d+)',
        text,
        flags=re.DOTALL,
    )
    if context:
        info["context_length"] = int(context.group(1))
    return info


def _episode_records(study_dir: Path, specs: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for scope, base in (("development", study_dir / "development"), ("holdout", study_dir / "holdout")):
        if not base.exists():
            continue
        for case_dir in sorted(path for path in base.iterdir() if path.is_dir()):
            for arm_dir in sorted(path for path in case_dir.iterdir() if path.is_dir()):
                arm = arm_dir.name.upper() if scope == "holdout" else "S0"
                records.append(_record_from_dir(scope, case_dir.name, arm, arm_dir, specs))
    e1_base = Path("runs/dev_e1")
    if e1_base.exists():
        for arm_dir in sorted(path for path in e1_base.iterdir() if path.is_dir()):
            state = _read_json(arm_dir / "state.json", {})
            case_id = state.get("case_id", "case_001") if isinstance(state, dict) else "case_001"
            records.append(_record_from_dir("e1_dev", str(case_id), arm_dir.name, arm_dir, specs))
    return records


def _counts(records: list[dict[str, object]], state: dict[str, object]) -> dict[str, object]:
    real = [r for r in records if r["backend"] == "real_llm" and r["status"] == "completed"]
    scripted = [r for r in records if r["backend"] in ("scripted", "mock")]
    holdout = [r for r in records if r["scope"] == "holdout"]
    pairs = {
        case_id
        for case_id in {str(r["case_id"]) for r in holdout}
        if {"S0", "S1"}.issubset({str(r["arm"]) for r in holdout if r["case_id"] == case_id and r["status"] == "completed"})
    }
    return {
        "real_llm_episodes": len(real),
        "scripted_or_mock_episodes": len(scripted),
        "development_episodes": len([r for r in records if r["scope"] == "development"]),
        "holdout_episodes": len(holdout),
        "e1_dev_episodes": len([r for r in records if r["scope"] == "e1_dev"]),
        "complete_pairs": len(pairs),
        "pairs_total": len({str(r["case_id"]) for r in holdout}),
        "total_actions": sum(int(r["actions_used"]) for r in records),
        "total_calls": sum(int(r["calls_used"]) for r in records),
        "total_tokens": sum(int(r["tokens_used"]) for r in records),
        "stopped_reason": state.get("stopped_reason", ""),
    }


def _e_level(freeze: dict[str, object], counts: dict[str, object]) -> str:
    if freeze and int(counts["complete_pairs"]) >= 4 and int(counts["real_llm_episodes"]) > 0:
        return "E2"
    if int(counts["real_llm_episodes"]) > 0 and int(counts["total_actions"]) > 0:
        return "E1"
    return "E0"


def _baseline_table(records: list[dict[str, object]]) -> str:
    seen: dict[str, dict[str, object]] = {}
    for record in records:
        baseline = record.get("baseline", {})
        if isinstance(baseline, dict) and record["case_id"] not in seen:
            seen[str(record["case_id"])] = baseline
    lines = [
        "| case_id | window BA | trial BA | subject BA | gap window-trial | trial-aggregated window BA |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case_id, baseline in sorted(seen.items()):
        lines.append(
            f"| {case_id} | {float(baseline.get('window_balanced_accuracy', float('nan'))):.3f} | "
            f"{float(baseline.get('trial_balanced_accuracy', float('nan'))):.3f} | "
            f"{float(baseline.get('subject_balanced_accuracy', float('nan'))):.3f} | "
            f"{float(baseline.get('gap_window_minus_trial', float('nan'))):+.3f} | "
            f"{float(baseline.get('window_trial_aggregated_balanced_accuracy', float('nan'))):.3f} |"
        )
    return "\n".join(lines)


def _tool_table(records: list[dict[str, object]]) -> str:
    lines = [
        "| case_id | arm | tool | valid | key metrics |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        scores = record.get("scores", [])
        if not isinstance(scores, list):
            continue
        for item in scores:
            if not isinstance(item, dict):
                continue
            tool = str(item.get("tool_id", ""))
            result = item.get("result", {})
            metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
            if not isinstance(metrics, dict):
                metrics = {}
            selected = {
                key: round(float(value), 3)
                for key, value in metrics.items()
                if key.endswith("mean") or key.endswith("balanced_accuracy") or key.endswith("chance")
            }
            lines.append(
                f"| {record['case_id']} | {record['arm']} | {tool} | {result.get('valid') if isinstance(result, dict) else ''} | "
                f"{json.dumps(selected, ensure_ascii=False)} |"
            )
    return "\n".join(lines) if len(lines) > 2 else "_No diagnostic tool results were saved._"


def _paired_table(records: list[dict[str, object]]) -> str:
    by_case: dict[str, dict[str, dict[str, object]]] = {}
    for record in records:
        if record["scope"] == "holdout":
            by_case.setdefault(str(record["case_id"]), {})[str(record["arm"])] = record
    lines = [
        "| case_id | S0 status | S1 status | S0 hits/total | S1 hits/total | S0 actions | S1 actions | S0 tokens | S1 tokens | paired |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for case_id, arms in sorted(by_case.items()):
        s0 = arms.get("S0", {})
        s1 = arms.get("S1", {})
        paired = s0.get("status") == "completed" and s1.get("status") == "completed"
        lines.append(
            f"| {case_id} | {s0.get('status', 'missing')} | {s1.get('status', 'missing')} | "
            f"{s0.get('predictions_hit', 0)}/{s0.get('predictions_total', 0)} | "
            f"{s1.get('predictions_hit', 0)}/{s1.get('predictions_total', 0)} | "
            f"{s0.get('actions_used', 0)} | {s1.get('actions_used', 0)} | "
            f"{s0.get('tokens_used', 0)} | {s1.get('tokens_used', 0)} | {paired} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "_No holdout pair records._"


def _failure_section(records: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for record in records:
        if record["status"] == "completed" and int(record["predictions_total"]) > 0:
            continue
        lines.append(
            f"## {record['case_id']} / {record['arm']}\n\n"
            f"- status: `{record['status']}`\n"
            f"- stop reason: `{record.get('stop_reason') or record.get('event_reason', '')}`\n"
            f"- actions: {record['actions_used']}; predictions: {record['predictions_hit']}/{record['predictions_total']}\n"
            f"- run: `{record['run_dir']}`\n"
        )
    if not lines:
        lines.append(
            "## No substantive failure recorded\n\n"
            "This is not evidence that the method is reliable. The most important unresolved boundary is that the study is small, "
            "synthetic, model-specific, and does not establish a population-level EEG mechanism. See the paired table and the "
            "review_only case specifications for the hidden mechanisms.\n"
        )
    return "\n".join(lines)


CORE_WALKTHROUGH = """# CORE CODE WALKTHROUGH

This is a reading guide, not a line-by-line transcript. LLM = Large Language Model, EEG = Electroencephalography, RSI = Recursive Self-Improvement. The project does **not** train an EEG foundation model and does **not** demonstrate RSI.

## 1. `schema.py`: a scientific claim as a structured object

- Input: model JSON, case JSON, experiment results.
- Output: Pydantic `Decision`, `ExperimentRequest`, `Prediction`, `ExperimentResult`; frozen dataclasses for numpy arrays and splits.
- Core logic: `Decision` requires exactly one of `action` and `stop`; numeric predictions require a metric key and direction; `not_applicable` requires check facts; arrays are validated for shape, labels, and global IDs.
- Why: the controller, not the model, decides what is executable. Types encode the minimum traceability fields.
- How to check: read `Decision`, `Prediction`, `FeatureDataset.__post_init__`, and `ExperimentResult._finite_metrics` in `src/eeg_scientist/schema.py`.

Self-test:
1. Which fields make a prediction auditable before the result? (Answer: `metric_key`, `primary_direction`, `threshold`, `update_rule_if_opposite`, and the sealed event in `storage.py`.)
2. What happens to a `not_applicable` prediction in the numeric hit-rate denominator? (Answer: it is reported separately and excluded from the numeric denominator in `score_prediction`.)

## 2. `splits.py`: why a shuffle does not remove identity

- Input: `FeatureDataset`, split level, seed.
- Output: `SplitIndices` with train/test row indices and `SplitAudit`.
- Core logic: window split keeps some windows of the same trial on both sides; trial split removes trial overlap; subject split removes subject overlap. The audit reports sample/trial/session/subject intersections and single-class invalidity.
- Why: a high random-shuffle score can still share trial identity; the estimand depends on which unit is held out.
- How to check: `build_split`, `audit_split`, and `tests/test_core.py::test_subject_split_disjoint`.

Self-test:
1. Which intersections are allowed for a window split? (Answer: subject/session/trial overlap is allowed; sample overlap is not.)
2. Which split is the strictest for a new participant? (Answer: subject split.)

## 3. `experiments.py`: trial random labels versus window random labels

- Input: dataset, sealed experiment request, fixed context (splits, random label seeds, classifier).
- Output: `ExperimentResult` with metrics, audit, randomization distribution, and validity.
- Core logic: every fit creates a new `StandardScaler` + `KNeighborsClassifier(n_neighbors=1)` pipeline on training rows only. `trial_random_labels` reassigns labels at trial level and shares them across windows; `window_random_labels` reassigns independently per window. `metadata_only` uses one-hot subject/session, not the feature matrix.
- Why: each fit on test rows would leak scaling; the random-label level changes the estimand.
- How to check: `fit_and_score`, `make_trial_random_labels`, `make_window_random_labels`, `_metadata_only`, and `tests/test_core.py`.

Self-test:
1. Why is `StandardScaler` inside the pipeline? (Answer: it is fit on training rows only; see `tests/test_core.py::test_scaler_fit_uses_training_rows_only`.)
2. Why does a window-random-label result not get a trial-aggregated score? (Answer: there is no trial-level true label after independent window randomization.)

## 4. `runner.py`: why the prediction is written first

- Input: `EpisodeConfig`, provider, public case.
- Output: `EpisodeSummary`, run directory with requests, predictions, results, events, state, final.
- Core logic: the controller builds a public request, calls the model, validates the decision, seals the prediction, executes the experiment, saves the result, and only then asks for the next decision. Up to three actions and four normal calls per episode; after three actions it forces a conclusion.
- Why: a prediction written after the result is not a prediction. The seal is an audit record, not external notarization.
- How to check: `run_episode`, `seal_prediction`, `run_sealed_experiment`, and the event-order test.

Self-test:
1. What happens if the model requests an experiment without a valid sealed prediction? (Answer: `run_sealed_experiment` refuses.)
2. Where is the action budget enforced? (Answer: the runner checks `state.actions_used` and sets `force_stop` after the third action.)

## 5. `scientist.py` and `provider.py`: what the model actually receives

- Input: `PublicCase`, rule text, public development facts, action history, tool specifications.
- Output: messages, parsed `Decision`, optional one-shot format repair.
- Core logic: the model never receives `CaseSpec`, family, seeds, hidden mechanism, other cases, or holdout results. The provider calls local Ollama native `/api/chat` with `think=false`, `format=json`, temperature 0. The repair call sees only the malformed output and validation error, not an unexecuted experiment result.
- Why: a model with repository access could read answers; the local model has no tools. The provider is a real_llm call, not a mock.
- How to check: `build_request`, `parse_decision`, `build_repair_request`, `OllamaProvider.decide`, and the secret-redaction test.

Self-test:
1. Which private fields are absent from the public request? (Answer: family, data seed, generator parameters, hidden answer, other cases, and holdout results.)
2. What is the difference between backend `real_llm` and `mock`? (Answer: `real_llm` records an actual provider response and usage; `mock` is only a test double and cannot satisfy E1/E2.)

## 6. `study.py`: what S0 and S1 share

- Input: study config, provider, private case specs.
- Output: development facts, Meta update, frozen S0/S1/facts/tools/model hashes, paired holdout runs.
- Core logic: S0 runs the two development cases; the Meta call sees only public development facts and event IDs; S1 adds up to three method rules; the freeze manifest records hashes; each holdout case runs S0 and S1 in pre-registered order with the same facts, tools, data, and model. The only allowed difference is the rule text.
- Why: if S1 sees holdout results or different tools, the comparison is contaminated.
- How to check: `freeze_study`, `_meta_update`, `_pair_order`, `tests/test_scientist_provider.py::test_s0_s1_share_same_public_facts_and_tools`, and `tests/test_scientist_provider.py::test_meta_request_uses_only_supplied_facts`.

Self-test:
1. What is frozen besides the rule text? (Answer: development facts, tool specs, model info, case-spec hashes, code hashes, seeds, classifier, and pair order.)
2. What happens if S1 is changed after freeze? (Answer: the study refuses to continue; a new version is required.)
"""


def render_reports(study_dir: Path, output_dir: Path | None = None) -> ReportPaths:
    study_dir = Path(study_dir)
    output_dir = ensure_dir(Path(output_dir or "reports"))
    state = _read_json(study_dir / "study_state.json", {})
    freeze = _read_json(study_dir / "FREEZE_MANIFEST.json", {})
    if not freeze:
        freeze = _read_json(Path("FREEZE_MANIFEST.json"), {})
    facts = _read_json(study_dir / "shared_development_facts.json", {})
    specs_raw = _read_json(Path("data/private/case_specs.json"), {"cases": []})
    specs: dict[str, object] = {}
    if isinstance(specs_raw, dict) and isinstance(specs_raw.get("cases"), list):
        for item in specs_raw["cases"]:
            if isinstance(item, dict) and isinstance(item.get("case_id"), str):
                specs[item["case_id"]] = item
    if not isinstance(state, dict):
        state = {}
    if not isinstance(freeze, dict):
        freeze = {}
    records = _episode_records(study_dir, specs)
    counts = _counts(records, state)
    level = _e_level(freeze, counts)
    test_summary = _read_json(output_dir / "test_summary.json", {"status": "not_recorded"})
    if not isinstance(test_summary, dict):
        test_summary = {"status": "not_recorded"}
    paired = _paired_table(records)
    baseline_table = _baseline_table(records)
    tool_table = _tool_table(records)
    episode_table = "\n".join(
        [
            "| case_id | data | seed (review-only) | arm | rule | backend | status | actions | calls | attempts | tokens | predictions | stop | run |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---:|---|---|---|",
            *[
                f"| {record['case_id']} | synthetic_features | {record.get('data_seed_review_only', '')} | {record['arm']} | {record['rule_version']} | {record['backend']} | {record['status']} | "
                f"{record['actions_used']} | {record['calls_used']} | {record['attempts_used']} | {record['tokens_used']} | "
                f"{record['predictions_hit']}/{record['predictions_total']} | {record.get('stop_reason') or record.get('event_reason', '')} | `{record['run_dir']}` |"
                for record in records
            ],
        ]
    )
    model = freeze.get("model", {}) if isinstance(freeze.get("model"), dict) else {}
    describe = model.get("describe", {}) if isinstance(model.get("describe"), dict) else {}
    details = describe.get("details", {}) if isinstance(describe.get("details"), dict) else {}
    model_summary = {
        "provider": model.get("provider"),
        "model": model.get("model"),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "context_length": details.get("context_length"),
        "digest": describe.get("digest") or model.get("digest"),
    }
    preflight_model = _preflight_model_info(output_dir, str(model_summary.get("model") or ""))
    if model_summary.get("digest") is None:
        model_summary["digest"] = preflight_model.get("digest")
    if model_summary.get("context_length") is None:
        model_summary["context_length"] = preflight_model.get("context_length")
    freeze_time = freeze.get("created_at", "not frozen")
    meta_info = freeze.get("meta", {}) if isinstance(freeze.get("meta"), dict) else {}
    meta_update = str(meta_info.get("update", "not_recorded"))
    meta_rules = int(meta_info.get("n_rules", 0) or 0)
    meta_errors = meta_info.get("meta_errors", [])
    if not isinstance(meta_errors, list):
        meta_errors = []
    study_tokens = sum(int(r["tokens_used"]) for r in records if r["scope"] in ("development", "holdout"))
    e1_tokens = sum(int(r["tokens_used"]) for r in records if r["scope"] == "e1_dev")
    meta_tokens = int(meta_info.get("meta_tokens", 0) or 0)
    costs = {
        "study_episode_tokens": study_tokens,
        "e1_dev_tokens": e1_tokens,
        "meta_tokens": meta_tokens,
        "total_recorded_tokens": study_tokens + e1_tokens + meta_tokens,
        "local_monetary_cost_usd": 0,
        "note": "Local Ollama; DSH development token/cost is a separate ledger.",
    }
    meta_text = ""
    if meta_errors or meta_update == "no_update":
        meta_text = (
            "## Meta method-update failure/limit\n\n"
            f"- update: `{meta_update}`; rules: {meta_rules}\n"
            f"- attempts: {meta_info.get('meta_attempts', 'unknown')}; tokens: {meta_info.get('meta_tokens', 'unknown')}\n"
            "- errors:\n"
            + "\n".join(f"  - {str(error)[:700]}" for error in meta_errors[:5])
            + "\n\nA `no_update` S1 is identical to S0 in rule content. The paired S0/S1 table is then a null-rule control; "
            "differences are model/order variation, not evidence of a rule effect. This is a limitation, not a success.\n"
        )
    zero_action = [r for r in records if int(r["actions_used"]) == 0]
    zero_action_text = ""
    if zero_action:
        zero_action_text = (
            f"- {len(zero_action)} episode(s) stopped with 0 actions: "
            + ", ".join(f"`{r['case_id']}/{r['arm']}`" for r in zero_action)
            + ". These are valid behavioral failures but weak paired comparisons.\n"
        )
    holdout_records = [r for r in records if r["scope"] == "holdout"]
    holdout_actions = sum(int(r["actions_used"]) for r in holdout_records)
    substantive_level = level
    substantive_caveat = ""
    if level == "E2" and (holdout_actions == 0 or meta_update == "no_update"):
        substantive_level = "E1"
        substantive_caveat = (
            "E2 is satisfied only as an engineering count (4 complete holdout pairs). "
            f"Holdout actions = {holdout_actions}; Meta update = `{meta_update}`. "
            "The S0/S1 table is therefore a behavioral/null-rule control, not an effective method-rule comparison. "
            "The substantive research evidence is E1."
        )
    level_label = f"{level} (engineering) / {substantive_level} (substantive)" if substantive_level != level else level
    post_freeze_note = (
        "Post-freeze edits were limited to presentation/reporting code (`reporting.py`); "
        "the study/experiment code hashes are recorded in `FREEZE_MANIFEST.json`."
    )
    report_data = {
        "study_id": state.get("study_id", study_dir.name),
        "phase": state.get("phase", ""),
        "e_level": level,
        "substantive_level": substantive_level,
        "substantive_caveat": substantive_caveat,
        "model_summary": model_summary,
        "costs": costs,
        "post_freeze_note": post_freeze_note,
        "counts": counts,
        "freeze": freeze,
        "test_summary": test_summary,
        "state": state,
        "records": records,
        "note": "Mechanism/family and data seeds are review-only fields; they never enter the Scientist public request.",
    }
    (output_dir / "report_data.json").write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    best = max(records, key=lambda r: (int(r["predictions_hit"]), int(r["actions_used"])), default=None)
    best_text = (
        f"`{best['case_id']}` / {best['arm']} with {best['predictions_hit']}/{best['predictions_total']} primary numeric hits and "
        f"{best['actions_used']} actions"
        if best
        else "no completed episode"
    )
    morning = f"""# MORNING REPORT

## 1. 本次达到哪个等级
**{level_label}**。{state.get('phase', 'unknown')}；配对完成 {counts['complete_pairs']}/{counts['pairs_total']}；停止原因：`{state.get('stopped_reason', '')}`。
{substantive_caveat}
这是受控合成数据的探索性结果，不是真实 EEG 发现，也不是 RSI 演示。

## 2. 真实 LLM / scripted / mock / S0-S1
- 真实 LLM episodes：{counts['real_llm_episodes']}
- scripted/mock episodes：{counts['scripted_or_mock_episodes']}
- 完整 S0/S1 配对：{counts['complete_pairs']}/{counts['pairs_total']}
- 总 actions：{counts['total_actions']}；总 calls：{counts['total_calls']}；项目记录 token：{counts['total_tokens']}

## 3. 模型、数据、代码版本、冻结时间
- 模型：{json.dumps(model_summary, ensure_ascii=False)}
- 数据：`synthetic_features`（EEG 风格分层特征，不是实测脑电）
- 冻结时间：{freeze_time}
- Meta 方法更新：`{meta_update}`；规则数：{meta_rules}
- 代码哈希与依赖：见 `FREEZE_MANIFEST.json`
- post-freeze note：{post_freeze_note}

## 4. 最值得看的一条证据
{best_text}。它支持“该固定模型的决策在该受控案例上可被执行和审计”；它不支持真实 EEG 机制、总体泛化或模型能力排序。

## 5. S1 改善/无变化/退步
见下方 paired 表。若 S1 与 S0 相同、变差或 `no_update`，都合法；4–8 个案例不支持统计确证。
{zero_action_text}

## 6. 成本
- 本地 Ollama：金额 $0；token 用量已记录。
- study episodes：{costs['study_episode_tokens']} tokens
- E1 dev episodes（含失败尝试）：{costs['e1_dev_tokens']} tokens
- Meta：{costs['meta_tokens']} tokens
- 合计（项目记录）：{costs['total_recorded_tokens']} tokens；上限 1,000,000。
- DSH 开发会话的 token/费用是另一账本，不由本项目统计。

## 7. 阻塞、风险、下一步
- 停止原因：`{state.get('stopped_reason', '')}`
- 当前风险：小样本、合成数据、单一 9B 模型、S1 可能无更新、`split_audit` 的 `not_applicable` 预测不进入数值命中率。
- 下次唯一最优先动作：先检查冻结是否成立和配对是否完整，再决定是否补第二数据种子；不要因为分数好看就直接扩成完整 RSI。

## Paired holdout
{paired}

## All episodes
{episode_table}

## Tests
- status: `{test_summary.get('status', 'not_recorded')}`
- exit code: `{test_summary.get('exit_code', 'not_recorded')}`
- command: `{test_summary.get('command', 'not_recorded')}`
- output: `{test_summary.get('output_path', 'not_recorded')}`

## Artifacts
- `reports/RESULTS_TABLE.md`
- `reports/FAILURE_CASES.md`
- `reports/CORE_CODE_WALKTHROUGH.md`
- `artifacts/review_bundle.zip`
- `PREFLIGHT.md` and `FREEZE_MANIFEST.json`
"""
    (output_dir / "MORNING_REPORT.md").write_text(morning, encoding="utf-8")
    results = f"""# RESULTS TABLE

## Episode table
{episode_table}

## Baseline table (initial public observation, computed from the actual data)
{baseline_table}

## Diagnostic tool table
{tool_table}

## Paired holdout table
{paired}

## Status
- E-level engineering: **{level}**
- E-level substantive: **{substantive_level}**
- caveat: {substantive_caveat or "none"}
- freeze hash: `{state.get('freeze_manifest_hash', '')}`
- Note: `synthetic_features`; 4–8 cases are exploratory, not a population-level inference. Classifier performance and Scientist decision quality are separate columns and must not be conflated.
"""
    (output_dir / "RESULTS_TABLE.md").write_text(results, encoding="utf-8")
    failures = f"""# FAILURE CASES

The following are records with no numeric primary prediction, incomplete status, or a non-completed arm. A missing failure is not evidence of success.

{_failure_section(records)}

{meta_text}

## Reviewer checklist (developer_review, not an automatic score)
For each episode, check:
1. Are the competing explanations really different?
2. Does the chosen experiment distinguish them?
3. Does the conclusion stay within the measured scope?
4. Is counterevidence or a null result acknowledged?

If no substantive failure was observed, the main unresolved boundary is the small synthetic, single-model design; this is a limitation, not proof of safety.
"""
    (output_dir / "FAILURE_CASES.md").write_text(failures, encoding="utf-8")
    (output_dir / "CORE_CODE_WALKTHROUGH.md").write_text(CORE_WALKTHROUGH, encoding="utf-8")
    reproduce = """# REPRODUCE

The working interpreter used for this run is the read-only Anaconda Python 3.12.4 fallback because `uv sync` could not finish in the network window. The project `.venv` is intentionally not modified by the fallback.

```powershell
cd X:\\projects\\EEG-AI-Scientist
$env:PYTHONPATH = 'src'
C:\\Users\\14090\\anaconda3\\python.exe -m pytest -q
C:\\Users\\14090\\anaconda3\\python.exe -m eeg_scientist.cli preflight --config configs/overnight.json
C:\\Users\\14090\\anaconda3\\python.exe -m eeg_scientist.cli overnight --config configs/overnight.json
C:\\Users\\14090\\anaconda3\\python.exe -m eeg_scientist.cli report --study runs\\study_20261019
```

The deterministic data and splits are reproducible from `data/private/case_specs.json`. Model outputs are not bit-identical even at temperature 0; the raw requests and responses are retained.
"""
    (output_dir / "REPRODUCE.md").write_text(reproduce, encoding="utf-8")
    bundle_path = ensure_dir(Path("artifacts")) / "review_bundle.zip"
    include: list[Path] = []
    for name in (
        "MORNING_REPORT.md",
        "RESULTS_TABLE.md",
        "FAILURE_CASES.md",
        "CORE_CODE_WALKTHROUGH.md",
        "PREFLIGHT.md",
        "CALIBRATION.md",
        "report_data.json",
        "REPRODUCE.md",
        "test_output.txt",
        "test_summary.json",
    ):
        path = output_dir / name
        if path.exists():
            include.append(path)
    for name in ("FREEZE_MANIFEST.json", "PROGRESS.md", "NEXT_ACTION.md", "DECISIONS.md", "pyproject.toml", "uv.lock"):
        path = Path(name)
        if path.exists():
            include.append(path)
    for directory in ("configs", "prompts", "memory"):
        base = Path(directory)
        if base.exists():
            include.extend(path for path in base.rglob("*") if path.is_file())
    facts_path = study_dir / "shared_development_facts.json"
    if facts_path.exists():
        include.append(facts_path)
    for path in study_dir.rglob("*"):
        if not path.is_file():
            continue
        if "cache" in path.parts:
            continue
        if path.name not in {
            "state.json",
            "final.json",
            "history.json",
            "public_input.json",
            "config_snapshot.json",
            "summary.md",
            "events.jsonl",
            "study_state.json",
            "study_events.jsonl",
        } and not path.name.startswith(("result_", "score_", "prediction_", "request_", "response_")):
            continue
        include.append(path)
    e1_dir = Path("runs/dev_e1")
    if e1_dir.exists():
        for path in e1_dir.rglob("*"):
            if not path.is_file() or "cache" in path.parts:
                continue
            if path.name not in {
                "state.json",
                "final.json",
                "history.json",
                "public_input.json",
                "config_snapshot.json",
                "summary.md",
                "events.jsonl",
            } and not path.name.startswith(("result_", "score_", "prediction_", "request_", "response_")):
                continue
            include.append(path)
    for directory in ("src", "tests"):
        base = Path(directory)
        if base.exists():
            include.extend(path for path in base.rglob("*.py") if path.is_file())
    review_only = ensure_dir(Path("review_only"))
    private_specs = Path("data/private/case_specs.json")
    if private_specs.exists():
        (review_only / "PRIVATE_CASE_SPECS.json").write_text(private_specs.read_text(encoding="utf-8"), encoding="utf-8")
        (review_only / "README.md").write_text(
            "Evaluator-only material included for the human reviewer. It was not inserted into any Scientist prompt.\n",
            encoding="utf-8",
        )
        include.extend([review_only / "PRIVATE_CASE_SPECS.json", review_only / "README.md"])
    seen: set[str] = set()
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in include:
            name = str(path).replace("\\", "/")
            if name in seen:
                continue
            seen.add(name)
            archive.write(path, name)
    return ReportPaths(
        morning_report=str(output_dir / "MORNING_REPORT.md"),
        results_table=str(output_dir / "RESULTS_TABLE.md"),
        failure_cases=str(output_dir / "FAILURE_CASES.md"),
        walkthrough=str(output_dir / "CORE_CODE_WALKTHROUGH.md"),
        review_bundle=str(bundle_path),
    )
