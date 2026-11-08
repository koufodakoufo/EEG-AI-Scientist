# EEGMAT attribute dependence (v2)

Study an official pretrained, frozen CBraMod backbone with the supplied newly
fitted, frozen binary head. The task is mental arithmetic versus background in
EEGMAT. This is a new adaptation, not a replication of published downstream
results and not a clinical stress, depression, or diagnostic task.

The parent question is whether the frozen classifier depends on a recoverable
feature more than on an equally disruptive random intervention. Investigate
three questions: Q1, which supplied EEG feature groups are
recoverable from layers 6 and 12; Q2, whether modifying a representation component
associated with selected features changes task predictions relative to suitable
controls; Q3, whether relevant feature information remains recoverable after the
modification. Recoverability, model reliance, and physiological causation are
different claims. State which questions the available evidence actually answers.

The public train and validation views contain EEG `x`, binary `y`, 62 feature
columns, layer 6/layer 12 activations, final embeddings, and opaque sample and
participant IDs. Participants are disjoint across splits. Windows are 5 seconds,
20 channels, 200 Hz, microvolts divided by 100. The fixed API describes the array
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

Read `EVIDENCE_POLICY.json`: the advisory obligations are at least 24 Q1
feature/layer groups, two matched interventions and two residual-refit groups.
Both guidance conditions receive the same obligations, resources and budgets.
Plan to address all three questions within the available budget. Honest partial
reports and valid negative/null findings remain allowed; disclose unmet
obligations. Coverage counts do not establish scientific validity, successful
refitting, control provenance or replay. Those require independent review.
