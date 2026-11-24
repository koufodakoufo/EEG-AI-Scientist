import csv
from pathlib import Path

import pytest

from eegfm.eeg.verify_objective_pilot import ARMS, TARGETS, verify


def write_table(path: Path, header: list[str], rows: list[list]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def fixtures(folder: Path, issue: str = "") -> tuple[Path, Path, Path]:
    regressions, conditions, windows = [], [], []
    for person in ("A", "B"):
        for win in range(2):
            windows.append([person, win])
            if issue == "lost_complete_window" and person == "A" and win == 1:
                continue
            for j, arm in enumerate(ARMS):
                for target in TARGETS:
                    truth = win * 2 - 1
                    regressions.append([person, win, arm, target, truth, (0, -truth, truth)[j]])
                # Exactly .5 is the positive category.
                conditions.append([person, win, arm, win, (0.5, 1 - win, win)[j]])
    if issue == "duplicate":
        regressions.append(regressions[-1])
    elif issue == "lost_arm":
        regressions.pop()
    elif issue == "different_truth":
        regressions[-1][-2] = 2
    elif issue == "nonfinite":
        regressions[0][-1] = "NaN"
    elif issue == "condition_missing_window":
        del conditions[-3:]
    files = (
        write_table(folder / "reg.csv", ["subject", "window", "arm", "target", "truth", "prediction"], regressions),
        write_table(folder / "cond.csv", ["subject", "window", "arm", "truth", "prediction"], conditions),
        write_table(folder / "index.csv", ["subject", "window"], windows),
    )
    return files


def test_pooled_r2_cluster_interval_and_secondary_ba(tmp_path: Path) -> None:
    result = verify(*fixtures(tmp_path))
    scores = result["targets"]["occipital_alpha"]
    assert scores["pooled_r2"]["by_arm"] == {"init": 0, "recon": -3, "spectral": 1}
    assert scores["spectral_minus_recon_percentile_ci95"] == [4, 4]
    assert scores["defined_bootstrap_draws"] == 2000
    assert result["secondary_condition_ba"]["pooled"]["by_arm"] == {"init": 0.5, "recon": 0, "spectral": 1}
    assert result["windows_per_subject"] == {"A": 2, "B": 2}
    assert len(result["input_sha256"]) == 3


def test_resamples_keep_all_windows_of_one_person_together(tmp_path: Path) -> None:
    # Both participants have identical targets; only the useful arm flips.
    # A-only and B-only draws must recover the entire +/-4 range.
    rows = []
    for subject in ("A", "B"):
        for window in range(20):
            truth = 2 * (window % 2) - 1
            recon = truth if subject == "A" else -truth
            for arm, prediction in zip(ARMS, (0, recon, -recon)):
                for target in TARGETS:
                    rows.append([subject, window, arm, target, truth, prediction])
    path = write_table(tmp_path / "heterogeneous.csv",
                       ["subject", "window", "arm", "target", "truth", "prediction"], rows)
    score = verify(path)["targets"]["central_beta"]
    assert score["pooled_r2"]["spectral_minus_recon"] == 0
    assert score["spectral_minus_recon_percentile_ci95"] == [-4, 4]
    assert score["by_subject_r2"]["A"]["spectral_minus_recon"] == -4


@pytest.mark.parametrize(
    ("issue", "message"),
    [("duplicate", "duplicate window"), ("lost_arm", "Incomplete arms"), ("different_truth", "Truth differs"),
     ("nonfinite", "nonfinite"), ("condition_missing_window", "windows differ"),
     ("lost_complete_window", "windows differ")],
)
def test_invalid_pairs_are_rejected(tmp_path: Path, issue: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        verify(*fixtures(tmp_path, issue))
