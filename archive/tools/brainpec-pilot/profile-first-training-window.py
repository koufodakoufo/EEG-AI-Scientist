"""Bounded feasibility probe using only one predeclared training recording."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '4'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import mne
import numpy as np
import psutil
import torch
from eegfm.research_bench.real_data import CHANNELS, make_windows, load_cbramod, read_edf_header, compute_feature_panel


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Profile evidence already exists')
    process = psutil.Process()
    process.cpu_affinity(process.cpu_affinity()[:4])
    torch.set_num_threads(4)
    source = args.cache/'eegmat/Subject00_1.edf'
    header = read_edf_header(source)
    raw = mne.io.read_raw_edf(source,preload=True,verbose='ERROR')
    raw.pick(list(CHANNELS)).reorder_channels(list(CHANNELS))
    raw.resample(200,npad='auto',n_jobs=1,verbose='ERROR')
    x, indices = make_windows(raw.get_data(units='uV'),unit='uV',maximum=12)
    raw.close()
    x = x[:1]
    start = time.monotonic()
    model = load_cbramod(args.cache,threads=4)
    loaded = time.monotonic()
    acts = model.activations(x,layers=(6,12))
    end = time.monotonic()
    features = compute_feature_panel(x)
    report = {'status':'passed','scope':'one training window, no test access',
        'recording':'Subject00_1','source_window_index':indices[0], 'header':header,
        'checkpoint_strict_load':True,'input_shape':list(x.shape),'input_unit':'uV/100',
        'layers':{str(k):list(v.shape) for k,v in acts.items()},'features_shape':list(features.shape),
        'finite':bool(all(np.isfinite(a).all() for a in acts.values()) and np.isfinite(features).all()),
        'load_seconds':loaded-start,'forward_seconds':end-loaded,'feature_seconds':time.monotonic()-end,
        'rss_bytes':process.memory_info().rss,'torch':torch.__version__,'mne':mne.__version__,
        'numpy':np.__version__,'device':'cpu','threads':torch.get_num_threads()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','finite','load_seconds','forward_seconds','feature_seconds','rss_bytes','torch')}))


if __name__ == '__main__':
    main()
