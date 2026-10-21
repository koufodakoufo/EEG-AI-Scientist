# REPRODUCE

The working interpreter used for this run is the read-only Anaconda Python 3.12.4 fallback because `uv sync` could not finish in the network window. The project `.venv` is intentionally not modified by the fallback.

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH = 'src'
C:\Users\14090\anaconda3\python.exe -m pytest -q
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli preflight --config configs/overnight.json
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli overnight --config configs/overnight.json
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli report --study runs\study_20261019
```

The deterministic data and splits are reproducible from `data/private/case_specs.json`. Model outputs are not bit-identical even at temperature 0; the raw requests and responses are retained.
