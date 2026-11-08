"""Synthetic contract fixtures, not EEG evidence or semantic calibration."""
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from eegfm.improvement import decision


def catalog():
    return {"task_id": "fixture-selection", "layer": 12, "code_hash": "a" * 64,
            "input_hashes": {"pooled": "b" * 64}, "entries": [
                {"action": "recovery", "parameters": {"method": "leace", "fit_design": "split_subjects", "penalty": 10},
                 "result": {"r2": -0.2, "fit_subjects": ["train-a"], "assessment_subjects": ["validation"]}}]}


def start(data=None, identity=None):
    return decision.start(data or catalog(), source_bindings={"pooled": "b" * 64},
                          identity=identity or {"episode": "fixture-1", "method_hash": "c" * 64})


def action(**updates):
    value = {"action": "recovery", "parameters": {"method": "leace", "fit_design": "split_subjects", "penalty": 10},
             "reason": "Distinguish residual recovery from same-fit covariance.",
             "discriminates": ["recoverable", "not recovered"], "evidence_refs": [], "conclusion": None}
    value.update(updates)
    return value


def finish(support_ids=None):
    return action(action="finish", parameters={}, conclusion={"statement": "Evidence is limited to this fixture.",
                  "support_ids": support_ids or [], "unresolved": ["Other cohorts"], "not_tested": ["Final test"]})


def test_serves_exact_registered_result_and_binds_provenance_without_mutation():
    data = catalog()
    initial = start(data)
    data["entries"][0]["result"]["r2"] = 42
    current, receipt = decision.dispatch(initial, action())
    assert receipt["result"]["data"]["r2"] == -0.2
    assert receipt["result"]["provenance"]["input_hashes"] == {"pooled": "b" * 64}
    assert receipt["result"]["provenance"]["parameters"]["fit_design"] == "split_subjects"
    assert receipt["remaining_requests"] == 3
    assert initial.receipts == ()
    receipt["result"]["data"]["r2"] = 99
    assert current.receipts[0] != decision.canonical_json(receipt)
    with pytest.raises(FrozenInstanceError):
        current.finished = True


@pytest.mark.parametrize("bad", [None, {}, action(action="test"), action(parameters={"path": "/private"}),
    action(parameters={"method": "leace", "fit_design": "split_subjects", "penalty": True}),
    action(evidence_refs=["not-served"]), action(extra="instruction"), action(conclusion={}),
    action(reason=""), action(discriminates="a versus b")])
def test_malformed_requests_consume_one_slot_and_never_serve_data(bad):
    state, receipt = decision.dispatch(start(), bad)
    assert receipt["error"] and receipt["result"] is None
    assert receipt["remaining_requests"] == 3
    assert not state.finished


def test_budget_is_four_requests_and_one_final_only_attempt():
    state = start()
    for _ in range(4):
        state, _ = decision.dispatch(state, {})
    state, receipt = decision.dispatch(state, action())
    assert receipt["error"] and state.finished
    assert receipt["remaining_requests"] == 0
    with pytest.raises(ValueError, match="finished"):
        decision.dispatch(state, finish())


def test_finish_can_use_only_successful_evidence_and_is_structurally_bounded():
    state, output = decision.dispatch(start(), action())
    state, final = decision.dispatch(state, finish([output["output_id"]]))
    assert state.finished and final["error"] is None
    assert final["result"]["conclusion"]["not_tested"] == ["Final test"]
    invalid = finish(["invented-output"])
    bad_state, receipt = decision.dispatch(start(), invalid)
    assert bad_state.finished and receipt["error"]


def test_unregistered_valid_request_is_retained_as_failure():
    requested = action(parameters={"method": "identity", "fit_design": "same_sample", "penalty": 1})
    state, receipt = decision.dispatch(start(), requested)
    assert receipt["error"] and receipt["remaining_requests"] == 3
    assert state.receipts


@pytest.mark.parametrize("mutation", ["source", "duplicate", "layer", "unknown", "hash"])
def test_catalog_rejects_invalid_bindings_and_unqualified_entries(mutation):
    data = catalog()
    if mutation == "source":
        data["input_hashes"]["pooled"] = "d" * 64
    elif mutation == "duplicate":
        data["entries"].append(deepcopy(data["entries"][0]))
    elif mutation == "layer":
        data["layer"] = 6
        data["entries"][0]["action"] = "consequence"
        data["entries"][0]["parameters"]["controls"] = True
    elif mutation == "hash":
        data["code_hash"] = "not-a-hash"
    else:
        data["entries"][0]["action"] = "execute"
    with pytest.raises(ValueError):
        start(data)


def test_resume_replays_chain_and_rejects_identity_catalog_or_receipt_drift():
    state, first = decision.dispatch(start(), action())
    state, second = decision.dispatch(state, finish([first["output_id"]]))
    kwargs = {"source_bindings": {"pooled": "b" * 64},
              "identity": {"episode": "fixture-1", "method_hash": "c" * 64}, "receipts": [first, second]}
    assert decision.resume(catalog(), **kwargs) == state
    changed = deepcopy(catalog())
    changed["entries"][0]["result"]["r2"] = 0.9
    with pytest.raises(ValueError):
        decision.resume(changed, **kwargs)
    kwargs["identity"] = {"episode": "different"}
    with pytest.raises(ValueError):
        decision.resume(catalog(), **kwargs)
    kwargs["identity"] = {"episode": "fixture-1", "method_hash": "c" * 64}
    kwargs["receipts"][0]["remaining_requests"] = 4
    with pytest.raises(ValueError):
        decision.resume(catalog(), **kwargs)


def test_full_operator_parameter_grid_has_no_aliases():
    data = catalog()
    data["entries"] = []
    for method in ("identity", "probe_direction", "leace"):
        for design in ("same_sample", "split_subjects"):
            for penalty in (1, 10, 100):
                parameters = {"method": method, "fit_design": design, "penalty": penalty}
                data["entries"].append({"action": "recovery", "parameters": parameters, "result": {"cell": len(data["entries"])}})
                for controls in (False, True):
                    data["entries"].append({"action": "consequence", "parameters": dict(parameters, controls=controls), "result": {"cell": len(data["entries"])}})
    state = start(data)
    for entry in data["entries"]:
        _, receipt = decision.dispatch(state, action(action=entry["action"], parameters=entry["parameters"]))
        assert receipt["result"]["data"] == entry["result"]


def test_input_named_code_cannot_mask_invalid_implementation_hash():
    data = catalog()
    data["code_hash"] = "not-a-code-hash"
    data["input_hashes"] = {"code": "b" * 64}
    with pytest.raises(ValueError):
        decision.start(data, source_bindings={"code": "b" * 64}, identity={"episode": "fixture"})


@pytest.mark.parametrize("bad", [action(action=[]), action(parameters={"method": {}, "fit_design": [], "penalty": 1}),
    action(evidence_refs=[{}]), finish([{}])])
def test_nested_invalid_json_shapes_return_errors_without_escaping_budget(bad):
    _, receipt = decision.dispatch(start(), bad)
    assert receipt["error"]
    assert receipt["remaining_requests"] == (4 if bad["action"] == "finish" else 3)


def test_lone_surrogate_json_text_is_journaled_and_consumes_budget():
    state, receipt = decision.dispatch(start(), action(reason="JSON escaped text: \ud800"))
    assert receipt["error"] is None
    assert receipt["remaining_requests"] == 3
    assert receipt["request"]["reason"].endswith("\ud800")
    assert len(receipt["receipt_hash"]) == 64
    assert decision.resume(catalog(), source_bindings={"pooled": "b" * 64},
                           identity={"episode": "fixture-1", "method_hash": "c" * 64},
                           receipts=[receipt]) == state


def test_malformed_finish_with_surrogate_text_is_retained_and_sealed():
    submitted = finish()
    submitted["reason"] = "\udfff"
    submitted["conclusion"]["support_ids"] = ["unknown"]
    state, receipt = decision.dispatch(start(), submitted)
    assert state.finished and receipt["error"]
    assert decision.resume(catalog(), source_bindings={"pooled": "b" * 64},
                           identity={"episode": "fixture-1", "method_hash": "c" * 64},
                           receipts=[receipt]) == state
