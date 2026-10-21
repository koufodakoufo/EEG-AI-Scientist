"""Review packet export, Markdown import, and proposal binding."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from .study_spec import (
    ProposalRecord,
    ReviewRecord,
    ReviewSource,
    ReviewVerdict,
    load_study_spec,
    proposal_id,
    text_sha256,
)

PACKET_VERSION = "review_packet_v1"


class ReviewIOError(RuntimeError):
    """Review packet or feedback cannot be bound safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _study_root(root: Path, study_id: str) -> Path:
    path = root / "studies" / study_id / "study.json"
    if not path.exists():
        raise ReviewIOError(f"study not found: {path}")
    return path.parent


def _run_parts(run_dir: Path) -> tuple[str, int]:
    repeat = 1
    arm = "unknown"
    for part in run_dir.parts:
        if part.startswith("repeat_"):
            try:
                repeat = int(part.split("_", 1)[1])
            except ValueError:
                repeat = 1
    if run_dir.parent.name.startswith("repeat_"):
        arm = run_dir.parent.parent.name
    else:
        arm = run_dir.name
    return arm, repeat


def collect_proposals(root: Path, study_id: str) -> list[ProposalRecord]:
    study_root = _study_root(root, study_id)
    proposals: list[ProposalRecord] = []
    for answer_path in sorted((study_root / "runs").rglob("final_answer.md")):
        run_dir = answer_path.parent
        state_path = run_dir / "state.json"
        final_path = run_dir / "final.json"
        accepted = False
        state: dict[str, object] = {}
        if state_path.exists():
            try:
                state = _read_json(state_path)
            except (OSError, json.JSONDecodeError):
                state = {}
            accepted = bool(state.get("accepted"))
        if not accepted and final_path.exists():
            try:
                accepted = bool(_read_json(final_path).get("accepted"))
            except (OSError, json.JSONDecodeError):
                accepted = False
        if not accepted:
            continue
        body = answer_path.read_bytes()
        arm, repeat = _run_parts(run_dir)
        finished = str(state.get("updated_at", ""))
        proposals.append(
            ProposalRecord(
                proposal_id=proposal_id(body),
                run_id=str(state.get("run_id", run_dir.name)),
                arm=arm,
                repeat=repeat,
                accepted=True,
                body_path=str(answer_path.relative_to(root)),
                body_sha256=hashlib.sha256(body).hexdigest(),
                produced_at=finished,
                cost_cny=0.0,
            )
        )
    return proposals


def _packet_id() -> str:
    return "packet_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def export_packet(root: Path, study_id: str) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    spec = load_study_spec(study_root / "study.json")
    proposals = collect_proposals(root, study_id)
    if not proposals:
        raise ReviewIOError("no accepted proposals found; run or point study at existing runs first")
    packet_id = _packet_id()
    packet_dir = study_root / "reviews" / "packets" / packet_id
    key_dir = study_root / "reviews" / "keys"
    packet_dir.mkdir(parents=True)
    key_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    key: dict[str, object] = {}
    lines = [
        f"# Review packet — {spec.title}",
        "",
        f"- packet_id: `{packet_id}`",
        f"- packet_version: `{PACKET_VERSION}`",
        "- This is a blind review packet. Do not infer the model from formatting; the coordinator holds the key.",
        "- Please answer the three questions below for each proposal, in your own words.",
        "- You may write the completed form directly in this Markdown file; no JSON is required.",
        "",
        "## Review criteria",
        "",
        "Evidence support; validity of reasoning; discriminating power of the proposed experiment; executability; research value. Readability is separate and must not substitute for scientific quality.",
        "",
        "## Proposals",
        "",
    ]
    for index, proposal in enumerate(sorted(proposals, key=lambda item: (item.run_id, item.proposal_id)), start=1):
        display = f"B{index:02d}"
        body = (root / proposal.body_path).read_text(encoding="utf-8")
        (packet_dir / "proposals").mkdir(exist_ok=True)
        (packet_dir / "proposals" / f"{display}.md").write_text(
            f"# Proposal {display}\n\n"
            f"<!-- proposal_id: {proposal.proposal_id}; body_sha256: {proposal.body_sha256}; packet: {packet_id} -->\n\n"
            f"{body}",
            encoding="utf-8",
        )
        entries.append(
            {
                "display_id": display,
                "proposal_id": proposal.proposal_id,
                "body_sha256": proposal.body_sha256,
            }
        )
        key[display] = {
            "proposal_id": proposal.proposal_id,
            "run_id": proposal.run_id,
            "arm": proposal.arm,
            "repeat": proposal.repeat,
            "body_path": proposal.body_path,
            "cost_cny": proposal.cost_cny,
        }
        lines.append(f"- **{display}**: `proposals/{display}.md`")
    lines.extend(["", "## Feedback form", ""])
    for entry in entries:
        display = str(entry["display_id"])
        lines.extend(
            [
                f"### {display}",
                "",
                f"proposal_id: {entry['proposal_id']}",
                f"body_sha256: {entry['body_sha256']}",
                "reviewer_id: ",
                "reviewer_role: ",
                "source_type: human",
                "blind: true",
                "developer_reviewer: false",
                "verdict: uncertain",
                "",
                "#### 1. Most important error or evidence gap",
                "",
                "",
                "#### 2. What the proposed experiment can and cannot distinguish",
                "",
                "",
                "#### 3. If only one change: what should change",
                "",
                "",
                "#### Unreviewed items",
                "",
                "",
            ]
        )
    (packet_dir / "review_packet.md").write_text("\n".join(lines), encoding="utf-8")
    packet: dict[str, object] = {
        "packet_id": packet_id,
        "packet_version": PACKET_VERSION,
        "study_id": study_id,
        "created_at": _now(),
        "proposals": entries,
    }
    _write_json(packet_dir / "packet.json", packet)
    _write_json(key_dir / f"{packet_id}.json", {"packet_id": packet_id, "study_id": study_id, "key": key})
    return {"packet_id": packet_id, "path": str(packet_dir.relative_to(root)), "proposals": entries}


def _parse_header(raw: str) -> tuple[dict[str, str], str]:
    header: dict[str, str] = {}
    body_lines: list[str] = []
    in_header = True
    for line in raw.splitlines():
        if line.startswith("### "):
            header["display_id"] = line[4:].strip().upper()
            in_header = True
            body_lines.append(line)
            continue
        if in_header and line.startswith("#### "):
            in_header = False
            body_lines.append(line)
            continue
        if in_header and not line.strip():
            in_header = False
            body_lines.append(line)
            continue
        if in_header and ": " in line:
            key, value = line.split(": ", 1)
            if re.fullmatch(r"[a-z_]+", key.strip()):
                header[key.strip()] = value.strip()
                continue
        body_lines.append(line)
    return header, "\n".join(body_lines).strip()


def _find_packet(study_root: Path, header: dict[str, str]) -> tuple[Path, dict[str, object], dict[str, object]]:
    packets = sorted((study_root / "reviews" / "packets").glob("*/packet.json"))
    if not packets:
        raise ReviewIOError("no review packets found")
    wanted_id = header.get("proposal_id", "")
    wanted_display = header.get("display_id", "")
    matches: list[tuple[Path, dict[str, object], dict[str, object]]] = []
    for packet_path in packets:
        packet = _read_json(packet_path)
        key_path = study_root / "reviews" / "keys" / f"{packet['packet_id']}.json"
        if not key_path.exists():
            continue
        key = _read_json(key_path)
        raw_entries = packet.get("proposals")
        entries_for_packet = raw_entries if isinstance(raw_entries, list) else []
        for entry in entries_for_packet:
            if not isinstance(entry, dict):
                continue
            if wanted_id and entry.get("proposal_id") == wanted_id:
                matches.append((packet_path.parent, packet, key))
                break
            if wanted_display and entry.get("display_id") == wanted_display:
                matches.append((packet_path.parent, packet, key))
                break
    if not matches:
        raise ReviewIOError("feedback does not match any exported proposal")
    if len(matches) > 1 and not header.get("packet_id"):
        raise ReviewIOError("feedback matches multiple packets; add packet_id to the header")
    if header.get("packet_id"):
        matches = [item for item in matches if item[1].get("packet_id") == header["packet_id"]]
        if not matches:
            raise ReviewIOError("packet_id does not match the proposal")
    return matches[0]


def _answers(raw: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = ""
    buffer: list[str] = []
    for line in raw.splitlines():
        if line.startswith("#### "):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = line[5:].strip()
            buffer = []
        elif current:
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).strip()
    return sections


def import_review(root: Path, study_id: str, file_path: Path) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    raw = file_path.read_text(encoding="utf-8")
    header, _ = _parse_header(raw)
    packet_dir, packet, key = _find_packet(study_root, header)
    proposal_ref = header.get("proposal_id", "")
    display = header.get("display_id", "")
    if not proposal_ref and display:
        raw_entries = packet.get("proposals")
        entries_for_packet = raw_entries if isinstance(raw_entries, list) else []
        entry = next((item for item in entries_for_packet if isinstance(item, dict) and item.get("display_id") == display), None)
        if not isinstance(entry, dict):
            raise ReviewIOError("display_id not found in packet")
        proposal_ref = str(entry.get("proposal_id", ""))
    if not proposal_ref:
        raise ReviewIOError("feedback lacks proposal_id")
    raw_entries = packet.get("proposals")
    entries_for_packet = raw_entries if isinstance(raw_entries, list) else []
    entry = next((item for item in entries_for_packet if isinstance(item, dict) and item.get("proposal_id") == proposal_ref), None)
    if not isinstance(entry, dict):
        raise ReviewIOError("proposal_id not found in packet")
    expected_sha = str(entry.get("body_sha256", ""))
    # Find the bound body via the key, never from reviewer text.
    raw_key = key.get("key")
    key_map = raw_key if isinstance(raw_key, dict) else {}
    key_entry = next((value for value in key_map.values() if isinstance(value, dict) and value.get("proposal_id") == proposal_ref), None)
    if not isinstance(key_entry, dict):
        raise ReviewIOError("proposal key missing")
    bound_path = root / str(key_entry.get("body_path", ""))
    if not bound_path.exists():
        raise ReviewIOError(f"bound proposal body missing: {bound_path}")
    actual_sha = _sha(bound_path)
    if actual_sha != expected_sha:
        raise ReviewIOError("proposal body hash changed; refusing to bind review")
    reviewer_id = header.get("reviewer_id", "").strip()
    reviewer_role = header.get("reviewer_role", "").strip()
    source_type = header.get("source_type", "human").strip()
    if not reviewer_id:
        raise ReviewIOError("reviewer_id is required")
    if source_type not in {"human", "chatgpt_manual", "model_api"}:
        raise ReviewIOError("source_type must be human/chatgpt_manual/model_api")
    verdict = header.get("verdict", "uncertain").strip()
    if verdict not in {"accept", "revise", "reject", "uncertain", "unreviewed"}:
        raise ReviewIOError("invalid verdict")
    review_id = "r_" + text_sha256(raw + proposal_ref)[:12]
    raw_dir = study_root / "reviews" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{review_id}.md"
    if raw_path.exists() and raw_path.read_text(encoding="utf-8") != raw:
        raise ReviewIOError("review_id collision with different raw text")
    raw_path.write_text(raw, encoding="utf-8")
    record = ReviewRecord(
        review_id=review_id,
        study_id=study_id,
        packet_id=str(packet["packet_id"]),
        proposal_id=proposal_ref,
        run_id=str(key_entry.get("run_id", "")),
        body_sha256=actual_sha,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        source_type=cast(ReviewSource, source_type),
        blind=header.get("blind", "true").lower() == "true",
        developer_reviewer=header.get("developer_reviewer", "false").lower() == "true",
        submitted_at=_now(),
        verdict=cast(ReviewVerdict, verdict),
        answers=_answers(raw),
        unreviewed=[line.strip() for line in header.get("unreviewed", "").split(";") if line.strip()],
        raw_path=str(raw_path.relative_to(root)),
        raw_sha256=_sha(raw_path),
        notes=header.get("notes", ""),
    )
    record_path = study_root / "reviews" / "records" / f"{review_id}.json"
    _write_json(record_path, record.model_dump(mode="json"))
    return {
        "review_id": review_id,
        "proposal_id": proposal_ref,
        "packet_id": packet["packet_id"],
        "raw_path": str(raw_path.relative_to(root)),
        "record_path": str(record_path.relative_to(root)),
    }


def make_feedback_set(root: Path, study_id: str, review_ids: list[str], version: str) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    records: list[dict[str, object]] = []
    for review_id in review_ids:
        path = study_root / "reviews" / "records" / f"{review_id}.json"
        if not path.exists():
            raise ReviewIOError(f"review record missing: {review_id}")
        records.append(_read_json(path))
    payload: dict[str, object] = {
        "schema_version": "1",
        "study_id": study_id,
        "feedback_set_version": version,
        "created_at": _now(),
        "review_ids": review_ids,
        "records": records,
    }
    target = study_root / "reviews" / f"feedback_set_{version}.json"
    _write_json(target, payload)
    return {"feedback_set": str(target.relative_to(root)), "reviews": len(records)}
