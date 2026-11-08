"""Deterministic validity-first selection over externally supplied audit scores."""
from __future__ import annotations

import math
from typing import Any

from .decision import _keys, _strings, _text, digest


def _finite_score(value: Any) -> bool:
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def select_method(*, methods: list[dict], tasks: dict[str, str], repeats: list[str],
                  audits: list[dict]) -> dict[str, Any]:
    """Require every declared selection cell; never score semantics internally."""
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError("declared task roles required")
    for task, role in tasks.items():
        _text(task)
        if role not in ("development", "selection", "target"):
            raise ValueError("unknown task role")
    selection_tasks = {task for task, role in tasks.items() if role == "selection"}
    if not selection_tasks:
        raise ValueError("no selection tasks")
    _strings(repeats, nonempty=True)
    if not isinstance(methods, list) or not methods:
        raise ValueError("declared methods required")
    declared = {}
    for method in methods:
        _keys(method, "method_id text input_task_ids")
        method_id = method["method_id"]
        if method_id not in ("baseline", "expert_recipe", "trace_method") or method_id in declared:
            raise ValueError("unknown or duplicate method")
        if not isinstance(method["text"], str) or len(method["text"].split()) > 120:
            raise ValueError("method must be text of at most 120 words")
        _strings(method["input_task_ids"])
        if any(tasks.get(task) != "development" for task in method["input_task_ids"]):
            raise ValueError("method input includes undeclared or protected task")
        declared[method_id] = method
    if "baseline" not in declared:
        raise ValueError("baseline required")
    expected = {(method, task, repeat) for method in declared
                for task in selection_tasks for repeat in repeats}
    if not isinstance(audits, list):
        raise ValueError("audit list required")
    cells = {}
    for row in audits:
        _keys(row, "method_id task_id repeat valid supported unsupported discrimination cost")
        for name in ("method_id", "task_id", "repeat"):
            _text(row[name])
        key = (row["method_id"], row["task_id"], row["repeat"])
        if key not in expected or key in cells:
            raise ValueError("duplicate, excluded or undeclared audit cell")
        if type(row["valid"]) is not bool:
            raise ValueError("valid must be boolean")
        for score in ("supported", "unsupported", "discrimination", "cost"):
            value = row[score]
            if (not _finite_score(value)
                    or (score != "cost" and type(value) is not int)):
                raise ValueError("scores must be nonnegative finite counts; cost may be fractional")
        cells[key] = row
    if set(cells) != expected:
        raise ValueError("incomplete selection matrix")
    aggregates = []
    for method_id, method in declared.items():
        rows = [row for key, row in cells.items() if key[0] == method_id]
        try:
            totals = {score: sum(row[score] for row in rows)
                      for score in ("supported", "unsupported", "discrimination", "cost")}
        except OverflowError as exc:
            raise ValueError("aggregate score overflow") from exc
        if not all(_finite_score(value) for value in totals.values()):
            raise ValueError("aggregate scores must remain finite")
        aggregates.append({"method_id": method_id, "valid": all(row["valid"] for row in rows),
                           **totals,
                           "words": len(method["text"].split()), "method_hash": digest(method)})
    valid = [row for row in aggregates if row["valid"]]
    def rank(row: dict) -> tuple:
        return (-row["supported"], row["unsupported"], -row["discrimination"], row["cost"],
                row["method_id"] != "baseline", row["words"], row["method_id"])
    return {"winner": min(valid, key=rank)["method_id"] if valid else None,
            "methods": sorted(aggregates, key=lambda row: row["method_id"]),
            "input_hash": digest({"methods": methods, "tasks": tasks, "repeats": repeats, "audits": audits}),
            "rule": "validity/support/unsupported/discrimination/cost/baseline/words/id",
            "limitation": "Trusted external audit scores; selection is not a semantic oracle or unbiased confirmation."}
