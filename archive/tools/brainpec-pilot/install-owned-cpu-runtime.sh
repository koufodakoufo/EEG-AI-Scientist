#!/usr/bin/env bash
set -euo pipefail
root=/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029
umask 077
export TMPDIR="$root/tmp" PIP_CACHE_DIR="$root/cache/pip"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR="$root/cache/matplotlib" XDG_CACHE_HOME="$root/cache/xdg"
wheel="$root/downloads/torch-2.6.0+cpu-cp310-cp310-linux_x86_64.whl"
test "$(sha256sum "$wheel" | cut -d' ' -f1)" = '35a9e78b7e4096968b54c1a198687b981569c50ae93e661aa430f9fd208da102'
# Public package hosts have verified direct campus access. This affects only pip.
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
  "$root/venv/bin/python" -B -m pip install --disable-pip-version-check --timeout 25 --retries 1 \
  --index-url https://pypi.org/simple "$wheel" numpy==2.2.6 scipy==1.15.3 scikit-learn==1.6.1 \
  pandas==2.2.3 PyWavelets==1.8.0 einops==0.8.1 mne==1.10.2 matplotlib==3.10.3 \
  pytest==8.4.0 PyYAML==6.0.2 psutil==7.0.0
"$root/venv/bin/python" -B -m pip freeze > "$root/evidence/requirements.lock.txt"
"$root/venv/bin/python" -B -c 'import torch,numpy,mne,sklearn; torch.set_num_threads(4); print({"torch":torch.__version__,"numpy":numpy.__version__,"mne":mne.__version__,"sklearn":sklearn.__version__,"cpu_probe":(torch.ones(2,device="cpu")+1).tolist()})'
du -sb "$root/venv" "$root/cache" > "$root/evidence/installed-runtime-storage.txt"
