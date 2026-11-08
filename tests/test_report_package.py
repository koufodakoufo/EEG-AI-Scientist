"""Pure lossless-view tests; no provider calls or private reference answers."""

from __future__ import annotations
import copy
import hashlib
import json

import pytest

from eegfm.evaluation.report_package import (
    build_report_package,
    validate_report_package,
    validate_authored_span,
    ReportPlanningError,
)


IDENTITIES = {
    "episode": "synthetic-episode",
    "episode_journal_sha256": "1" * 64,
    "transport_audit_sha256": "2" * 64,
}


def package(text="A result is 0.75.", **kwargs):
    raw = json.dumps(
        {
            "action": "finish",
            "reason": text,
            "conclusion": {"statement": "Another result."},
        },
        ensure_ascii=False,
    ).encode()
    return build_report_package(
        raw, source_id="report", source_identities=IDENTITIES, **kwargs
    )


def test_lossless_bytes_all_nested_values_offsets_and_literals():
    raw = b'{"action":"finish","reason":"quote \\"x\\" and \\\\ path \\ud83e\\udde0","parameters":{"a/b":[-1.25,1e-03,null,true,{},[]]},"conclusion":{"statement":"R2=-0.05; interval [0.01,0.09].","unresolved":["not known"],"not_tested":["new cohorts"]},"evidence_refs":["output-1"]}'
    result = build_report_package(raw, source_id="s", source_identities=IDENTITIES)
    assert result["raw_finish_utf8"].encode() == raw
    assert result["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["original_document"] == json.loads(raw)
    assert "1e-03" in result["view"]
    assert any(
        row.get("pointer") == "/parameters/a~1b/1" for row in result["source_map"]
    )
    assert any(
        row["source_role"] == "structure" and row.get("pointer") == "/evidence_refs/0"
        for row in result["source_map"]
    )
    for block in result["source_blocks"]:
        span = {
            "start": block["start"],
            "end": block["end"],
            "quote": result["view"][block["start"] : block["end"]],
        }
        binding = validate_authored_span(
            result, span, primary_block_ids=[block["block_id"]]
        )
        assert binding["pointer"] == block["pointer"]
        assert binding["quote"] == span["quote"]
        assert binding["raw_sha256"] == result["raw_sha256"]
    assert validate_report_package(result) == result


@pytest.mark.parametrize(
    "mutation",
    [
        "raw",
        "view",
        "pointer",
        "map_gap",
        "map_overlap",
        "block",
        "inventory_hash",
        "metadata",
    ],
)
def test_package_rejects_any_changed_map_view_original_or_ownership(mutation):
    original = package()
    changed = copy.deepcopy(original)
    if mutation == "raw":
        changed["raw_finish_utf8"] += " "
    if mutation == "view":
        changed["view"] += "x"
    if mutation == "pointer":
        next(x for x in changed["source_map"] if x["source_role"] == "authored")[
            "pointer"
        ] = "/absent"
    if mutation == "map_gap":
        changed["source_map"].pop(0)
    if mutation == "map_overlap":
        changed["source_map"][0]["end"] += 1
    if mutation == "block":
        changed["source_blocks"][0]["end"] -= 1
    if mutation == "inventory_hash":
        changed["source_blocks_sha256"] = "0" * 64
    if mutation == "metadata":
        changed["source_identities"]["episode"] = "different"
    with pytest.raises(ValueError):
        validate_report_package(changed)


def test_every_authored_character_owned_once_and_whole_block_packing():
    result = package("A first sentence. A second sentence. A third sentence.")
    for row in result["source_map"]:
        if row["source_role"] != "authored":
            continue
        owned = [b for b in result["source_blocks"] if b["pointer"] == row["pointer"]]
        assert (
            "".join(result["view"][b["start"] : b["end"]] for b in owned)
            == result["view"][row["start"] : row["end"]]
        )
    assigned = [b for s in result["segments"] for b in s["primary_block_ids"]]
    assert assigned == [b["block_id"] for b in result["source_blocks"]]
    for segment in result["segments"]:
        assert len(segment["primary_blocks"]) <= 2
        assert sum(len(b["text"]) for b in segment["primary_blocks"]) <= 800


def test_conservative_sentences_do_not_split_decimals_abbreviations_or_quoted_punctuation():
    text = 'Dr. Chen measured -0.25 and 7.5e-15, e.g. a small effect. A quote says "Stop. Stay." This ambiguous unit remains whole. Another sentence.'
    result = package(text)
    blocks = [b for b in result["source_blocks"] if b["pointer"] == "/reason"]
    assert "".join(result["view"][b["start"] : b["end"]] for b in blocks) == text
    assert (
        result["view"][blocks[0]["start"] : blocks[0]["end"]]
        == "Dr. Chen measured -0.25 and 7.5e-15, e.g. a small effect. "
    )
    assert any('"Stop. Stay."' in result["view"][b["start"] : b["end"]] for b in blocks)


def test_oversized_indivisible_unit_fails_preflight_without_repacking():
    with pytest.raises(ReportPlanningError, match="oversized"):
        package("x" * 801)


def test_renderer_metadata_neighbor_and_cross_block_quotes_cannot_anchor():
    result = package("One sentence. Two sentences.")
    authored = result["source_blocks"]
    with pytest.raises(ValueError):
        validate_authored_span(
            result,
            {"start": 0, "end": 1, "quote": result["view"][:1]},
            primary_block_ids=[authored[0]["block_id"]],
        )
    first, second = next(
        (a, b) for a, b in zip(authored, authored[1:]) if a["pointer"] == b["pointer"]
    )
    with pytest.raises(ValueError):
        validate_authored_span(
            result,
            {
                "start": first["start"],
                "end": second["end"],
                "quote": result["view"][first["start"] : second["end"]],
            },
            primary_block_ids=[first["block_id"], second["block_id"]],
        )
    with pytest.raises(ValueError):
        validate_authored_span(
            result,
            {
                "start": second["start"],
                "end": second["end"],
                "quote": result["view"][second["start"] : second["end"]],
            },
            primary_block_ids=[first["block_id"]],
        )
    with pytest.raises(ValueError):
        validate_authored_span(
            result,
            {
                "start": first["start"],
                "end": first["end"],
                "quote": result["view"][first["start"] : first["end"]],
            },
            primary_block_ids=[first["block_id"], "unknown-block"],
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"action":"finish","reason":"a","reason":"b"}',
        b'{"action":"finish","value":NaN}',
        b'{"action":"finish","value":1e999}',
        b'{"action":"other"}',
    ],
)
def test_duplicate_nonfinite_and_nonfinish_reject(raw):
    with pytest.raises(ValueError):
        build_report_package(raw, source_id="s", source_identities=IDENTITIES)
