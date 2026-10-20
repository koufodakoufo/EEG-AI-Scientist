"""Evidence snapshots and exact injection tracking.

A fetched document is stored once, with its URL, title, fetch time, SHA-256 and
text.  ``read_evidence`` can only address a registered ``evidence_id`` and an
explicit character range; arbitrary filesystem paths are never accepted.  Every
slice passed to the Scientist is appended to an injection log so the report can
show what actually entered the model context.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now

EVIDENCE_ID_PATTERN = re.compile(r"^ev_[0-9a-f]{12}$")
MAX_READ_CHARS = 6000


class EvidenceError(RuntimeError):
    """Invalid evidence identifier, range, or record."""


class EvidencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    char_start: int
    char_end: int


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    url: str
    title: str
    fetched_at: str
    sha256: str
    char_count: int
    source_kind: Literal["web_html", "web_search_content", "pdf"] = "web_html"
    extractor: str = "deepseek_fetch"
    text: str
    pages: list[EvidencePage] = Field(default_factory=list)


class EvidenceMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    url: str
    title: str
    fetched_at: str
    sha256: str
    char_count: int
    source_kind: str
    extractor: str
    page_count: int = 0


class EvidenceSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    url: str
    title: str
    start_char: int
    end_char: int
    total_chars: int
    text: str
    page_start: int | None = None
    page_end: int | None = None


class InjectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: str
    evidence_id: str
    start_char: int
    end_char: int
    slice_sha256: str
    purpose: str = "read_evidence"


class EvidenceStore:
    def __init__(self, root: Path | str) -> None:
        self.root = ensure_dir(Path(root))
        self.sources_dir = ensure_dir(self.root / "sources")
        self.index_path = self.root / "index.json"
        self.injection_path = self.root / "injections.jsonl"
        self._records: dict[str, EvidenceMeta] = {}
        if self.index_path.exists():
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise EvidenceError("evidence index is not a list")
            for item in raw:
                meta = EvidenceMeta.model_validate(item)
                self._records[meta.evidence_id] = meta

    def _save_index(self) -> None:
        items = [self._records[key].model_dump(mode="json") for key in sorted(self._records)]
        atomic_write_json(self.index_path, items)

    def add_text(
        self,
        *,
        url: str,
        title: str,
        text: str,
        source_kind: Literal["web_html", "web_search_content", "pdf"] = "web_html",
        extractor: str = "deepseek_fetch",
        pages: list[EvidencePage] | None = None,
    ) -> EvidenceRecord:
        if not text.strip():
            raise EvidenceError("refusing to register empty evidence text")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        evidence_id = f"ev_{digest[:12]}"
        existing = self._records.get(evidence_id)
        if existing is not None:
            return self.get(evidence_id)
        record = EvidenceRecord(
            evidence_id=evidence_id,
            url=url,
            title=title,
            fetched_at=utc_now(),
            sha256=digest,
            char_count=len(text),
            source_kind=source_kind,
            extractor=extractor,
            text=text,
            pages=pages or [],
        )
        atomic_write_json(self.sources_dir / f"{evidence_id}.json", record.model_dump(mode="json"))
        self._records[evidence_id] = EvidenceMeta(
            evidence_id=evidence_id,
            url=url,
            title=title,
            fetched_at=record.fetched_at,
            sha256=digest,
            char_count=record.char_count,
            source_kind=source_kind,
            extractor=extractor,
            page_count=len(record.pages),
        )
        self._save_index()
        return record

    def get(self, evidence_id: str) -> EvidenceRecord:
        if not EVIDENCE_ID_PATTERN.fullmatch(evidence_id):
            raise EvidenceError("evidence_id has an invalid format")
        path = self.sources_dir / f"{evidence_id}.json"
        if not path.exists():
            raise EvidenceError(f"unknown evidence_id {evidence_id}")
        return EvidenceRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_meta(self) -> list[EvidenceMeta]:
        return [self._records[key] for key in sorted(self._records)]

    def has(self, evidence_id: str) -> bool:
        return evidence_id in self._records

    def injected_ids(self) -> set[str]:
        """Evidence IDs that entered the model context at least once."""

        if not self.injection_path.exists():
            return set()
        injected: set[str] = set()
        for line in self.injection_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = InjectionRecord.model_validate_json(line)
            injected.add(item.evidence_id)
        return injected

    def read(
        self,
        evidence_id: str,
        *,
        start_char: int = 0,
        max_chars: int = 4000,
        purpose: str = "read_evidence",
    ) -> EvidenceSlice:
        if start_char < 0:
            raise EvidenceError("start_char must be >= 0")
        if not 1 <= max_chars <= MAX_READ_CHARS:
            raise EvidenceError(f"max_chars must be between 1 and {MAX_READ_CHARS}")
        record = self.get(evidence_id)
        start = min(start_char, record.char_count)
        end = min(start + max_chars, record.char_count)
        if start >= end:
            raise EvidenceError("requested range is empty or past the end of the document")
        text_slice = record.text[start:end]
        page_start: int | None = None
        page_end: int | None = None
        for page in record.pages:
            if page.char_start <= start < page.char_end:
                page_start = page.page
            if page.char_start < end <= page.char_end:
                page_end = page.page
        injection = InjectionRecord(
            at=utc_now(),
            evidence_id=evidence_id,
            start_char=start,
            end_char=end,
            slice_sha256=hashlib.sha256(text_slice.encode("utf-8")).hexdigest(),
            purpose=purpose,
        )
        with self.injection_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(injection.model_dump_json() + "\n")
        return EvidenceSlice(
            evidence_id=evidence_id,
            url=record.url,
            title=record.title,
            start_char=start,
            end_char=end,
            total_chars=record.char_count,
            text=text_slice,
            page_start=page_start,
            page_end=page_end,
        )

    def write_markdown(self, evidence_id: str) -> Path:
        """Write a human-readable copy next to the JSON snapshot."""

        record = self.get(evidence_id)
        target = self.sources_dir / f"{evidence_id}.md"
        header = (
            f"# {record.title or '(untitled)'}\n\n"
            f"- evidence_id: `{record.evidence_id}`\n"
            f"- url: {record.url}\n"
            f"- fetched_at: {record.fetched_at}\n"
            f"- sha256: `{record.sha256}`\n"
            f"- chars: {record.char_count}\n\n---\n\n"
        )
        atomic_write_text(target, header + record.text)
        return target


def _union_length(intervals: list[tuple[int, int]]) -> int:
    """Return the size of the union of half-open [start, end) intervals."""

    ordered = sorted((max(0, start), max(0, end)) for start, end in intervals if end > start)
    if not ordered:
        return 0
    total = 0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start > current_end:
            total += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    total += current_end - current_start
    return total


def estimate_injection_fraction(store: EvidenceStore) -> dict[str, object]:
    """Summarize how much of each source has ever been injected.

    Overlapping and repeated reads are merged as character intervals before
    counting.  Reading the same 1,000 characters twice does not mean 2,000
    characters were read.
    """

    injected: dict[str, list[tuple[int, int]]] = {}
    if store.injection_path.exists():
        for line in store.injection_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = InjectionRecord.model_validate_json(line)
            injected.setdefault(item.evidence_id, []).append((item.start_char, item.end_char))
    rows: list[dict[str, object]] = []
    for meta in store.list_meta():
        clamped = [
            (min(max(0, start), meta.char_count), min(max(0, end), meta.char_count))
            for start, end in injected.get(meta.evidence_id, [])
        ]
        chars = _union_length(clamped)
        rows.append(
            {
                "evidence_id": meta.evidence_id,
                "title": meta.title,
                "url": meta.url,
                "read_chars": chars,
                "total_chars": meta.char_count,
                "fraction_read": round(chars / max(meta.char_count, 1), 4),
            }
        )
    return {"sources": rows}
