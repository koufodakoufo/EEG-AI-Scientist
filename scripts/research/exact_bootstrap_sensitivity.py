"""Builder-only post hoc exact empirical participant-bootstrap sensitivity.

Reads saved predictions and frozen active-column masks only. Does not load a
model, fit a probe, invoke a test phase, or modify either original experiment.
Exactness concerns the observed-cohort bootstrap distribution, not population
coverage. All participants' rows remain together in every paired resample.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from math import factorial, prod
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[Any]
SIGN_TOLERANCE = 1e-12


def enumerate_counts(n: int) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """All n-component weak compositions of n, with ordered-draw multiplicity."""
    if not 1 <= n <= 10:
        raise ValueError("Enumeration requires 1..10 participants")
    rows: list[tuple[int, ...]] = []

    def visit(prefix: tuple[int, ...], remaining: int) -> None:
        if len(prefix) == n - 1:
            rows.append((*prefix, remaining))
            return
        for count in range(remaining + 1):
            visit((*prefix, count), remaining - count)

    visit((), n)
    counts = np.asarray(rows, dtype=np.int64)
    weights = np.asarray([factorial(n) // prod(factorial(int(c)) for c in row) for row in counts], dtype=np.int64)
    if int(weights.sum()) != n**n:
        raise AssertionError("Multinomial masses do not sum to the ordered sample space")
    return counts, weights


def weighted_quantile(values: Array, weights: Array, q: Fraction, *, linear: bool = False) -> float | None:
    """Inverse CDF inf{x:F(x)>=q}; integer ranks avoid cumulative rounding.

    The optional linear diagnostic exactly matches NumPy's default quantile
    on the multiplicity-expanded distribution. Undefined values are omitted,
    matching the original interval helper; callers report omitted probability.
    """
    values, weights = np.asarray(values, dtype=float), np.asarray(weights, dtype=np.int64)
    if values.ndim != 1 or values.shape != weights.shape or np.any(weights <= 0) or not 0 <= q <= 1:
        raise ValueError("Invalid weighted empirical quantile")
    finite = np.isfinite(values)
    if not finite.any():
        return None
    order = np.argsort(values[finite], kind="stable")
    ordered = values[finite][order]
    cumulative = np.cumsum(weights[finite][order])
    total = int(cumulative[-1])

    def order_statistic(rank: int) -> float:
        return float(ordered[np.searchsorted(cumulative, rank, side="left")])

    if not linear:
        rank = max(1, (q.numerator * total + q.denominator - 1) // q.denominator)
        return order_statistic(rank)
    position = q * (total - 1)
    lower = position.numerator // position.denominator
    remainder = float(position - lower)
    low = order_statistic(lower + 1)
    high = order_statistic(min(lower + 2, total))
    return low + remainder * (high - low)


def r2_distribution(target: Array, prediction: Array, subjects: Array, counts: Array, active: Array) -> NDArray[np.float64]:
    """Mean columnwise R² on training-active columns after cluster resampling."""
    target, prediction = np.asarray(target, dtype=float), np.asarray(prediction, dtype=float)
    active = np.asarray(active, dtype=bool)
    if target.shape != prediction.shape or target.ndim != 2 or active.shape != (target.shape[1],):
        raise ValueError("Invalid R2 arrays or active-column mask")
    if not np.isfinite(target).all() or not np.isfinite(prediction).all() or not active.any():
        raise ValueError("Nonfinite predictions/targets or no training-active columns")
    blocks = [np.flatnonzero(subjects == s) for s in np.unique(subjects)]
    # Centering before sufficient statistics reduces cancellation while leaving
    # sum((y-y_resample_mean)^2) invariant. No per-participant R² averaging.
    shifted = target - target.mean(axis=0)
    sums = np.asarray([shifted[b].sum(0) for b in blocks])
    squares = np.asarray([np.square(shifted[b]).sum(0) for b in blocks])
    errors = np.asarray([np.square(target[b] - prediction[b]).sum(0) for b in blocks])
    n = counts @ np.asarray([len(b) for b in blocks])
    denominator = counts @ squares - np.square(counts @ sums) / n[:, None]
    ratio = np.full_like(denominator, np.nan)
    np.divide(counts @ errors, denominator, out=ratio, where=denominator > 1e-20)
    columns = (1 - ratio)[:, active]
    valid = np.isfinite(columns).sum(axis=1)
    result = np.full(len(counts), np.nan)
    np.divide(np.nansum(columns, axis=1), valid, out=result, where=valid > 0)
    return result


def ba_distribution(y: Array, logits: Array, subjects: Array, counts: Array) -> NDArray[np.float64]:
    """Row balanced accuracy, preserving class/row weighting within draws."""
    blocks = [np.flatnonzero(subjects == s) for s in np.unique(subjects)]
    recalls: list[NDArray[np.float64]] = []
    for label in (0, 1):
        n = np.asarray([np.count_nonzero(y[b] == label) for b in blocks])
        correct = np.asarray([np.count_nonzero(((logits[b] >= 0) == label) & (y[b] == label)) for b in blocks])
        denominator = counts @ n
        if np.any(denominator == 0):
            raise ValueError("A resample is missing a class; BA policy requires both classes")
        recalls.append((counts @ correct) / denominator)
    return np.mean(recalls, axis=0)


def direct_r2(target: Array, prediction: Array, active: Array, rows: Array) -> float:
    """Independent direct row expansion for verification; no sufficient stats."""
    target, prediction = np.asarray(target[rows], dtype=float), np.asarray(prediction[rows], dtype=float)
    numerator = np.square(target - prediction).sum(axis=0)
    denominator = np.square(target - target.mean(axis=0)).sum(axis=0)
    valid = np.asarray(active, dtype=bool) & (denominator > 1e-20)
    return float(np.mean(1 - numerator[valid] / denominator[valid])) if valid.any() else float("nan")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def interval_sign(bounds: list[float | None]) -> str:
    if bounds[0] is None or bounds[1] is None:
        return "undefined"
    if bounds[0] > SIGN_TOLERANCE:
        return "positive"
    if bounds[1] < -SIGN_TOLERANCE:
        return "negative"
    return "includes_zero"


def generate(reference: Path, baseline: Path, output: Path, report: Path) -> dict[str, Any]:
    if output.exists() or report.exists():
        raise FileExistsError("New sensitivity outputs must not overwrite previous evidence")
    input_paths = [reference / name for name in ("REFERENCE_TEST_ARRAYS.npz", "REFERENCE_TEST_RESULT.json", "REFERENCE_FITS.json")]
    input_paths += [baseline / name for name in ("TEST_ARRAYS_PRIVATE.npz", "RESULT.json", "FROZEN_FITS.json", "PROTOCOL.json")]
    input_hashes = {str(path.resolve()): digest(path) for path in input_paths}
    original, extension = read_json(input_paths[1]), read_json(input_paths[4])
    original_fits, extension_fits = read_json(input_paths[2]), read_json(input_paths[5])
    protocol = read_json(input_paths[6])
    if original["arrays_sha256"] != digest(input_paths[0]) or extension["provenance"]["private_arrays_sha256"] != digest(input_paths[3]):
        raise ValueError("Saved prediction arrays do not match original result provenance")
    with np.load(input_paths[0], allow_pickle=False) as data:
        ref = dict(data)
    with np.load(input_paths[3], allow_pickle=False) as data:
        ext = dict(data)
    for key in ("y", "sample_ids", "subject_ids"):
        np.testing.assert_array_equal(ref[key], ext[key])
    subjects, labels = ref["subject_ids"], ref["y"]
    unique = np.unique(subjects)
    if len(unique) != 6 or len(original["q1"]) != 24 or len(original["q2_q3"]) != 2:
        raise ValueError("This sensitivity is restricted to the existing six-person / 24-Q1 / 2-Q2 study")
    counts, weights = enumerate_counts(len(unique))
    blocks = [np.flatnonzero(subjects == s) for s in unique]
    expanded_rows = [np.concatenate([np.tile(block, int(c)) for block, c in zip(blocks, row, strict=True)]) for row in counts]
    lookup = {tuple(row): i for i, row in enumerate(counts)}
    point_index = lookup[(1,) * len(unique)]
    mc_indices: dict[int, NDArray[np.int64]] = {}
    for seed in (20261029, 20261030):
        draws = np.random.default_rng(seed).integers(0, len(unique), size=(2000, len(unique)))
        mc_indices[seed] = np.asarray([lookup[tuple(np.bincount(draw, minlength=len(unique)))] for draw in draws])
    records: list[dict[str, Any]] = []
    curves: dict[str, NDArray[np.float64]] = {}
    max_direct_error = 0.0
    max_point_error = 0.0
    max_mc_endpoint_error = 0.0
    checks_r2 = 0
    checks_ba = 0

    def r2_curve(target: Array, prediction: Array, active: Array) -> NDArray[np.float64]:
        nonlocal max_direct_error, checks_r2
        result = r2_distribution(target, prediction, subjects, counts, active)
        direct = np.asarray([direct_r2(target, prediction, active, rows) for rows in expanded_rows])
        np.testing.assert_allclose(result, direct, rtol=1e-10, atol=1e-8, equal_nan=True)
        finite = np.isfinite(result) & np.isfinite(direct)
        if finite.any():
            max_direct_error = max(max_direct_error, float(np.max(np.abs(result[finite] - direct[finite]))))
        checks_r2 += len(counts)
        return result

    def ba_curve(logits: Array) -> NDArray[np.float64]:
        nonlocal max_direct_error, checks_ba
        result = ba_distribution(labels, logits, subjects, counts)
        direct = np.asarray([np.mean([np.mean((logits[rows][labels[rows] == c] >= 0) == c) for c in (0, 1)]) for rows in expanded_rows])
        np.testing.assert_allclose(result, direct, atol=1e-13, rtol=0)
        max_direct_error = max(max_direct_error, float(np.max(np.abs(result - direct))))
        checks_ba += len(counts)
        return result

    def add(name: str, family: str, size: int, curve: Array, point: float,
            old95: list[float], old_adjusted: list[float], seed: int,
            metadata: dict[str, Any]) -> None:
        nonlocal max_point_error, max_mc_endpoint_error
        computed = float(curve[point_index])
        max_point_error = max(max_point_error, abs(computed - point))
        np.testing.assert_allclose(computed, point, rtol=1e-10, atol=1e-8)
        curves[name] = curve
        sampled = curve[mc_indices[seed]]
        intervals: dict[str, Any] = {}
        for label, tail, previous in (("pointwise95", Fraction(1, 40), old95), ("family_adjusted", Fraction(1, 40 * size), old_adjusted)):
            quantiles = (tail, 1 - tail)
            bounds = [weighted_quantile(curve, weights, q) for q in quantiles]
            linear = [weighted_quantile(curve, weights, q, linear=True) for q in quantiles]
            mc_finite = sampled[np.isfinite(sampled)]
            mc_linear = np.quantile(mc_finite, [float(q) for q in quantiles]).tolist()
            np.testing.assert_allclose(mc_linear, previous, rtol=1e-10, atol=1e-8)
            max_mc_endpoint_error = max(max_mc_endpoint_error, max(abs(a - b) for a, b in zip(mc_linear, previous, strict=True)))
            mc_inverse = [weighted_quantile(sampled, np.ones(len(sampled), dtype=np.int64), q) for q in quantiles]
            intervals[label] = {"tail_probability": str(tail), "original_mc2000_linear": previous,
                "exact_inverse_cdf": bounds, "exact_linear_diagnostic": linear, "mc2000_inverse_cdf_diagnostic": mc_inverse,
                "original_sign": interval_sign(previous), "exact_sign": interval_sign(bounds),
                "sign_changed": interval_sign(previous) != interval_sign(bounds),
                "exact_minus_original_endpoints": [None if a is None else a - b for a, b in zip(bounds, previous, strict=True)]}
        records.append({"name": name, "family": family, "family_size": size, **metadata,
            "point": point, "recomputed_point": computed, "point_changed": False,
            "omitted_nonfinite_ordered_draws": int(weights[~np.isfinite(curve)].sum()),
            "finite_support_count_vectors": int(np.isfinite(curve).sum()), "intervals": intervals})

    for index, (fit, row) in enumerate(zip(original_fits["probes"], original["q1"], strict=True)):
        if (fit["feature"], fit["layer"]) != (row["feature"], row["layer"]):
            raise ValueError("Reference fit/result ordering mismatch")
        active = np.asarray(fit["fit"]["active_columns"], dtype=bool)
        curve = r2_curve(ref["features"][:, fit["columns"]], ref[f"probe_{index}_predictions"], active)
        add(f"reference_q1_{index:02d}", "reference_q1", 24, curve, row["r2"], row["r2_ci95"], row["r2_family_adjusted_ci"], 20261029,
            {"feature": row["feature"], "layer": row["layer"], "active_train_columns": int(active.sum())})
    for index, row in enumerate(original["q2_q3"]):
        variants = [ba_curve(ref[f"intervention_{index}_{number}_logits"]) for number in range(len(row["variants"]))]
        if row["variants"][0]["random_seed"] is not None or any(v["random_seed"] is None for v in row["variants"][1:]):
            raise ValueError("Q2 learned/random variant ordering mismatch")
        curve = variants[0] - np.mean(variants[1:], axis=0)
        add(f"reference_q2_{index:02d}", "reference_q2", 2, curve, row["learned_minus_mean_random_balanced_accuracy"],
            row["contrast_ci95"], row["contrast_family_adjusted_ci"], 20261029, {"feature": row["feature"], "layer": row["layer"]})
    methods = protocol["methods"]
    boot_ba = {name: ba_curve(ext[f"logits_{name}"]) for name in methods}
    random_names = [f"random200_s{seed}" for seed in protocol["random_seeds"]]
    boot_ba["random_seed_mean"] = np.mean([boot_ba[name] for name in random_names], axis=0)
    for index, row in enumerate(extension["classification_differences"]):
        left, right = row["comparison"].split("-minus-")
        add(f"baseline_ba_{index:02d}", "baseline_classification", 3, boot_ba[left] - boot_ba[right], row["balanced_accuracy_difference"],
            row["paired_subject_ci95"], row["paired_subject_family_adjusted_ci"], 20261030, {"comparison": row["comparison"]})
    boot_r2: dict[tuple[str, int, str], Array] = {}
    for index, (fit, row) in enumerate(zip(extension_fits["q1"], extension["q1"], strict=True)):
        identity = (fit["method"], fit["layer"], fit["feature"])
        if identity != (row["method"], row["layer"], row["feature"]):
            raise ValueError("Baseline fit/result ordering mismatch")
        curve = r2_curve(ref["features"][:, fit["columns"]], ext[f"q1_prediction_{index}"], np.asarray(fit["fit"]["active_columns"], dtype=bool))
        np.testing.assert_allclose(curve[point_index], row["r2"], rtol=1e-10, atol=1e-8)
        boot_r2[identity] = curve
    for index, row in enumerate(extension["q1_pretrained_minus_random"]):
        key = (row["layer"], row["feature"])
        curve = boot_r2[("pretrained200", *key)] - np.mean([boot_r2[(name, *key)] for name in random_names], axis=0)
        add(f"baseline_q1_{index:02d}", "baseline_q1_contrast", 24, curve, row["r2_difference"], row["paired_subject_ci95"],
            row["paired_subject_family_adjusted_ci"], 20261030, {"feature": row["feature"], "layer": row["layer"]})
    if len(records) != 53 or len(extension["classification_differences"]) != 3 or len(extension["q1_pretrained_minus_random"]) != 24:
        raise ValueError("Unexpected statistic family sizes")
    for path in input_paths:
        if input_hashes[str(path.resolve())] != digest(path):
            raise ValueError("An input changed during sensitivity computation")
    summary: dict[str, Any] = {}
    for family in ("reference_q1", "reference_q2", "baseline_classification", "baseline_q1_contrast"):
        selected = [row for row in records if row["family"] == family]
        summary[family] = {"count": len(selected), "point_changes": 0}
        for label in ("pointwise95", "family_adjusted"):
            summary[family][label] = {"changed_names": [r["name"] for r in selected if r["intervals"][label]["sign_changed"]],
                "original_sign_counts": {s: sum(r["intervals"][label]["original_sign"] == s for r in selected) for s in ("positive", "negative", "includes_zero")},
                "exact_sign_counts": {s: sum(r["intervals"][label]["exact_sign"] == s for r in selected) for s in ("positive", "negative", "includes_zero")}}
    result = {"schema": "exact_empirical_bootstrap_sensitivity_v1", "status": "EXPLORATORY_POSTHOC_SENSITIVITY", "builder_only": True,
        "created_at": datetime.now(timezone.utc).isoformat(), "new_model_calls": 0, "new_test_calls": 0,
        "participants": len(unique), "windows": len(labels), "count_vectors": len(counts), "ordered_resamples": int(weights.sum()),
        "probability_mass_sum": float(weights.sum() / len(unique)**len(unique)),
        "method": {"distribution": "All six-participant bootstrap count vectors with multinomial multiplicities 6!/product(c_i!); denominator 6^6.",
            "quantile": "Q(p)=inf{x:F(x)>=p}, rank=ceil(p*finite_total_multiplicity), integer arithmetic on rational probabilities; no interpolation.",
            "intervals": "[Q(0.05/(2*m)), Q(1-0.05/(2*m))]; m=1 pointwise, or original family size 24,2,3,24; families are not merged.",
            "r2": "Mean of per-column pooled-row R2 over original training-active columns; denominator <=1e-20 is undefined, then nanmean as original.",
            "ba": "Mean of row-level recall for classes 0 and 1; all paired windows retained, fixed threshold logit>=0.",
            "sign_tolerance": SIGN_TOLERANCE, "nonfinite": "Omit undefined draws and report their integer probability mass; none silently imputed.",
            "quantile_diagnostic": "Both full-distribution NumPy-style linear quantiles and MC2000 inverse-CDF quantiles distinguish interpolation convention from Monte Carlo noise.",
            "scope": "Conditional empirical bootstrap on six observed test participants, fixed training/validation fits and fixed random seeds. No claim of exact population coverage or multiplicity control in a six-person population."},
        "verification": {"input_hashes_unchanged": True, "all_original_mc2000_intervals_reproduced": True,
            "maximum_original_mc_endpoint_error": max_mc_endpoint_error, "maximum_point_error": max_point_error,
            "maximum_direct_row_error": max_direct_error, "r2_direct_expanded_row_checks": checks_r2,
            "ba_direct_expanded_row_checks": checks_ba, "all_count_vectors_verified_against_expanded_rows": True},
        "input_sha256": input_hashes, "script_sha256": digest(Path(__file__)), "summary": summary, "statistics": records}
    output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output / "DISTRIBUTIONS_PRIVATE.npz", participant_counts=counts, integer_multiplicities=weights,
                        **curves)
    result["distribution_sha256"] = digest(output / "DISTRIBUTIONS_PRIVATE.npz")
    with (output / "RESULT.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(result), encoding="utf-8")
    return result


def render_report(result: dict[str, Any]) -> str:
    """Aggregate-only report: no participant identifiers or per-row arrays."""
    sign_zh = {"positive": "全正", "negative": "全负", "includes_zero": "跨/触零", "undefined": "未定义"}

    def bounds(value: list[float | None]) -> str:
        return "[" + ", ".join("NA" if x is None else f"{x:.6f}" for x in value) + "]"

    changed = sum(row["intervals"]["family_adjusted"]["sign_changed"] for row in result["statistics"])
    changed95 = sum(row["intervals"]["pointwise95"]["sign_changed"] for row in result["statistics"])
    omitted = sum(row["omitted_nonfinite_ordered_draws"] for row in result["statistics"])
    lines = ["# EEGMAT 精确经验 bootstrap 敏感性分析", "", "状态：**Builder 独立探索性、事后敏感性分析**。不是新的未见测试，不替换原始参考或扩展结果。", "",
        f"六名测试参与者的 6⁶ = **46,656** 个有序重采样，可归并为 **462** 个计数向量。对既定 53 个统计量完成精确经验分布计算。点估计均复现；与原始 2,000 次 Monte Carlo 结果相比，家族调整区间的正负/跨零判定改变 **{changed}/53**，点态 95% 区间改变 **{changed95}/53**。", "",
        "精确枚举只消除有限 Monte Carlo 抽样噪声。六人的抽样信息、总体代表性、训练/验证集固定、随机初始化种子固定，以及任务/采集顺序混杂等限制均未改善。本文不声称精确总体覆盖率，也不能把负 R²、跨零区间或探索性追加分析解释成确认性因果证据。", "",
        "## 统计定义与边界", "",
        "- 参与者为重采样单位，每次抽六人、有放回，保留该参与者全部窗口，所有比较使用同一计数向量配对。每人原有两类各 12 个窗口，共 144 行。",
        "- 计数向量 c 的整数权重为 6!/∏cᵢ!，概率为该权重/46,656。整数权重总和为 46,656，概率和为 1；不是把 462 个向量等权。",
        "- 主分位数为 Q(p)=inf{x:F(x)≥p}：按值排序后取第 ceil(p×总整数权重) 个值，不插值。分位概率使用有理数，避免累计浮点误差改变阶数。",
        "- 区间为 [Q(0.05/(2m)), Q(1−0.05/(2m))]。点态 m=1；四个既有家族分别 m=24、2、3、24，未重定义为一个 53 项家族。这里只沿用原 Bonferroni 概率端点，不证明小样本覆盖率。",
        "- Q1 沿用训练期活跃列，在每个重采样的全部行上逐列计算 R²，再对有效列取平均；不先求每位参与者 R²，不将 SSE/SST 跨列合并。分母≤1e−20 的列沿用原未定义规则。",
        "- 分类沿用行级两类 recall 的平均及 logit≥0 阈值；随机种子对照是各固定种子指标的均值，不是预测集成。原 Q2 是 learned BA 减去随机方向 BA 的均值。",
        f"- 53 项分布遗漏的未定义有序重采样总数：{omitted}。数值判定零的容差为 1e−12。", "",
        "## 原始 Monte Carlo 与精确区间", "",
        "以下同时列出点态与原家族调整区间；所有数值均为 R² 或 balanced accuracy 原单位。点估计不变。原区间保留原 NumPy 默认线性插值；精确列使用上面的离散逆 CDF。", ""]
    names = {"reference_q1": "原始 Q1：24 个原始 R²", "reference_q2": "原始 Q2：2 个 learned−mean-random BA 对比",
             "baseline_classification": "扩展分类：3 个 BA 对比", "baseline_q1_contrast": "扩展 Q1：24 个 pretrained−mean-random R² 对比"}
    for family, title in names.items():
        lines += [f"### {title}", "", "| 统计量 | 点估计 | 原 MC 95% | 精确 95% | 原 MC 家族调整 | 精确家族调整 | 家族调整判定 原→精确 |", "|---|---:|---|---|---|---|---|"]
        for row in result["statistics"]:
            if row["family"] != family:
                continue
            name = row.get("comparison", f"L{row.get('layer')} {row.get('feature')}")
            a, b = row["intervals"]["pointwise95"], row["intervals"]["family_adjusted"]
            lines.append(f"| {name} | {row['point']:.6f} | {bounds(a['original_mc2000_linear'])} | {bounds(a['exact_inverse_cdf'])} | {bounds(b['original_mc2000_linear'])} | {bounds(b['exact_inverse_cdf'])} | {sign_zh[b['original_sign']]}→{sign_zh[b['exact_sign']]} |")
        lines.append("")
    lines += ["## 尾部精度、分位数约定与解释", "",
        "m=24 时每侧尾概率为 1/960。2,000 次 Monte Carlo 每尾预期仅约 2.083 次抽样；完整经验分布对应每尾 48.6 个有序重采样概率单位，其逆 CDF 下端取第 49 个顺序统计量。离散取值和重复值仍存在，不能把 46,656 个重采样解释为新增参与者。", "",
        "私有 RESULT.json 对每项区间同时保留：原 MC 线性分位数、精确逆 CDF、精确全分布线性分位数，以及同一 2,000 次抽样的逆 CDF。这样能区分有限抽样误差与分位数插值约定。下面列出两种贡献的最大绝对端点差。", "",
        "| 家族 | MC线性→全分布线性 最大端点差 | 全分布线性→精确逆CDF 最大端点差 |", "|---|---:|---:|"]
    for family, title in names.items():
        intervals = [r["intervals"][label] for r in result["statistics"] if r["family"] == family for label in ("pointwise95", "family_adjusted")]
        mc = max(abs(a - b) for v in intervals for a, b in zip(v["original_mc2000_linear"], v["exact_linear_diagnostic"], strict=True))
        convention = max(abs(a - b) for v in intervals for a, b in zip(v["exact_inverse_cdf"], v["exact_linear_diagnostic"], strict=True))
        lines.append(f"| {title} | {mc:.9g} | {convention:.9g} |")
    lines += ["", "## 可复核性", "",
        f"每个计数向量均用直接展开参与者窗口重算核对：R² {result['verification']['r2_direct_expanded_row_checks']:,} 项、BA {result['verification']['ba_direct_expanded_row_checks']:,} 项。另有三参与者玩具例的所有 3³ 个有序重采样与计数向量多重性逐一对应测试，并覆盖不等簇大小、训练活跃列、常数列和分位数边界。",
        f"全部 53 项原 2,000 次抽样的两类区间复现，最大端点差 {result['verification']['maximum_original_mc_endpoint_error']:.3g}；点估计最大差 {result['verification']['maximum_point_error']:.3g}；充分统计量与直接展开行的最大差 {result['verification']['maximum_direct_row_error']:.3g}。",
        "输入文件在运行前后逐一核对 SHA-256，原始结果和冻结拟合均未改写。原始预测继续保留于原参考与扩展私有目录，未复制数据集；新增计数分布与详细校验留在忽略的 `.local/research/2026-10-30-extension/exact-bootstrap/` 内。本报告只含聚合统计。新增模型调用 0，新增测试调用 0，GPU 0，网络访问 0。",
        "", "复核入口：`python -m pytest scripts/research/test_exact_bootstrap_sensitivity.py -q`。分析脚本拒绝覆盖已有结果，复跑须指定新的私有输出目录和报告路径。", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.reference, args.baseline, args.output, args.report)
    print(json.dumps({"status": result["status"], "summary": result["summary"], "verification": result["verification"]}, indent=2))


if __name__ == "__main__":
    main()
