"""Task-bound, advisory validation coverage. Counts never certify validity."""
from __future__ import annotations

import math
import re
from typing import Any


SESSION_GUIDANCE = frozenset({"fixed_stages_v1", "adaptive_evidence_v1"})
EVIDENCE_METRICS = frozenset({"q1_groups", "q2_interventions", "q3_residual_groups"})


def validate_policy(value: Any) -> dict[str, Any]:
    """Accept a small declaration, never an executable policy language."""
    if (not isinstance(value, dict) or set(value) != {
            "schema_version", "policy_id", "obligations", "lock_policy", "partial_reports_allowed"}
            or value["schema_version"] != "scientific_evidence_policy_v1"
            or not isinstance(value["policy_id"], str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,127}", value["policy_id"])
            or value["lock_policy"] != "advisory" or value["partial_reports_allowed"] is not True):
        raise ValueError("Invalid advisory scientific evidence policy")
    obligations = value["obligations"]
    if not isinstance(obligations, list) or not 1 <= len(obligations) <= len(EVIDENCE_METRICS):
        raise ValueError("Invalid evidence obligations")
    ids, metrics = set(), set()
    for item in obligations:
        if (not isinstance(item, dict) or set(item) != {"id", "metric", "minimum"}
                or not isinstance(item["id"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item["id"])
                or not isinstance(item["metric"], str) or item["metric"] not in EVIDENCE_METRICS
                or type(item["minimum"]) is not int or item["minimum"] <= 0
                or item["id"] in ids or item["metric"] in metrics):
            raise ValueError("Invalid or duplicate evidence obligation")
        ids.add(item["id"])
        metrics.add(item["metric"])
    return value


def validation_evidence_status(policy: dict[str, Any], projection: dict[str, Any], *,
                               max_iterations: int) -> dict[str, Any]:
    """Use only the latest iteration's own successful validation job result.

    A failed later iteration remains failed. Neither baseline nor final-test
    metrics can fill gaps, and an absent/invalid counter is not measured zero.
    """
    validate_policy(policy)
    iterations = [row for row in projection["attempts"] if row["kind"] == "iteration"]
    attempt = iterations[-1] if iterations else None
    metrics: dict[str, Any] = {}
    source_status = "not_assessed"
    if attempt:
        jobs = [row for row in projection["jobs"] if row["job_id"] in attempt["jobs"]
                and row["split"] == "validation" and row["attempt_id"] == attempt["id"]
                and row["candidate_digest"] == attempt["candidate_digest"]]
        source_status = "failed" if attempt["status"] == "failed" else "not_assessed"
        if len(jobs) == 1:
            job = jobs[0]
            result = job.get("result", {})
            if job["status"] == "failed" or result.get("status") == "failed":
                source_status = "failed"
            elif (attempt["status"] == "evaluated" and job["status"] == "succeeded"
                  and result.get("status") == "succeeded"
                  and all(result.get(key) == job[key] for key in ("job_id", "candidate_digest", "split"))):
                source_status = "succeeded"
                metrics = result.get("metrics", {})
            elif source_status != "failed" and job["status"] in {"waiting", "submitted"}:
                source_status = "waiting"
    requirements = []
    for obligation in policy["obligations"]:
        value = metrics.get(obligation["metric"])
        observed = None
        if (type(value) in {int, float} and math.isfinite(value)
                and value >= 0 and value == int(value)):
            observed = int(value)
        requirements.append({**obligation, "observed": observed,
            "status": "not_assessed" if observed is None else
                      "present" if observed >= obligation["minimum"] else "missing"})
    remaining = max(0, max_iterations - len(iterations))
    if projection.get("lock") or projection["state"]["status"] in {"done", "blocked"}:
        next_action = "complete_frozen_lifecycle_and_report_limitations"
    elif not attempt:
        next_action = "follow_lifecycle_to_validation_iteration"
    elif source_status == "waiting":
        next_action = "await_validation"
    elif source_status == "failed" and not remaining:
        next_action = "report_failed_attempt_and_limitations"
    elif remaining and any(row["status"] != "present" for row in requirements):
        next_action = "consider_revision_before_lock"
    else:
        next_action = "consider_lock_and_report_limitations"
    return {"policy_id": policy["policy_id"], "source_attempt_id": attempt["id"] if attempt else None,
            "source_split": "validation", "source_status": source_status, "requirements": requirements,
            "remaining_iterations": remaining, "next_action": next_action,
            "scientific_validity": "not_assessed"}
