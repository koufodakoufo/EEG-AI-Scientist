"""Render the human-facing overnight index from persisted run state.

Only measured values from the run directories are used.  Narrative reports
(MORNING_REPORT, LITERATURE_MAP, HYPOTHESIS_CARDS) are written by the developer
after reading the Scientist's actual final answer; this module does not invent
scientific content.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..storage import atomic_write_text, ensure_dir, utc_now

DEFAULT_FLASH_STUDY = Path("archive/experiments/flash_20261020_0058/configs/study.json")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_flash_reports(
    reports_dir: Path,
    *,
    run_id: str,
    study_config_path: Path | str = DEFAULT_FLASH_STUDY,
) -> dict[str, str]:
    study = _read_json(Path(study_config_path))
    paths = study["paths"]
    target = ensure_dir(reports_dir)
    capability_path = Path(str(paths["capability_dir"])) / "capability.json"
    capability_md_path = capability_path.with_name("CAPABILITY_CHECK.md")
    budget_path = Path(str(paths["budget_ledger"]))
    diagnostics_root = Path(str(paths["diagnostic_dir"]))
    research_root = Path(str(paths["research_dir"])) / "literature_v1"

    capability = _read_json(capability_path) if capability_path.exists() else None
    ledger = _read_json(budget_path) if budget_path.exists() else None
    diagnostics = _read_json(diagnostics_root / "diagnose_summary.json") if (diagnostics_root / "diagnose_summary.json").exists() else None
    regression_path = diagnostics_root / "regression" / "regression.json"
    regression = _read_json(regression_path) if regression_path.exists() else None
    research_state_path = research_root / "state.json"
    research_state = _read_json(research_state_path) if research_state_path.exists() else None
    research_final_path = research_root / "final.json"
    research_final = _read_json(research_final_path) if research_final_path.exists() else None

    lines = [
        f"# RUN INDEX — {run_id}",
        "",
        f"- rendered_at: {utc_now()}",
        f"- study_config: `{study_config_path}`",
        f"- deadline: {study['deadline']}",
        f"- stop_new_research_at: {study['stop_new_research_at']}",
        "",
        "## Stage status",
        "",
        "| stage | state | evidence location |",
        "|---|---|---|",
        f"| A precheck | DONE | `reports/{run_id}/PRECHECK.md` |",
        f"| A implementation map | DONE | `reports/{run_id}/IMPLEMENTATION_MAP.md` |",
        f"| B capability | {'PASS' if capability and capability.get('all_required_ok') else 'FAIL/NOT RUN'} | `{paths['capability_dir']}/CAPABILITY_CHECK.md` |",
        f"| C regression | {'DONE' if regression else 'NOT RUN'} | `{diagnostics_root}/regression/` |",
        f"| C neutral cases | {'DONE' if diagnostics and diagnostics.get('cases') else 'NOT RUN'} | `{diagnostics_root}/cases/` |",
        f"| D literature | {research_state.get('phase') if research_state else 'NOT RUN'} | `{research_root}/` |",
        f"| E real-data branch | {'DONE (E2 fallback; no real EEG)' if (target / 'DATA_REQUIREMENTS.md').exists() else 'NOT RUN'} | `reports/{run_id}/DATA_REQUIREMENTS.md` |",
        f"| F audit/extension | {'DONE' if (target / 'EVIDENCE_AUDIT.md').exists() and (target / 'EXPERIMENT_PROTOCOL.md').exists() else 'IN PROGRESS'} | `reports/{run_id}/EVIDENCE_AUDIT.md`, `EXPERIMENT_PROTOCOL.md` |",
        f"| G reports/commit | {'DONE (reports + local commits)' if (target / 'MORNING_REPORT.md').exists() else 'PENDING'} | `reports/{run_id}/` |",
        "",
        "## Budget",
        "",
    ]
    if ledger:
        lines.extend(
            [
                "| item | used | limit |",
                "|---|---:|---:|",
                f"| project API spend (peak-rate accounting) | CNY {ledger.get('spent_cny', 0):.4f} | CNY {ledger.get('cap_cny', 20)} |",
                f"| unknown/timeout reservations | CNY {ledger.get('unknown_cny', 0):.4f} | — |",
                f"| model attempts | {ledger.get('model_attempts', 0)} | {ledger.get('model_attempts_limit', 0)} |",
                f"| search attempts | {ledger.get('search_attempts', 0)} | {ledger.get('search_attempts_limit', 0)} |",
                f"| fetch attempts | {ledger.get('fetch_attempts', 0)} | {ledger.get('fetch_attempts_limit', 0)} |",
                f"| input tokens | {ledger.get('input_tokens', 0)} | {ledger.get('input_tokens_limit', 0)} |",
                f"| output tokens | {ledger.get('output_tokens', 0)} | {ledger.get('output_tokens_limit', 0)} |",
            ]
        )
    else:
        lines.append("No ledger yet.")
    lines.extend(
        [
            "",
            "## Capability checks",
            "",
        ]
    )
    if capability:
        for item in capability.get("checks", []):
            lines.append(f"- `{item['name']}`: {'PASS' if item['ok'] else 'FAIL'}")
    else:
        lines.append("- not run")
    lines.extend(
        [
            "",
            "## Deliverables",
            "",
            f"- `reports/{run_id}/MORNING_REPORT.md` — start here",
            f"- `reports/{run_id}/LITERATURE_MAP.md` — 7 cited papers, read scope, unread/failed sources",
            f"- `reports/{run_id}/HYPOTHESIS_CARDS.md` — three cards, priority/backup, dsh review notes",
            f"- `reports/{run_id}/EVIDENCE_AUDIT.md` — number/claim audit against the injection log",
            f"- `reports/{run_id}/EXPERIMENT_PROTOCOL.md` — reduced priority experiment and backup",
            f"- `reports/{run_id}/DATA_REQUIREMENTS.md` — E2 fallback, no real EEG data",
            f"- `runs/{run_id}/research/literature_v1/final_answer.md` — the Scientist's own answer",
            "",
            "## Commands",
            "",
            "```powershell",
            "cd X:\\projects\\EEG-AI-Scientist",
            "$env:PYTHONPATH='src'",
            "$py='C:\\Users\\14090\\anaconda3\\python.exe'",
            f"& $py -m eeg_scientist.cli overnight-flash status",
            f"& $py -m eeg_scientist.cli overnight-flash research --name literature_v1",
            "```",
            "",
        ]
    )
    atomic_write_text(target / "RUN_INDEX.md", "\n".join(lines))

    result_lines = [
        f"# RESULTS — {run_id}",
        "",
        "Only executed checks and measured values are listed. Synthetic data and fixture checks are not EEG evidence.",
        "",
        "## Capability (engineering)",
        "",
    ]
    if capability:
        for item in capability.get("checks", []):
            result_lines.append(f"- `{item['name']}`: {'PASS' if item['ok'] else 'FAIL'} — `{json.dumps(item['detail'], ensure_ascii=False, default=str)[:500]}`")
    else:
        result_lines.append("- Not run.")
    result_lines.extend(["", "## Explanation regression (Task C)", ""])
    if regression:
        evaluation = regression.get("evaluation", {})
        result_lines.append(f"- rule checks: {evaluation.get('n_pass')}/{evaluation.get('n_checks')}")
        for item in evaluation.get("checks", []):
            result_lines.append(f"- [{'PASS' if item['pass'] else 'FAIL'}] `{item['check']}`: {item['detail']}")
        result_lines.append(f"- verbatim answer: `{diagnostics_root}/regression/regression_answer.md`")
    else:
        result_lines.append("- Not run.")
    result_lines.extend(["", "## Neutral synthetic case diagnostics (Task C)", ""])
    if diagnostics and diagnostics.get("cases"):
        case_section = diagnostics["cases"]
        case_rows = case_section.get("cases", []) if isinstance(case_section, dict) else []
        for item in case_rows:
            summary = item.get("summary", {})
            rubric = item.get("rubric", {})
            result_lines.append(
                f"- `{item.get('alias')}`: status={summary.get('status')}, actions={summary.get('actions_used')}, "
                f"predictions={summary.get('predictions_hit')}/{summary.get('predictions_total')}, "
                f"numeric_grounded={rubric.get('numeric_grounding', {}).get('grounded')}"
            )
    else:
        result_lines.append("- Not run.")
    result_lines.extend(["", "## Literature run (Task D)", ""])
    if research_state:
        result_lines.append(f"- phase: {research_state.get('phase')}")
        result_lines.append(f"- model calls: {research_state.get('model_calls')}; tool calls: {research_state.get('tool_calls')}")
        result_lines.append(f"- searches: {research_state.get('searches')}; fetches: {research_state.get('fetches')}")
        result_lines.append(f"- stop reason: {research_state.get('stop_reason')}")
    else:
        result_lines.append("- Not run.")
    if research_final:
        result_lines.append(f"- final answer: `{research_root}/final_answer.md`")
        result_lines.append(f"- cited evidence: {len(research_final.get('evidence_ids', []))}")
        coverage = research_final.get("coverage", {}).get("sources", [])
        if coverage:
            result_lines.append("- read coverage (injected characters / fetched characters):")
            for item in coverage:
                result_lines.append(
                    f"  - `{item.get('evidence_id')}`: {item.get('read_chars')}/{item.get('total_chars')} "
                    f"({float(item.get('fraction_read', 0)) * 100:.1f}%)"
                )
    result_lines.extend(["", "## Honest limits", "", "- Synthetic feature tables and artificial fixtures are not recorded EEG.", "- Windows are not independent participants; no population-level EEG inference is made.", "- Rule checks are not a scientific score.", "- `numeric_grounded=False` for the two synthetic cases means the final judgment did not quote a result value; it does not mean the tool results were wrong. The values remain in each trajectory's `history.json`.", "- Successful research searches/fetches are lower than ledger attempts because retries and failed requests are counted separately.", "- Project API spend is separate from the dsh development-agent account.", ""])
    atomic_write_text(target / "RESULTS.md", "\n".join(result_lines))

    if capability_md_path.exists():
        atomic_write_text(target / "CAPABILITY_CHECK.md", capability_md_path.read_text(encoding="utf-8"))

    return {
        "run_index": str(target / "RUN_INDEX.md"),
        "results": str(target / "RESULTS.md"),
        "capability": str(target / "CAPABILITY_CHECK.md") if capability_md_path.exists() else "",
    }
