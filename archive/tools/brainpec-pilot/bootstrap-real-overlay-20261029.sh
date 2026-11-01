#!/usr/bin/env bash
set -euo pipefail
base=/data/duandh/eegfm-stage-a-20261028
root="$base/brainpec-real-20261029"
source "$base/environment.sh"
umask 077
export TMPDIR="$root/tmp" PIP_CACHE_DIR="$root/cache/pip312"
export PYTHONDONTWRITEBYTECODE=1 TORCH_HOME="$root/cache/torch" HF_HOME="$root/cache/hf"
export XDG_CACHE_HOME="$root/cache/xdg" MPLCONFIGDIR="$root/cache/matplotlib"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 CUDA_VISIBLE_DEVICES=''
test "$(df --output=avail -B1 "$root" | tail -n1)" -gt 21474836480
test "$(df --output=avail -B1 /home/duandh | tail -n1)" -gt 4294967296
# Reuse installed runtime by reading it; write only to this run's owned overlay.
# Every model/worker process keeps bytecode disabled and shared runtime mounted RO.
readonly_python=/mnt/dataset4/ddh/conda_envs/daily-emo-eeg/bin/python
if [ ! -e "$root/cpu-env312/bin/python" ]; then
  "$readonly_python" -I -B -m venv --system-site-packages "$root/cpu-env312"
fi
"$root/cpu-env312/bin/python" -B -m pip install --disable-pip-version-check --timeout 25 --retries 1 scikit-learn==1.6.1 PyWavelets==1.8.0 einops==0.8.1 pytest==8.4.0 PyYAML==6.0.2
"$root/cpu-env312/bin/python" -B -m pip freeze > "$root/evidence/requirements-overlay.lock.txt"
"$root/cpu-env312/bin/python" -B -c 'import torch,numpy,mne,sklearn,einops,pywt; torch.set_num_threads(4); print({"torch":torch.__version__,"numpy":numpy.__version__,"mne":mne.__version__,"sklearn":sklearn.__version__,"cpu_probe":(torch.ones(2,device="cpu")+1).tolist()})'
