"""Five GPU source forwards; InfoNCE remains separate for each batch of 64."""
from __future__ import annotations

import torch
from isa_loss import paired_info_nce
from isa_representation import represent


def separate_source_losses(tokens, representation, temperature, *, source_count=5, batch_size=64):
    if tokens.shape[0] != source_count * batch_size:
        raise ValueError("Physical source batch geometry changed")
    losses = []
    for source in range(source_count):
        block = tokens[source * batch_size:(source+1) * batch_size]
        loss, logits, _ = paired_info_nce(represent(block.float(), representation), temperature=temperature)
        if tuple(logits.shape) != (batch_size, batch_size - 1):
            raise ValueError("Cross-source negatives were introduced")
        losses.append(loss)
    return torch.stack(losses).mean(), torch.stack([loss.detach() for loss in losses])


class _ReplicaAutocast(torch.nn.Module):
    """Restore the calling thread's precision inside each replica thread."""
    def __init__(self, replica, enabled, dtype, replica_index):
        super().__init__()
        self.replica = replica
        self.enabled = enabled
        self.dtype = dtype
        self.replica_index = replica_index

    def forward(self, *args, **kwargs):
        with torch.autocast("cuda", enabled=self.enabled, dtype=self.dtype):
            self.observation = {
                "replica_index": self.replica_index,
                "autocast_enabled": torch.is_autocast_enabled("cuda"),
                "autocast_dtype": str(torch.get_autocast_dtype("cuda")),
            }
            return self.replica(*args, **kwargs)


class _SourceDataParallel(torch.nn.DataParallel):
    def parallel_apply(self, replicas, inputs, kwargs):
        # Torch 2.7.1 propagates only autocast_enabled into worker threads;
        # their default CUDA dtype is FP16 even when this caller chose BF16.
        enabled = torch.is_autocast_enabled("cuda")
        dtype = torch.get_autocast_dtype("cuda")
        self.last_replica_autocast = []
        replicas = [_ReplicaAutocast(replica, enabled, dtype, index)
                    for index, replica in enumerate(replicas)]
        outputs = super().parallel_apply(replicas, inputs, kwargs)
        # Read only after all replica threads have joined; replace each call.
        self.last_replica_autocast = [dict(replica.observation) for replica in replicas]
        return outputs


def parallel_model(model):
    if not torch.cuda.is_available() or torch.cuda.device_count() < 5:
        raise RuntimeError("Five local GPU source replicas required")
    return _SourceDataParallel(model, device_ids=list(range(5)), output_device=0, dim=0)
