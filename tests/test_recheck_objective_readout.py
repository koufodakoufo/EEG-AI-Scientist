import csv

import numpy as np
import pytest

from eegfm.eeg.recheck_objective_readout import ARMS, READOUTS, recheck


def build_seed(directory, issue=None):
    train_values = np.array([-1.0, -1.0, 1.0, 1.0])
    test_values = np.array([-1.0, 1.0, 1.0])
    people, windows = np.array(["p1", "p1", "p2"]), np.array([3, 7, 3])
    spectral_rows, condition_rows = [], []
    for a, arm in enumerate(ARMS, start=1):
        train = np.zeros((4, 3, 200))
        test = np.zeros((3, 3, 200))
        y_train = np.column_stack([17 + train_values * 2, 3 - train_values, (1 + train_values) / 2])
        y_test = np.column_stack([17 + test_values * 2, 3 - test_values, (1 + test_values) / 2])
        for j, target in enumerate(READOUTS):
            # Only one feature varies during fitting; training-only centering,
            # scaling and ridge shrinkage therefore admit a scalar solution.
            train[:, j, j] = 13 + (j + 1) * train_values
            test_offset = 2 * a + j
            test[:, j, j] = 13 + (j + 1) * (test_values + test_offset)
            test[:, j, -1] = 990.0  # Unseen variation on a constant training feature.
            slope = (2.0, -1.0, 0.5)[j]
            expected = y_train[:, j].mean() + slope * (test_values + test_offset) * (4 / 104)
            for i, value in enumerate(expected):
                row = [people[i], int(windows[i]), arm]
                if target != "condition":
                    row.append(target)
                if issue == "corrupt_prediction" and arm == "recon" and target == "central_beta":
                    value += 0.001
                row.extend([y_test[i, j], value])
                (condition_rows if target == "condition" else spectral_rows).append(row)
        (directory / arm).mkdir()
        test_windows = windows.copy()
        if issue == "duplicate_window" and arm == "spectral":
            test_windows[1] = test_windows[0]
        np.savez(directory / arm / "readout_inputs.npz", x_train=train, y_train=y_train,
                 x_test=test, y_test=y_test, window_test=test_windows, subject_test=people)
    for filename, columns, rows in [
        ("predictions.csv", ["target"], spectral_rows), ("condition_predictions.csv", [], condition_rows),
    ]:
        with (directory / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["subject", "window", "arm", *columns, "truth", "prediction"])
            writer.writerows(reversed(rows))


def test_readout_refit_matches_analytic_shrinkage_despite_shuffled_csv(tmp_path):
    build_seed(tmp_path)
    result = recheck(tmp_path)
    for arm in ARMS:
        assert result["arms"][arm]["test_windows"] == 3
        assert max(result["arms"][arm]["max_abs_prediction_error"].values()) < 1e-12


@pytest.mark.parametrize(("issue", "message"), [
    ("corrupt_prediction", "readout predictions differ"),
    ("duplicate_window", "feature windows differ"),
])
def test_readout_refit_rejects_misbound_data(tmp_path, issue, message):
    build_seed(tmp_path, issue=issue)
    with pytest.raises(ValueError, match=message):
        recheck(tmp_path)
