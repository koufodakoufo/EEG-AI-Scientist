"""Immutable per-fold process; independent head RNG, no DDP negative expansion."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from artifact_io import read_json, verify_source_snapshot


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["validation", "final_test"], required=True)
    for name in ("target", "directory", "artifacts", "device"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--fold", type=int, required=True)
    p.add_argument("--deadline", type=float, required=True)
    p.add_argument("--encoder-checkpoint")
    p.add_argument("--feature-path")
    args = p.parse_args()
    from downstream import final_test_unit, train_validation_unit
    from release_io import Release
    from gpu_diagnostics import require_cuda
    require_cuda(args.device)
    root = Path(__file__).resolve().parent
    verify_source_snapshot(root)
    fold = read_json(root / "split_manifest.json")["targets"][args.target]["folds"][args.fold]
    release = Release.open(args.target)
    release.preload_signals(Path(args.artifacts), deadline=args.deadline)
    directory = Path(args.directory)
    if args.phase == "validation":
        condition = read_json(directory / "identity.json")
        for mode in ("lp", "ft"):
            train_validation_unit(release, fold, mode, directory / f"{mode}/fold{args.fold}", condition_identity=condition,
                                  encoder_checkpoint=args.encoder_checkpoint, feature_path=args.feature_path,
                                  device=args.device, deadline=args.deadline)
    else:
        plan = read_json(directory / "test_plan.json")
        from evaluation_contract import final_conditions, locked_round_limit
        from broker_contract import deployment_contract
        limit = locked_round_limit(plan["method_lock"], expected=deployment_contract()["round_limit"])
        if set(plan["conditions"]) != set(final_conditions(limit)):
            raise ValueError("Final condition set differs from the frozen round limit")
        for condition in final_conditions(limit):
            for mode in ("lp", "ft"):
                final_test_unit(release, fold, mode, Path(plan["conditions"][condition]) / f"{mode}/fold{args.fold}",
                                directory / f"{condition}/{mode}/fold{args.fold}", method_lock=plan["method_lock"],
                                device=args.device, deadline=args.deadline)


if __name__ == "__main__":
    main()
