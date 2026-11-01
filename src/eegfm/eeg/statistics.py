"""Auditable numerical primitives for the private real-EEG reference.

This module is Builder/reference material, not an Actor method hint. It uses
only training data to fit transforms. Validation selection is caller-owned.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[Any]


def _matrix(value: Array) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 2 or not np.isfinite(result).all():
        raise ValueError('Expected a finite two-dimensional matrix')
    return result


def validate_partitions(partitions: Mapping[str, Array]) -> dict[str, int]:
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for name, values in partitions.items():
        ids = {str(value) for value in values}
        if not ids or seen & ids:
            raise ValueError('Empty partition or subject overlap')
        seen.update(ids)
        counts[name] = len(ids)
    return counts


def fit_probe(x: Array, y: Array, *, alpha: float) -> dict[str, Any]:
    from sklearn.linear_model import Ridge
    x, y = _matrix(x), _matrix(y)
    if len(x) != len(y) or len(x) < 3 or not np.isfinite(alpha) or alpha <= 0:
        raise ValueError('Invalid probe samples or regularization')
    xm, ym = x.mean(0), y.mean(0)
    xs, ys = x.std(0), y.std(0)
    active = ys > np.maximum(np.abs(ym)*1e-12, 1e-12)
    xs = np.where(xs > 1e-12, xs, 1.0)
    ys = np.where(active, ys, 1.0)
    model = Ridge(alpha=alpha, fit_intercept=False, solver='svd')
    model.fit((x-xm)/xs, (y-ym)/ys)
    coefficient = np.atleast_2d(model.coef_).T
    return {'x_mean': xm, 'x_scale': xs, 'y_mean': ym, 'y_scale': ys,
            'coefficient': coefficient, 'directions': coefficient/xs[:,None],
            'active_columns': active, 'alpha': alpha, 'training_samples': len(x)}


def predict_probe(fit: Mapping[str, Any], x: Array) -> NDArray[np.float64]:
    return ((_matrix(x)-fit['x_mean'])/fit['x_scale']) @ fit['coefficient'] * fit['y_scale'] + fit['y_mean']


def r2_columns(y: Array, prediction: Array) -> NDArray[np.float64]:
    y, prediction = _matrix(y), _matrix(prediction)
    if y.shape != prediction.shape:
        raise ValueError('Prediction and target shape mismatch')
    numerator = np.square(y-prediction).sum(0)
    denominator = np.square(y-y.mean(0)).sum(0)
    # Constant held-out targets have undefined R2; never promote them to 1/0.
    out = np.full(y.shape[1], np.nan)
    good = denominator > 1e-20
    out[good] = 1-numerator[good]/denominator[good]
    return out


def subspace(directions: Array, *, relative_tolerance: float = 1e-8) -> NDArray[np.float64]:
    u, s, _ = np.linalg.svd(_matrix(directions), full_matrices=False)
    if not len(s) or s[0] <= 1e-14:
        return np.empty((directions.shape[0], 0))
    return u[:, s > max(s[0]*relative_tolerance, 1e-14)]


def perturb(activations: Array, basis: Array, center: Array, *, random_seed: int | None = None) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Subtract a pooled-component shift from every token; preserve other axes.

    Random controls match the learned basis' actual rank and EACH row's shift
    norm. Their direction is independent. This measures representation-level
    sensitivity, not intervention on the source EEG or physiological causation.
    """
    z = np.asarray(activations, dtype=np.float64)
    basis = _matrix(basis)
    center = np.asarray(center, dtype=np.float64)
    if z.ndim != 4 or z.shape[-1] != basis.shape[0] or center.shape != (z.shape[-1],) or not np.isfinite(z).all():
        raise ValueError('Activation/basis/center shape or finite-value error')
    if not np.allclose(basis.T@basis, np.eye(basis.shape[1]), atol=1e-7):
        raise ValueError('Basis must have orthonormal columns')
    pooled = z.mean((1,2))
    shift = (pooled-center) @ basis @ basis.T
    norms = np.linalg.norm(shift, axis=1)
    used_basis = basis
    if random_seed is not None and basis.shape[1]:
        rng = np.random.default_rng(random_seed)
        used_basis, _ = np.linalg.qr(rng.normal(size=basis.shape))
        random_shift = (pooled-center) @ used_basis @ used_basis.T
        random_norm = np.linalg.norm(random_shift, axis=1)
        zero = random_norm < 1e-14
        random_shift[zero] = used_basis[:,0]
        random_norm[zero] = 1
        shift = random_shift * (norms/random_norm)[:,None]
    shifted = z - shift[:,None,None,:]
    return shifted, {'rank': basis.shape[1], 'random_seed': random_seed,
                     'pooled_shift_l2': norms, 'basis': used_basis,
                     'relative_shift_l2': norms/np.maximum(np.linalg.norm(pooled,axis=1),1e-14)}


def permute_subject_blocks(subjects: Array, *, seed: int) -> NDArray[np.int64]:
    subjects = np.asarray(subjects)
    unique = np.unique(subjects)
    blocks = [np.flatnonzero(subjects == item) for item in unique]
    if len(blocks) < 2 or len({len(block) for block in blocks}) != 1:
        raise ValueError('Effective subject-block control requires equal blocks and two subjects')
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(blocks))
    # A nonzero cyclic shift of a random ordering is a guaranteed derangement.
    shuffled = np.roll(order, int(rng.integers(1,len(blocks))))
    result = np.empty(len(subjects), dtype=np.int64)
    for source, destination in zip(order, shuffled):
        # Destroy condition and window-position alignment as well as subject
        # correspondence. This is a diagnostic target randomization, not a
        # participant permutation significance test.
        result[blocks[source]] = rng.permutation(blocks[destination])
    return result


def cluster_bootstrap_indices(subjects: Array, *, resamples: int, seed: int) -> list[NDArray[np.int64]]:
    subjects = np.asarray(subjects)
    unique = np.unique(subjects)
    if len(unique) < 2 or not 1 <= resamples <= 10000:
        raise ValueError('Invalid subject bootstrap')
    blocks = [np.flatnonzero(subjects == item) for item in unique]
    rng = np.random.default_rng(seed)
    return [np.concatenate([blocks[index] for index in draw])
            for draw in rng.integers(0,len(blocks),size=(resamples,len(blocks)))]


def interval(values: Array, *, confidence: float = 0.95) -> list[float | None]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return [None,None]
    tail = (1-confidence)/2
    return np.quantile(values,[tail,1-tail]).tolist()


def fit_head(train_x: Array, train_y: Array, val_x: Array, val_y: Array, *, c_grid: tuple[float,...]=(0.01,0.1,1.0,10.0)) -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    train_x, val_x = _matrix(train_x), _matrix(val_x)
    mean, scale = train_x.mean(0), train_x.std(0)
    scale = np.where(scale > 1e-12,scale,1)
    candidates: list[dict[str, Any]] = []
    for c in c_grid:
        head = LogisticRegression(C=c, max_iter=2000, solver='lbfgs', random_state=20261029)
        head.fit((train_x-mean)/scale,train_y)
        score = balanced_accuracy_score(val_y, head.predict((val_x-mean)/scale))
        candidates.append({'C': c, 'validation_balanced_accuracy': float(score),
                           'coefficient': head.coef_[0], 'intercept': float(head.intercept_[0])})
    best = max(candidates,key=lambda item: item['validation_balanced_accuracy'])
    return {**best, 'x_mean':mean, 'x_scale':scale, 'selection_grid':[
        {'C':item['C'],'validation_balanced_accuracy':item['validation_balanced_accuracy']} for item in candidates]}


def head_logits(head: Mapping[str,Any], x: Array) -> NDArray[np.float64]:
    return ((_matrix(x)-head['x_mean'])/head['x_scale']) @ head['coefficient'] + head['intercept']


def classification_metrics(y: Array, logits: Array) -> dict[str,float]:
    from sklearn.metrics import balanced_accuracy_score, accuracy_score, roc_auc_score
    y, logits = np.asarray(y), np.asarray(logits)
    if not np.isfinite(logits).all() or set(np.unique(y)) != {0,1}:
        raise ValueError('Need finite logits and both classes')
    return {'accuracy':float(accuracy_score(y,logits >= 0)),
            'balanced_accuracy':float(balanced_accuracy_score(y,logits >= 0)),
            'auroc':float(roc_auc_score(y,logits))}
