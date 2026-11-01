"""Finite cost estimates from observed cloud smoke, before a long worker phase."""
from __future__ import annotations

import math
import time
from statistics import median

from artifact_io import atomic_json
from evaluation_contract import final_conditions


def forecast(smoke, releases, target, folds, phase, *, deadline, output, round_limit=2, training_probe=None):
    posttrain_seconds = 0.0
    timing = None
    if phase == 'development':
        if not training_probe or training_probe.get('passed') is not True:
            raise ValueError('Development forecast requires a successful formal-path throughput probe')
        timing = training_probe.get('timing', {})
        samples = timing.get('step_seconds', [])
        if (timing.get('warmup_steps', 0) < 3 or len(samples) < 20
                or timing.get('measured_steps') != len(samples)
                or training_probe.get('updates_completed') != timing['warmup_steps'] + len(samples)
                or any(not math.isfinite(value) or value <= 0 for value in samples)):
            raise ValueError('Formal forecast requires at least three warmup and twenty finite complete update timings')
        # A conservative nearest-rank p90 retains observed slow complete updates;
        # no synthetic speedup or timing from the diagnostic path is substituted.
        posttrain_seconds = sorted(samples)[math.ceil(0.9 * len(samples)) - 1]
    observed={"posttrain_update":posttrain_seconds,
              "ft_step":median(smoke["ft_batch128_step_seconds"]),
              "lp_step":median(smoke["lp_head_batch128_step_seconds"]),
              "lp_statistics":smoke["lp_statistics_batch128_seconds"],
              "encoder_inference":smoke["encoder_inference_batch128_seconds"]}
    if any(not math.isfinite(value) or value<=0 for key,value in observed.items() if key != 'posttrain_update'):
        raise ValueError("Throughput forecast needs actual finite positive measurements")
    train_batches=max(math.ceil(fold["train_n"]/128) for fold in folds)
    val_batches=max(math.ceil(fold["val_n"]/128) for fold in folds)
    extraction_batches=math.ceil(len(releases[target].labels)/128)
    # Six independently assigned GPUs cover folds in parallel. Worst fold is
    # used, with a named estimate margin for IO/checkpoint/validation overhead.
    features=extraction_batches*observed["encoder_inference"]
    lp_statistics=train_batches*observed["lp_statistics"]
    lp=100*(train_batches+val_batches)*observed["lp_step"]+lp_statistics
    ft=60*(train_batches*observed["ft_step"]+val_batches*observed["encoder_inference"])
    posttrain=0 if phase=="baseline" else 40*max(math.ceil(len(release.labels)/64) for name,release in releases.items() if name!=target)*observed["posttrain_update"]
    if phase == "final_test":
        # Already-trained conditions, each with six parallel folds. No
        # training epochs or posttraining are launched by this worker phase.
        test_batches = max(math.ceil(fold["test_n"]/128) for fold in folds)
        conditions = len(final_conditions(round_limit))
        features = conditions * extraction_batches * observed["encoder_inference"]
        lp = conditions * test_batches * observed["lp_step"]
        ft = conditions * test_batches * observed["encoder_inference"]
        posttrain = 0
    raw=features+lp+ft+posttrain
    estimate=raw*1.5
    remaining=max(0.0,deadline-time.time())
    report={"phase":phase,"target":target,"measured_batch_seconds":observed,
            "estimated_seconds":estimate,"margin_multiplier":1.5,
            "components_seconds_before_margin":{"feature_extraction":features,"lp":lp,"ft":ft,"posttrain":posttrain},
            "parallel_fold_processes":6,"worker_remaining_seconds":remaining,
            "fits_worker_bound":estimate<=remaining,
            "engineering_review_threshold_seconds":43200,
            "requires_engineering_review":estimate>43200,
            "posttrain_timing":timing,
            "posttrain_estimator":"formal_update_p90_after_3_warmup_at_least_20_measured" if timing else "not_applicable",
            "evidence_boundary":"Linear workload estimate from real smoke, not a completion claim or guaranteed ETA"}
    atomic_json(output,report)
    if estimate>remaining:
        raise TimeoutError(f"Complete {phase} estimate {estimate:.1f}s exceeds remaining worker bound {remaining:.1f}s; preserve real smoke and require scheduling/IO repair")
    if estimate>43200:
        raise TimeoutError(f"Complete {phase} estimate {estimate:.1f}s exceeds 12h; engineering review and measured repair required before long training")
    return report
