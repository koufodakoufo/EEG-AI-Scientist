"""Run-level provenance: code commit, full config, model, material, rule, cost.

Every new research run gets its own `run_manifest.json`.  Rule snapshots live
under the run (not in the global prompts/S0/S1 or memory directories), so a
Meta rule cannot silently alter an older study.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(root: Path) -> dict[str, object]:
    def run(*arguments: str) -> str:
        try:
            return subprocess.check_output(
                ["git", *arguments],
                cwd=root,
                text=True,
                encoding="utf-8",
                errors="replace",
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception as error:  # noqa: BLE001 - provenance must degrade visibly
            return f"unavailable: {type(error).__name__}"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def write_rule_snapshot(run_dir: Path, *, rule_text: str, rule_version: str, source: str) -> dict[str, object]:
    target = ensure_dir(run_dir / "rules") / f"{rule_version}.md"
    atomic_write_text(target, rule_text if rule_text.endswith("\n") else rule_text + "\n")
    return {
        "version": rule_version,
        "source": source,
        "path": str(target),
        "sha256": sha256_file(target),
        "chars": len(rule_text),
    }


def write_run_manifest(
    run_dir: Path,
    *,
    run_id: str,
    study_config: dict[str, object],
    run_config: dict[str, object],
    model_info: dict[str, object],
    tool_info: dict[str, object],
    question: str,
    rule_snapshot: dict[str, object],
    material_manifest_path: Path | None,
    material_version: str,
    ledger_path: Path,
    attribution: str,
    code_root: Path,
) -> dict[str, object]:
    material_info: dict[str, object] = {
        "version": material_version,
        "manifest_path": str(material_manifest_path) if material_manifest_path else "",
        "manifest_sha256": sha256_file(material_manifest_path) if material_manifest_path and material_manifest_path.exists() else "",
    }
    manifest: dict[str, object] = {
        "schema_version": "1",
        "run_id": run_id,
        "study_id": str(study_config.get("study_id", "")),
        "created_at": utc_now(),
        "git": git_state(code_root),
        "study_config": study_config,
        "study_config_sha256": sha256_text(json.dumps(study_config, sort_keys=True, ensure_ascii=False, default=str)),
        "run_config": run_config,
        "run_config_sha256": sha256_text(json.dumps(run_config, sort_keys=True, ensure_ascii=False, default=str)),
        "question": question,
        "question_sha256": sha256_text(question),
        "model": model_info,
        "tool": tool_info,
        "rule": rule_snapshot,
        "material": material_info,
        "cost_attribution": {
            "ledger": str(ledger_path),
            "attribution": attribution,
        },
    }
    atomic_write_json(run_dir / "run_manifest.json", manifest)
    return manifest


def assert_material_frozen(material_manifest_path: Path, expected_sha256: str) -> None:
    if not material_manifest_path.exists():
        raise RuntimeError(f"material manifest missing: {material_manifest_path}")
    actual = sha256_file(material_manifest_path)
    if actual != expected_sha256:
        raise RuntimeError(
            "material manifest changed after freeze: "
            f"expected {expected_sha256}, got {actual}; refusing to run"
        )
