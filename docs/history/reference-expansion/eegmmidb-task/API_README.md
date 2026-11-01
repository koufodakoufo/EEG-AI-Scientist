# EEG helper API

The controller provides `eeg_api.py` beside a read-only `resources/` directory.
Use NumPy arrays with shape `(N, 20, 5, 200)`, ordered as sample, channel,
one-second patch, sample within patch. Values represent microvolts divided by
100 at 200 Hz. The helper validates shape and finite values; units are the input
contract. It runs on CPU with four PyTorch threads.

```python
from eeg_api import EEGModel, FEATURE_COLUMNS, compute_feature_panel

model = EEGModel()  # uses resources/ beside eeg_api.py
features = compute_feature_panel(x)  # (N, 62), order given by FEATURE_COLUMNS
activations = model.activations(x, layers=(6, 12))  # each (N, 20, 5, 200)
tokens = model.continue_from(activations[6], layer=6)  # (N, 20, 5, 200)
embedding = tokens.mean(axis=(1, 2))  # (N, 200)
logits = model.head_logits(embedding)  # (N,), binary decision score
direct_logits = model.logits(x)  # same frozen backbone/head path
```

Layers are one-based, with activations taken after the selected transformer
layer. `continue_from` starts with the following layer and includes the final
encoder normalization. The backbone checkpoint is loaded strictly before its
pretraining projection is replaced by the identity. The frozen linear head
normalizes embeddings using its supplied mean and scale, then applies its
coefficient and intercept. No model fitting occurs in this API.

Required packages are NumPy, PyTorch, and einops. The supplied resource manifest
identifies the two official model source files, their license, the checkpoint,
and the sanitized frozen head. File hashes and sizes are checked before loading.
The generic feature adaptation and its MIT notice are included in `eeg_api.py`.
Feature columns comprise six channel aggregations for each of ten registered
features, followed by two across-channel correlation summaries.

Public train/validation arrays use opaque sample and participant IDs. Treat row
order and IDs as provided; IDs do not encode condition or source chronology.
Evaluation input has only `x`, `sample_ids`, and `subject_ids`. Available data and
allowed evaluations are defined by the separate task instructions.
