# Cached EEG input API

Public `train.npz` and `validation.npz` contain exactly `x`, `y`, `sample_ids`,
and `subject_ids`. Each `x` is a finite numeric matrix with 325 columns. Binary
`y` uses 0 for eyes open and 1 for eyes closed. Evaluation input contains exactly
`x`, `sample_ids`, and `subject_ids`; labels remain private.

| Zero-based columns | Content |
| --- | --- |
| `0:200` | Frozen final representation, 200 columns |
| `200:262` | Handcrafted attribute panel, 62 columns |
| `262` | Original frozen classifier logit |
| `263:325` | Fixed random-feature control, 62 columns |

The accompanying `resources/CACHE_SCHEMA.json` describes this layout and its
provenance. The schema-only `eeg_api.py` exports `INPUT_COLUMNS=325`,
`EMBEDDING_COLUMNS=(0,200)`, `ATTRIBUTE_COLUMNS=(200,262)`,
`ORIGINAL_LOGIT_COLUMN=262`, `RANDOM_COLUMNS=(263,325)`, and
`LABELS={0:"eyes_open",1:"eyes_closed"}`. It contains no functions or fitting
recipe. Models and their weights are
not exposed because this task operates on frozen cached inputs. Train your own
readouts using available numerical libraries. A direct loading pattern is:

```python
from pathlib import Path
import numpy as np

with np.load(Path(public) / "train.npz", allow_pickle=False) as archive:
    x = archive["x"]
    y = archive["y"]
    participants = archive["subject_ids"]
    representation = x[:, :200]
    attributes = x[:, 200:262]
    original_logits = x[:, 262]
```

Fit transformations and parameters on training rows. Use validation to select
choices and then freeze them. Participant IDs support grouped analyses; windows
within a participant are dependent. All IDs are opaque. Preserve supplied
sample IDs and row order, including when producing the original score. The
required original output equals `x[:, 262]` exactly, without clipping,
recalibration, rounding, or other transformation. A separate declared readout
may examine calibration.

Use only the public export. Cached attributes are candidate predictors for this
task; the private labels, final-test cohort membership, and final-test input
are unavailable to the Actor. The inference worker receives the sealed input
only after lock and returns aggregate metrics through the trusted projection.
