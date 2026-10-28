"""Builder export: correct interface contracts before enrolling any Actor."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'framework'))
from eegfm.research_bench.bundle import create_public_bundle,freeze_experiment,digest_file,canonical_bytes


def main() -> None:
    private=ROOT/'.local/overnight-20261029/private'
    build=private/'task-build'
    names=['TASK_PUBLIC.md','DATA_DICTIONARY.md','RESOURCE_MANIFEST.json','OUTPUT_CONTRACT.json','fixed_model.py','train.csv','validation.csv']
    budgets={'model':'gpt-6.1-sol','reasoning_effort':'medium','episode_seconds':900,'analysis_command_seconds':60,
             'cpu_threads':4,'ram_bytes':12*1024**3,'output_bytes':64*1024**2,'gpu':0,'extra_agents':0,
             'network':False,'resource_tier':'synthetic_mechanism','replicates_planned':1,'maximum_optional_replicates':2}
    records=[]
    for group in ('dev','holdout'):
        source=private/'export-source'/group
        source.mkdir(parents=True,exist_ok=False)
        for name in names: shutil.copyfile(build/f'{group}_public_source'/name,source/name)
        contract=json.loads((source/'OUTPUT_CONTRACT.json').read_text())
        contract['evidence_json']['record_fields']['status']='Use completed for successful commands; failed otherwise. Executed is not a valid success label.'
        contract['evidence_json']['record_fields']['data_split']='validation for validation metrics, train for training-only metrics, not_applicable for code or plans. Record both input partitions in the analysis metadata when fitting train and evaluating validation.'
        contract['commands_json']={'type':'array','required_fields':['command_id','argv','artifacts'],
            'argv':'Relative, reproducible argv, e.g. ["python3","output/analysis.py"]. Run from episode root. No absolute episode paths.',
            'artifacts':'List of artifact paths relative to output/, e.g. ["metrics.json"].',
            'command_id':'Your stable identifier; the trusted evaluator will bind it to a separate sandboxed replay, and preserve the original record.',
            'required_file':'output/COMMANDS.json','replay_limit_seconds':60}
        contract['evidence_requirements'].append('All deliverables live under output/. Provide COMMANDS.json and executable analysis code for an independent sandboxed replay. Replay integrity and original tool-trace integrity are reported separately.')
        (source/'OUTPUT_CONTRACT.json').write_bytes(canonical_bytes(contract))
        with (source/'TASK_PUBLIC.md').open('a',encoding='utf-8') as handle:
            handle.write('\nExecution interface: put deliverables under output/. Include COMMANDS.json as specified in OUTPUT_CONTRACT.json. Use paths relative to the episode root so an independent evaluator can replay the analysis in a fresh sandbox. Reference agreement and reproducibility are separate reports.\n')
        public=ROOT/'.local/overnight-20261029/public-bundles'/group
        manifest=json.loads((source/'RESOURCE_MANIFEST.json').read_text())
        task_id=manifest.get('task_id') or f'synthetic_{group}_v1'
        create_public_bundle(source,public,names,task_id=task_id,tier='synthetic_mechanism')
        policy_path=build/f'{group}_private/score_policy.json'
        if not policy_path.exists():
            candidates=list((build/f'{group}_private').glob('*policy*.json'))
            if len(candidates)!=1: raise ValueError('Ambiguous private score policy')
            policy_path=candidates[0]
        policy=json.loads(policy_path.read_text())
        policy['evaluation_protocol']='fire_inspired_v1; structured author claims plus fresh semantic judge, not official FIRE score replication'
        policy['judge_model']='gpt-6.1-sol'
        policy['judge_reasoning_effort']='medium'
        policy['reference_extraction']='Builder-authored structured reference with exact source spans, schema research_bench_v1'
        policy['agent_extraction']='Actor-authored structured claims with exact source spans; semantic judge audits atomicity/completeness before matching; differences disclosed'
        seal=private/'seals'/f'{group}.json'
        result=freeze_experiment(public,build/f'{group}_private/REFERENCE_PRIVATE.json',policy,budgets,['synthetic_mechanism'],seal)
        records.append({'group':group,'task_id':task_id,'public_manifest_sha256':digest_file(public/'PUBLIC_MANIFEST.json'),
                        'reference_sha256':result['reference_sha256'],'seal_sha256':result['seal_sha256']})
    (private/'EXPORT_FREEZE.json').write_bytes(canonical_bytes({'enrolled_actors':0,'cases':records,
        'contract_correction':'Before first Actor, aligned evidence success status with schema and required reproducible relative command manifests. Original generated source package preserved; public export overlays versioned separately.',
        'builder_test_exposure':'See task-build/BUILD_AUDIT.md. Final test is not Actor-evaluated and not included in score.'}))
    print(json.dumps(records,indent=2))


if __name__=='__main__': main()
