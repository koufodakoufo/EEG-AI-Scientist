"""Deterministic opt-in transport/projection tests, never model calibration."""

from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest

from eegfm.evaluation import assessment, claims
from eegfm.evaluation.report_package import build_report_package
from eegfm.evaluation.registered_assessment import (
    assess_registered_report,
    extract_registered_report,
    build_registered_context,
    project_reference_views,
    JUDGE_VERSION,
)
from test_paper import private_task


IDENTITIES = {
    "episode": "synthetic",
    "episode_journal_sha256": "1" * 64,
    "transport_audit_sha256": "2" * 64,
}
ORIGIN = {
    "source_id": "verified-public-packet",
    "sha256": "3" * 64,
    "description": "Controller-verified synthetic registration",
}


def task_fixture():
    task = private_task()
    task["scope"]["conditions"].update(
        layer=12, target_attribute="accuracy", target_columns=1
    )
    task["references"][0]["claim"]["scope"] = copy.deepcopy(task["scope"])
    return task


def registered_fixture(text="Accuracy is 0.75.", document=None):
    task = task_fixture()
    package = build_report_package(
        json.dumps(document or {"action": "finish", "reason": text}),
        source_id="report",
        source_identities=IDENTITIES,
    )
    context = build_registered_context(task["scope"], origin=ORIGIN)
    return task, package, context


def core(identifier, block, *, qualifiers=None, context_assertions=None):
    span = {key: block[key] for key in ("start", "end")}
    span["quote"] = block["text"]
    return {
        "claim_id": identifier,
        "kind": "point",
        "subject": "classifier",
        "predicate": "accuracy",
        "direction": "positive",
        "qualifiers": [],
        "payload": {"metric": "accuracy", "estimate": 0.75, "unit": "fraction"},
        "source_spans": [span],
        "evidence_ids": [],
        "condition_qualifiers": qualifiers or [],
        "context_assertions": context_assertions or [],
    }


def fixture_provider(request):
    if request["operation"] == "registered_extract":
        segment = request["data"]["segment"]
        atoms = [
            core(segment["segment_id"] + f"-{i}", block)
            for i, block in enumerate(segment["primary_blocks"])
        ]
        return json.dumps(
            {
                "segment_id": segment["segment_id"],
                "status": "complete",
                "claims": atoms,
                "notes": "",
            }
        )
    return json.dumps(
        {
            "batch_id": request["data"]["batch_id"],
            "status": "complete",
            "judgments": [
                {
                    **{
                        k: e[k]
                        for k in (
                            "edge_id",
                            "agent_claim_id",
                            "reference_claim_id",
                            "direction",
                        )
                    },
                    "relation": "supported",
                    "judge_version": JUDGE_VERSION,
                }
                for e in request["data"]["edges"]
            ],
            "notes": "Synthetic schema fixture only",
        }
    )


def test_complete_new_path_exact_replay_and_context_not_model_retyped():
    task, p, context = registered_fixture()
    result = assess_registered_report(
        task, p, context, fixture_provider, provider_id="fixture"
    )
    assert result["status"] == "scored_dimensions"
    assert result["dimensions"]["reference_coverage"]["f1"] == 1
    assert len(result["calls"]) == 2  # extraction + one two-direction batch
    extraction_request = result["calls"][0]["request"]
    assert extraction_request["data"]["registered_study_context"] == context
    assert "scope" not in extraction_request["response_contract"]["claims"][0]
    assert "context_id" not in extraction_request["response_contract"]["claims"][0]
    assert (
        result["dimensions"]["researcher_reporting_completeness"][
            "controller_metadata_credit"
        ]
        is False
    )
    assert result["accounting"]["actual_provider_contexts"] is None
    replay = assessment.ReplayProvider(result["calls"])
    assert result == assess_registered_report(
        task, p, context, replay, provider_id="fixture"
    )
    replay.assert_consumed()
    with pytest.raises(assessment.ReplayMismatch):
        assess_registered_report(
            task,
            p,
            context,
            assessment.ReplayProvider(result["calls"]),
            provider_id="changed",
        )


def test_every_segment_has_full_same_context_and_primary_ownership():
    _, p, context = registered_fixture(
        document={
            "action": "finish",
            "reason": ["Sentence " + str(i) + "." for i in range(9)],
        }
    )
    result = extract_registered_report(
        p, context, fixture_provider, provider_id="fixture"
    )
    assert len(result["calls"]) > 1
    for call in result["calls"]:
        assert call["request"]["data"]["registered_study_context"] == context
        assert "primary authored blocks" in call["request"]["instructions"]
        assert "not researcher-authored" in call["request"]["instructions"]
    assert result["extraction"]["eligible_for_scoring"]
    assert all(
        o["context_id"] == context["context_id"]
        for o in result["extraction"]["occurrences"]
    )


def test_projected_references_preserve_every_condition_and_provenance_without_mutation():
    task, _, context = registered_fixture()
    reference = task["references"][0]
    reference["claim"]["scope"]["conditions"].update(
        fold=0,
        method="leace",
        fit_design="opposite_B",
        residual_probe_penalty=1,
        primary_penalty=10,
        comparison_metric="absolute-logit",
        evaluation="observed",
    )
    before = copy.deepcopy(task)
    views = project_reference_views(task, context)
    view = views["views"][0]
    assert task == before
    assert view["original_conditions"] == reference["claim"]["scope"]["conditions"]
    assert view["provenance"] == reference["provenance"]
    mapped = {v["field"]: v["value"] for v in view["condition_qualifiers"]}
    for field in (
        "fold",
        "method",
        "fit_design",
        "residual_probe_penalty",
        "primary_penalty",
        "comparison_metric",
        "evaluation",
    ):
        assert mapped[field] == reference["claim"]["scope"]["conditions"][field]
    assert (
        len(view["projection_map"])
        == len(reference["claim"]["scope"]["conditions"]) + 3
    )


def test_fold_penalty_metric_restrictions_survive_hashing_and_dedup():
    task, p, context = registered_fixture()
    block = p["segments"][0]["primary_blocks"][0]
    span = {"start": block["start"], "end": block["end"], "quote": block["text"]}

    def provider(request):
        if request["operation"] != "registered_extract":
            return fixture_provider(request)
        atoms = []
        for index, (fold, penalty, metric) in enumerate(
            ((0, 1, "BA"), (1, 1, "BA"), (0, 10, "BA"), (0, 1, "logit"))
        ):
            qualifiers = [
                {"field": k, "value": v, "source_spans": [span]}
                for k, v in (
                    ("fold", fold),
                    ("residual_probe_penalty", penalty),
                    ("comparison_metric", metric),
                )
            ]
            atoms.append(core("a" + str(index), block, qualifiers=qualifiers))
        return json.dumps(
            {"segment_id": "s0001", "status": "complete", "claims": atoms, "notes": ""}
        )

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    assert len(result["extraction"]["claims"]) == 4
    assert len(set(result["extraction"]["semantic_hashes"].values())) == 4
    edges = next(
        c["request"]["data"]["edges"]
        for c in result["calls"]
        if c["request"]["operation"] == "registered_judge_batch"
    )
    assert all(e["agent_view"]["condition_qualifiers"] for e in edges)
    assert "Do not infer a fold" in next(
        c["request"]["instructions"]
        for c in result["calls"]
        if c["request"]["operation"] == "registered_judge_batch"
    )


@pytest.mark.parametrize(
    "mode",
    [
        "dataset",
        "split",
        "checkpoint",
        "unknown_condition",
        "unknown_reference",
        "unknown_context",
    ],
)
def test_explicit_conflicts_or_unknown_fields_stay_pending_never_bound_into_support(
    mode,
):
    task, p, context = registered_fixture("Accuracy is 0.75 on a test cohort.")
    if mode == "unknown_reference":
        task["references"][0]["claim"]["scope"]["conditions"][
            "unrecognized_field"
        ] = "x"
    if mode == "unknown_context":
        scope = copy.deepcopy(task["scope"])
        scope["conditions"]["checkpoint"] = None
        context = build_registered_context(scope, origin=ORIGIN)

    def provider(request):
        response = json.loads(fixture_provider(request))
        if request["operation"] == "registered_extract":
            atom = response["claims"][0]
            span = atom["source_spans"][0]
            if mode == "unknown_condition":
                atom["condition_qualifiers"] = [
                    {
                        "field": "invented_condition",
                        "value": "x",
                        "source_spans": [span],
                    }
                ]
            if mode in ("dataset", "split", "checkpoint"):
                field = {
                    "dataset": "dataset",
                    "split": "split",
                    "checkpoint": "conditions/checkpoint",
                }[mode]
                atom["context_assertions"] = [
                    {
                        "field": field,
                        "value": "explicitly different",
                        "source_spans": [span],
                    }
                ]
        return json.dumps(response)

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    assert result["status"] == "pending_or_incomplete"
    assert result["dimensions"]["reference_coverage"]["f1"] is None
    assert not any(
        c["request"]["operation"] == "registered_judge_batch" for c in result["calls"]
    )
    if mode in ("dataset", "split", "checkpoint"):
        occurrence = result["extraction"]["occurrences"][0]
        assert occurrence["context_assertions"][0]["value"] == "explicitly different"
        assert occurrence["status"] == "pending"


@pytest.mark.parametrize(
    "count,expected", [(63, "complete"), (64, "truncated"), (65, "service_failure")]
)
def test_exact_63_64_65_cap_boundaries_retained(count, expected):
    _, p, context = registered_fixture()

    def provider(request):
        block = request["data"]["segment"]["primary_blocks"][0]
        atoms = [core("a" + str(i), block) for i in range(count)]
        for i, a in enumerate(atoms):
            a["payload"]["metric"] = "metric" + str(i)
        return json.dumps(
            {"segment_id": "s0001", "status": "complete", "claims": atoms, "notes": ""}
        )

    result = extract_registered_report(p, context, provider, provider_id="fixture")
    assert result["extraction"]["status"] == expected
    assert len(json.loads(result["calls"][0]["raw_response"])["claims"]) == count
    assert result["extraction"]["eligible_for_scoring"] == (count == 63)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "wrong_id",
        "wrong_direction",
        "wrong_claim",
        "truncated",
        "late_invalid",
    ],
)
def test_exact_batch_failure_is_pending_without_salvaging_partial_labels(mutation):
    task, p, context = registered_fixture()

    def provider(request):
        response = json.loads(fixture_provider(request))
        if request["operation"] == "registered_extract":
            first = response["claims"][0]
            response["claims"] = [
                {
                    **copy.deepcopy(first),
                    "claim_id": "a" + str(i),
                    "payload": {
                        "metric": "accuracy" + str(i),
                        "estimate": 0.75,
                        "unit": "fraction",
                    },
                }
                for i in range(21)
            ]
        elif mutation != "late_invalid" or request["data"]["batch_id"] == "jb0002":
            if mutation in ("missing", "late_invalid"):
                response["judgments"].pop()
            if mutation == "duplicate":
                response["judgments"][-1] = copy.deepcopy(response["judgments"][0])
            if mutation == "wrong_id":
                response["judgments"][0]["edge_id"] = "unknown"
            if mutation == "wrong_direction":
                response["judgments"][0]["direction"] = "wrong"
            if mutation == "wrong_claim":
                response["judgments"][0]["agent_claim_id"] = "unknown"
            if mutation == "truncated":
                response.update(status="truncated", judgments=[])
        return json.dumps(response)

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    assert result["status"] == "pending_or_incomplete"
    assert result["dimensions"]["reference_coverage"]["precision"] is None
    assert result["dimensions"]["unsupported_claims"] == []
    assert result["judging"]["pending_edges"]
    assert all(e["reason"] != "not_covered" for e in result["judging"]["pending_edges"])
    assert any(c["status"] in ("invalid_output", "truncated") for c in result["calls"])


def test_budgets_never_skip_pairs_or_count_missing_as_not_covered():
    task, p, context = registered_fixture()
    for kwargs in ({"max_logical_edges": 1}, {"max_provider_requests": 1}):
        result = assess_registered_report(
            task, p, context, fixture_provider, provider_id="fixture", **kwargs
        )
        assert result["status"] == "pending_or_incomplete"
        assert result["judging"]["planned_judge_directional_edges"] == 2
        assert len(result["judging"]["pending_edges"]) == 2
        assert not result["judgments"]
        assert len(result["calls"]) == 1


def test_original_paper_unknown_scope_cannot_inherit_adapted_registration():
    task, p, context = registered_fixture()
    task["references"][0]["claim"]["scope"]["conditions"]["checkpoint"] = None
    result = assess_registered_report(
        task, p, context, fixture_provider, provider_id="fixture"
    )
    view = result["reference_views"]["views"][0]
    assert view["original_conditions"]["checkpoint"] is None
    assert view["projection"]["identity"]["conditions"]["checkpoint"] is None
    assert view["status"] == "pending"
    assert result["status"] == "pending_or_incomplete"


def test_registration_conflicting_with_selected_task_stays_pending():
    task, p, context = registered_fixture()
    different = copy.deepcopy(task["scope"])
    different["dataset"] = "Different registered study"
    context = build_registered_context(different, origin=ORIGIN)
    result = assess_registered_report(
        task, p, context, fixture_provider, provider_id="fixture"
    )
    assert result["status"] == "pending_or_incomplete"
    assert not any(
        c["request"]["operation"] == "registered_judge_batch" for c in result["calls"]
    )


def test_reference_folds_and_penalties_do_not_deduplicate_under_shared_context():
    task, p, context = registered_fixture()
    original = copy.deepcopy(task["references"][0])
    task["references"] = []
    for number, (fold, penalty) in enumerate(((0, 1), (1, 1), (0, 10), (1, 10))):
        reference = copy.deepcopy(original)
        reference["claim"]["claim_id"] = "r" + str(number)
        reference["claim"]["scope"]["conditions"].update(
            fold=fold, residual_probe_penalty=penalty
        )
        task["references"].append(reference)
    result = assess_registered_report(
        task, p, context, fixture_provider, provider_id="fixture"
    )
    assert len(result["reference_canonicalization"]["claims"]) == 4
    assert result["judging"]["planned_judge_directional_edges"] == 8
    for view in result["reference_views"]["views"]:
        assert any(
            m.get("mapped_qualifier", "").startswith("condition:fold=")
            for m in view["projection_map"]
        )


@pytest.mark.parametrize("failure", ["bad_json", "timeout"])
def test_new_failure_calls_replay_exactly_without_implicit_retry(failure):
    task, p, context = registered_fixture()

    def provider(request):
        if failure == "bad_json":
            return "{broken"
        raise TimeoutError("Synthetic transport timeout")

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    replay = assessment.ReplayProvider(result["calls"])
    assert result == assess_registered_report(
        task, p, context, replay, provider_id="fixture"
    )
    replay.assert_consumed()
    assert len(result["calls"]) == 1


def test_explicit_conflict_marker_text_is_retained_and_not_treated_as_controller_metadata():
    text = "Controller scope: test. Do not erase this literal conflict marker."
    task, p, context = registered_fixture(text)

    def provider(request):
        response = json.loads(fixture_provider(request))
        if request["operation"] == "registered_extract":
            response["claims"][0]["context_assertions"] = [
                {
                    "field": "split",
                    "value": "test",
                    "source_spans": response["claims"][0]["source_spans"],
                }
            ]
        return json.dumps(response)

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    assert text in p["view"]
    assert result["status"] == "pending_or_incomplete"
    assert (
        result["extraction"]["occurrences"][0]["context_assertions"][0]["value"]
        == "test"
    )


def test_late_invalid_extraction_or_cross_block_span_never_calls_judge():
    task, p, context = registered_fixture(
        document={
            "action": "finish",
            "reason": ["A sentence.", "B sentence.", "C sentence."],
        }
    )

    def provider(request):
        response = json.loads(fixture_provider(request))
        if request["data"]["segment"]["segment_id"] == "s0002":
            response["claims"][0]["source_spans"][0]["quote"] = "wrong"
        return json.dumps(response)

    result = assess_registered_report(task, p, context, provider, provider_id="fixture")
    assert result["extraction"]["status"] == "service_failure"
    assert len(result["calls"]) == 2
    assert not result["judgments"]


def test_new_path_requests_have_new_hashes_and_preserve_legacy_golden():
    from test_paper_assessment import fixture_provider as old_provider

    old = assessment.assess_report(
        private_task(), "Accuracy is 0.75.", old_provider, provider_id="fixture"
    )
    assert (
        old["calls"][0]["request_sha256"]
        == "5e22c035585b96708eb54cd06902d3a913ae269f90aaa86e27c6bc8682762c29"
    )
    assert (
        claims.canonical_sha256(old)
        == "140bc28b4fb8b6def0ac17508450c98a0bbb7e4324b87f7861d88270f02f90bd"
    )
    task, p, context = registered_fixture()
    new = assess_registered_report(
        task, p, context, fixture_provider, provider_id="fixture"
    )
    assert new["calls"][0]["request_sha256"] != old["calls"][0]["request_sha256"]


def test_actual_closed_report_wrong_both_fold_logit_claim_reaches_judge_unchanged():
    # Private artifacts remain outside Git. This dispatch fixture never supplies
    # an expected semantic label and makes no model call.
    root = Path(__file__).resolve().parents[1] / ".local/research-renewal"
    report_path = root / "real-report-assessment-direct/raw/INPUT.json"
    task_path = root / "paper-alignment/adapted-assessment-task.json"
    if not report_path.is_file() or not task_path.is_file():
        pytest.skip("Private closed-report fixture not installed")
    raw = json.loads(report_path.read_text(encoding="utf-8"))["report"]
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["references"] = [
        r
        for r in task["references"]
        if r["claim"]["claim_id"] == "adapted-logit-boundary"
    ]
    p = build_report_package(
        raw, source_id="closed-report", source_identities=IDENTITIES
    )
    context = build_registered_context(task["scope"], origin=ORIGIN)
    actual = next(
        b
        for b in p["source_blocks"]
        if "these lie within each fold" in p["view"][b["start"] : b["end"]]
    )
    text = p["view"][actual["start"] : actual["end"]]
    seen = []

    def provider(request):
        if request["operation"] == "registered_extract":
            segment = request["data"]["segment"]
            atoms = []
            if actual["block_id"] in segment["primary_block_ids"]:
                a = core("actual-wrong-range", {**actual, "text": text})
                a.update(kind="qualitative", payload={"statement": text})
                atoms = [a]
            return json.dumps(
                {
                    "segment_id": segment["segment_id"],
                    "status": "complete",
                    "claims": atoms,
                    "notes": "",
                }
            )
        seen.extend(request["data"]["edges"])
        response = json.loads(fixture_provider(request))
        for judgment in response["judgments"]:
            judgment["relation"] = "needs_review"
        return json.dumps(response)

    assess_registered_report(task, p, context, provider, provider_id="dispatch-fixture")
    assert len(seen) == 2
    assert all(e["agent_view"]["claim"]["payload"]["statement"] == text for e in seen)
    assert all(
        e["agent_view"]["claim"]["source_spans"][0]["quote"] == text for e in seen
    )
    assert all(
        e["reference_view"]["original_claim"]["claim_id"] == "adapted-logit-boundary"
        for e in seen
    )
