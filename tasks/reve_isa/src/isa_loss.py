"""Stimulus paired flatten InfoNCE; no label-based positives or projection."""
from __future__ import annotations

import math
import torch
import torch.nn.functional as F


def flatten_normalize(tokens: torch.Tensor) -> torch.Tensor:
    if tokens.ndim != 4 or any(size < 1 for size in tokens.shape):
        raise ValueError("Require [batch, channels, patches, embedding] tokens")
    if not torch.isfinite(tokens).all():
        raise ValueError("Nonfinite encoder output")
    # BF16/FP16 encoder kernels retain a FP32 contrastive normalization/loss.
    # FP64 is preserved for controlled reference and finite-difference tests.
    if tokens.dtype in {torch.bfloat16, torch.float16}:
        tokens = tokens.float()
    flat = tokens.reshape(tokens.shape[0], -1)
    if torch.any(torch.linalg.vector_norm(flat, dim=1) == 0):
        raise ValueError("Zero encoder representation")
    return F.normalize(flat, p=2, dim=1)


def paired_info_nce(features: torch.Tensor, *, temperature: float):
    if not math.isfinite(temperature) or not 0.03 <= temperature <= 0.3:
        raise ValueError("Temperature outside declared task bounds")
    if features.ndim != 2 or features.shape[0] < 4 or features.shape[0] % 2:
        raise ValueError("Require even [view_a; view_b] batch with negatives")
    if not torch.isfinite(features).all():
        raise ValueError("Nonfinite contrastive features")
    norms = torch.linalg.vector_norm(features.detach(), dim=1)
    if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5, rtol=1e-5):
        raise ValueError("InfoNCE expects L2-normalized features")
    batch = features.shape[0]
    identities = torch.arange(batch, device=features.device) % (batch // 2)
    same = identities[:, None] == identities[None, :]
    diagonal = torch.eye(batch, dtype=torch.bool, device=features.device)
    similarity = features @ features.T
    positives = similarity[same & ~diagonal].reshape(batch, 1)
    negatives = similarity[~same].reshape(batch, batch - 2)
    logits = torch.cat((negatives, positives), dim=1) / temperature
    labels = torch.full((batch,), batch - 2, dtype=torch.long, device=features.device)
    return F.cross_entropy(logits, labels), logits, labels
