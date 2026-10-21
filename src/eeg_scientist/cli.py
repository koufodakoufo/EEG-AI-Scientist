"""Command-line entry points for preflight, episodes, the study, and reports."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

from .cases import build_public_case, generate_case, load_case_specs
from .experiments import compute_baselines, execute_experiment
from .provider import provider_from_config
from .runner import run_episode
from .schema import (
    CaseSpec,
    EpisodeConfig,
    ExperimentContext,
    ExperimentRequest,
    Prediction,
    StudyConfig,
)
from .scientist import probe_request
from .splits import build_all_splits
from .storage import atomic_write_json, ensure_dir, sha256_text, utc_now


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_float_list(value: object) -> tuple[float, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_as_float(item) for item in value)




def _archived_path(path: Path | str) -> bool:
    return "archive" in Path(path).parts


def _archive_hint(action: str) -> int:
    print(f"{action}: this old experiment is archived and read-only; no new run was started.")
    print("Use the unified entry point instead:")
    print("  .\\.venv\\Scripts\\python.exe -m eeg_scientist.cli study --help")
    print("  .\\.venv\\Scripts\\python.exe -m eeg_scientist.cli review --help")
    print("Read archive/README.md for the old experiment index and old commands.")
    return 2


def _probe_parse(text: str) -> dict[str, object]:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("probe JSON is not an object")
    return value


def _git_status() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        return (result.stdout or result.stderr).strip()
    except Exception as error:  # noqa: BLE001 - environment report
        return f"git status unavailable: {error}"


def _power_report() -> str:
    try:
        result = subprocess.run(
            ["powercfg", "/q", "SCHEME_CURRENT", "SUB_SLEEP", "STANDBYIDLE"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        return (result.stdout or result.stderr).strip()
    except Exception as error:  # noqa: BLE001 - environment report
        return f"powercfg unavailable: {error}"


def _env_flags() -> dict[str, bool]:
    names = [
        "SCIENTIST_API_KEY",
        "SCIENTIST_BASE_URL",
        "SCIENTIST_MODEL",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]
    return {name: bool(os.environ.get(name)) for name in names}


def command_preflight(args: argparse.Namespace) -> int:
    if _archived_path(getattr(args, 'config', '')):
        return _archive_hint('preflight')
    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    deadline = _deadline(config.deadline)
    reports_dir = ensure_dir(Path(config.reports_dir))
    health = getattr(provider, "health", lambda: {"ok": False, "error": "no health method"})()
    describe: dict[str, object] = getattr(provider, "describe", lambda: {})()
    probe_ok = False
    probe_status = "not_run"
    probe_latency = 0.0
    probe_usage: dict[str, object] = {}
    probe_error = ""
    try:
        response = provider.decide(probe_request())
        probe_status = response.status
        probe_latency = response.latency_ms
        probe_usage = dict(response.usage)
        if response.status == "ok":
            parsed = _probe_parse(response.visible_text)
            probe_ok = bool(parsed.get("ok"))
        else:
            probe_error = response.error or ""
    except Exception as error:  # noqa: BLE001 - preflight boundary
        probe_error = str(error)
    disk = shutil.disk_usage(".")
    env_flags = _env_flags()
    lines = [
        "# PREFLIGHT",
        "",
        f"- checked_at_utc: {utc_now()}",
        f"- local_time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- timezone: {datetime.now().astimezone().tzinfo}",
        f"- deadline: {config.deadline}",
        f"- deadline_utc: {deadline.isoformat()}",
        f"- report_reserve_minutes: {config.report_reserve_minutes}",
        f"- cwd: {Path.cwd()}",
        f"- python: {sys.version.split()[0]}",
        f"- platform: {platform.platform()}",
        f"- cpu_count: {os.cpu_count()}",
        f"- disk_free_gb: {disk.free / (1024 ** 3):.1f}",
        "",
        "## Model route",
        "",
        f"- provider_kind: {config.provider.get('kind')}",
        f"- provider_name: {provider.provider_name}",
        f"- model: {provider.model_name}",
        f"- backend: {provider.backend}",
        f"- health: {json.dumps(health, default=str)[:1000]}",
        f"- describe: {json.dumps(describe, default=str)[:1500]}",
        f"- probe_status: {probe_status}",
        f"- probe_ok: {probe_ok}",
        f"- probe_latency_ms: {round(probe_latency, 1)}",
        f"- probe_usage: {json.dumps(probe_usage, default=str)}",
        f"- probe_error: {probe_error[:800]}",
        "",
        "## Cloud/API environment (boolean only; no values)",
        "",
    ]
    for name, present in env_flags.items():
        lines.append(f"- {name}: {present}")
    lines.extend(
        [
            "",
            "## Repository and power",
            "",
            "```text",
            _git_status(),
            "```",
            "",
            "```text",
            _power_report()[:2000],
            "```",
            "",
            "## Interpretation",
            "",
            "Desktop login and Python model access are separate. The local Ollama route is the primary route when the provider kind is ollama_native. "
            "A probe failure is a blocker; it must not be reported as a successful AI run.",
            "",
        ]
    )
    target = reports_dir / "PREFLIGHT.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {target}")
    print(f"model={provider.provider_name}/{provider.model_name} probe_ok={probe_ok} status={probe_status}")
    return 0 if probe_ok else 1


def command_episode(args: argparse.Namespace) -> int:
    if _archived_path(getattr(args, 'config', '')):
        return _archive_hint('episode')
    config = EpisodeConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_episode(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.status == "completed" else 1


def command_overnight(args: argparse.Namespace) -> int:
    if _archived_path(getattr(args, 'config', '')):
        return _archive_hint('overnight')
    from .study import run_study

    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_study(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.pairs_completed > 0 else 1


def command_resume(args: argparse.Namespace) -> int:
    if _archived_path(getattr(args, 'config', '')):
        return _archive_hint('resume')
    from .study import run_study

    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_study(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.pairs_completed > 0 else 1


def command_report(args: argparse.Namespace) -> int:
    if _archived_path(getattr(args, 'study', '')):
        return _archive_hint('report')
    from .reporting import render_reports

    paths = render_reports(Path(args.study))
    print(paths.model_dump_json(indent=2))
    return 0


def command_calibrate(args: argparse.Namespace) -> int:
    return _archive_hint("calibrate")
    from .experiments import SUPPORTED_METRIC_KEYS

    seeds = {"T": 9001, "G": 9002, "D": 9003, "N": 9004}
    random_seeds = list(range(101, 111))
    rows: list[str] = [
        "# CALIBRATION",
        "",
        "Engineering calibration on separate development seeds. These numbers are not Scientist successes and are not holdout results.",
        "",
        "| family | window BA | trial BA | subject BA | gap window-trial |",
        "|---|---:|---:|---:|---:|",
    ]
    details: list[str] = []
    for family, seed in seeds.items():
        spec = CaseSpec(
            case_id=f"cal_{family}",
            family=family,
            data_seed=seed,
            split_seed=seed + 1000,
            label_seed=seed + 2000,
            model_seed=seed + 3000,
        )
        dataset = generate_case(spec)
        splits = build_all_splits(dataset, spec.split_seed)
        baseline = compute_baselines(dataset, splits)
        metrics = baseline.metrics
        rows.append(
            f"| {family} | {metrics.get('window_balanced_accuracy', float('nan')):.3f} | "
            f"{metrics.get('trial_balanced_accuracy', float('nan')):.3f} | "
            f"{metrics.get('subject_balanced_accuracy', float('nan')):.3f} | "
            f"{metrics.get('gap_window_minus_trial', float('nan')):+.3f} |"
        )
        context = ExperimentContext(
            splits=splits,
            random_label_seeds=random_seeds,
            tool_version="1.0",
            timeout_seconds=300,
            data_hash=baseline.data_hash,
            seed=spec.model_seed,
        )
        tool_rows: list[str] = []
        for tool, metric in (
            ("trial_random_labels", "trial_random_gap_mean"),
            ("trial_shuffle_within_subject", "trial_shuffle_gap_mean"),
            ("window_random_labels", "window_random_ba_mean"),
            ("metadata_only", "metadata_only_balanced_accuracy"),
        ):
            request = ExperimentRequest(
                request_id=f"cal_{family}_{tool}",
                tool_id=tool,
                parameters={},
                distinguishes=["H1", "H2"],
                prediction=Prediction(
                    scoring_status="numeric",
                    metric_key=metric,
                    primary_direction="positive",
                    threshold=0.05,
                ),
            )
            result = execute_experiment(dataset, request, context)
            selected = {
                key: round(value, 3)
                for key, value in result.metrics.items()
                if key.endswith("mean") or key.endswith("balanced_accuracy") or key.endswith("chance")
            }
            tool_rows.append(f"| {tool} | {result.valid} | {json.dumps(selected, ensure_ascii=False)} | {result.invalid_reason or ''} |")
        details.extend(
            [
                f"## {family}",
                "",
                "| tool | valid | metrics | invalid |",
                "|---|---|---|---|",
                *tool_rows,
                "",
            ]
        )
    output = Path("archive/experiments/synthetic_20261019/reports/CALIBRATION.md")
    ensure_dir(output.parent)
    output.write_text("\n".join(rows + [""] + details), encoding="utf-8")
    print(f"wrote {output}")
    return 0


# ---------------------------------------------------------------------------
# DeepSeek Flash overnight commands
# ---------------------------------------------------------------------------

FLASH_CONFIG = "archive/experiments/flash_20261020_0058/configs/study.json"


def _flash_paths(args: argparse.Namespace) -> tuple[dict[str, object], dict[str, object]]:
    study = _read_json(Path(args.config))
    model = _read_json(Path("archive/experiments/flash_20261020_0058/configs/deepseek_flash.json"))
    return study, model


def _flash_client(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from .credentials import load_deepseek_key
    from .deepseek_api import DeepSeekClient
    from .ledger import BudgetLedger

    study, model = _flash_paths(args)
    budget = _as_dict(study.get("budget"))
    paths = _as_dict(study.get("paths"))
    key, report = load_deepseek_key(Path(_as_str(model.get("credential_file"))))
    ledger = BudgetLedger(
        Path(_as_str(paths.get("budget_ledger"))),
        run_id=_as_str(study.get("run_id")),
        cap_cny=_as_float(budget.get("project_api_cost_cny_cap")),
        wrap_up_reserve_cny=_as_float(budget.get("wrap_up_reserve_cny")),
        model_attempts_limit=_as_int(budget.get("model_attempts_cap")),
        search_attempts_limit=_as_int(budget.get("search_attempts_cap")),
        fetch_attempts_limit=_as_int(budget.get("fetch_attempts_cap")),
        input_tokens_limit=_as_int(budget.get("input_tokens_cap")),
        output_tokens_limit=_as_int(budget.get("output_tokens_cap")),
    )
    client = DeepSeekClient(
        api_key=key,
        ledger=ledger,
        base_url=_as_str(model.get("base_url")),
        model=_as_str(model.get("model")),
        timeout_seconds=_as_int(model.get("request_timeout_seconds"), 600),
        connect_timeout_seconds=_as_int(model.get("connect_timeout_seconds"), 20),
        search_timeout_seconds=_as_int(model.get("search_timeout_seconds"), 60),
        fetch_timeout_seconds=_as_int(model.get("fetch_timeout_seconds"), 60),
        max_retries=_as_int(model.get("max_retries"), 2),
        retry_wait_seconds=_as_float_list(model.get("retry_wait_seconds")),
    )
    return study, model, client, ledger, report


def command_flash_capability(args: argparse.Namespace) -> int:
    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("overnight-flash capability")
    from .capability import run_capability_check

    study, _model, client, ledger, report = _flash_client(args)
    if report.warnings:
        print("credential warnings: " + "; ".join(report.warnings))
    run_dir = Path(str(study["paths"]["capability_dir"]))
    payload = run_capability_check(client, run_dir=run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"ledger: {json.dumps(ledger.snapshot(), ensure_ascii=False)}")
    return 0 if payload["all_required_ok"] else 1


def command_flash_diagnose(args: argparse.Namespace) -> int:
    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("overnight-flash diagnose")
    from .diagnostic import run_case_diagnostics, run_explanation_regression

    study, _model, client, ledger, report = _flash_client(args)
    root = Path(str(study["paths"]["diagnostic_dir"]))
    ensure_dir(root)
    if report.warnings:
        print("credential warnings: " + "; ".join(report.warnings))
    summary: dict[str, object] = {"run_id": study["run_id"]}
    try:
        summary["regression"] = run_explanation_regression(client, run_dir=root / "regression")
    except Exception as error:  # noqa: BLE001 - diagnostic boundary
        summary["regression_error"] = f"{type(error).__name__}: {error}"
    try:
        summary["cases"] = run_case_diagnostics(
            client,
            ledger=ledger,
            source_specs_path=Path("archive/experiments/synthetic_20261019/data/private/case_specs.json"),
            run_dir=root / "cases",
            deadline=str(study["deadline"]),
        )
    except Exception as error:  # noqa: BLE001 - diagnostic boundary
        summary["cases_error"] = f"{type(error).__name__}: {error}"
    atomic_write_json(root / "diagnose_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"ledger: {json.dumps(ledger.snapshot(), ensure_ascii=False)}")
    return 0


def command_flash_research(args: argparse.Namespace) -> int:
    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("overnight-flash research")
    from .research import ResearchConfig, ResearchRunner

    study, _model, client, ledger, report = _flash_client(args)
    paths = study["paths"]
    research = study["research"]
    research_dir = Path(str(paths["research_dir"])) / str(getattr(args, "name", "literature_v1"))
    capability_path = Path(str(paths["capability_dir"])) / "capability.json"
    if not bool(getattr(args, "allow_incomplete_capability", False)):
        if not capability_path.exists():
            print("capability check has not run; run `overnight-flash capability` first")
            return 2
        capability = json.loads(capability_path.read_text(encoding="utf-8"))
        if not capability.get("all_required_ok"):
            print("capability check did not pass; refusing to start paid research without a real tool route")
            print(json.dumps(capability.get("checks", []), ensure_ascii=False, indent=2))
            return 2
    question = str(research["main_question"]) + "\n\nExtension choice: " + str(research["secondary_extension"])
    config = ResearchConfig(
        run_id=f"{study['run_id']}_{getattr(args, 'name', 'research')}",
        run_dir=str(research_dir),
        question=question,
        deadline=str(study["deadline"]),
        stop_new_at=str(study["stop_new_research_at"]),
        max_model_calls=int(getattr(args, "max_model_calls", 48)),
        max_tool_calls=int(getattr(args, "max_tool_calls", 60)),
    )
    if report.warnings:
        print("credential warnings: " + "; ".join(report.warnings))
    runner = ResearchRunner(config, client=client, ledger=ledger)
    summary = runner.run()
    print(summary.model_dump_json(indent=2))
    print(f"ledger: {json.dumps(ledger.snapshot(), ensure_ascii=False)}")
    return 0 if summary.accepted else 1


def command_flash_status(args: argparse.Namespace) -> int:
    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        paths = study["paths"]
        ledger_path = Path(str(paths["budget_ledger"]))
        payload: dict[str, object] = {
            "run_id": study["run_id"],
            "archived": True,
            "started_at": study["started_at"],
            "deadline": study["deadline"],
            "ledger": json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {},
            "paths": paths,
            "subruns": _scan_subruns(Path(str(paths["run_root"]))),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    study, _model, client, ledger, report = _flash_client(args)
    paths = study["paths"]
    payload: dict[str, object] = {
        "run_id": study["run_id"],
        "started_at": study["started_at"],
        "deadline": study["deadline"],
        "stop_new_at": study["stop_new_research_at"],
        "credential": report.public_dict(),
        "ledger": ledger.snapshot(),
        "paths": paths,
    }
    for name, key in (("capability", "capability_dir"), ("diagnostics", "diagnostic_dir"), ("research", "research_dir")):
        root = Path(str(paths[key]))
        state = root / "state.json"
        if state.exists():
            try:
                payload[f"{name}_state"] = json.loads(state.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload[f"{name}_state"] = {"error": "unreadable state.json"}
        heartbeat = root / "heartbeat.json"
        if heartbeat.exists():
            payload[f"{name}_heartbeat"] = json.loads(heartbeat.read_text(encoding="utf-8"))
        final = root / "final.json"
        if final.exists():
            payload[f"{name}_final"] = str(final)
    payload["subruns"] = _scan_subruns(Path(str(paths["run_root"])))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def command_flash_report(args: argparse.Namespace) -> int:
    from .flash_report import render_flash_reports

    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        print(f"archived read-only report directory: {study.get('paths', {}).get('reports_dir', '')}")
        print("No report was rewritten. Use archive/README.md or the unified study report.")
        return 0
    study, _model, _client, _ledger, _report = _flash_client(args)
    paths = render_flash_reports(
        Path(str(study["paths"]["reports_dir"])),
        run_id=str(study["run_id"]),
        study_config_path=Path(args.config),
    )
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    return 0


def command_check_dataset(args: argparse.Namespace) -> int:
    from .dataset_io import check_feature_table, write_artificial_fixture

    target = Path(args.path)
    if args.write_fixture:
        write_artificial_fixture(target)
    summary = check_feature_table(target, split_seed=int(args.split_seed))
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if all(not audit.get("invalid_reason") for audit in summary["audits"].values()) else 1


def _scan_subruns(root: Path) -> list[dict[str, object]]:
    """Collect nested research/study state without overwriting anything."""

    found: list[dict[str, object]] = []
    if not root.exists():
        return found
    for state_path in sorted(root.rglob("state.json")):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {"error": "unreadable"}
        manifest_path = state_path.parent / "run_manifest.json"
        manifest: dict[str, object] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {"error": "unreadable"}
        found.append(
            {
                "path": str(state_path.parent),
                "phase": state.get("phase", ""),
                "accepted": state.get("accepted", False),
                "acceptance": state.get("acceptance", ""),
                "stop_reason": state.get("stop_reason", ""),
                "model_calls": state.get("model_calls", 0),
                "run_id": state.get("run_id", ""),
                "model": (manifest.get("model") or {}).get("model_name", "") if isinstance(manifest, dict) else "",
                "rule_version": (manifest.get("rule") or {}).get("version", "") if isinstance(manifest, dict) else "",
            }
        )
    return found


def command_emotion_run(args: argparse.Namespace) -> int:
    from .emotion_experiment import load_study, run_study

    study = load_study(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("emotion-study run")
    print(json.dumps({"study_id": study["study_id"], "phase": "starting"}, ensure_ascii=False))
    result = run_study(Path(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("phase") == "completed" else 1


def command_emotion_evaluate(args: argparse.Namespace) -> int:
    from .emotion_experiment import evaluate_study

    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("emotion-study evaluate")
    summary = evaluate_study(Path(args.config))
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def command_emotion_retry(args: argparse.Namespace) -> int:
    from .emotion_experiment import retry_failed_runs

    study = _read_json(Path(args.config))
    if bool(study.get("archive")):
        return _archive_hint("emotion-study retry-failed")
    result = retry_failed_runs(Path(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def command_emotion_status(args: argparse.Namespace) -> int:
    from .emotion_experiment import load_study, make_ledger
    from .backends import load_registry

    study = load_study(Path(args.config))
    registry = load_registry(Path("configs/models/backends_20261021.json"))
    ledger = make_ledger(study, registry)
    root = Path(str(study["paths"]["run_root"]))
    state_path = root / "study_state.json"
    payload: dict[str, object] = {
        "study_id": study["study_id"],
        "run_root": str(root),
        "study_state": json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None,
        "subruns": _scan_subruns(root / "runs"),
        "ledger": ledger.snapshot(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eeg-scientist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--config", default="archive/experiments/synthetic_20261019/configs/overnight.json")
    preflight.set_defaults(func=command_preflight)

    episode = subparsers.add_parser("episode")
    episode.add_argument("--config", default="archive/experiments/synthetic_20261019/configs/dev_episode.json")
    episode.set_defaults(func=command_episode)

    overnight = subparsers.add_parser("overnight")
    overnight.add_argument("--config", default="archive/experiments/synthetic_20261019/configs/overnight.json")
    overnight.set_defaults(func=command_overnight)

    resume = subparsers.add_parser("resume")
    resume.add_argument("--config", default="archive/experiments/synthetic_20261019/configs/overnight.json")
    resume.set_defaults(func=command_resume)

    report = subparsers.add_parser("report")
    report.add_argument("--study", required=True)
    report.set_defaults(func=command_report)

    calibrate = subparsers.add_parser("calibrate")
    calibrate.set_defaults(func=command_calibrate)

    flash = subparsers.add_parser("overnight-flash", help="DeepSeek Flash overnight research commands")
    flash_sub = flash.add_subparsers(dest="flash_command", required=True)
    for name, function in (
        ("capability", command_flash_capability),
        ("diagnose", command_flash_diagnose),
        ("status", command_flash_status),
        ("report", command_flash_report),
    ):
        sub = flash_sub.add_parser(name)
        sub.add_argument("--config", default=FLASH_CONFIG)
        sub.set_defaults(func=function)
    research = flash_sub.add_parser("research")
    research.add_argument("--config", default=FLASH_CONFIG)
    research.add_argument("--name", default="literature_v1")
    research.add_argument("--max-model-calls", type=int, default=48)
    research.add_argument("--max-tool-calls", type=int, default=60)
    research.add_argument("--allow-incomplete-capability", action="store_true")
    research.set_defaults(func=command_flash_research)

    check_dataset = subparsers.add_parser("check-dataset")
    check_dataset.add_argument("--path", required=True)
    check_dataset.add_argument("--split-seed", type=int, default=20261020)
    check_dataset.add_argument("--write-fixture", action="store_true")
    check_dataset.set_defaults(func=command_check_dataset)

    emotion = subparsers.add_parser("emotion-study", help="Controlled emotion state-vs-trait study")
    emotion_sub = emotion.add_subparsers(dest="emotion_command", required=True)
    emotion_config = "archive/experiments/emotion_20261021/configs/study.json"
    for name, function in (
        ("run", command_emotion_run),
        ("evaluate", command_emotion_evaluate),
        ("retry-failed", command_emotion_retry),
        ("status", command_emotion_status),
    ):
        sub = emotion_sub.add_parser(name)
        sub.add_argument("--config", default=emotion_config)
        sub.set_defaults(func=function)

    from .study_cli import add_commands as add_study_commands

    add_study_commands(subparsers)

    args = parser.parse_args(argv)
    return int(args.func(args))



if __name__ == "__main__":
    raise SystemExit(main())
