# EEGMAT residual attribute recovery

Task ID: `eegmat-residual-recovery-v1`. This is an externally designed,
adapted EEG development task. It is not automated paper decomposition, a
FIRE replication, or evidence of recursive self-improvement (RSI).

If present, read `resources/PAPER_TASK.json` for the frozen paper-derived
question and report contract. Apply the fixed scientific constraints below.

Ask whether six attributes remain recoverable from fixed cached EEG features
after linear erasure, and whether a flexible readout adds useful recovery
beyond the declared finite affine comparator. The five independent views,
in order, are `identity`, `leace`, `random_2301`, `random_2302`, `random_2303`.
Each has 200 pooled features. Targets are original attribute columns 12–17.
The frozen fold-0 LEACE operator was fitted on the separate 12-participant A
half. B is the other 12 training participants. Do not refit the eraser or
change participants, fold, targets, pooling or intervention directions.
Use no original-head logits, old classification readouts, Q1/Q2/Q3 analyses,
raw EEG, new backbone computation, IDs as predictors, or cross-view mixing.

Author a deterministic regularized linear baseline. Fit only on B training
rows, including all scaling and preprocessing. The linear branch must be
affine overall. The flexible family may be nonlinear.
Declare at most four validation-inspected recipes per family per view,
including preprocessing; select one recipe per view for all six targets by
equal-weight fixed-mask validation R². Break exact ties by earliest declared
recipe. Shuffled fits reuse the selected indices; they do not select again.
Implement the fixed PCG64 shuffle seed 230418: in canonical sample order,
draw `offset = rng.integers(1, 12)`, then
`offsets = rng.integers(1, 24, size=12)` from `rng = Generator(PCG64(230418))`.
For receiving participant sorted index r and canonical sorted sample index j,
the donor is participant `(r + offset) % 12`, sample `(j + offsets[r]) % 24`.
The permutation records the donor source row for each receiving row in the
existing B order and is shared across all views and families. Require exactly
12 equal blocks of 24; fail on any mismatch. See the public
cache schema for prepared row identity and the API contract for input fields.

Baseline models are `linear`, `linear_shuffled`. The final model order appends
`flexible`, `flexible_shuffled`. Two public fits reconstruct the same baseline
source, declarations, numeric arrays and validation predictions. A trusted
pre-lock hash check compares those baseline components and ordered validation
bindings. ZIP metadata is ignored. Parity certifies those validation rows;
it does not prove semantic correctness, dependency closure or absence of
evaluation fitting. Independent source, fit and prediction replay audit is
required; two replay slots are reserved separately.

The registered useful LEACE effect requires flexible R² > 0, the lower 95%
bound of flexible minus its own shuffle > 0, and flexible minus linear point
and lower bound both > 0.05. The identity operational gate also requires
flexible R² > 0 and its own-shuffle lower bound > 0. Linear recovery requires
LEACE linear R² > 0 and its own-shuffle lower bound > 0. Undefined intervals
make useful-effect gates inconclusive. Source/audit validity is separate.

Report the actual evidence and uncertainty, including negative and inconclusive
findings. Completion requires baseline, flexible and shuffled controls, locked
test evidence and a report; it requires no positive effect and does not close
the scientific question by itself. The final test has six participants and
has prior project exposure: withheld from this researcher until lock is not
project-unseen confirmation. Additional recovery beyond this finite affine
comparator does not establish intrinsic/exclusive nonlinearity, causal
reliance, method gain or RSI.
