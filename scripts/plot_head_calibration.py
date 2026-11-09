"""Plot the published aggregate surrogate-head calibration (no participant data)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot(summary_path: Path, output_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    figure, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    methods = ("probe_direction", "leace")
    seeds = (2301, 2302, 2303)
    for axis, head, color in zip(axes, summary["heads"], ("#237D80", "#84569B"), strict=True):
        metrics = head["folds"][0]
        values = [metrics[name]["logit_absolute_change"] for name in methods]
        axis.bar([0, 1], values, width=0.52, color=color, label="Target intervention")
        for position, method in enumerate(methods):
            controls = [metrics[f"{method}_random{seed}"]["logit_absolute_change"] for seed in seeds]
            axis.scatter([position - 0.07, position, position + 0.07], controls,
                         color="#333333", s=25, zorder=3,
                         label="3 matched random controls" if position == 0 else None)
            label = "~0" if values[position] < 1e-10 else f"{values[position]:.3f}"
            offset = 0.05 if values[position] < 1e-10 else 0.025
            axis.text(position, values[position] + offset, label, ha="center", fontsize=10)
        axis.set_title(head["label"], fontsize=12)
        axis.set_xticks([0, 1], ["Probe projection", "LEACE"])
        axis.set_ylim(0, 0.94)
        axis.set_axisbelow(True)
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Mean absolute score change")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=2, frameon=False,
                  bbox_to_anchor=(0.5, 0.99))
    figure.text(0.5, 0.015,
                "Engineered heads; anchor fold; 6 validation participants. Dots are fixed controls, not confidence intervals.",
                ha="center", fontsize=8.5, color="#444444")
    figure.tight_layout(rect=(0, 0.07, 1, 0.89))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, facecolor="white")
    plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    plot(arguments.summary, arguments.output)
