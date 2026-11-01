"""Read-only intervention precision diagnosis; no model/scorer execution.

By default use synthetic tokens only. Optional NPZ inputs are validation evidence,
candidate fitted centers, and public validation layer tokens. No labels, targets,
logits, sample identifiers, or residual predictions are consumed. Reports go to
stdout; preserve them outside public artifacts if they contain machine paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np

RTOL = 1e-6
ATOL = 1e-8


def summary(values: np.ndarray) -> dict[str, float]:
    """Summarize numerical diagnostics without exporting per-row evidence."""
    return {"min": float(values.min()), "median": float(np.median(values)),
            "max": float(values.max())}


def basis(directions: np.ndarray) -> np.ndarray:
    """Use the frozen check's documented numerical rank convention."""
    u, singular, _ = np.linalg.svd(directions.astype(np.float64), full_matrices=False)
    if not len(singular) or singular[0] <= 1e-14:
        return np.empty((directions.shape[0], 0), dtype=np.float64)
    return u[:, singular > max(singular[0] * 1e-8, 1e-14)]


def intended_shifts(pooled: np.ndarray, center: np.ndarray,
                    directions: np.ndarray, controls: np.ndarray) -> np.ndarray:
    """Independently reconstruct the candidate's stated projection algebra."""
    delta = pooled.astype(np.float64) - center
    learned = (delta @ directions) @ directions.T
    target = np.linalg.norm(learned, axis=1)
    shifts = [learned]
    for control in controls:
        raw = (delta @ control) @ control.T
        length = np.linalg.norm(raw, axis=1)
        shifted = np.zeros_like(raw)
        good = length > 1e-12
        shifted[good] = raw[good] * (target[good] / length[good])[:, None]
        fallback = (~good) & (target > 0)
        shifted[fallback] = target[fallback, None] * control[:, 0]
        shifts.append(shifted)
    return np.asarray(shifts)


def check(shifts: np.ndarray, bases: list[np.ndarray]) -> dict[str, Any]:
    """Reproduce strength/span conditions, without trusted scoring or truth."""
    lengths = np.linalg.norm(shifts, axis=2)
    error = np.abs(lengths[1:] - lengths[0])
    tolerance = ATOL + RTOL * lengths[0]
    span = []
    for delta, direction in zip(shifts, bases):
        residual = np.linalg.norm(delta - (delta @ direction) @ direction.T, axis=1)
        allowed = ATOL + RTOL * np.linalg.norm(delta, axis=1)
        span.append({"fail_count": int(np.sum(residual > allowed)),
                     "residual_l2": summary(residual),
                     "max_tolerance_ratio": float(np.max(residual / allowed))})
    return {"learned_norm": summary(lengths[0]),
            "norm_fail_counts": np.sum(error > tolerance, axis=1).tolist(),
            "norm_failed_windows": int(np.any(error > tolerance, axis=0).sum()),
            "norm_error": summary(error),
            "norm_relative_error": summary(error / np.maximum(lengths[0], 1e-300)),
            "norm_max_tolerance_ratio": float(np.max(error / tolerance)),
            "span": span}


def token_experiment(tokens: np.ndarray, shifts: np.ndarray,
                     bases: list[np.ndarray], recorded_original: np.ndarray | None = None,
                     recorded_altered: np.ndarray | None = None) -> dict[str, Any]:
    """Separate token cast error from accumulator precision on identical tokens.

    Keep the intended shifts fixed across all conditions. No learned parameters,
    choices, or task predictions are changed or evaluated by this experiment.
    """
    original32 = tokens.mean(axis=(1, 2)).astype(np.float64)
    original64 = tokens.mean(axis=(1, 2), dtype=np.float64)
    pooled32, pooled64, unrounded = [], [], []
    cast_bounds, cast_errors = [], []
    for shift in shifts:
        modified64 = tokens.astype(np.float64) - shift[:, None, None, :]
        modified32 = modified64.astype(np.float32)
        pooled32.append(modified32.mean(axis=(1, 2)).astype(np.float64))
        pooled64.append(modified32.mean(axis=(1, 2), dtype=np.float64))
        unrounded.append(modified64.mean(axis=(1, 2)))
        cast_error = modified32.astype(np.float64) - modified64
        cast_errors.append(np.linalg.norm(cast_error.mean(axis=(1, 2)), axis=1))
        cast_bounds.append(np.linalg.norm(np.abs(cast_error).mean(axis=(1, 2)), axis=1))
    pooled32, pooled64, unrounded = map(np.asarray, (pooled32, pooled64, unrounded))
    actual32 = original32[None] - pooled32
    actual64 = original64[None] - pooled64
    accumulation = (original32 - original64)[None] - (pooled32 - pooled64)
    quantization = actual64 - shifts
    out: dict[str, Any] = {
        "token_shape": list(tokens.shape), "token_dtype": str(tokens.dtype),
        "float32_tokens_float32_mean": check(actual32, bases),
        "float32_tokens_float64_mean": check(actual64, bases),
        "float64_tokens_float64_mean": check(original64[None] - unrounded, bases),
        "original_pool_accumulation_error_l2": summary(np.linalg.norm(original32 - original64, axis=1)),
        "shift_accumulation_error_l2": [summary(v) for v in np.linalg.norm(accumulation, axis=2)],
        "shift_token_quantization_error_l2": [summary(v) for v in np.linalg.norm(quantization, axis=2)],
        "mean_token_cast_error_l2": [summary(v) for v in cast_errors],
        "absolute_cast_error_envelope_l2": [summary(v) for v in cast_bounds],
        "error_decomposition_max_abs": float(np.max(np.abs(actual32 - shifts - accumulation - quantization))),
    }
    if recorded_original is not None and recorded_altered is not None:
        out["recorded_original_replay_max_abs"] = float(np.max(np.abs(original32 - recorded_original)))
        out["recorded_altered_replay_max_abs"] = float(np.max(np.abs(pooled32 - recorded_altered)))
    return out


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnose(evidence: Path, fitted: Path, token_path: Path | None) -> dict[str, Any]:
    files = [evidence, fitted] + ([token_path] if token_path is not None else [])
    hashes = {str(path): sha256(path) for path in files}
    with np.load(evidence, allow_pickle=False) as source:
        arrays = {key: source[key] for key in ("selected_groups", "selected_layers", "directions",
                  "control_directions", "original_pooled", "altered_pooled")}
    with np.load(fitted, allow_pickle=False) as source:
        centers = source["centers"]
    tokens: dict[int, np.ndarray] = {}
    if token_path is not None:
        with np.load(token_path, allow_pickle=False) as source:
            tokens = {int(layer): source[f"layer_{int(layer)}"] for layer in set(arrays["selected_layers"])}
    slots = []
    for index, layer in enumerate(arrays["selected_layers"]):
        original, altered = arrays["original_pooled"][index], arrays["altered_pooled"][index]
        learned, controls = arrays["directions"][index], arrays["control_directions"][index]
        bases = [basis(directions) for directions in (learned, *controls)]
        projectors = [direction @ direction.T for direction in bases]
        projector_pairs = [(left, right) for i, left in enumerate(projectors) for right in projectors[i + 1:]]
        ideal = intended_shifts(original, centers[index], learned, controls)
        actual = original[None] - altered
        slot: dict[str, Any] = {
            "group": int(arrays["selected_groups"][index]), "layer": int(layer), "n": len(original),
            "ranks": [direction.shape[1] for direction in bases],
            "distinct_spans": all(not np.allclose(left, right, rtol=RTOL, atol=ATOL)
                                  for left, right in projector_pairs),
            "minimum_pairwise_projector_frobenius": min(float(np.linalg.norm(left - right))
                                                        for left, right in projector_pairs),
            "original_norm": summary(np.linalg.norm(original, axis=1)),
            "actual": check(actual, bases), "intended": check(ideal, bases),
            "actual_minus_intended_l2": [summary(v) for v in np.linalg.norm(actual - ideal, axis=2)],
            "pooled_float32_roundtrip_max_error": float(np.max(np.abs(original - original.astype(np.float32).astype(np.float64)))),
            "altered_float32_roundtrip_max_error": float(np.max(np.abs(altered - altered.astype(np.float32).astype(np.float64)))),
        }
        if tokens:
            slot["token_experiment"] = token_experiment(tokens[int(layer)], ideal, bases, original, altered)
        slots.append(slot)
    unchanged = all(sha256(path) == hashes[str(path)] for path in files)
    if not unchanged:
        raise RuntimeError("An input changed during diagnosis")
    return {"input_sha256": hashes, "inputs_unchanged": unchanged, "slots": slots}


def synthetic(seed: int = 20261030) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    common = rng.normal(0, .035, size=(1, 1, 1, 200))
    window = rng.normal(0, .004, size=(144, 1, 1, 200))
    tokens = (common + window + rng.normal(0, .15, size=(144, 20, 5, 200))).astype(np.float32)
    directions = [np.linalg.qr(rng.normal(size=(200, 6)))[0] for _ in range(4)]
    pooled = tokens.mean(axis=(1, 2)).astype(np.float64)
    shifts = intended_shifts(pooled, pooled.mean(axis=0), directions[0], np.asarray(directions[1:]))
    return {"seed": seed, "intended": check(shifts, directions),
            "token_experiment": token_experiment(tokens, shifts, directions)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--fitted", type=Path)
    parser.add_argument("--tokens", type=Path, help="Public validation NPZ, selected layer arrays only")
    args = parser.parse_args()
    if (args.evidence is None) != (args.fitted is None) or (args.tokens is not None and args.evidence is None):
        parser.error("--evidence and --fitted must be paired; --tokens requires both")
    output: dict[str, Any] = {"python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
                             "rtol": RTOL, "atol": ATOL, "synthetic": synthetic()}
    if args.evidence is not None:
        output["validation"] = diagnose(args.evidence, args.fitted, args.tokens)
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
