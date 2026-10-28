r"""Post-fix offline probe. No model requests; writes only to a temporary directory.

Run from the repository root:

    .\.venv\Scripts\python.exe audit_20261022\probe_fixed_code.py --source-root src
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("src"))
    args: argparse.Namespace = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))

    from eeg_scientist.anthropic_api import AnthropicClient
    from eeg_scientist.deepseek_api import DeepSeekChatResult, DeepSeekToolCall
    from eeg_scientist.evidence import EvidenceStore
    from eeg_scientist.gemini_api import GeminiClient
    from eeg_scientist.ledger import BudgetLedger
    from eeg_scientist.research import ResearchConfig, ResearchError, ResearchRunner
    from eeg_scientist.review_io import ReviewIOError, collect_proposals, export_packet, import_review
    from eeg_scientist.run_manifest import sha256_file
    from eeg_scientist.study_spec import StudyArm, StudySpec, write_study_spec

    findings: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="eeg-audit-after-") as temporary:
        root: Path = Path(temporary)
        ledger: BudgetLedger = BudgetLedger(root / "budget.json", run_id="probe", cap_cny=10, wrap_up_reserve_cny=0)
        rule: Path = root / "rule.md"
        rule.write_text("RULE_SENTINEL_ANNOTATE_CLAIMS\n", encoding="utf-8")
        task: Path = root / "task.md"
        task.write_text("TASK_SENTINEL_DISCRIMINATE\n", encoding="utf-8")
        system: Path = root / "system.md"
        system.write_text("SYSTEM_BASE_SENTINEL\n", encoding="utf-8")
        config: ResearchConfig = ResearchConfig(
            run_id="probe",
            run_dir=str(root / "run"),
            question="A frozen test question",
            deadline="2099-01-01T00:00:00+00:00",
            stop_new_at="2099-01-01T00:00:00+00:00",
            task_text_path=str(task),
            system_prompt_path=str(system),
            research_mode="materials_only",
            rule_text_path=str(rule),
            rule_version="probe_rule",
            code_root=str(root),
        )
        runner: ResearchRunner = ResearchRunner(config, model_client=object(), ledger=ledger)  # type: ignore[arg-type]
        runner._initialize()
        snapshot: dict[str, Any] = _read_json(root / "run" / "input_snapshot.json")
        manifest: dict[str, Any] = _read_json(root / "run" / "run_manifest.json")
        findings["input_injection"] = {
            "task_in_user": "TASK_SENTINEL" in str(runner.messages[1]["content"]),
            "rule_in_system": "RULE_SENTINEL" in str(runner.messages[0]["content"]),
            "rule_not_in_user": "RULE_SENTINEL" not in str(runner.messages[1]["content"]),
            "rule_snapshot_file_sha256": sha256_file(root / "run" / "rules" / "probe_rule.md"),
            "manifest_rule_sha256": manifest["rule"]["sha256"],
            "snapshot_rule_sha256": snapshot["rule"]["snapshot_sha256"],
            "snapshot_rule_text_sha256": snapshot["rule"]["text_sha256"],
            "snapshot_request_system_sha256": snapshot["request"]["system_sha256"],
            "actual_system_sha256": _sha256_text(str(runner.messages[0]["content"])),
            "rule_injected_into": snapshot["rule"]["injected_into"],
            "scientist_input_has_rule": "RULE_SENTINEL" in (root / "run" / "scientist_input.md").read_text(encoding="utf-8"),
            "tool_definition_sha256": snapshot["tools"]["sha256"],
        }

        evidence: EvidenceStore = runner.evidence
        record = evidence.add_text(url="https://example.org/offline", title="Offline", text="Evidence content " * 40)
        evidence.read(record.evidence_id, max_chars=30)
        finish_rejected = False
        finish_error = ""
        try:
            runner._tool_finish(
                {"answer": "Test proposal " * 25 + f" [{record.evidence_id}]", "evidence_ids": [record.evidence_id]},
                DeepSeekToolCall(id="finish_probe", name="finish_study", arguments="{}"),
            )
        except ResearchError as error:
            finish_rejected = True
            finish_error = str(error)
        findings["finish_missing_unresolved"] = {
            "rejected": finish_rejected,
            "error": finish_error,
            "accepted": runner.state.accepted,
            "final_written": (root / "run" / "final.json").exists(),
        }

        study_root: Path = root / "studies/probe_study"
        study_root.mkdir(parents=True)
        (study_root / "materials").mkdir()
        (study_root / "materials/manifest.json").write_text(
            json.dumps({"version": "v1", "materials": [{"evidence_id": "ev_probe"}]}), encoding="utf-8"
        )
        (study_root / "prompt.md").write_text("prompt", encoding="utf-8")
        (study_root / "task.md").write_text("task", encoding="utf-8")
        spec: StudySpec = StudySpec(
            study_id="probe_study",
            title="Probe",
            question="Question",
            task_path="studies/probe_study/task.md",
            material_manifest_path="studies/probe_study/materials/manifest.json",
            material_evidence_dir="studies/probe_study/materials",
            material_version="v1",
            system_prompt_path="studies/probe_study/prompt.md",
            arms=[StudyArm(name="baseline", backend="offline"), StudyArm(name="meta_rule", backend="offline")],
        )
        write_study_spec(study_root / "study.json", spec)
        for arm in ["baseline", "meta_rule"]:
            run: Path = study_root / "runs" / arm / "repeat_01"
            run.mkdir(parents=True)
            (run / "final_answer.md").write_text("Identical proposal body for binding probe.\n", encoding="utf-8")
            (run / "state.json").write_text(
                json.dumps(
                    {
                        "run_id": f"probe__{arm}__01",
                        "accepted": True,
                        "phase": "completed",
                        "updated_at": "2026-10-22T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
        third_run: Path = study_root / "runs" / "third_arm" / "repeat_01"
        third_run.mkdir(parents=True)
        (third_run / "final_answer.md").write_text("A different proposal body.\n", encoding="utf-8")
        (third_run / "state.json").write_text(
            json.dumps(
                {
                    "run_id": "probe__third_arm__01",
                    "accepted": True,
                    "phase": "completed",
                    "updated_at": "2026-10-22T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        proposals = collect_proposals(root, "probe_study")
        findings["review_arm_labels"] = [
            {"run_id": p.run_id, "arm": p.arm, "repeat": p.repeat, "binding_source": p.binding_source, "cost": p.cost_cny}
            for p in proposals
        ]
        exported: dict[str, object] = export_packet(root, "probe_study")
        packet_dir: Path = root / str(exported["path"])
        packet: dict[str, Any] = _read_json(packet_dir / "packet.json")
        imported_pairs: list[dict[str, object]] = []
        for index, form_rel in enumerate(cast(list[str], exported["forms"])):
            form: str = (root / form_rel).read_text(encoding="utf-8")
            form = form.replace("reviewer_id: \n", f"reviewer_id: expert_{index}\n").replace(
                "reviewer_role: \n", "reviewer_role: EEG researcher\n"
            )
            form = form.replace(
                "#### 1. Most important error or evidence gap\n",
                "#### 1. Most important error or evidence gap\n\nA concrete error.\n",
            )
            form = form.replace(
                "#### 2. What the proposed experiment can and cannot distinguish\n",
                "#### 2. What the proposed experiment can and cannot distinguish\n\nIt separates A from B.\n",
            )
            form = form.replace(
                "#### 3. If only one change: what should change\n",
                "#### 3. If only one change: what should change\n\nPre-register the contrast.\n",
            )
            completed: Path = root / f"completed_form_{index}.md"
            completed.write_text(form, encoding="utf-8")
            imported = import_review(root, "probe_study", completed)
            imported_pairs.append({"display_id": imported["display_id"], "run_id": imported["run_id"]})
        findings["exported_form_import"] = {
            "status": "imported",
            "forms": len(imported_pairs),
            "bindings": imported_pairs,
            "identical_body_proposal_ids": [entry["proposal_id"] for entry in packet["proposals"]],
        }

        swapped_text = (root / cast(list[str], exported["forms"])[0]).read_text(encoding="utf-8")
        swapped_text = swapped_text.replace("reviewer_id: \n", "reviewer_id: expert_swap\n").replace(
            "reviewer_role: \n", "reviewer_role: EEG researcher\n"
        )
        swapped_text = swapped_text.replace("display_id: B01", "display_id: B03", 1)
        swapped_text = swapped_text.replace(
            "#### 1. Most important error or evidence gap\n",
            "#### 1. Most important error or evidence gap\n\nA.\n",
        ).replace(
            "#### 2. What the proposed experiment can and cannot distinguish\n",
            "#### 2. What the proposed experiment can and cannot distinguish\n\nB.\n",
        ).replace(
            "#### 3. If only one change: what should change\n",
            "#### 3. If only one change: what should change\n\nC.\n",
        )
        swapped = root / "swapped.md"
        swapped.write_text(swapped_text, encoding="utf-8")
        try:
            import_review(root, "probe_study", swapped)
            swap_rejected = False
            swap_error = ""
        except ReviewIOError as error:
            swap_rejected = True
            swap_error = str(error)
        findings["swapped_display_rejected"] = {"rejected": swap_rejected, "error": swap_error}

        anthropic: AnthropicClient = AnthropicClient(api_key="offline", ledger=ledger, model="offline")
        claude_raw: dict[str, object] = {
            "content": [
                {"type": "thinking", "thinking": "opaque probe", "signature": "CLAUDE_SIGNATURE_SENTINEL"},
                {"type": "redacted_thinking", "data": "CLAUDE_REDACTED_SENTINEL"},
                {"type": "tool_use", "id": "call_A", "name": "read_evidence", "input": {"evidence_id": "ev_test"}},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 2},
            "stop_reason": "max_tokens",
        }
        claude_result: DeepSeekChatResult = anthropic._parse(claude_raw, time.perf_counter())
        claude_message: dict[str, object] = {
            "role": "assistant",
            "content": claude_result.content,
            "tool_calls": [
                {"id": item.id, "type": "function", "function": {"name": item.name, "arguments": item.arguments}}
                for item in claude_result.tool_calls
            ],
            "native_blocks": claude_result.native_blocks,
        }
        _system, claude_wire = anthropic._wire(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "question"},
                claude_message,
                {"role": "tool", "tool_call_id": "call_A", "content": "{}"},
            ],
            None,
        )
        claude_wire_text = json.dumps(claude_wire)
        findings["claude_protocol"] = {
            "signature_survives_next_request": "CLAUDE_SIGNATURE_SENTINEL" in claude_wire_text,
            "redacted_block_survives": "CLAUDE_REDACTED_SENTINEL" in claude_wire_text,
            "max_tokens_marks_truncated": claude_result.truncated,
            "prompt_tokens_including_cache": claude_result.usage.prompt_tokens,
        }

        gemini: GeminiClient = GeminiClient(api_key="offline", ledger=ledger, model="offline")
        gemini_raw: dict[str, object] = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "visible", "thought": False},
                            {"text": "opaque thought", "thought": True},
                            {"functionCall": {"name": "read_evidence", "args": {}}, "thoughtSignature": "GEMINI_SIGNATURE_SENTINEL"},
                        ]
                    },
                    "finishReason": "MAX_TOKENS",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "thoughtsTokenCount": 6,
                "totalTokenCount": 20,
            },
        }
        gemini_result: DeepSeekChatResult = gemini._parse(gemini_raw, time.perf_counter())
        gemini_message: dict[str, object] = {
            "role": "assistant",
            "content": gemini_result.content,
            "tool_calls": [
                {"id": item.id, "type": "function", "function": {"name": item.name, "arguments": item.arguments}}
                for item in gemini_result.tool_calls
            ],
            "native_blocks": gemini_result.native_blocks,
        }
        _system, gemini_wire = gemini._wire(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "question"},
                gemini_message,
                {"role": "tool", "tool_call_id": gemini_result.tool_calls[0].id, "content": "{}"},
            ],
            None,
        )
        gemini_wire_text = json.dumps(gemini_wire)
        findings["gemini_protocol"] = {
            "signature_survives_next_request": "GEMINI_SIGNATURE_SENTINEL" in gemini_wire_text,
            "max_tokens_marks_truncated": gemini_result.truncated,
            "tool_call_id": gemini_result.tool_calls[0].id,
            "thought_text_not_in_visible_content": "opaque thought" not in gemini_result.content,
            "usage_total_parsed": gemini_result.usage.total_tokens,
            "completion_tokens_parsed": gemini_result.usage.completion_tokens,
            "reasoning_tokens_parsed": gemini_result.usage.reasoning_tokens,
        }
    print(json.dumps(findings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
