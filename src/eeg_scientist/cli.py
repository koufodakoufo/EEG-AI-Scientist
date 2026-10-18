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
from .storage import ensure_dir, sha256_text, utc_now


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    deadline = _deadline(config.deadline)
    reports_dir = ensure_dir(Path(config.reports_dir))
    health = getattr(provider, "health", lambda: {"ok": False, "error": "no health method"})()
    describe = getattr(provider, "describe", lambda: {})()
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
    config = EpisodeConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_episode(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.status == "completed" else 1


def command_overnight(args: argparse.Namespace) -> int:
    from .study import run_study

    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_study(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.pairs_completed > 0 else 1


def command_resume(args: argparse.Namespace) -> int:
    from .study import run_study

    config = StudyConfig.model_validate(_read_json(Path(args.config)))
    provider = provider_from_config(dict(config.provider))
    summary = run_study(config, provider)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.pairs_completed > 0 else 1


def command_report(args: argparse.Namespace) -> int:
    from .reporting import render_reports

    paths = render_reports(Path(args.study))
    print(paths.model_dump_json(indent=2))
    return 0


def command_calibrate(args: argparse.Namespace) -> int:
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
    output = Path("reports/CALIBRATION.md")
    ensure_dir(output.parent)
    output.write_text("\n".join(rows + [""] + details), encoding="utf-8")
    print(f"wrote {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eeg-scientist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--config", default="configs/overnight.json")
    preflight.set_defaults(func=command_preflight)

    episode = subparsers.add_parser("episode")
    episode.add_argument("--config", default="configs/dev_episode.json")
    episode.set_defaults(func=command_episode)

    overnight = subparsers.add_parser("overnight")
    overnight.add_argument("--config", default="configs/overnight.json")
    overnight.set_defaults(func=command_overnight)

    resume = subparsers.add_parser("resume")
    resume.add_argument("--config", default="configs/overnight.json")
    resume.set_defaults(func=command_resume)

    report = subparsers.add_parser("report")
    report.add_argument("--study", required=True)
    report.set_defaults(func=command_report)

    calibrate = subparsers.add_parser("calibrate")
    calibrate.set_defaults(func=command_calibrate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
