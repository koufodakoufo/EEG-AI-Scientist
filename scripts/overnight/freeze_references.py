"""Finalize symmetric extraction and preregistration before enrolling Actors."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'framework'))
from eegfm.research_bench.bundle import canonical_bytes,digest_file,freeze_experiment
from eegfm.research_bench.extraction import exclude_fixture_administration


def main() -> None:
    private=ROOT/'.local/overnight-20261029/private'
    raw=private/'reference-extraction-v1/VALIDATED.json'
    filtered=exclude_fixture_administration(json.loads(raw.read_text()))
    final=private/'reference-v2'; final.mkdir(exist_ok=False)
    (final/'FILTERED.json').write_bytes(canonical_bytes(filtered))
    previous=json.loads((private/'seals/dev.json').read_text())
    policy={'version':'fire_inspired_v2','primary':'directional reference agreement; not scientific truth',
            'model':'gpt-6.1-sol','reasoning_effort':'medium','extraction_protocol':'atomic_extract_v1',
            'extraction_protocol_sha256':digest_file(ROOT/'framework/benchmarks/brainpec_pilot/policies/extract_claims_v1.md'),
            'extraction_postprocessing':'exclude_fixture_admin_v1; symmetric exact administrative header only; raw preserved',
            'extraction_code_sha256':digest_file(ROOT/'framework/eegfm/research_bench/extraction.py'),
            'judge_protocol_sha256':digest_file(ROOT/'framework/benchmarks/brainpec_pilot/policies/judge_directional_v1.md'),
            'empty_agent':0,'empty_reference':'excluded','full_text_support':True,
            'unmatched_alternative_findings':'reviewable separately, not declared false',
            'evidence_audit':'separate trusted replay and original tool trace',
            'reference_model_call':'M11','reference_raw_sha256':digest_file(raw),
            'json_repair_max_per_output':1,'failed_launched_episodes':'retain in denominator; no selective retry'}
    records=[]
    for group in ('dev','holdout'):
        doc=next(d for d in filtered['documents'] if d['document_id']==f'R_{group}')
        target=final/f'{group}.json'
        target.write_bytes(canonical_bytes({'schema_version':'research_bench_v1','claims':doc['claims']}))
        seal=freeze_experiment(ROOT/f'.local/overnight-20261029/public-bundles/{group}',target,policy,
                               previous['budgets'],['synthetic_mechanism'],private/f'seals-v2/{group}.json')
        records.append({'group':group,'claims':len(doc['claims']),'seal_sha256':seal['seal_sha256'],
                        'reference_sha256':seal['reference_sha256'],'public_manifest_sha256':seal['public_manifest_sha256']})
    (final/'FREEZE.json').write_bytes(canonical_bytes({'enrolled_actors':0,'previous_seals':'preserved as pre-enrollment draft',
            'change':'Same extractor for both sides; excludes administrative fixture statement symmetrically.',
            'cases':records}))
    print(json.dumps(records,indent=2))


if __name__=='__main__': main()
