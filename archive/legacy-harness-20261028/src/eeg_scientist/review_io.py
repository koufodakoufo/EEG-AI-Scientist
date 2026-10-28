"""Review packet export, Markdown form import, and proposal binding.

Design constraints:

* one self-contained, directly fillable Markdown form per proposal;
* packet/display/proposal/run/body-SHA binding is checked, never guessed;
* raw reviewer text and structured records are stored separately;
* re-importing identical content is idempotent;
* a feedback-set version is immutable once created.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
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
FORM_VERSION = "review_form_v2"
FORM_MARKER = "<!-- BEGIN REVIEW -->"
FEEDBACK_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,40}$")
REQUIRED_ANSWER_PREFIXES = ("1.", "2.", "3.")


class ReviewIOError(RuntimeError):
    """Review packet or feedback cannot be bound safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _study_root(root: Path, study_id: str) -> Path:
    path = root / "studies" / study_id / "study.json"
    if not path.exists():
        raise ReviewIOError(f"study not found: {path}")
    return path.parent


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _run_binding(run_dir: Path, state: dict[str, object], final: dict[str, object]) -> tuple[str, int, str, str]:
    """Return (arm, repeat, run_id, binding_source) from records, not guesses alone."""

    run_id = ""
    for payload in (state, final):
        value = payload.get("run_id")
        if isinstance(value, str) and value:
            run_id = value
            break
    index_path = run_dir / "run_index.json"
    if index_path.exists():
        index = _read_json(index_path)
        if not run_id and isinstance(index.get("run_id"), str):
            run_id = str(index["run_id"])
        arm = index.get("arm")
        repeat = index.get("repeat")
        if isinstance(arm, str) and arm:
            source = "run_index"
            return arm, repeat if isinstance(repeat, int) and not isinstance(repeat, bool) and repeat > 0 else 1, run_id or run_dir.name, source
    arm_value = state.get("arm")
    repeat_value = state.get("repeat")
    if isinstance(arm_value, str) and arm_value:
        repeat = repeat_value if isinstance(repeat_value, int) and not isinstance(repeat_value, bool) and repeat_value > 0 else 1
        return arm_value, repeat, run_id or run_dir.name, "state"
    arm, repeat = _path_binding(run_dir)
    return arm, repeat, run_id or run_dir.name, "path"


def _path_binding(run_dir: Path) -> tuple[str, int]:
    """Legacy fallback: ``runs/<arm>/repeat_XX`` or ``runs/<batch>/<arm>/repeat_XX``."""

    name = run_dir.name
    if name.startswith("repeat_"):
        try:
            repeat = int(name.split("_", 1)[1])
        except ValueError:
            repeat = 1
        if run_dir.parent.name:
            return run_dir.parent.name, repeat
    parent = run_dir.parent
    if parent.name.startswith("repeat_"):
        try:
            repeat = int(parent.name.split("_", 1)[1])
        except ValueError:
            repeat = 1
        return parent.parent.name, repeat
    return name, 1


def collect_proposals(root: Path, study_id: str) -> list[ProposalRecord]:
    study_root = _study_root(root, study_id)
    proposals: list[ProposalRecord] = []
    runs_root = study_root / "runs"
    if not runs_root.exists():
        return proposals
    for answer_path in sorted(runs_root.rglob("final_answer.md")):
        run_dir = answer_path.parent
        state_path = run_dir / "state.json"
        final_path = run_dir / "final.json"
        accepted = False
        state: dict[str, object] = {}
        final: dict[str, object] = {}
        if state_path.exists():
            try:
                state = _read_json(state_path)
            except (OSError, json.JSONDecodeError):
                state = {}
            accepted = bool(state.get("accepted"))
        if final_path.exists():
            try:
                final = _read_json(final_path)
            except (OSError, json.JSONDecodeError):
                final = {}
            accepted = accepted or bool(final.get("accepted"))
        if not accepted:
            continue
        body = answer_path.read_bytes()
        arm, repeat, run_id, source = _run_binding(run_dir, state, final)
        cost = _number_or_none(final.get("cost_cny"))
        if cost is None:
            cost = _number_or_none(state.get("cost_cny"))
        proposals.append(
            ProposalRecord(
                proposal_id=proposal_id(body),
                run_id=run_id,
                arm=arm,
                repeat=repeat,
                accepted=True,
                body_path=str(answer_path.relative_to(root)),
                body_sha256=hashlib.sha256(body).hexdigest(),
                produced_at=str(state.get("updated_at", "")),
                cost_cny=cost,
                binding_source=source,
            )
        )
    return proposals


def _packet_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return "packet_" + stamp + "_" + uuid.uuid4().hex[:4]


def _cost_text(cost: float | None) -> str:
    return "unknown" if cost is None else f"{cost:.6f} CNY"


def export_packet(root: Path, study_id: str) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    spec = load_study_spec(study_root / "study.json")
    proposals = collect_proposals(root, study_id)
    if not proposals:
        raise ReviewIOError("no accepted proposals found; run or point study at existing runs first")
    packet_id = _packet_id()
    packet_dir = study_root / "reviews" / "packets" / packet_id
    key_dir = study_root / "reviews" / "keys"
    forms_dir = packet_dir / "forms"
    forms_dir.mkdir(parents=True)
    key_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    key: dict[str, object] = {}
    ordered = sorted(proposals, key=lambda item: (item.run_id, item.proposal_id))
    for index, proposal in enumerate(ordered, start=1):
        display = f"B{index:02d}"
        body = (root / proposal.body_path).read_text(encoding="utf-8")
        form = _form_text(
            display=display,
            packet_id=packet_id,
            proposal=proposal,
            body=body,
            title=spec.title,
        )
        (forms_dir / f"{display}.md").write_text(form, encoding="utf-8")
        entries.append(
            {
                "display_id": display,
                "proposal_id": proposal.proposal_id,
                "body_sha256": proposal.body_sha256,
                "run_id": proposal.run_id,
                "arm": proposal.arm,
                "repeat": proposal.repeat,
                "body_path": proposal.body_path,
                "cost_cny": proposal.cost_cny,
                "cost_status": "unknown" if proposal.cost_cny is None else "recorded",
                "binding_source": proposal.binding_source,
            }
        )
        key[display] = {
            "proposal_id": proposal.proposal_id,
            "run_id": proposal.run_id,
            "arm": proposal.arm,
            "repeat": proposal.repeat,
            "body_path": proposal.body_path,
            "body_sha256": proposal.body_sha256,
            "cost_cny": proposal.cost_cny,
            "binding_source": proposal.binding_source,
        }
    lines = [
        f"# Review packet — {spec.title}",
        "",
        f"- packet_id: `{packet_id}`",
        f"- packet_version: `{PACKET_VERSION}`",
        f"- form_version: `{FORM_VERSION}`",
        "- This is a blind review packet. Forms do not show the arm, model, or repeat; the coordinator holds the key.",
        "",
        "## Instructions",
        "",
        "1. Open one form per proposal under `forms/`.",
        "2. Fill `reviewer_id`, `reviewer_role`, and the three numbered questions in the section after the "
        f"`{FORM_MARKER}` marker. Do not delete the `packet_id`, `display_id`, `proposal_id`, or `body_sha256` lines.",
        "3. Set `verdict` to one of `accept`, `revise`, `reject`, `uncertain`.",
        "4. Return the completed form(s) unchanged otherwise; no JSON editing is required.",
        "",
        "## Criteria",
        "",
        "Evidence support; validity of reasoning; discriminating power of the proposed experiment; executability; "
        "research value. Readability is separate and must not substitute for scientific quality.",
        "",
        "## Proposals in this packet",
        "",
        "| form | cost recorded |",
        "|---|---|",
    ]
    for entry in entries:
        lines.append(
            f"| `forms/{entry['display_id']}.md` | {_cost_text(cast(float | None, entry['cost_cny']))} |"
        )
    lines.extend(
        [
            "",
            "The coordinator holds the arm/model/repeat key; it is intentionally absent from this packet.",
            "",
        ]
    )
    (packet_dir / "review_packet.md").write_text("\n".join(lines), encoding="utf-8")
    packet: dict[str, object] = {
        "packet_id": packet_id,
        "packet_version": PACKET_VERSION,
        "form_version": FORM_VERSION,
        "study_id": study_id,
        "created_at": _now(),
        "proposals": entries,
    }
    _write_json(packet_dir / "packet.json", packet)
    _write_json(key_dir / f"{packet_id}.json", {"packet_id": packet_id, "study_id": study_id, "key": key})
    return {
        "packet_id": packet_id,
        "path": str(packet_dir.relative_to(root)),
        "overview": str((packet_dir / "review_packet.md").relative_to(root)),
        "forms": [str((forms_dir / f"{entry['display_id']}.md").relative_to(root)) for entry in entries],
        "proposals": entries,
    }


def _form_text(*, display: str, packet_id: str, proposal: ProposalRecord, body: str, title: str) -> str:
    return f"""# Review form — {display}

- packet: `{packet_id}`
- form_version: `{FORM_VERSION}`
- study: {title}
- proposal: `{display}`

## Proposal under review (verbatim, read-only)

{body.rstrip()}

---

{FORM_MARKER}

display_id: {display}
packet_id: {packet_id}
proposal_id: {proposal.proposal_id}
body_sha256: {proposal.body_sha256}
reviewer_id: 
reviewer_role: 
source_type: human
blind: true
developer_reviewer: false
verdict: uncertain

#### 1. Most important error or evidence gap

#### 2. What the proposed experiment can and cannot distinguish

#### 3. If only one change: what should change

#### Unreviewed items
"""


def _parse_header(raw: str) -> tuple[dict[str, str], str]:
    """Parse key/value fields, tolerating blank lines between them.

    Everything before ``FORM_MARKER`` is proposal text and is ignored.  The
    header ends at the first ``####``/``##`` heading or a non-field line.
    """

    feedback = raw.rsplit(FORM_MARKER, 1)[1] if FORM_MARKER in raw else raw
    header: dict[str, str] = {}
    body_lines: list[str] = []
    in_header = True
    for line in feedback.splitlines():
        if not in_header:
            body_lines.append(line)
            continue
        if line.startswith("#### ") or line.startswith("## "):
            in_header = False
            body_lines.append(line)
            continue
        if line.startswith("### "):
            header.setdefault("display_id", line[4:].strip().upper())
            body_lines.append(line)
            continue
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*):\s?(.*)", line)
        if match:
            header[match.group(1).strip().lower()] = match.group(2).strip()
            continue
        in_header = False
        body_lines.append(line)
    return header, "\n".join(body_lines).strip()


def _packet_entries(packet: dict[str, object]) -> list[dict[str, object]]:
    raw = packet.get("proposals")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _find_packet(
    study_root: Path,
    study_id: str,
    header: dict[str, str],
) -> tuple[Path, dict[str, object], dict[str, object], dict[str, object], str]:
    packet_id_value = header.get("packet_id", "").strip()
    display = header.get("display_id", "").strip().upper()
    proposal_ref = header.get("proposal_id", "").strip()
    submitted_sha = header.get("body_sha256", "").strip()
    if not (packet_id_value or display or proposal_ref):
        raise ReviewIOError("feedback lacks packet_id, display_id, and proposal_id; refusing to guess")
    if packet_id_value:
        packet_path = study_root / "reviews" / "packets" / packet_id_value / "packet.json"
        if not packet_path.exists():
            raise ReviewIOError(f"packet_id {packet_id_value!r} was not exported for this study")
        packet_paths = [packet_path]
    else:
        packet_paths = sorted((study_root / "reviews" / "packets").glob("*/packet.json"))
        if not packet_paths:
            raise ReviewIOError("no review packets found")
    matches: list[tuple[Path, dict[str, object], dict[str, object], dict[str, object], str]] = []
    for packet_path in packet_paths:
        packet = _read_json(packet_path)
        if packet.get("study_id") not in {study_id, None}:
            continue
        entries = _packet_entries(packet)
        entry: dict[str, object] | None = None
        if display:
            entry = next((item for item in entries if item.get("display_id") == display), None)
            if entry is None:
                continue
            if proposal_ref and entry.get("proposal_id") != proposal_ref:
                raise ReviewIOError(
                    f"display {display} belongs to proposal {entry.get('proposal_id')!r}, not {proposal_ref!r}"
                )
        else:
            candidates = [item for item in entries if item.get("proposal_id") == proposal_ref]
            if len(candidates) > 1:
                raise ReviewIOError("proposal_id appears in multiple packet slots; add display_id and packet_id")
            if not candidates:
                continue
            entry = candidates[0]
        assert entry is not None
        if submitted_sha and submitted_sha != entry.get("body_sha256"):
            raise ReviewIOError("submitted body_sha256 does not match the exported proposal")
        packet_key_id = str(packet.get("packet_id", packet_path.parent.name))
        key_path = study_root / "reviews" / "keys" / f"{packet_key_id}.json"
        if not key_path.exists():
            raise ReviewIOError(f"coordinator key missing for packet {packet_key_id}")
        key = _read_json(key_path)
        matches.append((packet_path.parent, packet, key, entry, str(entry.get("display_id", display))))
    if not matches:
        raise ReviewIOError("feedback does not match any exported proposal in this study")
    if len(matches) > 1:
        raise ReviewIOError("feedback matches multiple packets; add packet_id to the form")
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


def _required_answers(sections: dict[str, str]) -> dict[str, str]:
    answers: dict[str, str] = {}
    missing: list[str] = []
    for prefix in REQUIRED_ANSWER_PREFIXES:
        label = next((key for key in sections if key.startswith(prefix)), "")
        value = sections.get(label, "").strip() if label else ""
        if not label or not value:
            missing.append(prefix)
            continue
        answers[label] = value
    if missing:
        raise ReviewIOError("review must answer all three numbered questions; missing: " + ", ".join(missing))
    return answers


def _unreviewed(sections: dict[str, str], header: dict[str, str]) -> list[str]:
    items: list[str] = []
    label = next((key for key in sections if key.lower().startswith("unreviewed")), "")
    if label:
        for line in sections[label].splitlines():
            value = line.strip().lstrip("-* ").strip()
            if value and value.lower() not in {"none", "none.", "n/a", "nothing"}:
                items.append(value)
    for value in header.get("unreviewed", "").split(";"):
        stripped = value.strip()
        if stripped and stripped.lower() not in {"none", "none.", "n/a"}:
            items.append(stripped)
    return items


def _bool_field(header: dict[str, str], key: str, default: bool) -> bool:
    value = header.get(key, "").strip().lower()
    if value in {"true", "yes", "1"}:
        return True
    if value in {"false", "no", "0"}:
        return False
    if not value:
        return default
    raise ReviewIOError(f"{key} must be true or false")


def _record_matches(existing: dict[str, object], expected: dict[str, object]) -> bool:
    keys = (
        "review_id",
        "study_id",
        "packet_id",
        "display_id",
        "proposal_id",
        "run_id",
        "body_sha256",
        "reviewer_id",
        "reviewer_role",
        "source_type",
        "blind",
        "developer_reviewer",
        "verdict",
        "answers",
        "unreviewed",
        "raw_sha256",
        "form_version",
        "binding_source",
        "notes",
    )
    return all(existing.get(key) == expected.get(key) for key in keys)


def import_review(root: Path, study_id: str, file_path: Path) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReviewIOError(f"review file unreadable: {file_path} ({type(error).__name__})") from error
    header, _body = _parse_header(raw)
    packet_dir, packet, key, entry, display = _find_packet(study_root, study_id, header)
    proposal_ref = str(entry.get("proposal_id", ""))
    expected_sha = str(entry.get("body_sha256", ""))
    raw_key = key.get("key")
    key_map = raw_key if isinstance(raw_key, dict) else {}
    key_entry = key_map.get(display)
    if not isinstance(key_entry, dict):
        raise ReviewIOError(f"coordinator key has no binding for display {display}")
    if key_entry.get("proposal_id") != proposal_ref:
        raise ReviewIOError("coordinator key proposal does not match the packet entry")
    run_id = str(key_entry.get("run_id", ""))
    if not run_id:
        raise ReviewIOError("coordinator key has no run_id")
    bound_path = root / str(key_entry.get("body_path", ""))
    if not bound_path.is_file():
        raise ReviewIOError(f"bound proposal body missing: {bound_path}")
    actual_sha = _sha(bound_path)
    if actual_sha != expected_sha:
        raise ReviewIOError("proposal body hash changed; refusing to bind review")
    if header.get("body_sha256") and header["body_sha256"] != actual_sha:
        raise ReviewIOError("review form body_sha256 does not match the bound proposal body")
    # Verify the run record still agrees with the binding.
    state_path = bound_path.parent / "state.json"
    if state_path.exists():
        state = _read_json(state_path)
        state_run_id = state.get("run_id")
        if isinstance(state_run_id, str) and state_run_id and state_run_id != run_id:
            raise ReviewIOError("run_id in the coordinator key does not match the run's state.json")
    reviewer_id = header.get("reviewer_id", "").strip()
    reviewer_role = header.get("reviewer_role", "").strip()
    if not reviewer_id:
        raise ReviewIOError("reviewer_id is required; fill the `reviewer_id:` line in the exported form")
    if not reviewer_role:
        raise ReviewIOError("reviewer_role is required; fill the `reviewer_role:` line in the exported form")
    source_type = header.get("source_type", "human").strip() or "human"
    if source_type not in {"human", "chatgpt_manual", "model_api"}:
        raise ReviewIOError("source_type must be human/chatgpt_manual/model_api")
    verdict = header.get("verdict", "uncertain").strip() or "uncertain"
    if verdict not in {"accept", "revise", "reject", "uncertain", "unreviewed"}:
        raise ReviewIOError("invalid verdict")
    sections = _answers(_body)
    answers = _required_answers(sections)
    form_version = header.get("form_version", FORM_VERSION).strip() or FORM_VERSION
    binding_source = str(key_entry.get("binding_source", "unknown"))
    review_id = "r_" + text_sha256(raw + "|" + str(packet["packet_id"]) + "|" + display + "|" + run_id)[:12]
    record_payload: dict[str, object] = {
        "schema_version": "1",
        "review_id": review_id,
        "study_id": study_id,
        "packet_id": str(packet["packet_id"]),
        "display_id": display,
        "proposal_id": proposal_ref,
        "run_id": run_id,
        "body_sha256": actual_sha,
        "reviewer_id": reviewer_id,
        "reviewer_role": reviewer_role,
        "source_type": source_type,
        "blind": _bool_field(header, "blind", True),
        "developer_reviewer": _bool_field(header, "developer_reviewer", False),
        "submitted_at": _now(),
        "verdict": verdict,
        "answers": answers,
        "unreviewed": _unreviewed(sections, header),
        "raw_path": "",
        "raw_sha256": "",
        "form_version": form_version,
        "binding_source": binding_source,
        "converter": "review_import.py",
        "notes": header.get("notes", ""),
    }
    raw_dir = study_root / "reviews" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{review_id}.md"
    if raw_path.exists() and raw_path.read_text(encoding="utf-8") != raw:
        raise ReviewIOError("review_id collision with different raw text")
    raw_path.write_text(raw, encoding="utf-8")
    record_payload["raw_path"] = str(raw_path.relative_to(root))
    record_payload["raw_sha256"] = _sha(raw_path)
    record = ReviewRecord.model_validate(record_payload)
    record_path = study_root / "reviews" / "records" / f"{review_id}.json"
    expected = record.model_dump(mode="json")
    if record_path.exists():
        existing = _read_json(record_path)
        if _record_matches(existing, expected):
            return {
                "status": "unchanged",
                "review_id": review_id,
                "display_id": display,
                "packet_id": packet["packet_id"],
                "proposal_id": proposal_ref,
                "run_id": run_id,
                "raw_path": str(raw_path.relative_to(root)),
                "record_path": str(record_path.relative_to(root)),
            }
        raise ReviewIOError("review_id already exists with different structured content; refusing to overwrite")
    _write_json(record_path, expected)
    return {
        "status": "imported",
        "review_id": review_id,
        "display_id": display,
        "packet_id": packet["packet_id"],
        "proposal_id": proposal_ref,
        "run_id": run_id,
        "raw_path": str(raw_path.relative_to(root)),
        "record_path": str(record_path.relative_to(root)),
    }


def make_feedback_set(root: Path, study_id: str, review_ids: list[str], version: str) -> dict[str, object]:
    study_root = _study_root(root, study_id)
    if not FEEDBACK_VERSION_RE.fullmatch(version):
        raise ReviewIOError("feedback set version must match [a-z0-9][a-z0-9._-]{0,40}")
    records: list[dict[str, object]] = []
    for review_id in review_ids:
        path = study_root / "reviews" / "records" / f"{review_id}.json"
        if not path.exists():
            raise ReviewIOError(f"review record missing: {review_id}")
        records.append(_read_json(path))
    target = study_root / "reviews" / f"feedback_set_{version}.json"
    canonical = json.dumps(
        {"review_ids": sorted(review_ids), "records": sorted(records, key=lambda item: str(item.get("review_id", "")))},
        sort_keys=True,
        ensure_ascii=False,
    )
    if target.exists():
        existing = _read_json(target)
        existing_ids_raw = existing.get("review_ids")
        existing_ids = [str(item) for item in existing_ids_raw] if isinstance(existing_ids_raw, list) else []
        existing_records_raw = existing.get("records")
        existing_records = (
            [item for item in existing_records_raw if isinstance(item, dict)]
            if isinstance(existing_records_raw, list)
            else []
        )
        existing_canonical = json.dumps(
            {
                "review_ids": sorted(existing_ids),
                "records": sorted(existing_records, key=lambda item: str(item.get("review_id", ""))),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if existing_canonical == canonical:
            return {
                "status": "unchanged",
                "feedback_set": str(target.relative_to(root)),
                "reviews": len(records),
            }
        raise ReviewIOError(
            f"feedback set version {version!r} already exists with different content; "
            "choose a new version instead of overwriting the frozen selection"
        )
    payload: dict[str, object] = {
        "schema_version": "1",
        "study_id": study_id,
        "feedback_set_version": version,
        "created_at": _now(),
        "review_ids": review_ids,
        "records": records,
    }
    _write_json(target, payload)
    return {"status": "created", "feedback_set": str(target.relative_to(root)), "reviews": len(records)}
