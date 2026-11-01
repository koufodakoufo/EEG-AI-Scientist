# EEGMMIDB baseline-condition representation analysis

Study an official pretrained, frozen CBraMod backbone with the supplied newly
fitted, frozen binary head. The task is eyes-open baseline (0) versus eyes-closed baseline (1) in
PhysioNet EEGMMIDB 1.0.0. These are R01 and R02 baseline recording conditions,
not motor-imagery event labels. This is a new adaptation with a newly fitted
training-only frozen head, not a replication of published downstream results
and not a clinical stress, depression, or diagnostic task.

Investigate three questions: Q1, which supplied EEG feature groups are
recoverable from layers 6 and 12; Q2, whether modifying a representation component
associated with selected features changes task predictions relative to suitable
controls; Q3, whether relevant feature information remains recoverable after the
modification. Recoverability, model reliance, and physiological causation are
different claims. State which questions the available evidence actually answers.

The public train and validation views contain EEG `x`, binary `y`, 62 feature
columns, layer 6/layer 12 activations, final embeddings, and opaque sample and
participant IDs. Participants are disjoint across splits. Windows are 5 seconds,
20 channels, 200 Hz, microvolts divided by 100. The 20 measured scalp channels are Fp1, Fp2, F3, F4, F7, F8, T7, T8,
C3, C4, P7, P8, P3, P4, O1, O2, Fz, Cz, Pz, and FCz. Native 160 Hz recordings
were FFT-resampled to 200 Hz; no new high-frequency information is implied.
The original reference is retained without asserting linked-ear referencing.
The fixed API describes the array
layout and column order. Use participant IDs when reasoning about dependence.
The supplied feature panel defines the measurement scope; it is not a ranking
of useful features. No reference choices or reference results are supplied.

Choose and document your own analysis. Fit only on training data and make all
choices using validation. Freeze a protocol before the baseline. Freeze all
code, fitted parameters, and choices before requesting the one final test.
Keep the pretrained backbone and supplied task head frozen. A trusted worker
alone receives the sealed, unlabelled test input after a candidate lock. You
cannot inspect test inputs, private truth, source recordings, or controller
storage. Do not attempt to access them. Raw worker output is private; only
predeclared aggregate statistics are released.

Use `INTERFACE.md` for the lifecycle and `PUBLIC_RESULT_SCHEMA.md` for executable
output requirements. `API_README.md` describes the frozen helper. A `SKILL.md`
file, when present, is the sole additional condition material. Read it as an
optional research aid. It does not change the resources, permissions, budgets,
task, result schema, or evaluation rules.

Write a self-contained `REPORT.md` with questions, frozen choices, methods,
baseline and analysis evidence, controls, uncertainty, retained negative/null
findings, limitations, and exact candidate/test identifiers. Clearly label
unimplemented or unsupported Q2/Q3 and any partial Q1 coverage. A successful
program exit or completed lifecycle does not establish scientific success.
Do not invent statistics, clinical conclusions, or claims of paper replication.

The first 60 seconds of each baseline recording supply twelve consecutive,
nonoverlapping windows. R01/R02 order is confounded with eye condition; fatigue,
recording drift, eye movements and other artifacts are not independently
controlled. The fixed convenience subset contains 36 participants, with only
six final-test participants. New to this development project does not establish
absence from backbone pretraining. Use these limitations in interpretation.

Data source: https://physionet.org/content/eegmmidb/1.0.0/ (ODC-By 1.0);
Schalk (2009), DOI 10.13026/C28G6P, and Schalk et al. (2004),
DOI 10.1109/TBME.2004.827072.
