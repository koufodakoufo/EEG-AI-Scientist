"""Opt-in lossless structured-finish view and authored-block ownership.

No provider calls, inferred claims, source execution or legacy schema changes.
Offsets are Unicode code-point offsets; original UTF-8 bytes remain recoverable.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping

from eegfm.evaluation import claims

VERSION = "registered_report_package_v1"
RENDERER_VERSION = "lossless_finish_blocks_v1"
SENTENCE_POLICY = "conservative_outside_quotes_brackets_v1"


class ReportPlanningError(ValueError):
    """An intact source unit exceeds the prospectively declared transport plan."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _resolve(document: Any, pointer: str) -> Any:
    value = document
    if pointer == "":
        return value
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _parse_leaves(raw: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Decode once while retaining exact raw scalar/container token lexemes."""
    decoder = json.JSONDecoder(
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("Nonfinite JSON value")
        )
    )
    leaves: list[dict[str, Any]] = []

    def whitespace(index: int) -> int:
        while index < len(raw) and raw[index] in " \t\r\n":
            index += 1
        return index

    def parse(index: int, pointer: str, depth: int) -> tuple[Any, int]:
        if depth > 32:
            raise ValueError("Finish JSON nesting exceeds 32")
        start = whitespace(index)
        if start >= len(raw):
            raise ValueError("Incomplete finish JSON")
        character = raw[start]
        if character == "{":
            value: dict[str, Any] = {}
            index = whitespace(start + 1)
            if index < len(raw) and raw[index] == "}":
                leaves.append(
                    {
                        "pointer": pointer,
                        "value": {},
                        "raw_start": start,
                        "raw_end": index + 1,
                    }
                )
                return value, index + 1
            while True:
                if index >= len(raw) or raw[index] != '"':
                    raise ValueError("Object key required")
                key, index = decoder.raw_decode(raw, index)
                if key in value:
                    raise ValueError("Duplicate JSON key")
                index = whitespace(index)
                if index >= len(raw) or raw[index] != ":":
                    raise ValueError("Object colon required")
                child, index = parse(
                    index + 1, pointer + "/" + _pointer_part(key), depth + 1
                )
                value[key] = child
                index = whitespace(index)
                if index < len(raw) and raw[index] == "}":
                    return value, index + 1
                if index >= len(raw) or raw[index] != ",":
                    raise ValueError("Object separator required")
                index = whitespace(index + 1)
        if character == "[":
            array: list[Any] = []
            index = whitespace(start + 1)
            if index < len(raw) and raw[index] == "]":
                leaves.append(
                    {
                        "pointer": pointer,
                        "value": [],
                        "raw_start": start,
                        "raw_end": index + 1,
                    }
                )
                return array, index + 1
            while True:
                child, index = parse(index, pointer + "/" + str(len(array)), depth + 1)
                array.append(child)
                index = whitespace(index)
                if index < len(raw) and raw[index] == "]":
                    return array, index + 1
                if index >= len(raw) or raw[index] != ",":
                    raise ValueError("Array separator required")
                index = whitespace(index + 1)
        value, end = decoder.raw_decode(raw, start)
        if isinstance(value, (dict, list)):
            raise ValueError("Unexpected container token")
        if type(value) in (int, float) and not math.isfinite(value):
            raise ValueError("Nonfinite JSON number")
        leaves.append(
            {"pointer": pointer, "value": value, "raw_start": start, "raw_end": end}
        )
        return value, end

    document, end = parse(0, "", 0)
    if whitespace(end) != len(raw):
        raise ValueError("Trailing JSON content")
    if not isinstance(document, dict) or document.get("action") != "finish":
        raise ValueError("Complete structured finish object required")
    claims.canonical_sha256(document)
    return document, leaves


def _sentence_slices(text: str) -> list[tuple[int, int]]:
    """Lossless conservative units, not a general scientific sentence parser.

    Decimal/exponent punctuation, fixed abbreviations, quoted/bracketed text
    and ambiguous boundaries remain intact. Oversized units fail upstream.
    """
    if not text:
        return []
    cuts = []
    start = 0
    quote: str | None = None
    brackets: list[str] = []
    abbreviations = (
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
        "prof.",
        "fig.",
        "eq.",
        "e.g.",
        "i.e.",
        "vs.",
        "no.",
        "et al.",
    )
    pairs = {"(": ")", "[": "]", "{": "}"}
    for index, character in enumerate(text):
        escaped = False
        if character in ('"', "“", "”", "‘", "’", "'"):
            previous = index - 1
            while previous >= 0 and text[previous] == "\\":
                previous -= 1
            escaped = (index - 1 - previous) % 2 == 1
        if quote:
            if character == quote and not escaped:
                quote = None
            continue
        if character in ('"', "“", "‘", "'") and not escaped:
            if character == "'" and index > 0 and text[index - 1].isalnum():
                continue
            quote = {"“": "”", "‘": "’"}.get(character, character)
            continue
        if character in pairs:
            brackets.append(pairs[character])
            continue
        if brackets:
            if character == brackets[-1]:
                brackets.pop()
            continue
        if character not in ".!?":
            continue
        end = index + 1
        while end < len(text) and text[end].isspace():
            end += 1
        if end == index + 1 or end == len(text) or not text[end].isupper():
            continue
        prefix = text[max(0, index - 24) : index + 1].lower()
        if character == "." and (
            any(prefix.endswith(a) for a in abbreviations)
            or re.search(r"(?:\b[a-z]\.){1,}$", prefix)
        ):
            continue
        cuts.append((start, end))
        start = end
    if start < len(text):
        cuts.append((start, len(text)))
    return cuts


def _structural(pointer: str, value: Any) -> bool:
    return (
        pointer == "/action"
        or pointer.startswith("/evidence_refs/")
        or pointer.startswith("/conclusion/support_ids/")
        or isinstance(value, (dict, list))
    )


def build_report_package(
    raw_finish: bytes | str,
    *,
    source_id: str,
    source_identities: Mapping[str, Any],
    max_blocks_per_segment: int = 2,
    max_authored_chars: int = 800,
) -> dict[str, Any]:
    """Render all values and preserve original bytes, offsets and exact ownership."""
    if isinstance(raw_finish, bytes):
        raw = raw_finish.decode("utf-8", errors="strict")
    elif isinstance(raw_finish, str):
        raw = raw_finish
    else:
        raise ValueError("UTF-8 finish bytes or text required")
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or len(raw) > claims.MAX_REPORT_CHARS
    ):
        raise ValueError("Invalid source identity/report size")
    if (
        type(max_blocks_per_segment) is not int
        or not 1 <= max_blocks_per_segment <= 2
        or type(max_authored_chars) is not int
        or not 1 <= max_authored_chars <= 800
    ):
        raise ValueError(
            "Declared packing may not exceed 2 blocks or 800 authored characters"
        )
    identities = copy.deepcopy(dict(source_identities))
    if (
        not isinstance(identities.get("episode"), str)
        or not identities["episode"].strip()
    ):
        raise ValueError("Episode provenance required")
    for key in ("episode_journal_sha256", "transport_audit_sha256"):
        if not isinstance(identities.get(key), str) or not re.fullmatch(
            "[0-9a-f]{64}", identities[key]
        ):
            raise ValueError("Exact provenance hashes required")
    claims.canonical_sha256(identities)
    document, leaves = _parse_leaves(raw)
    pieces: list[str] = []
    mapping: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    position = 0

    def append(text: str, role: str, **metadata: Any) -> tuple[int, int]:
        nonlocal position
        start = position
        position += len(text)
        pieces.append(text)
        mapping.append(
            {"start": start, "end": position, "source_role": role, **metadata}
        )
        return start, position

    for leaf in leaves:
        pointer, value = leaf["pointer"], leaf["value"]
        append("[" + (pointer or "/") + "]\n", "renderer")
        structural = _structural(pointer, value)
        decoded = isinstance(value, str) and not structural
        text = value if decoded else raw[leaf["raw_start"] : leaf["raw_end"]]
        encoding = "decoded_string" if decoded else "json_literal"
        role = "structure" if structural else "authored"
        start, end = append(
            text,
            role,
            pointer=pointer,
            value_encoding=encoding,
            source_start=0,
            source_end=len(text),
            raw_start=leaf["raw_start"],
            raw_end=leaf["raw_end"],
        )
        if role == "authored":
            for begin, stop in _sentence_slices(text):
                if stop - begin > max_authored_chars:
                    raise ReportPlanningError(
                        f"oversized indivisible source block at {pointer}: {stop-begin} authored characters"
                    )
                blocks.append(
                    {
                        "block_id": f"b{len(blocks)+1:04d}",
                        "pointer": pointer,
                        "start": start + begin,
                        "end": start + stop,
                        "source_start": begin,
                        "source_end": stop,
                        "value_encoding": encoding,
                        "source_role": "authored",
                    }
                )
        append("\n", "renderer")
    view = "".join(pieces)
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    count = 0
    for block in blocks:
        length = block["end"] - block["start"]
        if current and (
            len(current) == max_blocks_per_segment
            or count + length > max_authored_chars
        ):
            groups.append(current)
            current = []
            count = 0
        current.append(block)
        count += length
    if current:
        groups.append(current)
    if not groups:
        groups = [[]]
    if len(groups) > claims.MAX_SEGMENTS:
        raise ReportPlanningError("Source-block segment limit exceeded")
    segments = []

    def excerpt(block: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **copy.deepcopy(dict(block)),
            "text": view[block["start"] : block["end"]],
        }

    for index, group in enumerate(groups):
        first = blocks.index(group[0]) if group else 0
        last = first + len(group)
        segments.append(
            {
                "segment_id": f"s{index+1:04d}",
                "primary_block_ids": [b["block_id"] for b in group],
                "primary_blocks": [excerpt(b) for b in group],
                "context_before": [
                    excerpt(b) for b in blocks[max(0, first - 1) : first]
                ],
                "context_after": [excerpt(b) for b in blocks[last : last + 1]],
            }
        )
    return {
        "schema_version": VERSION,
        "renderer_version": RENDERER_VERSION,
        "sentence_policy": SENTENCE_POLICY,
        "source_id": source_id,
        "source_identities": identities,
        "source_identities_sha256": claims.canonical_sha256(identities),
        "raw_finish_utf8": raw,
        "raw_sha256": _sha(raw),
        "raw_byte_length": len(raw.encode("utf-8")),
        "original_document": document,
        "view": view,
        "view_sha256": _sha(view),
        "offset_unit": "unicode_codepoints",
        "source_map": mapping,
        "source_map_sha256": claims.canonical_sha256(mapping),
        "source_blocks": blocks,
        "source_blocks_sha256": claims.canonical_sha256(blocks),
        "max_blocks_per_segment": max_blocks_per_segment,
        "max_authored_chars": max_authored_chars,
        "segments": segments,
    }


def validate_report_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the complete deterministic map/plan, rejecting all silent drift."""
    try:
        expected = build_report_package(
            package["raw_finish_utf8"],
            source_id=package["source_id"],
            source_identities=package["source_identities"],
            max_blocks_per_segment=package["max_blocks_per_segment"],
            max_authored_chars=package["max_authored_chars"],
        )
    except (KeyError, TypeError, UnicodeError, RecursionError) as error:
        raise ValueError("Malformed registered report package") from error
    if dict(package) != expected:
        raise ValueError("Lossless package/source/map/ownership changed")
    return expected


def validate_authored_span(
    package: Mapping[str, Any],
    span: Mapping[str, Any],
    *,
    primary_block_ids: Iterable[str],
) -> dict[str, Any]:
    """Bind an exact rendered quote back to its intact original value substring."""
    p = validate_report_package(package)
    if (
        set(span) != {"start", "end", "quote"}
        or type(span["start"]) is not int
        or type(span["end"]) is not int
    ):
        raise ValueError("Exact authored source span required")
    start, end, quote = span["start"], span["end"], span["quote"]
    if (
        not isinstance(quote, str)
        or not quote.strip()
        or not 0 <= start < end <= len(p["view"])
        or p["view"][start:end] != quote
    ):
        raise ValueError("Rendered quote/offset mismatch")
    owned = set(primary_block_ids)
    if not owned <= {b["block_id"] for b in p["source_blocks"]}:
        raise ValueError("Unknown primary authored block ID")
    block = next(
        (
            b
            for b in p["source_blocks"]
            if b["block_id"] in owned and b["start"] <= start < end <= b["end"]
        ),
        None,
    )
    if block is None:
        raise ValueError("Quote is not wholly inside one primary authored block")
    entry = next(
        m
        for m in p["source_map"]
        if m["source_role"] == "authored" and m["pointer"] == block["pointer"]
    )
    begin = entry["source_start"] + start - entry["start"]
    stop = begin + end - start
    if entry["value_encoding"] == "decoded_string":
        original = _resolve(p["original_document"], entry["pointer"])
    else:
        original = p["raw_finish_utf8"][entry["raw_start"] : entry["raw_end"]]
    if original[begin:stop] != quote:
        raise ValueError("Original decoded value/source-map round-trip mismatch")
    return {
        "pointer": entry["pointer"],
        "source_start": begin,
        "source_end": stop,
        "value_encoding": entry["value_encoding"],
        "quote": quote,
        "block_id": block["block_id"],
        "raw_sha256": p["raw_sha256"],
        "view_sha256": p["view_sha256"],
    }
