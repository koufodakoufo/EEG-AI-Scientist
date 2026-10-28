"""Immutable offline REVE loader and shared input/evaluation representation.

Research always loads pinned safetensors; controlled tests may instantiate a
tiny model directly. No external module search, random fallback or downloads.
"""
from __future__ import annotations

import math
from pathlib import Path
import types

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

from artifact_io import read_json, sha256_file
from data_contract import token_shape

ROOT = Path(__file__).resolve().parent
WEIGHT_ROOT = Path("/mnt/omni-eeg-01/cx/EEG_FM/baseline/REVE/weights")
BASE_WEIGHT_SHA256 = "8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe"
POSITION_WEIGHT_SHA256 = "4b793820b9df0998667deb6c8ce2dbb86b38221d5165c1844bc4971941b13f13"


def load_exact_state(module, state):
    expected = module.state_dict()
    if set(state) != set(expected):
        raise ValueError(f"Weight keys differ: missing={sorted(set(expected)-set(state))}, extra={sorted(set(state)-set(expected))}")
    for key, value in state.items():
        if value.shape != expected[key].shape or not torch.isfinite(value).all():
            raise ValueError(f"Invalid official tensor: {key}")
    result = module.load_state_dict(state, strict=True)
    if result.missing_keys or result.unexpected_keys:
        raise ValueError("Official load was incomplete")


def checked_positions(bank, channel_names):
    if len(channel_names) != 60 or len(set(channel_names)) != 60:
        raise ValueError("Require the complete ordered 60-channel release montage")
    missing = [name for name in channel_names if name not in bank.mapping]
    if missing:
        raise ValueError(f"Official position bank lacks channels: {missing}")
    indices = torch.tensor([bank.mapping[name] for name in channel_names], device=bank.embedding.device)
    positions = bank.embedding.index_select(0, indices)
    if positions.shape != (60, 3) or not torch.isfinite(positions).all():
        raise ValueError("Invalid channel positions")
    return positions.detach().clone()


def prepare_input(signals):
    """Explicit starting choice: released float32 uV, 200Hz, NoClip; no zscore.

    Official forward/card do not specify a scaling transform. This choice is
    identical for R0/R1/R2; a failed cloud numerical gate requires common repair.
    """
    if signals.ndim != 3 or tuple(signals.shape[1:]) != (60, 2000):
        raise ValueError("REVE input must be [B,60,2000]")
    if not torch.isfinite(signals).all():
        raise ValueError("Nonfinite released signal")
    return signals.float()


def flatten_for_evaluation(tokens):
    if tuple(tokens.shape[1:]) != (60, 11, 512) or tokens.ndim != 4:
        raise ValueError("Official REVE token/position geometry changed")
    if not torch.isfinite(tokens).all():
        raise ValueError("Nonfinite downstream feature")
    return tokens.float().reshape(tokens.shape[0], -1)


def enable_checkpointing(model):
    from vendor.reve.modeling_reve import TransformerBackbone

    class CheckpointBackbone(TransformerBackbone):
        # Class dispatch survives DataParallel replication. Instance-bound
        # monkeypatch methods would remain bound to the original device.
        def forward(self, value, return_out_layers=False):
            if not self.training or not torch.is_grad_enabled():
                return super().forward(value, return_out_layers)
            if return_out_layers:
                raise ValueError("Layer-list output is outside the frozen task interface")
            for attention, feedforward in self.layers:
                def block(x, attn=attention, ff=feedforward):
                    x = attn(x) + x
                    return ff(x) + x
                value = checkpoint(block, value, use_reentrant=False, preserve_rng_state=True)
            return value

    if type(model.transformer) is TransformerBackbone:
        model.transformer.__class__ = CheckpointBackbone


def pin_sdpa_attention(model):
    """Freeze the supported torch SDPA backend on both CPU and CUDA.

    The optional flash_attn dependency is selected merely by importability in
    the original source. SDPA uses the same Q/K/V and weights, supports CPU
    validation, and avoids silently changing kernels between workers.
    """
    from vendor.reve.modeling_reve import ClassicalAttention
    for attention, _ in model.transformer.layers:
        attention.use_flash = False
        attention.attend = ClassicalAttention(attention.heads, use_sdpa=True)


def build_head(mode, feature_dim, classes):
    if mode == "lp":
        return nn.Linear(feature_dim, classes)
    if mode == "ft":
        # Exact inspected decop _build_simple_nn3 topology.
        return nn.Sequential(nn.LayerNorm(feature_dim), nn.Linear(feature_dim, 256),
                             nn.ReLU(), nn.Dropout(0.2), nn.Linear(256, 128),
                             nn.ReLU(), nn.Dropout(0.2), nn.Linear(128, classes))
    raise ValueError("Unknown downstream mode")


def load_official(channel_names, *, device, encoder_checkpoint=None, gradient_checkpointing=True):
    from safetensors.torch import load_file
    from vendor.reve.configuration_reve import ReveConfig
    from vendor.reve.configuration_bank import RevePositionBankConfig
    from vendor.reve.modeling_reve import Reve
    from vendor.reve.position_bank import RevePositionBank

    base_path = WEIGHT_ROOT / "reve-base/model.safetensors"
    pos_path = WEIGHT_ROOT / "reve-positions/model.safetensors"
    # File hash verification is actual at run time, never replaced by old logs.
    for path, expected in ((base_path, BASE_WEIGHT_SHA256), (pos_path, POSITION_WEIGHT_SHA256)):
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"Official resource missing or changed: {path}")
    config = read_json(ROOT / "vendor/reve/config.json")
    if token_shape(config) != (60, 11, 512):
        raise ValueError("Official geometry differs from pinned config")
    model = Reve(ReveConfig(**config))
    pin_sdpa_attention(model)
    load_exact_state(model, load_file(str(base_path), device="cpu"))
    bank = RevePositionBank(RevePositionBankConfig(**read_json(ROOT / "vendor/reve/position_config.json")))
    load_exact_state(bank, load_file(str(pos_path), device="cpu"))
    positions = checked_positions(bank, channel_names)
    if encoder_checkpoint is not None:
        # Completed candidate is a plain encoder state in the same architecture.
        load_exact_state(model, torch.load(encoder_checkpoint, map_location="cpu", weights_only=True))
    if gradient_checkpointing:
        enable_checkpointing(model)
    model.to(device)
    positions = positions.to(device)
    identity = {"base_weight_sha256": BASE_WEIGHT_SHA256,
                "position_weight_sha256": POSITION_WEIGHT_SHA256,
                "encoder_checkpoint_sha256": sha256_file(encoder_checkpoint) if encoder_checkpoint else BASE_WEIGHT_SHA256,
                "config_sha256": sha256_file(ROOT / "vendor/reve/config.json"),
                "channel_names": list(channel_names), "token_shape": [60, 11, 512],
                "special_tokens_in_output": 0, "valid_tokens": 660,
                "input_policy": "released_uV_NoClip_no_zscore"}
    identity["attention_policy"] = "torch_SDPA_no_external_flash_attn"
    return model, positions, identity
