"""Editable stimulus ISA optimization. Always exports a plain REVE encoder."""
from __future__ import annotations

import math
from pathlib import Path
import time

import numpy as np
import torch

from artifact_io import atomic_json, atomic_torch_save, check_deadline, publish_completion, verify_completion
from data_contract import lodo_sources
from gpu_diagnostics import Telemetry, require_cuda, seed_process, utilization
from isa_builder import StimulusBatchBuilder
from isa_loss import paired_info_nce
from isa_representation import build_representation, represent
from official_model import load_official, prepare_input
from source_parallel import parallel_model, separate_source_losses


PROBE_WARMUP_STEPS = 3
PROBE_MEASURED_STEPS = 20


def available_memory_bytes():
    """Bound RAM staging by host availability and the active cgroup limit."""
    fields = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
              for line in Path('/proc/meminfo').read_text().splitlines()}
    available = int(fields['MemAvailable'].split()[0]) * 1024
    # Container mounts can expose the current cgroup at the mount root. In a
    # visible host hierarchy, every ancestor can impose a tighter shared limit.
    roots = {Path('/sys/fs/cgroup'), Path('/sys/fs/cgroup/memory')}
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        _, controllers, relative = line.split(':', 2)
        if not controllers or 'memory' in controllers.split(','):
            if '..' in Path(relative).parts:
                raise RuntimeError('Cannot safely resolve process cgroup memory hierarchy')
            for mount in (Path('/sys/fs/cgroup'), Path('/sys/fs/cgroup/memory')):
                current = mount / relative.lstrip('/')
                while True:
                    roots.add(current)
                    if current == mount:
                        break
                    current = current.parent
    accounting_visible = False
    for root in roots:
        for limit_name, usage_name in (('memory.max', 'memory.current'),
                                       ('memory.limit_in_bytes', 'memory.usage_in_bytes')):
            limit_path, usage_path = root / limit_name, root / usage_name
            if limit_path.is_file() and usage_path.is_file():
                accounting_visible = True
                limit = limit_path.read_text().strip()
                if limit != 'max':
                    available = min(available, max(0, int(limit) - int(usage_path.read_text())))
    if not accounting_visible:
        raise RuntimeError('RAM staging requires readable cgroup memory accounting in the trusted worker sandbox')
    return available


def stage_source_signals(releases, sources, *, deadline):
    """Copy verified decoded rows once to bounded read-only RAM, without RNG use.

    Keep the original cache to restore after posttraining. The sampler and
    Release.load_signals are unchanged, including duplicate/order semantics.
    """
    pending = [name for name in sources if not hasattr(releases[name], '_posttrain_disk_cache')]
    needed = sum(len(releases[name].labels) * 60 * 2000 * 4 for name in pending)
    available = available_memory_bytes()
    reserve = max(2 * 1024**3, int(available * 0.1))
    if needed and needed + reserve > available:
        raise MemoryError(f'Posttrain RAM staging needs {needed} bytes plus {reserve} reserve; '
                          f'only {available} bytes available. Require engineering resource review.')
    start = time.monotonic()
    staged = []
    try:
        for name in pending:
            release = releases[name]
            disk = release.signal_cache
            shape = (len(release.labels), 60, 2000)
            if disk is None or disk.shape != shape or disk.dtype != np.float32:
                raise ValueError('RAM staging requires the verified decoded FP32 signal cache')
            resident = np.empty(shape, dtype=np.float32)
            for offset in range(0, len(release.labels), 64):
                check_deadline(deadline)
                block = np.asarray(disk[offset:offset+64])
                if not np.isfinite(block).all():
                    raise ValueError('Nonfinite signal in decoded cache during RAM staging')
                resident[offset:offset+64] = block
            resident.flags.writeable = False
            release._posttrain_disk_cache = disk
            release.signal_cache = resident
            staged.append(name)
    except BaseException:
        release_source_signals({name: releases[name] for name in staged})
        raise
    return {'sources': list(sources), 'bytes': sum(releases[name].signal_cache.nbytes for name in sources),
            'newly_staged_bytes': needed, 'staging_seconds': time.monotonic() - start,
            'available_memory_before_bytes': available, 'reserve_bytes': reserve,
            'storage': 'process_owned_readonly_FP32_RAM', 'sample_order_and_values_unchanged': True}


def release_source_signals(releases):
    """Return to the unchanged verified memmaps before the six fold processes."""
    for release in releases.values():
        if hasattr(release, '_posttrain_disk_cache'):
            release.signal_cache = release._posttrain_disk_cache
            del release._posttrain_disk_cache


def validate_parameters(parameters):
    bounds = {"posttrain_lr": (1e-6, 2e-4), "temperature": (0.03, 0.3),
              "posttrain_weight_decay": (0, 1e-2), "warmup_epochs": (0, 8),
              "gradient_clip": (0.5, 5)}
    if set(parameters) != set(bounds):
        raise ValueError("Posttrain parameter names differ from frozen bounds")
    for key, (low, high) in bounds.items():
        value = parameters[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Parameter out of bounds: {key}")
    if int(parameters["warmup_epochs"]) != parameters["warmup_epochs"]:
        raise ValueError("Warmup must be an integer epoch count")


def learning_rate_multiplier(step, total_steps, warmup_steps):
    if warmup_steps and step < warmup_steps:
        return (step + 1) / warmup_steps
    progress = min(1.0, max(0.0, (step - warmup_steps) / max(1, total_steps - warmup_steps)))
    return 0.5 * (1 + math.cos(math.pi * progress))


def _write_failure_context(directory, *, target, sources, epoch, step, completed_updates,
                           stage, selected_rows, tensors, tokens, model, representation,
                           optimizer_step_completed, error):
    """Small error-only summaries; never store signal, activation or weight payloads."""
    def summary(value, source):
        value = value.detach()
        finite = torch.isfinite(value)
        finite_count = int(finite.sum().item())
        maximum = float(value[finite].abs().max().item()) if finite_count else None
        return {"source": source, "shape": list(value.shape), "dtype": str(value.dtype),
                "device": str(value.device), "elements": value.numel(),
                "finite_count": finite_count, "nonfinite_count": value.numel() - finite_count,
                "finite_absmax": maximum}

    with torch.no_grad():
        invalid = []
        for prefix, module in (("encoder", model), ("representation", representation)):
            for name, parameter in module.named_parameters():
                if not torch.isfinite(parameter).all():
                    invalid.append(prefix + "." + name)
        report = {
            "schema_version": "1.0", "kind": "posttrain_failure_context",
            "target": target, "source_names": list(sources), "epoch": epoch,
            "step": step, "step_indexing": "zero_based", "completed_updates": completed_updates,
            "stage": stage, "optimizer_step_completed": optimizer_step_completed,
            "exception_type": type(error).__name__,
            "selected_rows": {name: rows.tolist() for name, rows in selected_rows.items()},
            "input_summaries": [summary(value, sources[index]) for index, value in enumerate(tensors)],
            "token_summaries": ([] if tokens is None else
                [summary(tokens[index * 64:(index + 1) * 64], name)
                 for index, name in enumerate(sources)]),
            "parameter_nonfinite_names": invalid[:512],
            "parameter_nonfinite_count": len(invalid),
            "configured_forward_autocast_dtype": "torch.bfloat16",
            "precision_boundary": "Tensor dtypes do not prove worker-thread autocast dtype.",
        }
    atomic_json(Path(directory) / "failure_context.json", report)


def run_posttrain(target, releases, parameters, directory, *, device, identity, deadline, smoke_steps=None):
    if smoke_steps is not None and (type(smoke_steps) is not int or smoke_steps != PROBE_WARMUP_STEPS + PROBE_MEASURED_STEPS):
        raise ValueError("Formal-path smoke requires exactly three warmup and twenty measured discarded updates")
    validate_parameters(parameters)
    directory = Path(directory)
    if (directory / "COMPLETE.json").is_file():
        verify_completion(directory, identity)
        from artifact_io import read_json
        return read_json(directory / "training.json")
    seed_process(42)
    device = require_cuda(device)
    sources = lodo_sources(target, posttrain_split="all")
    ram_staging = stage_source_signals(releases, sources, deadline=deadline)
    model, positions, initialization = load_official(releases[sources[0]].channel_names, device=device)
    if any(releases[name].channel_names != initialization["channel_names"] for name in sources):
        raise ValueError("Source montage order differs; separate positions must be implemented and reviewed")
    representation = build_representation((60, 11, 512)).to(device)
    parallel = parallel_model(model)
    builders = {name: StimulusBatchBuilder(source=name, target=target, subject_ids=releases[name].subjects,
                                          session_ids=releases[name].sessions, trial_indices=releases[name].trials) for name in sources}
    diagnostics = {name: builders[name].diagnostics() for name in sources}
    optimizer = torch.optim.Adam(list(model.parameters()) + list(representation.parameters()),
                                 lr=parameters["posttrain_lr"], weight_decay=parameters["posttrain_weight_decay"],
                                 betas=(0.9, 0.999), eps=1e-8)
    steps_per_epoch = max(math.ceil(len(releases[name].labels) / 64) for name in sources)
    total_steps = 40 * steps_per_epoch
    warmup_steps = int(parameters["warmup_epochs"]) * steps_per_epoch
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step: learning_rate_multiplier(step, total_steps, warmup_steps))
    telemetry = Telemetry(device)
    records, global_step = [], 0
    smoke_losses, smoke_gradients, smoke_precisions = [], [], []
    smoke_times = []
    for epoch in range(1, 41):
        model.train()
        representation.train()
        rng = np.random.default_rng(42 + epoch * 7919)
        epoch_losses, epoch_gradients, duplicate_rows = [], [], 0
        source_loss_sum = torch.zeros(5, device=device, dtype=torch.float64)
        start_epoch = time.monotonic()
        for step in range(steps_per_epoch):
            check_deadline(deadline)
            start_step = time.monotonic()
            stage = "zero_grad"
            selected_rows, tensors, tokens = {}, [], None
            optimizer_step_completed = False
            try:
                optimizer.zero_grad(set_to_none=True)
                # Each source is one complete batch64 on one local replica. Gather
                # tokens, then construct FIVE separate objectives with 62 negatives.
                for name in sources:
                    stage = "sample_batch"
                    rows = builders[name].sample_batch(batch_size=64, rng=rng).numpy()
                    selected_rows[name] = rows
                    duplicate_rows += 64 - len(np.unique(rows))
                    start_read = time.monotonic()
                    stage = "load_signals"
                    values = releases[name].load_signals(rows)
                    telemetry.data_wait_seconds += time.monotonic() - start_read
                    stage = "input_copy"
                    tensor, before, after = telemetry.copy(values)
                    tensors.append(tensor)
                    after.synchronize()
                    telemetry.h2d_seconds += before.elapsed_time(after) / 1000
                    telemetry.samples += 64
                stage = "encoder_forward"
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    tokens = parallel(prepare_input(torch.cat(tensors)), positions.expand(320, -1, -1))
                if smoke_steps is not None:
                    observed = getattr(parallel, "last_replica_autocast", [])
                    if len(observed) != 5 or any(
                            r.get("replica_index") != i or r.get("autocast_enabled") is not True
                            or r.get("autocast_dtype") != "torch.bfloat16" for i, r in enumerate(observed)):
                        raise ValueError("Formal training path did not preserve all five BF16 replicas")
                    smoke_precisions.append([dict(r) for r in observed])
                stage = "loss"
                loss, losses = separate_source_losses(tokens, representation, parameters["temperature"])
                if not torch.isfinite(loss):
                    raise ValueError("Source-separated contrastive objective failed")
                stage = "backward"
                loss.backward()
                stage = "gradient_clip"
                grad = torch.nn.utils.clip_grad_norm_(list(model.parameters()) + list(representation.parameters()), parameters["gradient_clip"], error_if_nonfinite=True)
                if not torch.isfinite(grad) or grad <= 0:
                    raise ValueError("Posttrain encoder gradient is zero or nonfinite")
                stage = "optimizer_step"
                optimizer.step()
                optimizer_step_completed = True
                stage = "scheduler_step"
                scheduler.step()
                stage = "update_metrics"
                telemetry.steps += 1
                epoch_losses.append(float(loss.detach().cpu()))
                source_loss_sum += losses.double()
                epoch_gradients.append(float(grad.cpu()))
                global_step += 1
                if smoke_steps is not None:
                    # Time the complete formal update, including sampling, RAM
                    # reads, copies, assertions, optimizer, scheduler and metrics.
                    for device_id in parallel.device_ids:
                        torch.cuda.synchronize(device_id)
                    smoke_times.append(time.monotonic() - start_step)
                    smoke_losses.append(epoch_losses[-1])
                    smoke_gradients.append(epoch_gradients[-1])
                    if global_step == smoke_steps:
                        report = {"passed": True, "updates_completed": global_step,
                                  "training_budget_steps": total_steps, "research_rounds": 0,
                                  "test_evaluations": 0, "optimizer_states_reused": False,
                                  "losses": smoke_losses, "gradient_norms": smoke_gradients,
                                  "replica_autocast_observations": smoke_precisions,
                                  "ram_staging": ram_staging,
                                  "timing": {"warmup_steps": PROBE_WARMUP_STEPS,
                                             "measured_steps": len(smoke_times) - PROBE_WARMUP_STEPS,
                                             "step_seconds": smoke_times[PROBE_WARMUP_STEPS:],
                                             "warmup_step_seconds": smoke_times[:PROBE_WARMUP_STEPS],
                                             "scope": "Complete formal update including sampling, IO, H2D, numerics, optimizer and scheduler; one-time staging and serial diagnostic excluded"},
                                  "lr_after_last_update": optimizer.param_groups[0]["lr"],
                                  "scope": "Exact formal sampler, warmup, optimizer and forward path; states discarded"}
                        atomic_json(directory / "training_path_smoke.json", report)
                        return report
                telemetry.step_seconds += time.monotonic() - start_step
                if step % 50 == 0:
                    telemetry.utilization_samples.append({"epoch": epoch, "step": step, **utilization(device)})
            except Exception as error:
                try:
                    _write_failure_context(
                        directory, target=target, sources=sources, epoch=epoch, step=step,
                        completed_updates=global_step, stage=stage, selected_rows=selected_rows,
                        tensors=tensors, tokens=tokens, model=model, representation=representation,
                        optimizer_step_completed=optimizer_step_completed, error=error)
                except Exception:
                    # Diagnostic collection/storage failure must never replace the cause.
                    pass
                raise
        records.append({"epoch": epoch, "updates": steps_per_epoch, "loss_mean": float(np.mean(epoch_losses)),
                        "loss_first": epoch_losses[0], "loss_last": epoch_losses[-1],
                        "gradient_norm_mean_before_clip": float(np.mean(epoch_gradients)),
                        "lr_end": optimizer.param_groups[0]["lr"], "duplicate_sampled_rows": duplicate_rows,
                        "source_loss_mean": dict(zip(sources,(source_loss_sum/steps_per_epoch).cpu().tolist(),strict=True)),
                        "wall_seconds": time.monotonic() - start_epoch})
        atomic_json(directory / "epochs.json", records)
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    atomic_torch_save(directory / "encoder.pt", state)
    report = {"identity": identity, "initialization": initialization, "target": target,
              "sources": list(sources), "posttrain_split": "all", "seed": 42,
              "parameters": parameters, "epochs_requested": 40, "epochs_completed": len(records),
              "updates_requested": total_steps, "updates_completed": global_step,
              "stop_reason": "fixed_epoch_budget", "checkpoint_selection": "last_epoch_40",
              "contrastive_batch_per_source": 64, "negatives_per_anchor": 62,
              "source_losses_per_update": 5, "gradient_accumulation": "five independent source losses averaged, not enlarged InfoNCE batch",
              "source_forward_devices": [0, 1, 2, 3, 4], "physical_forward_rows": 320,
              "cross_source_negatives": False,
              "objective": "stimulus_cross_subject_InfoNCE_only", "representation_state_exported": False,
              "pairing": diagnostics, "epoch_records": records, "telemetry": telemetry.report(),
              "ram_staging": ram_staging,
              "test_evaluations": 0}
    if len(records) != 40 or global_step != total_steps:
        raise ValueError("Posttrain incomplete; no completion marker")
    atomic_json(directory / "training.json", report)
    publish_completion(directory, identity, ["encoder.pt", "training.json", "epochs.json"])
    return report
