"""Verify existing seals and produce metadata-only public/private package index."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
NIGHT=ROOT/'.local/overnight-20261029'
sys.path.insert(0,str(ROOT/'framework'))
from eegfm.research_bench.bundle import digest_file,verify_seal,verify_public_bundle
from eegfm.research_bench.budget import write_atomic


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    protocol=read(NIGHT/'private/HOLDOUT_PROTOCOL.json')
    skill=ROOT/'framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/SKILL.md'
    assert digest_file(skill)==protocol['skill_sha256']
    assert digest_file(ROOT/'scripts/overnight/actor_job.py')==protocol['actor_prompt_script_sha256']
    cases=[]
    for group in ('dev','holdout'):
        public=NIGHT/'public-bundles'/group
        reference=NIGHT/f'private/reference-v2/{group}.json'
        seal=verify_seal(public,reference,NIGHT/f'private/seals-v2/{group}.json')
        manifest=verify_public_bundle(public)
        assert len(manifest['files'])==7
        gold=NIGHT/f'private/task-build/{group}_private/REFERENCE_REPORT.md'
        assert digest_file(gold) not in {f['sha256'] for f in manifest['files']}
        cases.append({'group':group,'public':str(public.relative_to(ROOT)).replace('\\','/'),
            'public_manifest_sha256':digest_file(public/'PUBLIC_MANIFEST.json'),
            'files':manifest['files'],'private_reference':str(reference.relative_to(ROOT)).replace('\\','/'),
            'private_reference_sha256':digest_file(reference),'reference_report_sha256':digest_file(gold),
            'reference_claims':len(read(reference)['claims']),'seal_sha256':seal['seal_sha256'],'verification':'passed'})
    budget=read(ROOT/'docs/overnight/2026-10-29/BUDGET.json')
    assert len(budget['calls'])==24 and all(c['status'] not in ('running','reserved') for c in budget['calls'])
    report={'schema_version':'nightly_freeze_verification_v1','cases':cases,
        'skill_sha256':digest_file(skill),'actor_job_sha256':digest_file(ROOT/'scripts/overnight/actor_job.py'),
        'holdout_protocol_sha256':digest_file(NIGHT/'private/HOLDOUT_PROTOCOL.json'),
        'taskbook_sha256':digest_file(ROOT/'EEG_FM_Codex_Overnight_Taskbook_2026-10-29.md'),
        'all_24_worker_reservations_terminal':True,'model_calls_added':0,
        'reference_tree':'.local/overnight-20261029/private/reference/research_tree.json',
        'reference_tree_validation':'.local/overnight-20261029/private/reference/validation_report.json',
        'limits':['Hash sealing verifies preserved bytes, not scientific adequacy or semantic non-leakage.',
                  'Exact reference-report copy absent from public manifests; live boundary tests are a separate check.']}
    write_atomic(ROOT/'docs/overnight/2026-10-29/TASK_PACKAGE_INDEX.json',report)
    print(json.dumps({'cases':len(cases),'sealed_files':14,'skill_unchanged':True,'actor_prompt_unchanged':True,'workers_terminal':24}))


if __name__=='__main__': main()
