"""Recompute exploratory baseline summaries from private saved predictions.

Does not fit models, access Actor state, or repeat the extension test phase.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def balanced(y: np.ndarray, logits: np.ndarray) -> float:
    return float(sum(np.mean((logits[y == value] >= 0) == value) for value in (0, 1)) / 2)


def r2(y: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    return 1 - np.square(y - prediction).sum(0) / np.square(y - y.mean(0)).sum(0)


def verify(output: Path, reference: Path, prepared: Path) -> dict[str, Any]:
    result = read_json(output / "RESULT.json")
    protocol = read_json(output / "PROTOCOL.json")
    lock = read_json(output / "EXTENSION_LOCK.json")
    reservation = read_json(output / "TEST_RESERVATION.json")
    fits = read_json(output / "FROZEN_FITS.json")
    for record in lock["files"]:
        assert digest(Path(record["path"])) == record["sha256"], record["path"]
    assert protocol["registered_at"] < lock["at"] < reservation["at"] < result["at"]
    assert result["provenance"]["protocol_sha256"] == digest(output / "PROTOCOL.json")
    assert result["provenance"]["lock_sha256"] == digest(output / "EXTENSION_LOCK.json")
    assert reservation["extension_lock_sha256"] == digest(output / "EXTENSION_LOCK.json")
    assert result["provenance"]["test_input_sha256"] == digest(prepared / "test.npz")
    assert result["provenance"]["private_arrays_sha256"] == digest(output / "TEST_ARRAYS_PRIVATE.npz")
    arrays = dict(np.load(output / "TEST_ARRAYS_PRIVATE.npz", allow_pickle=False))
    original = dict(np.load(reference / "test-representations.npz", allow_pickle=False))
    assert np.array_equal(arrays["sample_ids"], original["sample_ids"])
    assert len(np.unique(arrays["sample_ids"])) == len(arrays["sample_ids"])
    names = protocol["methods"]
    seeds = protocol["random_seeds"]
    state_digests = []
    for seed in seeds:
        receipts = [read_json(output / f"random-{seed}-{split}.json") for split in ("train", "validation", "test")]
        assert len({r["state_sha256"] for r in receipts}) == 1
        state_digests.append(receipts[0]["state_sha256"])
    assert len(set(state_digests)) == len(seeds)
    rng = np.random.default_rng(protocol["uncertainty"]["seed"])
    unique = np.unique(arrays["subject_ids"])
    blocks = [np.flatnonzero(arrays["subject_ids"] == subject) for subject in unique]
    samples = [np.concatenate([blocks[i] for i in draw]) for draw in rng.integers(0, len(blocks), size=(2000, len(blocks)))]
    bootstrap = {}
    worst_logit_error = 0.0
    for name in names:
        if name == "transparent62":
            x = original["features"]
        elif name == "pretrained200":
            x = original["embedding"]
        else:
            seed = int(name.split("_s")[1])
            with np.load(output / f"random-{seed}-test.npz", allow_pickle=False) as data:
                assert np.array_equal(data["sample_ids"], arrays["sample_ids"])
                x = data["embedding"]
        fit = fits["heads"][name]
        recomputed = ((x.astype(float) - np.array(fit["x_mean"])) / np.array(fit["x_scale"])) @ np.array(fit["coefficient"]) + fit["intercept"]
        saved = arrays[f"logits_{name}"]
        worst_logit_error = max(worst_logit_error, float(np.max(np.abs(recomputed - saved))))
        np.testing.assert_allclose(recomputed, saved, atol=1e-12, rtol=0)
        np.testing.assert_allclose(balanced(arrays["y"], saved), result["classification"][name]["balanced_accuracy"], atol=1e-12)
        np.testing.assert_allclose(roc_auc_score(arrays["y"], saved), result["classification"][name]["auroc"], atol=1e-12)
        bootstrap[name] = np.array([balanced(arrays["y"][row], saved[row]) for row in samples])
        np.testing.assert_allclose(np.quantile(bootstrap[name], [.025, .975]), result["classification"][name]["balanced_accuracy_ci95"], atol=1e-12)
    bootstrap["random_seed_mean"] = np.mean([bootstrap[name] for name in names[2:]], axis=0)
    for record in result["classification_differences"]:
        left, right = record["comparison"].split("-minus-")
        np.testing.assert_allclose(np.quantile(bootstrap[left] - bootstrap[right], [.025, .975]), record["paired_subject_ci95"], atol=1e-12)
        tail = .05 / 3 / 2
        np.testing.assert_allclose(np.quantile(bootstrap[left] - bootstrap[right], [tail, 1 - tail]), record["paired_subject_family_adjusted_ci"], atol=1e-12)
    worst_r2_error = 0.0
    for index, (fit, record) in enumerate(zip(fits["q1"], result["q1"], strict=True)):
        target = original["features"][:, fit["columns"]].astype(float)
        active = np.array(fit["fit"]["active_columns"], dtype=bool)
        recomputed = float(np.mean(r2(target, arrays[f"q1_prediction_{index}"])[active]))
        worst_r2_error = max(worst_r2_error, abs(recomputed - record["r2"]))
        np.testing.assert_allclose(recomputed, record["r2"], atol=1e-12)
    # Direct row-resampling check of two Q1 intervals, including the strong
    # negative Hjorth activity case. No sufficient-statistics helper is reused.
    for selected in (result["q1_pretrained_minus_random"][0], result["q1_pretrained_minus_random"][-1]):
        curve = []
        indices = [i for i, item in enumerate(fits["q1"]) if item["layer"] == selected["layer"] and item["feature"] == selected["feature"]]
        for i in indices:
            item = fits["q1"][i]
            target = original["features"][:, item["columns"]].astype(float)
            prediction = arrays[f"q1_prediction_{i}"]
            active = np.array(item["fit"]["active_columns"], dtype=bool)
            curve.append(np.array([np.mean(r2(target[row], prediction[row])[active]) for row in samples]))
        delta = curve[0] - np.mean(curve[1:], axis=0)
        np.testing.assert_allclose(np.quantile(delta, [.025, .975]), selected["paired_subject_ci95"], atol=1e-8)
        tail = .05 / 24 / 2
        np.testing.assert_allclose(np.quantile(delta, [tail, 1 - tail]), selected["paired_subject_family_adjusted_ci"], atol=1e-8)
    previous = read_json(reference / "FROZEN_HEAD.json")
    np.testing.assert_allclose(previous["coefficient"], fits["heads"]["pretrained200"]["coefficient"], atol=1e-10, rtol=0)
    np.testing.assert_allclose(previous["intercept"], fits["heads"]["pretrained200"]["intercept"], atol=1e-10, rtol=0)
    return {"status": "passed", "locked_files_checked": len(lock["files"]), "classification_heads": len(names),
        "q1_point_estimates": len(fits["q1"]), "q1_intervals_direct_spot_checks": 2,
        "maximum_logit_reconstruction_error": worst_logit_error, "maximum_r2_recomputation_error": worst_r2_error,
        "original_pretrained_head_reproduced": True, "random_states_distinct_and_same_across_splits": True,
        "timestamp_order_verified": True, "full_backbone_independent_reexecution": False,
        "result_sha256": digest(output / "RESULT.json"), "verifier_sha256": digest(Path(__file__))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = verify(args.output, args.reference, args.prepared)
    if args.receipt:
        with args.receipt.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
