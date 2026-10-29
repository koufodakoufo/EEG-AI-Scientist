#!/usr/bin/env bash
set -euo pipefail
base=/data/duandh/eegfm-stage-a-20261028
root="$base/brainpec-real-20261029"
source "$base/environment.sh"
umask 077
mkdir -p "$root"/{cache,tmp,downloads,evidence,private,episodes,controls}
export TMPDIR="$root/tmp" PIP_CACHE_DIR="$root/cache/pip"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4
test "$(df --output=avail -B1 "$root" | tail -n1)" -gt 21474836480
test "$(df --output=avail -B1 /home/duandh | tail -n1)" -gt 4294967296
if [ ! -e "$root/venv/bin/python" ]; then
  "$base/venv/bin/python" -m venv --without-pip "$root/venv"
fi
if ! "$root/venv/bin/python" -m pip --version >/dev/null 2>&1; then
  "$base/venv/bin/python" -m pip --python "$root/venv/bin/python" install --disable-pip-version-check --timeout 25 --retries 1 pip
fi
"$root/venv/bin/python" -m pip install --disable-pip-version-check --timeout 25 --retries 1 'torch==2.6.0' --index-url https://download.pytorch.org/whl/cpu
"$root/venv/bin/python" -m pip install --disable-pip-version-check --timeout 25 --retries 1 numpy==2.2.6 scipy==1.15.3 scikit-learn==1.6.1 pandas==2.2.3 PyWavelets==1.8.0 einops==0.8.1 mne==1.10.2 matplotlib==3.10.3 pytest==8.4.0 PyYAML==6.0.2
"$root/venv/bin/python" -m pip freeze > "$root/evidence/requirements.lock.txt"
du -sb "$root/cache" "$root/venv" > "$root/evidence/bootstrap-storage.txt"
