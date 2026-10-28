"""Real TiONE-only weight/gradient/shape/throughput gate, before R0/R1/R2."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import time

import numpy as np
import torch

from artifact_io import atomic_json, check_deadline
from data_contract import lodo_sources
from gpu_diagnostics import Telemetry, require_cuda, seed_process, utilization
from isa_builder import StimulusBatchBuilder
from isa_loss import flatten_normalize, paired_info_nce
from isa_representation import build_representation
from official_model import build_head, flatten_for_evaluation, load_official, prepare_input
from source_parallel import parallel_model, separate_source_losses


def serial_source_backward(model, representation, positions, inputs, temperature, *, mixed=False, deadline=None):
    """Diagnostic reference: preserve source batches and sum their mean gradients."""
    losses = []
    for values in inputs:
        if deadline is not None:
            check_deadline(deadline)
        context = torch.autocast("cuda", dtype=torch.bfloat16) if mixed else nullcontext()
        with context:
            tokens = model(prepare_input(values), positions.expand(len(values), -1, -1))
        loss, _ = separate_source_losses(tokens, representation, temperature,
                                         source_count=1, batch_size=len(values))
        (loss / len(inputs)).backward()
        losses.append(loss.detach())
    return torch.stack(losses).mean()


def source_gradient_equivalence(model, parallel, representation, positions, inputs, temperature, *, deadline=None):
    """FP32 eval-with-gradients gate; not a training RNG/checkpoint equivalence claim."""
    if len(inputs) != 5 or any(len(value) != len(inputs[0]) for value in inputs):
        raise ValueError("Gradient gate requires five equal source batches")
    parameters = {"encoder." + name: value for name, value in model.named_parameters() if value.requires_grad}
    parameters.update({"representation." + name: value for name, value in representation.named_parameters()
                       if value.requires_grad})
    modes = model.training, representation.training
    try:
        # Gradients remain enabled; eval disables training-only positional or
        # dropout randomness rather than comparing unrelated device RNG draws.
        model.eval()
        representation.eval()
        model.zero_grad(set_to_none=True)
        representation.zero_grad(set_to_none=True)
        serial_loss = serial_source_backward(model, representation, positions, inputs, temperature, deadline=deadline)
        reference = {name: None if value.grad is None else value.grad.detach().cpu().clone()
                     for name, value in parameters.items()}
        model.zero_grad(set_to_none=True)
        representation.zero_grad(set_to_none=True)
        if deadline is not None:
            check_deadline(deadline)
        values = torch.cat(inputs)
        tokens = parallel(prepare_input(values), positions.expand(len(values), -1, -1))
        parallel_loss, _ = separate_source_losses(tokens, representation, temperature, batch_size=len(inputs[0]))
        parallel_loss.backward()
        if not torch.allclose(serial_loss, parallel_loss, rtol=1e-4, atol=1e-5):
            raise ValueError("Multi-GPU source loss differs from serial FP32 reference")
        checked, unused, materialized_unused, maximum = 0, [], [], 0.0
        reference_squared, difference_squared = 0.0, 0.0
        for name, parameter in parameters.items():
            expected = reference[name]
            actual = None if parameter.grad is None else parameter.grad.detach().cpu()
            if expected is None and actual is None:
                unused.append(name)
                continue
            # REVE token forward never uses its attention-pooling CLS query.
            # DataParallel's coalesced Broadcast backward can materialize zero
            # for this unused output. No other presence mismatch is accepted.
            if (name == "encoder.cls_query_token" and expected is None and actual is not None
                    and torch.isfinite(actual).all() and torch.count_nonzero(actual) == 0):
                unused.append(name)
                materialized_unused.append(name)
                continue
            if expected is None or actual is None:
                raise ValueError(f"Multi-GPU gradient presence differs: {name}")
            if (not torch.isfinite(expected).all() or not torch.isfinite(actual).all()
                    or not torch.allclose(expected, actual, rtol=1e-3, atol=1e-5)):
                raise ValueError(f"Multi-GPU gradient differs from serial FP32 reference: {name}")
            difference = actual - expected
            maximum = max(maximum, float(difference.abs().max()))
            reference_squared += float(expected.square().sum())
            difference_squared += float(difference.square().sum())
            checked += 1
        if not checked or not np.isfinite(reference_squared) or reference_squared <= 0:
            raise ValueError("Serial reference has no nonzero trainable gradient")
        return {"passed": True, "source_count": 5, "batch_per_source": len(inputs[0]),
                "mode": "eval_with_gradients", "checkpoint_recomputation_compared": False,
                "training_rng_equivalence_claimed": False,
                "precision": "FP32", "serial_loss": float(serial_loss.detach().cpu()),
                "parallel_loss": float(parallel_loss.detach().cpu()), "gradient_parameters": checked,
                "unused_parameters": unused, "materialized_unused_parameters": materialized_unused,
                "optimizer_update_equivalence_claimed": False,
                "maximum_gradient_absolute_error": maximum,
                "serial_gradient_l2_norm": reference_squared ** 0.5,
                "gradient_relative_l2_error": (difference_squared / reference_squared) ** 0.5,
                "loss_rtol": 1e-4, "loss_atol": 1e-5, "gradient_rtol": 1e-3, "gradient_atol": 1e-5}
    finally:
        model.zero_grad(set_to_none=True)
        representation.zero_grad(set_to_none=True)
        model.train(modes[0])
        representation.train(modes[1])


def synchronize_sources(parallel):
    for device_id in parallel.device_ids:
        torch.cuda.synchronize(device_id)


def smoke(target, releases, parameters, output, *, device, deadline):
    device = require_cuda(device)
    seed_process(42)
    source_names = lodo_sources(target, posttrain_split="all")
    from posttrain import stage_source_signals
    ram_staging = stage_source_signals(releases, source_names, deadline=deadline)
    atomic_json(Path(output) / 'source_ram_staging.json', ram_staging)
    release = releases[source_names[0]]
    model, positions, identity = load_official(release.channel_names, device=device)
    builder = StimulusBatchBuilder(source=source_names[0], target=target, subject_ids=release.subjects,
                                  session_ids=release.sessions, trial_indices=release.trials)
    telemetry = Telemetry(device)
    rng = np.random.default_rng(42)
    check_deadline(deadline)
    # Small paired input permits an actual FP32/BF16 numerical comparison.
    rows = builder.sample_batch(batch_size=8, rng=rng).numpy()
    values = release.load_signals(rows)
    tensor, _, _ = telemetry.copy(values)
    model.eval()
    with torch.no_grad():
        reference = model(prepare_input(tensor), positions.expand(8, -1, -1))
        with torch.autocast("cuda", dtype=torch.bfloat16):
            mixed = model(prepare_input(tensor), positions.expand(8, -1, -1))
    if tuple(reference.shape) != (8, 60, 11, 512):
        raise ValueError("Real official token geometry failed")
    reference_loss = paired_info_nce(flatten_normalize(reference), temperature=0.1)[0]
    mixed_loss = paired_info_nce(flatten_normalize(mixed), temperature=0.1)[0]
    if not torch.allclose(reference_loss, mixed_loss, rtol=0.02, atol=0.03):
        raise ValueError("BF16 contrastive numerics differ from FP32 beyond the frozen gate")
    del reference, mixed, tensor
    parallel = parallel_model(model)
    # Real multi-GPU/serial equivalence on the same controlled released rows.
    small_inputs = []
    for name in source_names:
        source = releases[name]
        b = StimulusBatchBuilder(source=name, target=target, subject_ids=source.subjects,
                                session_ids=source.sessions, trial_indices=source.trials)
        small_inputs.append(torch.as_tensor(source.load_signals(b.sample_batch(batch_size=8, rng=rng).numpy()), device=device))
    with torch.no_grad():
        serial = torch.cat([model(prepare_input(value), positions.expand(8, -1, -1)) for value in small_inputs])
        distributed = parallel(prepare_input(torch.cat(small_inputs)), positions.expand(40, -1, -1))
    if not torch.allclose(serial, distributed, rtol=1e-4, atol=1e-4):
        raise ValueError("Multi-GPU source forwards differ from serial FP32 output")
    parallel_error = float((serial-distributed).abs().max().cpu())
    representation = build_representation((60, 11, 512)).to(device)
    gradient_equivalence = source_gradient_equivalence(
        model, parallel, representation, positions, small_inputs, parameters["temperature"], deadline=deadline)
    del serial, distributed, small_inputs
    model.train()
    representation.train()
    trainable = list(model.parameters()) + list(representation.parameters())
    optimizer = torch.optim.Adam(trainable, lr=parameters["posttrain_lr"], weight_decay=parameters["posttrain_weight_decay"])
    posttrain_times, gradients = [], []
    replica_autocast_observations = []
    serial_compute_times, parallel_compute_times = [], []
    serial_diagnostic_times, posttrain_wall_times = [], []
    # Match posttrain: pairing setup is once per source, outside update timing.
    pair_builders = {
        name: StimulusBatchBuilder(source=name, target=target,
                                   subject_ids=releases[name].subjects,
                                   session_ids=releases[name].sessions,
                                   trial_indices=releases[name].trials)
        for name in source_names
    }
    # Actual batch64 per-source negatives. Smoke weights are discarded afterward.
    for update in range(3):
        check_deadline(deadline)
        start = time.monotonic()
        optimizer.zero_grad(set_to_none=True)
        tensors = []
        for name in source_names:
            source = releases[name]
            selected = pair_builders[name].sample_batch(batch_size=64, rng=rng).numpy()
            before_read = time.monotonic()
            batch_values = source.load_signals(selected)
            telemetry.data_wait_seconds += time.monotonic() - before_read
            tensor, before, after = telemetry.copy(batch_values)
            tensors.append(tensor)
            after.synchronize()
            telemetry.h2d_seconds += before.elapsed_time(after) / 1000
            telemetry.samples += 64
        # Reuse these exact rows and weights; this diagnostic does not step the
        # optimizer or alter source sampling. Timings are observations only.
        # The extra baseline must not advance the existing parallel smoke's
        # CPU/device stochastic streams. Training behavior itself stays enabled.
        # Exclude the entire added diagnostic interval from the training ETA,
        # including RNG save/restore, synchronization and gradient cleanup.
        diagnostic_start = time.monotonic()
        with torch.random.fork_rng(devices=parallel.device_ids):
            synchronize_sources(parallel)
            baseline_start = time.monotonic()
            serial_source_backward(model, representation, positions, tensors, parameters["temperature"],
                                   mixed=True, deadline=deadline)
            synchronize_sources(parallel)
            serial_compute_times.append(time.monotonic() - baseline_start)
        optimizer.zero_grad(set_to_none=True)
        diagnostic_seconds = time.monotonic() - diagnostic_start
        serial_diagnostic_times.append(diagnostic_seconds)
        parallel_start = time.monotonic()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            tokens = parallel(prepare_input(torch.cat(tensors)), positions.expand(320, -1, -1))
        observed = getattr(parallel, "last_replica_autocast", [])
        if (len(observed) != 5 or any(
                item.get("replica_index") != index or
                item.get("autocast_enabled") is not True or
                item.get("autocast_dtype") != "torch.bfloat16"
                for index, item in enumerate(observed))):
            raise ValueError("Posttrain replica autocast must observe BF16 enabled on all five replicas")
        replica_autocast_observations.append([dict(item) for item in observed])
        loss, _ = separate_source_losses(tokens, representation, parameters["temperature"])
        loss.backward()
        synchronize_sources(parallel)
        parallel_compute_times.append(time.monotonic() - parallel_start)
        norm = torch.nn.utils.clip_grad_norm_(trainable, parameters["gradient_clip"], error_if_nonfinite=True)
        if norm <= 0 or not torch.isfinite(norm):
            raise ValueError("Real REVE encoder gradient failed")
        gradients.append(float(norm.cpu()))
        optimizer.step()
        torch.cuda.synchronize(device)
        posttrain_wall_times.append(time.monotonic() - start)
        posttrain_times.append(posttrain_wall_times[-1] - diagnostic_seconds)
        telemetry.steps += 1
        telemetry.step_seconds += posttrain_times[-1]
        telemetry.utilization_samples.append(utilization(device))
    # Full flatten MLP and batch128 get a real CUDA/gradient/memory check too.
    del model, parallel, optimizer, tokens, tensors, loss, norm, representation, trainable
    torch.cuda.empty_cache()
    model, positions, ft_initialization = load_official(releases[target].channel_names, device=device)
    head = build_head("ft", 337920, len(np.unique(releases[target].labels))).to(device)
    optimizer = torch.optim.AdamW(list(model.parameters())+list(head.parameters()), lr=1e-5, weight_decay=1e-4)
    ft_times = []
    target_release = releases[target]
    for _ in range(2):
        check_deadline(deadline)
        start = time.monotonic()
        from artifact_io import read_json
        fold = read_json(Path(__file__).resolve().parent / "split_manifest.json")["targets"][target]["folds"][0]
        selected = target_release.partitions(fold)["train"][:128]
        tensor, _, _ = telemetry.copy(target_release.load_signals(selected))
        labels = torch.as_tensor(target_release.labels[selected], device=device, dtype=torch.long)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            tokens = model(prepare_input(tensor), positions.expand(128, -1, -1))
        logits = head(flatten_for_evaluation(tokens))
        loss = torch.nn.functional.cross_entropy(logits, labels)
        if not torch.isfinite(loss):
            raise ValueError("Real FT head numerical gate failed")
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(list(model.parameters())+list(head.parameters()), 1.0, error_if_nonfinite=True)
        if norm <= 0:
            raise ValueError("Real FT gradient gate failed")
        optimizer.step()
        torch.cuda.synchronize(device)
        ft_times.append(time.monotonic() - start)
    # Measure actual inference and LP head costs instead of assuming their ETA.
    model.eval()
    torch.cuda.synchronize(device)
    start = time.monotonic()
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
        tokens = model(prepare_input(tensor), positions.expand(128,-1,-1))
    features = flatten_for_evaluation(tokens).detach()
    torch.cuda.synchronize(device)
    encoder_inference_seconds = time.monotonic()-start
    del head, optimizer, loss, logits, norm
    # Measure the same disk-backed FP32 feature read, CPU normalization and
    # pinned H2D copy used by LP, rather than timing a GPU-resident head alone.
    lp_probe_path = Path(output) / "lp_smoke_features.npy"
    np.save(lp_probe_path, features.cpu().numpy())
    lp_cache = np.load(lp_probe_path, mmap_mode="r")
    from evaluation_contract import training_statistics
    start = time.monotonic()
    mean, std = training_statistics(lp_cache, np.arange(128))
    lp_statistics_seconds = time.monotonic()-start
    lp_head = build_head("lp",337920,len(np.unique(target_release.labels))).to(device)
    lp_optimizer = torch.optim.Adam(lp_head.parameters(),lr=1e-3,weight_decay=1e-4)
    lp_times=[]
    for _ in range(2):
        check_deadline(deadline)
        lp_optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(device)
        start=time.monotonic()
        values=(np.asarray(lp_cache[np.arange(128)],dtype=np.float32)-mean)/std
        lp_tensor,_,_=telemetry.copy(values)
        lp_loss=torch.nn.functional.cross_entropy(lp_head(lp_tensor),labels)
        if not torch.isfinite(lp_loss):
            raise ValueError("Real LP loss numerical gate failed")
        lp_loss.backward()
        if not all(torch.isfinite(parameter.grad).all() for parameter in lp_head.parameters()):
            raise ValueError("Real LP head gradient numerical gate failed")
        lp_optimizer.step()
        torch.cuda.synchronize(device)
        lp_times.append(time.monotonic()-start)
    telemetry_report = telemetry.report()
    telemetry_report['prefetch'] = 'process-owned decoded read-only FP32 RAM; pinned selected CPU batches'
    report = {"passed": True, "level": "E0_smoke", "research_rounds": 0,
              "official_initialization": identity, "ft_official_initialization": ft_initialization,
              "token_shape": [8, 60, 11, 512],
              "fp32_loss": float(reference_loss.cpu()), "bf16_loss": float(mixed_loss.cpu()),
              "gradient_norms": gradients, "posttrain_step_seconds": posttrain_times,
              "posttrain_replica_autocast_observations": replica_autocast_observations,
              "parallel_serial_fp32_max_error": parallel_error,
              "parallel_serial_gradient_equivalence": gradient_equivalence,
              "source_throughput_observation": {
                  "serial_forward_backward_seconds": serial_compute_times,
                  "parallel_forward_backward_seconds": parallel_compute_times,
                  "serial_diagnostic_total_seconds": serial_diagnostic_times,
                  "posttrain_observed_wall_seconds": posttrain_wall_times,
                  "median_speedup_after_first_pair": float(np.median(serial_compute_times[1:]) / np.median(parallel_compute_times[1:])),
                  "batch_per_source": 64, "source_count": 5, "device_ids": [0, 1, 2, 3, 4],
                  "scope": "same staged tensors and parameter values; BF16 forward and FP32 source losses; optimizer excluded",
                  "mode": "train_with_checkpointing", "baseline_rng_restored": True,
                  "training_stochastic_equivalence_claimed": False,
                  "first_pair_excluded_as_warmup": True, "speedup_threshold": None,
                  "posttrain_step_seconds_includes_serial_diagnostic": False,
                  "posttrain_step_seconds_scope": "IO, H2D, parallel forward/backward and optimizer; full serial diagnostic interval excluded"},
              "source_gpu_replicas": 5, "cross_source_negatives": False,
              "ram_staging": ram_staging,
              "ft_batch128_step_seconds": ft_times, "posttrain_batch_per_source": 64,
              "encoder_inference_batch128_seconds": encoder_inference_seconds,
              "lp_head_batch128_step_seconds": lp_times,
              "lp_statistics_batch128_seconds": lp_statistics_seconds,
              "lp_smoke_scope": "real train-row features; disk read, CPU scaling, pinned H2D and FP32 head; discarded smoke states",
              "negatives_per_anchor": 62, "ft_batch": 128,
              "telemetry": telemetry_report, "smoke_weights_reused": False, "test_evaluations": 0}
    # Success is reached only after all real checks above. No bootstrap caller runs this.
    atomic_json(Path(output) / "cuda_smoke.json", report)
    del model, lp_head, lp_optimizer, features, tokens, tensor, lp_cache, lp_tensor, lp_loss
    lp_probe_path.unlink()
    torch.cuda.empty_cache()
    return report
