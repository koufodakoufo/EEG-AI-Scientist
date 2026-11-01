# EEGMMIDB readout bottleneck investigation

Investigate whether a frozen EEG classifier's performance is limited by its
readout, and whether the supplied handcrafted EEG properties are predictively
sufficient for the same task. The task is eyes-open baseline (0) versus
eyes-closed baseline (1) in PhysioNet EEGMMIDB 1.0.0. These are recording
conditions, not motor imagery or clinical diagnoses.

You receive cached final representations, handcrafted properties, the original
classifier's decision score, and a fixed random-feature control. Choose your own
readout methods, comparisons, controls, selection procedure, and interpretation.
Compare the original score with a new readout of the frozen representation.
Execute and justify a competing explanation or control, and assess what the
available evidence says about attribute sufficiency. Different questions may
require different comparisons. An omitted comparison remains uncovered; it is
not evidence that its hypothesis is false. A better accuracy alone is not a
better scientific investigation.

Fit transformations and learned parameters on training data only. Use validation
for model selection and planned diagnostic checks. The backbone, original head,
and cached inputs remain fixed. New training-only readouts are allowed. Freeze
all source, fitted parameters, readout declarations, and choices before the
single held-out test. The trusted worker evaluates all declared readouts on the
same sealed 1,008 rows. Participant identities are disjoint across training,
validation, and test. Opaque IDs identify dependence and alignment; they do not
encode condition or chronology.

The final result has a combined primary evaluation and two predefined
descriptive subsets, diagnostic and confirmation. Their membership is private.
There is no diagnostic feedback before confirmation or a second final-test
opportunity. Use participant-level uncertainty and account for multiple
comparisons. The evaluator reports balanced accuracy, AUROC, log loss, paired
participant-bootstrap intervals, a declared primary contrast if present, and
all pairwise balanced-accuracy differences. A useful balanced-accuracy margin
is 0.03. Negative and inconclusive findings remain valid evidence.

State what your design discriminates. Distinguish a readout limitation from
alternative explanations such as calibration, model capacity, or a control
that exploits no meaningful representation. Attribute sufficiency concerns the
available panel and evaluated prediction problem. Similar performance does not
by itself establish equivalent information, a causal mechanism, or a universal
property of EEG. Ratio claims require compatible, independently verified
evidence; no closure ratio is required.

Write a self-contained `REPORT.md` recording questions, competing predictions,
frozen choices, methods, controls, validation and final-test evidence,
uncertainty, retained null findings, limitations, and exact candidate/test IDs.
Separately state the status of original/new readout comparison, executed
competing explanation or control, and attribute-sufficiency assessment. Use
missing, invalid, or pending where appropriate. Declared role labels and a
completed lifecycle do not establish source semantics or scientific validity;
source review, deterministic refitting, and prediction replay are required.

Read `INTERFACE.md`, `API_README.md`, and `PUBLIC_RESULT_SCHEMA.md` for the fixed
interface. Optional `SKILL.md` supplies research guidance only; it changes none
of the resources, permissions, budgets, or evaluation rules. Access only the
public bundle and your own episode output. Other episodes, private evaluation,
source recordings, external resources, and global memory are unavailable.

The source windows are five seconds from the first minute of baseline
recordings. Recording order is confounded with eye condition; fatigue, drift,
eye movements, and artifacts are not independently controlled. This is a
convenience sample in one data family, not an across-dataset generalization
test. Absence of a participant from this project's fitting set does not
establish absence from backbone pretraining.

Data source: https://physionet.org/content/eegmmidb/1.0.0/ (ODC-By 1.0);
Schalk (2009), DOI 10.13026/C28G6P, and Schalk et al. (2004),
DOI 10.1109/TBME.2004.827072.
