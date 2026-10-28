"""H2 provenance and parameter-plan checks; no training or external data reads."""
from pathlib import Path

from artifact_io import read_json, sha256_file
from data_contract import TARGETS
from evaluation_contract import EVALUATION_HASH
from posttrain import validate_parameters

PREVIOUS_RUN = 'reve_isa_recovery_20261017'
PREVIOUS_SNAPSHOT = 'acc39335a877e8d19a1bb334be3e8d480c6103a50e7319d0a37a90f129c8cc65'
PREVIOUS_VALIDATION = 'e2e5bfe06eb43ac650711ea9b8a7395d9e4f31fbbb8b0a7b5e3f74dc721b5f1d'
SUMMARY_SHA256 = 'b27b5813b254f5ba8fbaf9d08744aadda668d37bf373b2b5157c3a3562d2b210'
OLD_PARAMETERS = {'posttrain_lr': 1e-5, 'temperature': 0.1,
                  'posttrain_weight_decay': 1e-4, 'warmup_epochs': 3, 'gradient_clip': 1.0}


def load_previous(root):
    path = Path(root) / 'previous_validation_summary.json'
    if sha256_file(path) != SUMMARY_SHA256:
        raise ValueError('Historical validation summary hash changed')
    previous = read_json(path)
    if (previous['source']['sha256'] != PREVIOUS_VALIDATION
            or previous['snapshot_hash'] != PREVIOUS_SNAPSHOT
            or previous['evaluation_hash'] != EVALUATION_HASH
            or previous['test_evaluations'] != 0 or previous['validation_evaluations'] != 72
            or previous['baseline_evaluations'] != 72
            or previous['execution_valid'] is not True
            or previous['protocol_gate']['passed'] is not True
            or set(previous['validation_summary']['datasets']) != set(TARGETS)
            or set(previous['training']) != set(TARGETS)):
        raise ValueError('Historical evidence is not the pinned complete validation-only H1 evidence')
    for target in TARGETS:
        training = previous['training'][target]
        if training['parameters'] != OLD_PARAMETERS or training['epochs_completed'] != 40:
            raise ValueError('Historical parameter/training provenance differs')
    return previous


def validate_h2_parameters(parameters):
    validate_parameters(parameters)
    if parameters == OLD_PARAMETERS:
        raise ValueError('H2 requires at least one material numeric parameter change from H1')


def verify_scientist_plan(plan, root, parameters=None):
    load_previous(root)
    if (plan.get('decision_status') != 'selected_by_scientist'
            or plan.get('decision_owner') != 'Scientist'
            or plan.get('candidate_label') != 'H2' or plan.get('research_round') != 1
            or plan.get('previous_parameters') != OLD_PARAMETERS
            or plan.get('previous_validation_sha256') != PREVIOUS_VALIDATION):
        raise ValueError('Scientist must finalize the H2 plan with pinned H1 evidence before execution')
    chosen = plan.get('parameters')
    if not isinstance(chosen, dict):
        raise ValueError('The plan must record all five chosen numeric parameters')
    validate_h2_parameters(chosen)
    if parameters is not None and chosen != parameters:
        raise ValueError('Scheduled parameters differ from the reviewed Scientist plan')
    changed = sorted(key for key in OLD_PARAMETERS if chosen[key] != OLD_PARAMETERS[key])
    if plan.get('changed_parameters') != changed:
        raise ValueError('Declared parameter changes differ from the actual H1-to-H2 change')
    expected = {'path': 'previous_validation_summary.json', 'sha256': SUMMARY_SHA256}
    if expected not in plan.get('evidence', []):
        raise ValueError('H2 must cite its actual packaged validation/training evidence')
    for field in ('hypothesis', 'change', 'opposite_result', 'decision_value'):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            raise ValueError('The Scientist plan lacks ' + field)
    ideas = plan.get('parameter_ideas', [])
    if not isinstance(ideas, list) or not 2 <= len(ideas) <= 4:
        raise ValueError('Record a small comparison of two to four parameter ideas; execute only one')
    for idea in ideas:
        if not isinstance(idea, dict) or any(not isinstance(idea.get(key), str) or not idea[key].strip()
                                           for key in ('idea', 'evidence_reason', 'decision')):
            raise ValueError('Parameter ideas need an evidence rationale and selection decision')
    return plan
