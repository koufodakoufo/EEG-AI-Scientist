"""Frozen synthetic evaluator mimicking an EEG FM LODO evaluation.

Each dataset (shard) has a hidden optimum; balanced accuracy over 6 subject
splits depends smoothly on the method configuration, with per-split noise.
Validation and test use different noise. --phase test reads the val output
(as a real evaluator would load val-selected checkpoints) and never retrains.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import yaml

OPTIMA = {  # dataset: (best lr_log10, best temperature, best warmup, chance %, gain %)
    "dsA": (-4.6, 0.07, 4, 33.3, 25.0),
    "dsB": (-4.9, 0.12, 2, 25.0, 18.0),
    "dsC": (-4.4, 0.05, 5, 50.0, 12.0),
}


def noise(*parts):
    digest = hashlib.sha256(json.dumps(parts).encode()).digest()
    return (int.from_bytes(digest[:4], "big") / 2 ** 32 - 0.5) * 2


def bacc(cfg, shard, split, phase):
    lr, temp, warm, chance, gain = OPTIMA[shard]
    if cfg["posttrain_lr_log10"] > -3.8:
        raise RuntimeError(f"post-training diverged on {shard}: loss became NaN at epoch 7 (lr too high)")
    distance = ((cfg["posttrain_lr_log10"] - lr) / 0.5) ** 2 + ((math.log(cfg["temperature"] / temp)) / 0.7) ** 2 \
        + ((cfg["warmup_epochs"] - warm) / 4) ** 2
    return chance + gain * math.exp(-distance) + 1.5 * noise(cfg, shard, split, phase)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["val", "test"], required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--from", dest="from_dir")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.phase == "test":
        selected = json.loads((Path(args.from_dir) / "selected.json").read_text())
        cfg = selected["config"]
    else:
        cfg = yaml.safe_load(Path("method.yaml").read_text())
    time.sleep(2)  # stands in for hours of GPU training
    folds = [bacc(cfg, args.target, split, args.phase) for split in range(42, 48)]
    metrics = {"ft_bacc": sum(folds) / len(folds), "ft_bacc_folds": folds, "config": cfg}
    if args.phase == "val":
        (out / "selected.json").write_text(json.dumps({"config": cfg}))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({"target": args.target, "phase": args.phase, "ft_bacc": metrics["ft_bacc"]}))


if __name__ == "__main__":
    main()
