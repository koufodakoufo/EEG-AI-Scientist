"""Train-only affine LEACE for continuous EEG attributes.

Independent NumPy implementation of Belrose et al., arXiv:2306.03819v4,
Theorems 4.2–4.3. This audits empirical linear covariance, not nonlinear
information removal, held-out erasure, or physiological causality. No shrinkage
or norm-growth heuristic from the external package is applied.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _matrix(value: Any, name: str, *, minimum_rows: int = 1) -> np.ndarray:
    array = np.asarray(value)
    if (array.ndim != 2 or array.shape[0] < minimum_rows or array.shape[1] < 1
            or array.dtype.kind not in 'biuf' or not np.isfinite(array).all()):
        raise ValueError(f'{name} must be a nonempty finite real matrix')
    return array.astype(np.float64, copy=False)


def fit_leace(x: np.ndarray, concepts: np.ndarray, *, rcond: float = 1e-10) -> dict[str, Any]:
    """Fit from training rows; return a JSON-safe frozen affine operator.

    Singular representation directions below ``rcond * largest variance`` are
    excluded from whitening. The measured covariance residual records the
    resulting numerical limitation instead of claiming exact population erasure.
    Concept columns are standardized using training moments only; this leaves
    the mathematical zero-covariance constraint invariant.
    """
    x = _matrix(x, 'x', minimum_rows=2)
    z = _matrix(concepts, 'concepts', minimum_rows=2)
    if len(x) != len(z):
        raise ValueError('Training representations and concepts must align')
    if isinstance(rcond, (bool, np.bool_)) or not np.isfinite(rcond) or not 0 < rcond < 1:
        raise ValueError('rcond must be a finite number between zero and one')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        mean = x.mean(axis=0)
        centered = x - mean
        z = z - z.mean(axis=0)
        scale = np.sqrt(np.mean(z*z, axis=0))
        z = z / np.where(scale > 0, scale, 1.)
        covariance = centered.T @ centered / len(x)
        cross = centered.T @ z / len(x)
        values, vectors = np.linalg.eigh(covariance)
        keep = values > max(float(values[-1]), 0.) * rcond
        roots = np.sqrt(values[keep])
        vectors = vectors[:, keep]
        white = (vectors / roots) @ vectors.T
        unwhite = (vectors * roots) @ vectors.T
        whitened_cross = white @ cross
        directions, singular, _ = np.linalg.svd(whitened_cross, full_matrices=False)
        numerical_floor = (np.finfo(np.float64).eps * max(x.shape + z.shape)
                           * max(1., np.sqrt(int(keep.sum()) * z.shape[1])))
        threshold = max(numerical_floor, rcond * (float(singular[0]) if len(singular) else 0.))
        rank = int(np.count_nonzero(singular > threshold))
        directions = directions[:, :rank]
        removal = unwhite @ directions @ directions.T @ white
        residual = cross - removal @ cross
        cross_norm = float(np.linalg.norm(cross))
        relative_residual = float(np.linalg.norm(residual) / cross_norm) if cross_norm else 0.
    if not np.isfinite(removal).all() or not np.isfinite(relative_residual):
        raise ValueError('Nonfinite fitted erasure operator')
    return {'schema_version': 'linear_erasure_v1', 'method': 'leace',
            'mean': mean.tolist(), 'removal': removal.tolist(), 'rank': rank,
            'covariance_rank': int(keep.sum()), 'rcond': float(rcond),
            'training_rows': len(x), 'concept_columns': z.shape[1],
            'cross_covariance_relative_residual': relative_residual,
            'singular_threshold': threshold,
            'guarantee_scope': 'empirical training covariance in retained numerical subspace'}


def apply_erasure(fitted: dict[str, Any], x: np.ndarray) -> np.ndarray:
    """Apply frozen training moments; evaluation rows never refit the operator."""
    x = _matrix(x, 'x')
    if fitted.get('schema_version') != 'linear_erasure_v1' or fitted.get('method') != 'leace':
        raise ValueError('Unknown erasure operator')
    mean = np.asarray(fitted['mean'], dtype=np.float64)
    removal = _matrix(fitted['removal'], 'removal')
    if mean.shape != (x.shape[1],) or removal.shape != (x.shape[1], x.shape[1]) or not np.isfinite(mean).all():
        raise ValueError('Erasure operator dimension or mean differs')
    with np.errstate(over='raise', invalid='raise'):
        changed = x - (x - mean) @ removal.T
    if not np.isfinite(changed).all():
        raise ValueError('Erasure produced nonfinite values')
    return changed
