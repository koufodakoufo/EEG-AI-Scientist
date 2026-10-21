"""Task C diagnostics: explanation regression and neutral-ID case episodes.

Two diagnostics are deliberately separated:

1. A raw historical 99%/50% table is shown without an answer template.  The
   response is preserved verbatim and checked with transparent, rule-based
   arithmetic/sentence checks.  These checks are not a scientific score.
2. Two synthetic cases with different generative structures are run through
   the existing decision state machine using neutral case IDs.  Family labels,
   generator parameters, and evaluator notes are never placed in the model
   context; the private mapping stays in the run directory and ``review_only``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

from ..deepseek_api import ChatClient, DeepSeekDecisionProvider
from ..ledger import BudgetLedger
from .runner import run_episode
from ..schema import EpisodeConfig, EpisodeSummary
from ..storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now

REGRESSION_SYSTEM = """You are a careful methodologist reviewing a reported table of classification results. Explain what the numbers do and do not support. Consider competing interpretations and say when the evidence is insufficient. Do not assume there is a single correct story. Answer in Chinese, with the numbers quoted explicitly."""

REGRESSION_TABLE = """下面是一组历史实验结果（不是今晚新做的实验）。同一份特征和同一套分类流程下，重新训练后得到：

| 条件 | window 切分 | trial 切分 |
|---|---:|---:|
| 原标签 | 99.3% | 49.6% |
| 试次级随机标签后重新训练 | 99.2% | 50.8% |

说明：trial 切分下，同一试次的所有窗口只出现在训练侧或测试侧；window 切分下，同一试次的不同窗口可以同时出现在训练侧和测试侧。随机化是在试次层级重新分配标签，同一试次的所有窗口共享新标签，然后重新训练分类器。"""

REGRESSION_QUESTION = """请回答：
1. 哪些数值发生了变化？变化幅度各是多少？哪些几乎没有变化？
2. 能否说“随机化使 trial 切分的性能从高水平降到了机会水平”？为什么？
3. 这些数字支持或不支持哪些关于任务语义泛化、窗口级泄漏、会话/被试因素的结论？
4. 还需要哪些对照或证据，才能区分仍然存在的竞争解释？

请列出至少两种竞争解释，并明确指出哪些结论目前不能下。"""


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?；;\n])", text) if item.strip()]


def _near(text: str, left: str, right: str, window: int = 80) -> bool:
    for match in re.finditer(re.escape(left), text):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        if right in text[start:end]:
            return True
    return False


def evaluate_regression(text: str) -> dict[str, object]:
    """Transparent rule checks.  A fail is a prompt for human review, not proof."""

    sentences = _sentences(text)
    near_chance_terms = ("机会", "随机水平", "接近50", "接近 50", "50%", "chance", "随机猜测")
    stable_terms = ("几乎不变", "没有明显变化", "基本不变", "仅变化0.1", "仅变化 0.1", "0.1个百分点", "稳定", "unchanged", "stable")
    split_terms = ("同一试次", "共享试次", "trial 重叠", "trial重叠", "窗口切分", "window 切分", "窗口级", "same trial")
    caution_terms = ("不能", "不足以", "无法", "不应", "不支持", "cannot", "not sufficient")
    generalization_terms = ("泛化", "语义", "泄漏", "leakage", "generaliz")

    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "pass": passed, "detail": detail})

    add(
        "recognizes_trial_baseline_near_chance",
        _near(text, "49.6", "机会", 100) or _near(text, "49.6", "50%", 100) or _near(text, "49.6", "随机", 100),
        "49.6% must be described as already near chance, not as a post-randomization collapse.",
    )
    add(
        "recognizes_window_stays_high",
        ("99.3" in text and "99.2" in text) and (any(term in text for term in stable_terms) or ("0.1" in text)),
        "window-level values 99.3% and 99.2% should be compared; the change is about 0.1 percentage point.",
    )
    add(
        "mentions_both_deltas",
        "0.1" in text and "1.2" in text,
        "Expected deltas: window -0.1 pp; trial +1.2 pp. This checks arithmetic presence, not correctness of interpretation.",
    )

    invalid_sentences: list[str] = []
    for sentence in sentences:
        if "随机" not in sentence:
            continue
        if not re.search(r"(trial|试次)", sentence, re.IGNORECASE):
            continue
        if not re.search(r"(下降|降低|降到|降至|drop|decreas)", sentence, re.IGNORECASE):
            continue
        if any(term in sentence for term in ("不能", "不是", "并非", "没有", "不应", "无法", "不等于")):
            continue
        if re.search(r"(99|9[0-9](\.\d+)?%?)", sentence) and re.search(r"(50|机会|chance)", sentence):
            invalid_sentences.append(sentence)
    add(
        "rejects_trial_collapse_claim",
        not invalid_sentences,
        "No sentence should claim that randomization moved trial performance from ~99% to chance."
        + (" Offending sentence(s): " + " | ".join(invalid_sentences) if invalid_sentences else ""),
    )
    add(
        "mentions_split_or_shared_trial",
        any(term in text for term in split_terms),
        "The window/trial split distinction or shared-trial structure should be named.",
    )
    add(
        "states_a_limit_on_generalization_claim",
        any(_near(text, term, caution, 150) for term in generalization_terms for caution in caution_terms),
        "The answer should say what cannot be concluded about semantic generalization or leakage.",
    )

    return {
        "checks": checks,
        "n_pass": sum(1 for item in checks if item["pass"]),
        "n_checks": len(checks),
        "ground_truth_arithmetic": {
            "window_change_percentage_points": round(99.2 - 99.3, 2),
            "trial_change_percentage_points": round(50.8 - 49.6, 2),
            "trial_baseline_is_near_chance": True,
        },
        "warning": "Rule-based checks only; they cannot establish that the scientific interpretation is correct.",
    }


def run_explanation_regression(
    client: ChatClient,
    *,
    run_dir: Path,
    max_tokens: int = 8000,
) -> dict[str, object]:
    target = ensure_dir(run_dir)
    user_text = f"{REGRESSION_TABLE}\n\n{REGRESSION_QUESTION}"
    atomic_write_text(
        target / "regression_prompt.md",
        "# Explanation regression prompt\n\n## System\n\n"
        + REGRESSION_SYSTEM
        + "\n\n## User\n\n"
        + user_text
        + "\n",
    )
    result = client.chat(
        [
            {"role": "system", "content": REGRESSION_SYSTEM},
            {"role": "user", "content": user_text},
        ],
        tools=None,
        max_tokens=max_tokens,
        json_mode=False,
        stage="regression_explanation",
    )
    evaluation = evaluate_regression(result.content)
    payload = {
        "created_at": utc_now(),
        "requested_model": result.requested_model,
        "returned_model": result.returned_model,
        "finish_reason": result.finish_reason,
        "usage": result.usage.model_dump(mode="json"),
        "response_text": result.content,
        "reasoning_chars": len(result.reasoning_content),
        "evaluation": evaluation,
    }
    atomic_write_json(target / "regression.json", payload)
    atomic_write_text(target / "regression_answer.md", result.content + "\n")
    atomic_write_text(
        target / "regression_review.md",
        "# Explanation regression: rule-based review\n\n"
        f"- returned_model: `{result.returned_model}`\n"
        f"- checks passed: {evaluation['n_pass']}/{evaluation['n_checks']}\n\n"
        + "\n".join(
            f"- [{'PASS' if item['pass'] else 'FAIL'}] `{item['check']}` — {item['detail']}"
            for item in cast(list[dict[str, object]], evaluation["checks"])
        )
        + "\n\nSee `regression_answer.md` for the verbatim answer. These are rule checks, not a scientific score.\n",
    )
    return payload


def _neutral_specs(source_specs_path: Path, target_path: Path, aliases: dict[str, str]) -> None:
    raw = json.loads(source_specs_path.read_text(encoding="utf-8"))
    cases = raw.get("cases", [])
    by_id = {item["case_id"]: item for item in cases if isinstance(item, dict)}
    selected: list[dict[str, object]] = []
    for alias, source_id in aliases.items():
        if source_id not in by_id:
            raise ValueError(f"source case {source_id} not found")
        clone = dict(by_id[source_id])
        clone["case_id"] = alias
        selected.append(clone)
    atomic_write_json(target_path, {"generator_version": raw.get("generator_version", "1.0"), "cases": selected})


def _numeric_grounding(final_text: str, history: list[dict[str, object]]) -> dict[str, object]:
    values: set[float] = set()
    for item in history:
        result = item.get("result", {})
        metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
        if isinstance(metrics, dict):
            for value in metrics.values():
                if isinstance(value, (int, float)):
                    values.add(round(float(value), 3))
    text_values = [float(match) for match in re.findall(r"\b(0\.\d{1,4}|[01]\.\d{1,4})\b", final_text)]
    matches: list[dict[str, object]] = []
    for text_value in text_values:
        for value in values:
            if abs(text_value - value) <= 0.002 or abs(text_value - value) <= 0.02 and value in {0.5, 0.0}:
                matches.append({"text_value": text_value, "result_value": value})
                break
    return {
        "result_values_available": sorted(values)[:40],
        "numeric_mentions": text_values[:20],
        "matches": matches[:10],
        "grounded": bool(matches),
    }


def _case_rubric(final: dict[str, object], history: list[dict[str, object]], summary: EpisodeSummary) -> dict[str, object]:
    decision = final.get("decision", {})
    stop = decision.get("stop", {}) if isinstance(decision, dict) else {}
    final_text = json.dumps(stop, ensure_ascii=False) if isinstance(stop, dict) else ""
    hypotheses = decision.get("hypotheses", []) if isinstance(decision, dict) else []
    evidence_ids = stop.get("evidence_ids", []) if isinstance(stop, dict) else []
    return {
        "status_completed": summary.status == "completed",
        "actions_executed": summary.actions_used,
        "predictions_scored": summary.predictions_total,
        "predictions_hit": summary.predictions_hit,
        "model_calls": summary.calls_used,
        "hypothesis_count": len(hypotheses) if isinstance(hypotheses, list) else 0,
        "stop_has_evidence_ids": bool(evidence_ids),
        "stop_has_remaining_uncertainty": bool(isinstance(stop, dict) and str(stop.get("remaining_uncertainty", "")).strip()),
        "numeric_grounding": _numeric_grounding(final_text, history),
        "note": "Rule checks only. Distinguishing power and interpretation strength require human review.",
    }


def run_case_diagnostics(
    client: ChatClient,
    *,
    ledger: BudgetLedger,
    source_specs_path: Path,
    run_dir: Path,
    deadline: str,
) -> dict[str, object]:
    target = ensure_dir(run_dir)
    aliases = {"case_c41a": "case_001", "case_a72e": "case_002"}
    specs_path = target / "case_specs_neutral.json"
    _neutral_specs(source_specs_path, specs_path, aliases)
    mapping = {
        "created_at": utc_now(),
        "warning": "EVALUATOR-ONLY. Never place this mapping or family labels in a Scientist prompt.",
        "aliases": aliases,
    }
    atomic_write_json(target / "PRIVATE_MAPPING.json", mapping)
    review_only = Path("archive/experiments/synthetic_20261019/review_only")
    if review_only.exists():
        atomic_write_json(review_only / "DIAGNOSTIC_MAP.json", mapping)

    provider = DeepSeekDecisionProvider(client, max_output_tokens=8000)
    results: list[dict[str, object]] = []
    for alias, source_case_id in aliases.items():
        case_dir = ensure_dir(target / alias)
        config = EpisodeConfig(
            episode_id=f"diag_{alias}",
            case_id=alias,
            case_specs_path=str(specs_path),
            rule_path="archive/experiments/synthetic_20261019/prompts/DIAGNOSTIC_v2.md",
            provider={"kind": "deepseek_chat", "model": "deepseek-flash"},
            backend="real_llm",
            model="deepseek-flash",
            max_actions=3,
            max_calls=4,
            max_attempts=8,
            deadline=deadline,
            run_dir=str(case_dir),
            shared_facts_path=None,
        )
        summary = run_episode(config, provider)
        final_path = case_dir / "final.json"
        final: dict[str, object] = {}
        history: list[dict[str, object]] = []
        if final_path.exists():
            final = json.loads(final_path.read_text(encoding="utf-8"))
        history_path = case_dir / "history.json"
        if history_path.exists():
            loaded = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = [item for item in loaded if isinstance(item, dict)]
        rubric = _case_rubric(final, history, summary)
        results.append(
            {
                "alias": alias,
                "source_case_id_evaluator_only": source_case_id,
                "summary": summary.model_dump(mode="json"),
                "rubric": rubric,
                "run_dir": str(case_dir),
            }
        )
    payload = {
        "created_at": utc_now(),
        "cases": results,
        "mapping_path": str(target / "PRIVATE_MAPPING.json"),
        "note": (
            "Both cases are synthetic feature tables, not recorded EEG. The two aliases have different "
            "generative structures; this is an engineering/explanation diagnostic, not a benchmark win."
        ),
    }
    atomic_write_json(target / "diagnostic_summary.json", payload)
    return payload
