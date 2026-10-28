"""Unified `study` and `review` command group."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backends import load_registry
from .paths import project_root
from .review_io import ReviewIOError, export_packet, import_review, make_feedback_set
from .study_runtime import (
    StudyRuntimeError,
    init_study,
    load_study,
    preflight,
    report,
    run_study,
    status,
)
from .study_spec import validate_spec

ROOT = project_root()
BACKENDS = "configs/models/backends_20261021.json"


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def command_study_init(args: argparse.Namespace) -> int:
    try:
        target = init_study(args.id, ROOT, template=args.template)
    except (StudyRuntimeError, ValueError) as error:
        print(f"study init failed: {error}")
        return 2
    print(f"created {target / 'study.json'}")
    return 0


def command_study_validate(args: argparse.Namespace) -> int:
    try:
        _path, spec = load_study(ROOT, args.study)
        errors = validate_spec(spec, ROOT, load_registry(ROOT / BACKENDS))
    except Exception as error:  # noqa: BLE001 - validation boundary
        print(f"study validate failed: {type(error).__name__}: {error}")
        return 2
    if errors:
        _print({"study_id": spec.study_id, "valid": False, "errors": errors})
        return 1
    _print({"study_id": spec.study_id, "valid": True, "errors": []})
    return 0


def command_study_run(args: argparse.Namespace) -> int:
    try:
        if not args.confirm_cost:
            _path, spec = load_study(ROOT, args.study)
            _print(
                {
                    "study_id": spec.study_id,
                    "paid_run": False,
                    "reason": "pass --confirm-cost to start",
                    "budget": spec.budget.model_dump(mode="json"),
                    "arms": [arm.model_dump(mode="json") for arm in spec.arms],
                }
            )
            return 2
        payload = run_study(ROOT, args.study, confirm_cost=True)
    except Exception as error:  # noqa: BLE001 - command boundary
        print(f"study run failed: {type(error).__name__}: {error}")
        return 2
    _print(payload)
    raw_results = payload.get("results")
    results = raw_results if isinstance(raw_results, list) else []
    return 0 if all(isinstance(item, dict) and item.get("status") in {"completed", "completed_unverified", "already_terminal"} for item in results) else 1


def command_study_preflight(args: argparse.Namespace) -> int:
    try:
        payload = preflight(ROOT, args.study)
    except Exception as error:  # noqa: BLE001 - preflight boundary
        print(f"study preflight failed: {type(error).__name__}: {error}")
        return 2
    _print(payload)
    return 0 if payload.get("ok") else 1


def command_study_status(args: argparse.Namespace) -> int:
    try:
        _print(status(ROOT, args.study))
    except Exception as error:  # noqa: BLE001 - status boundary
        print(f"study status failed: {type(error).__name__}: {error}")
        return 2
    return 0


def command_study_report(args: argparse.Namespace) -> int:
    try:
        _print(report(ROOT, args.study))
    except Exception as error:  # noqa: BLE001 - report boundary
        print(f"study report failed: {type(error).__name__}: {error}")
        return 2
    return 0


def command_review_export(args: argparse.Namespace) -> int:
    try:
        payload = export_packet(ROOT, args.study)
    except (ReviewIOError, OSError) as error:
        print(f"review export failed: {type(error).__name__}: {error}")
        return 2
    _print(payload)
    return 0


def command_review_import(args: argparse.Namespace) -> int:
    files = args.file if isinstance(args.file, list) else [args.file]
    imported: list[dict[str, object]] = []
    for value in files:
        try:
            payload = import_review(ROOT, args.study, Path(value))
        except (ReviewIOError, OSError, ValueError) as error:
            print(f"review import failed for {value}: {type(error).__name__}: {error}")
            return 2
        imported.append(payload)
    _print({"imported": imported})
    return 0


def command_review_select(args: argparse.Namespace) -> int:
    try:
        review_ids = [item.strip() for item in args.reviews.split(",") if item.strip()]
        if not review_ids:
            raise ReviewIOError("no review IDs supplied")
        payload = make_feedback_set(ROOT, args.study, review_ids, args.version)
    except (ReviewIOError, OSError, ValueError) as error:
        print(f"review select failed: {type(error).__name__}: {error}")
        return 2
    _print(payload)
    return 0


def add_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    study = subparsers.add_parser("study", help="unified study entry (offline commands by default)")
    study_sub = study.add_subparsers(dest="study_command", required=True)

    init = study_sub.add_parser("init", help="create a draft study directory")
    init.add_argument("--id", required=True)
    init.add_argument("--template", choices=["generic", "emotion_20261021"], default="generic")
    init.set_defaults(func=command_study_init)

    validate = study_sub.add_parser("validate", help="validate study files and verified backends")
    validate.add_argument("--study", required=True)
    validate.set_defaults(func=command_study_validate)

    run = study_sub.add_parser("run", help="run configured arms; requires --confirm-cost")
    run.add_argument("--study", required=True)
    run.add_argument("--confirm-cost", action="store_true")
    run.set_defaults(func=command_study_run)

    status_cmd = study_sub.add_parser("status", help="show state/ledger without any model call")
    status_cmd.add_argument("--study", required=True)
    status_cmd.set_defaults(func=command_study_status)

    preflight_cmd = study_sub.add_parser(
        "preflight", help="show task/material/rule hashes and per-arm prompt diffs (offline)"
    )
    preflight_cmd.add_argument("--study", required=True)
    preflight_cmd.set_defaults(func=command_study_preflight)

    report_cmd = study_sub.add_parser("report", help="write studies/<id>/report.md from state")
    report_cmd.add_argument("--study", required=True)
    report_cmd.set_defaults(func=command_study_report)

    review = subparsers.add_parser("review", help="export/import blind review packets")
    review_sub = review.add_subparsers(dest="review_command", required=True)

    export = review_sub.add_parser("export", help="export a blind packet from accepted proposals")
    export.add_argument("--study", required=True)
    export.set_defaults(func=command_review_export)

    import_cmd = review_sub.add_parser("import", help="import one or more Markdown reviews and bind them to proposals")
    import_cmd.add_argument("--study", required=True)
    import_cmd.add_argument("--file", required=True, action="append", help="form path; repeat for multiple forms")
    import_cmd.set_defaults(func=command_review_import)

    select = review_sub.add_parser("select", help="create a versioned feedback set for Meta")
    select.add_argument("--study", required=True)
    select.add_argument("--reviews", required=True, help="comma-separated review IDs")
    select.add_argument("--version", default="v1")
    select.set_defaults(func=command_review_select)
