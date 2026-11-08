"""Selection arithmetic over supplied fixture audits; no semantic oracle."""
from copy import deepcopy

import pytest

from eegfm.improvement.selection import select_method


def inputs():
    methods = [{"method_id": "baseline", "text": "", "input_task_ids": []},
               {"method_id": "expert_recipe", "text": "Check provenance and controls.", "input_task_ids": []},
               {"method_id": "trace_method", "text": "Check scope.", "input_task_ids": ["development"]}]
    audits = [{"method_id": method["method_id"], "task_id": task, "repeat": repeat,
               "valid": True, "supported": 1, "unsupported": 0, "discrimination": 1, "cost": 4}
              for method in methods for task in ("specificity-a", "specificity-b") for repeat in ("first", "second")]
    return {"methods": methods, "tasks": {"development": "development", "specificity-a": "selection",
            "specificity-b": "selection", "confirmation": "target"}, "repeats": ["first", "second"], "audits": audits}


def test_ties_retain_baseline_and_return_every_aggregate():
    result = select_method(**inputs())
    assert result["winner"] == "baseline"
    assert len(result["methods"]) == 3
    assert result["methods"][0]["supported"] == 4
    assert "audit" in result["limitation"]


@pytest.mark.parametrize("field,value,winner", [("supported", 2, "trace_method"),
    ("unsupported", 1, "baseline"), ("discrimination", 2, "trace_method"), ("cost", 3, "trace_method"),
    ("valid", False, "baseline")])
def test_validity_first_ranking(field, value, winner):
    data = inputs()
    for row in data["audits"]:
        if row["method_id"] == "trace_method":
            row[field] = value
    assert select_method(**data)["winner"] == winner


def test_supported_precedes_unsupported_discrimination_and_cost():
    data = inputs()
    for row in data["audits"]:
        if row["method_id"] == "expert_recipe":
            row.update(supported=2, unsupported=100, discrimination=0, cost=100)
    assert select_method(**data)["winner"] == "expert_recipe"


def test_without_valid_baseline_tie_prefers_shorter_method_and_all_invalid_has_no_winner():
    data = inputs()
    for row in data["audits"]:
        if row["method_id"] == "baseline":
            row["valid"] = False
    assert select_method(**data)["winner"] == "trace_method"
    for row in data["audits"]:
        row["valid"] = False
    assert select_method(**data)["winner"] is None


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "target", "development", "unknown_method",
    "unknown_task", "unknown_role", "leakage", "undeclared_input", "duplicate_method", "duplicate_repeat", "nan", "bool_score", "negative"])
def test_rejects_incomplete_or_leaking_selection_inputs(mutation):
    data = inputs()
    if mutation == "missing":
        data["audits"].pop()
    elif mutation == "duplicate":
        data["audits"].append(deepcopy(data["audits"][0]))
    elif mutation in ("target", "development", "unknown_task"):
        data["audits"][0]["task_id"] = {"target": "confirmation", "development": "development", "unknown_task": "undeclared"}[mutation]
    elif mutation == "unknown_method":
        data["audits"][0]["method_id"] = "unregistered"
    elif mutation == "unknown_role":
        data["tasks"]["confirmation"] = "holdout-ish"
    elif mutation in ("leakage", "undeclared_input"):
        data["methods"][2]["input_task_ids"] = ["confirmation" if mutation == "leakage" else "undeclared"]
    elif mutation == "duplicate_method":
        data["methods"].append(deepcopy(data["methods"][0]))
    elif mutation == "duplicate_repeat":
        data["repeats"].append("first")
    else:
        data["audits"][0]["cost" if mutation == "nan" else "supported"] = {"nan": float("nan"), "bool_score": True, "negative": -1}[mutation]
    with pytest.raises(ValueError):
        select_method(**data)


@pytest.mark.parametrize("field", ["method_id", "task_id", "repeat"])
def test_malformed_cell_identifier_is_validation_error(field):
    data = inputs()
    data["audits"][0][field] = []
    with pytest.raises(ValueError):
        select_method(**data)


def test_finite_individual_costs_cannot_overflow_aggregate():
    data = inputs()
    for row in data["audits"]:
        row["cost"] = 1e308
    with pytest.raises(ValueError):
        select_method(**data)


@pytest.mark.parametrize("score", ["supported", "unsupported", "discrimination", "cost"])
def test_oversized_integer_scores_fail_closed_with_validation_error(score):
    data = inputs()
    data["audits"][0][score] = 10 ** 400
    with pytest.raises(ValueError):
        select_method(**data)


def test_mixed_cost_sum_overflow_is_validation_error():
    data = inputs()
    for row, cost in zip(data["audits"], [10 ** 308, 10 ** 308, 1.0, 1]):
        row["cost"] = cost
    with pytest.raises(ValueError):
        select_method(**data)
