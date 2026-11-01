"""Cloud-only timing and memory telemetry. A missing utilization API is explicit."""
from __future__ import annotations

import contextlib
import time
import torch


def seed_process(seed):
    import random
    import numpy as np
    random.seed(int(seed))
    np.random.seed(int(seed))
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def require_cuda(device):
    device = torch.device(device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("Research training must use an authorized TiONE CUDA worker")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("Frozen BF16 policy unsupported; requires a common reviewed repair")
    torch.cuda.set_device(device)
    return device


def utilization(device):
    try:
        # torch delegates this optional call to NVML; never installs packages.
        return {"gpu_percent": float(torch.cuda.utilization(device)), "unavailable_reason": None}
    except Exception as exc:
        return {"gpu_percent": None, "unavailable_reason": f"{type(exc).__name__}: {exc}"}


class Telemetry:
    def __init__(self, device):
        self.device = device
        self.start = time.monotonic()
        self.samples = 0
        self.steps = 0
        self.data_wait_seconds = 0.0
        self.h2d_seconds = 0.0
        self.step_seconds = 0.0
        self.utilization_samples = []
        torch.cuda.reset_peak_memory_stats(device)

    def copy(self, values):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        # Explicit synchronization is measured in throughput smoke only.
        start.record()
        tensor = torch.as_tensor(values).pin_memory().to(self.device, non_blocking=True)
        end.record()
        return tensor, start, end

    def report(self):
        torch.cuda.synchronize(self.device)
        elapsed = time.monotonic() - self.start
        props = torch.cuda.get_device_properties(self.device)
        return {"gpu_name": props.name, "gpu_memory_total_bytes": props.total_memory,
                "gpu_memory_used_bytes": torch.cuda.memory_allocated(self.device),
                "gpu_peak_memory_bytes": torch.cuda.max_memory_allocated(self.device),
                "wall_seconds": elapsed, "steps": self.steps, "samples": self.samples,
                "mean_step_seconds": self.step_seconds / self.steps if self.steps else None,
                "samples_per_second": self.samples / elapsed if elapsed else 0,
                "tokens_per_second": self.samples * 660 / elapsed if elapsed else 0,
                "data_wait_seconds": self.data_wait_seconds, "h2d_seconds": self.h2d_seconds,
                "utilization_samples": self.utilization_samples,
                "precision": "BF16_encoder_FP32_contrastive_loss_and_head",
                "gradient_checkpointing": True, "compile": False, "attention": "torch_SDPA",
                "workers": 0, "prefetch": "run-scoped decoded read-only memmap; pinned selected CPU batches",
                "pin_memory": True, "nonblocking_copy": True,
                "synchronization": "smoke CUDA events and per-step diagnostic finite/norm assertions; scalar log collection after optimizer step; final report synchronize"}
