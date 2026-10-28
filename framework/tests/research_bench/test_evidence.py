"""Portable integrity adversaries using only owned temporary synthetic files."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from eegfm.research_bench.evidence import _is_link, audit_evidence
from eegfm.research_bench.scoring import score_directional


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.artifact = self.root / "metrics.json"
        self.artifact.write_bytes(b'{"accuracy": 0.7}')
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.record: dict[str, Any] = {"evidence_id": "e1", "run_id": "r1", "artifact_path": "metrics.json",
                                       "sha256": self.digest, "command_id": "c1", "status": "completed", "data_split": "synthetic"}
        self.command: dict[str, Any] = {"command_id": "c1", "run_id": "r1", "status": "completed", "exit_code": 0,
                                        "data_split": "synthetic", "artifacts": [{"artifact_path": "metrics.json", "sha256": self.digest}]}

    def audit(self, **options: Any) -> dict[str, Any]:
        return audit_evidence([self.record], self.root, [self.command], **options)

    def assert_invalid(self, reason: str, **options: Any) -> None:
        result = self.audit(**options)
        self.assertFalse(result["valid"])
        self.assertIn(reason, result["records"][0]["errors"])

    def test_valid_ledger_binding_and_pins(self) -> None:
        result = self.audit(expected_run_id="r1", expected_data_split="synthetic")
        self.assertTrue(result["valid"])
        self.assertEqual(result["valid_evidence_ids"], ["e1"])
        self.assertEqual(result["records"][0]["observed_sha256"], self.digest)
        self.assertTrue(audit_evidence([self.record], self.root, {"c1": self.command})["valid"])

    def test_no_evidence_fails_without_touching_agreement(self) -> None:
        result = audit_evidence([], self.root, [])
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "no_evidence")
        # A perfect reference score cannot manufacture any evidence.
        base = {"text": "A", "scope": {}, "polarity": "positive", "source_span": {"source": "x", "start": 0, "end": 1}, "evidence_ids": []}
        matches = [{"agent_claim_id": "a", "reference_claim_id": "r", "direction": d, "relation": "supported", "reason": "fixture", "judge_version": "fixture_v1"}
                   for d in ("reference_supports_agent", "agent_covers_reference")]
        score = score_directional([{**base, "claim_id": "a"}], [{**base, "claim_id": "r"}], matches)
        self.assertEqual(score["scores"]["f1"], 1)
        self.assertIsNone(score["evidence_audit"])

    def test_missing_artifact(self) -> None:
        self.artifact.unlink()
        self.assert_invalid("missing_artifact")

    def test_mutated_file_hash(self) -> None:
        self.artifact.write_bytes(b"fabricated")
        self.assert_invalid("sha256_mismatch")

    def test_submission_hash_cannot_override_ledger(self) -> None:
        self.record["sha256"] = "0" * 64
        self.assert_invalid("artifact_not_bound_to_command")

    def test_missing_command(self) -> None:
        self.record["command_id"] = "invented"
        self.assert_invalid("missing_command_record")
        self.assertFalse(audit_evidence([self.record], self.root)["valid"])

    def test_fabricated_run(self) -> None:
        self.record["run_id"] = "invented"
        self.assert_invalid("run_id_mismatch")

    def test_pinned_run_and_split(self) -> None:
        self.assert_invalid("unexpected_run_id", expected_run_id="different")
        self.assert_invalid("unexpected_data_split", expected_data_split="validation")

    def test_command_status_exit_and_missing_artifact_binding(self) -> None:
        for changes, reason in [({"status": "running"}, "command_not_successful"), ({"exit_code": 1}, "command_not_successful"),
                                ({"exit_code": False}, "command_not_successful"), ({"artifacts": []}, "artifact_not_bound_to_command"),
                                ({"artifacts": None}, "missing_or_invalid_command_artifacts")]:
            with self.subTest(changes=changes):
                command = {**self.command, **changes}
                result = audit_evidence([self.record], self.root, [command])
                self.assertIn(reason, result["records"][0]["errors"])

    def test_invalid_evidence_status(self) -> None:
        self.record["status"] = "planned"
        self.assert_invalid("evidence_not_completed")

    def test_split_mismatch_and_unknown(self) -> None:
        self.record["data_split"] = "validation"
        self.assert_invalid("data_split_mismatch")
        self.record["data_split"] = "unknown"
        self.assert_invalid("disallowed_data_split")

    def test_test_split_requires_explicit_authorization(self) -> None:
        self.record["data_split"] = self.command["data_split"] = "test"
        self.assert_invalid("disallowed_data_split")
        self.assertTrue(self.audit(allowed_data_splits=["test"], expected_data_split="test")["valid"])

    def test_traversal_absolute_unc_drive_and_device_paths(self) -> None:
        paths = ["../secret", "sub/../../secret", "/etc/passwd", "C:/secret", "C:secret", "\\\\host\\share", "sub\\file",
                 "metrics.json:stream", "./metrics.json", "sub//file", "NUL", "CON.txt", "file. "]
        for path in paths:
            with self.subTest(path=path):
                self.record["artifact_path"] = path
                self.command["artifacts"][0]["artifact_path"] = path
                self.assert_invalid("unsafe_artifact_path")

    def test_directory_not_file(self) -> None:
        self.artifact.unlink()
        self.artifact.mkdir()
        self.assert_invalid("artifact_not_regular_file")

    def test_symlink_file_rejected_even_inside_root(self) -> None:
        target = self.root / "target.json"
        self.artifact.rename(target)
        try:
            self.artifact.symlink_to(target)
        except OSError as error:
            self.skipTest(f"symlink unavailable on this host: {error}")
        self.assert_invalid("symlink_or_reparse_point")

    def test_symlink_directory_escape_rejected(self) -> None:
        folder = self.root / "actual"
        folder.mkdir()
        self.artifact.rename(folder / "metrics.json")
        link = self.root / "linked"
        try:
            link.symlink_to(folder, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink unavailable on this host: {error}")
        self.record["artifact_path"] = self.command["artifacts"][0]["artifact_path"] = "linked/metrics.json"
        self.assert_invalid("symlink_or_reparse_point")

    def test_symlink_root_rejected(self) -> None:
        actual = self.root / "actual"
        actual.mkdir()
        self.artifact.rename(actual / "metrics.json")
        linked = self.root / "linked"
        try:
            linked.symlink_to(actual, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink unavailable on this host: {error}")
        self.assertFalse(audit_evidence([self.record], linked, [self.command])["valid"])

    def test_duplicate_evidence_and_commands_fail_all_affected(self) -> None:
        result = audit_evidence([self.record, self.record], self.root, [self.command])
        self.assertEqual(result["counts"]["valid"], 0)
        self.assertIn("duplicate_evidence_id", result["records"][0]["errors"])
        result = audit_evidence([self.record], self.root, [self.command, self.command])
        self.assertIn("duplicate_command_id", result["records"][0]["errors"])

    def test_ledger_map_key_mismatch_fails(self) -> None:
        result = audit_evidence([self.record], self.root, {"forged": self.command})
        self.assertFalse(result["valid"])
        self.assertIn("command_mapping_key_mismatch", result["ledger_errors"])

    def test_malformed_record_and_size_cap(self) -> None:
        self.assertFalse(audit_evidence([{"evidence_id": "bad"}], self.root, [self.command])["valid"])
        self.assert_invalid("artifact_size_limit", max_artifact_bytes=1)

    def test_artifact_contents_are_never_executed(self) -> None:
        self.artifact.write_text("raise RuntimeError('this artifact must not execute')", encoding="utf-8")
        digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.record["sha256"] = self.command["artifacts"][0]["sha256"] = digest
        self.assertTrue(self.audit()["valid"])

    def test_reparse_and_symlink_flags_fail_closed_on_all_hosts(self) -> None:
        self.assertTrue(_is_link(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)))
        self.assertTrue(_is_link(SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)))
        self.assertFalse(_is_link(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0)))

    def test_hardlink_is_rejected(self) -> None:
        try:
            os.link(self.artifact, self.root / "alias.json")
        except OSError as error:
            self.skipTest(f"hardlinks unavailable on this host: {error}")
        self.assert_invalid("artifact_hardlink")


if __name__ == "__main__":
    unittest.main()
