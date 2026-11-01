#!/usr/bin/env bash
# Owned, CPU-only infrastructure setup; no shared environment or dataset writes.
set -euo pipefail
root=/home/duandh/projects/EEG-AI-Scientist-20261030
umask 077
test "$(id -u)" = 1027
test -d "$root" && test ! -L "$root"
test "$(stat -c %u "$root")" = "$(id -u)"
test "$(stat -c %a "$root")" = 700
for directory in downloads runtime source cache tmp evidence bin cache/home cache/pip cache/huggingface cache/xdg; do
  target="$root/$directory"
  test ! -L "$target"
  if [ -e "$target" ]; then test "$(stat -c %u "$target")" = "$(id -u)"; fi
  mkdir -p "$target"
done
cat > "$root/environment.sh" <<'ENV'
export VOLCANO_ROOT=/home/duandh/projects/EEG-AI-Scientist-20261030
export HOME="$VOLCANO_ROOT/cache/home"
export TMPDIR="$VOLCANO_ROOT/tmp" TMP="$VOLCANO_ROOT/tmp" TEMP="$VOLCANO_ROOT/tmp"
export XDG_CACHE_HOME="$VOLCANO_ROOT/cache/xdg" PIP_CACHE_DIR="$VOLCANO_ROOT/cache/pip"
export PIP_CONFIG_FILE=/dev/null
export HF_HOME="$VOLCANO_ROOT/cache/huggingface" TORCH_HOME="$VOLCANO_ROOT/cache/torch"
export MPLCONFIGDIR="$VOLCANO_ROOT/cache/matplotlib"
export CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export PATH="$VOLCANO_ROOT/venv/bin:$PATH"
unset PYTHONPATH PYTHONHOME
ENV
source "$root/environment.sh"
test "$(sha256sum "$root/downloads/python.tar.gz" | cut -d' ' -f1)" = ce4f6d0a6cfdb3bed6e44c2f9affd85943c76a42e25ad3a259002f31d6fb8a20
if [ ! -x "$root/runtime/python/bin/python3.12" ]; then
  test -z "$(ls -A "$root/runtime")"
  tar --no-same-owner -xzf "$root/downloads/python.tar.gz" -C "$root/runtime"
fi
if [ ! -x "$root/venv/bin/python" ]; then
  test ! -e "$root/venv"
  "$root/runtime/python/bin/python3.12" -m venv "$root/venv"
fi
wheel="$root/downloads/torch-2.6.0+cpu-cp312-cp312-linux_x86_64.whl"
"$root/venv/bin/python" -B -c 'import hashlib,json,pathlib,sys; p=pathlib.Path(sys.argv[1]); m=json.loads((p.parent/"wheel-source.json").read_text()); assert p.stat().st_size==m["bytes"] and hashlib.sha256(p.read_bytes()).hexdigest()==m["sha256"]' "$wheel"
if [ -f "$root/evidence/dependency-plan.json" ]; then
  "$root/venv/bin/python" -B "$root/bin/volcano_acquire_dependencies.py" --verify-plan
else
  "$root/venv/bin/python" -B "$root/bin/volcano_acquire_dependencies.py"
fi
"$root/venv/bin/python" -B -m pip install --no-index --find-links "$root/downloads/dependencies" \
  --only-binary=:all: --disable-pip-version-check "$wheel" \
  numpy==2.2.6 einops==0.8.1 transformers==4.56.2 safetensors==0.6.2
"$root/venv/bin/python" -B -m pip freeze > "$root/evidence/requirements.lock.txt"
"$root/venv/bin/python" -B -m pip check > "$root/evidence/pip-check.txt"
"$root/venv/bin/python" -B -c 'import json,sys,torch,numpy,transformers,safetensors; assert sys.version_info >= (3,11); assert torch.version.cuda is None; print(json.dumps({"python":sys.version,"executable":sys.executable,"torch":torch.__version__,"numpy":numpy.__version__,"transformers":transformers.__version__,"safetensors":safetensors.__version__,"cuda_build":torch.version.cuda}))' > "$root/evidence/runtime.json"
du -sb "$root/runtime" "$root/venv" "$root/cache" > "$root/evidence/runtime-storage.txt"
cat "$root/evidence/runtime.json"
