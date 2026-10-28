"""Trusted local preparation/validation of symmetric extraction and blind judging."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]; NIGHT=ROOT/'.local/overnight-20261029'; PRIVATE=NIGHT/'private'
sys.path.insert(0,str(ROOT/'framework'))
from eegfm.research_bench.budget import reserve_call,write_atomic
from eegfm.research_bench.bundle import digest_file,verify_seal
from eegfm.research_bench.extraction import validate_extraction,exclude_fixture_administration
from eegfm.research_bench.scoring import score_directional


def read(path: Path): return json.loads(path.read_text(encoding='utf-8'))


def new_job(call_id: str,role: str,protocol: str,payload: dict) -> Path:
    source=PRIVATE/f'jobs/{call_id}/source'; source.mkdir(parents=True,exist_ok=False)
    names={'atomic_extract_v1':'extract_claims_v1.md','directional_judge_v1':'judge_directional_v1.md'}
    shutil.copyfile(ROOT/'framework/benchmarks/brainpec_pilot/policies'/names[protocol],source/'PROTOCOL.md')
    write_atomic(source/'INPUT.json',payload)
    write_atomic(source.parent/'JOB.json',{'call_id':call_id,'role':role,'protocol_version':protocol,'timeout_seconds':600})
    reserve_call(ROOT/'docs/overnight/2026-10-29/BUDGET.json',call_id,role,600)
    return source.parent


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['extract','validate','judge','score'])
    parser.add_argument('call_id'); parser.add_argument('--group',choices=['dev','holdout'])
    parser.add_argument('--episodes',nargs='+'); parser.add_argument('--extraction')
    args=parser.parse_args()
    if args.action=='extract':
        if not args.group or not args.episodes: parser.error('extract needs group and episodes')
        seal=verify_seal(NIGHT/f'public-bundles/{args.group}',PRIVATE/f'reference-v2/{args.group}.json',PRIVATE/f'seals-v2/{args.group}.json')
        docs=[]; mapping=[]
        task_id=read(NIGHT/f'public-bundles/{args.group}/RESOURCE_MANIFEST.json')['task_id']
        for index,episode in enumerate(args.episodes,1):
            frozen=NIGHT/f'submissions/{episode}/output'; identifier=f'S{index:02d}'
            # Raw proposed annex does not constrain complete-report extraction.
            proposed=read(frozen/'claims.json') if (frozen/'claims.json').is_file() else {'claims':[]}
            docs.append({'document_id':identifier,'source':identifier+'.md','task_id':task_id,
                         'text':(frozen/'REPORT.md').read_text(encoding='utf-8'),'proposed_claims':proposed.get('claims',[])})
            mapping.append({'document_id':identifier,'episode':episode,'report_sha256':digest_file(frozen/'REPORT.md')})
        job=new_job(args.call_id,'submission_extractor','atomic_extract_v1',{'documents':docs})
        if digest_file(job/'source/PROTOCOL.md')!=seal['scoring_policy']['extraction_protocol_sha256']:
            raise ValueError('Extractor prompt differs from sealed version')
        write_atomic(job/'mapping.json',{'group':args.group,'documents':mapping,'experiment_seal_sha256':seal['seal_sha256']})
        print(job)
    elif args.action=='validate':
        job=PRIVATE/f'jobs/{args.call_id}'
        raw=read(NIGHT/f'evidence/server/{args.call_id}/final.txt')
        validated=validate_extraction(raw,read(job/'source/INPUT.json')['documents'])
        write_atomic(job/'VALIDATED.json',validated)
        filtered=exclude_fixture_administration(validated); write_atomic(job/'FILTERED.json',filtered)
        print(json.dumps({'documents':{d['document_id']:len(d['claims']) for d in filtered['documents']},
                          'span_alignments':len(validated['deterministic_span_alignments'])}))
    elif args.action=='judge':
        if not args.extraction: parser.error('judge needs extraction ID')
        extraction=PRIVATE/f'jobs/{args.extraction}'; mapping=read(extraction/'mapping.json'); group=mapping['group']
        filtered=read(extraction/'FILTERED.json'); sources=read(extraction/'source/INPUT.json')['documents']
        original=read(PRIVATE/f'seals/{group}.json'); current=read(PRIVATE/f'seals-v2/{group}.json')
        criteria={k:original['scoring_policy'][k] for k in ('claim_criteria','alternative_findings','bootstrap_scope','no_fixed_method_requirement','relations','score_rules','directions','deduplication')}
        reference_claims=read(PRIVATE/f'reference-v2/{group}.json')['claims']
        reference_text=(PRIVATE/f'task-build/{group}_private/REFERENCE_REPORT.md').read_text(encoding='utf-8')
        evaluations=[]
        for doc in filtered['documents']:
            source=next(d for d in sources if d['document_id']==doc['document_id'])
            evaluations.append({'evaluation_id':doc['document_id'],'reference_report':reference_text,
                'submission_report':source['text'],'reference_claims':reference_claims,'agent_claims':doc['claims'],
                'criteria':criteria})
        job=new_job(args.call_id,'semantic_judge','directional_judge_v1',{'evaluations':evaluations,'calibration':[]})
        if digest_file(job/'source/PROTOCOL.md')!=current['scoring_policy']['judge_protocol_sha256']:
            raise ValueError('Judge prompt differs from sealed version')
        write_atomic(job/'mapping.json',{'group':group,'extraction_id':args.extraction,'documents':mapping['documents'],
            'original_seal_sha256':original['seal_sha256'],'symmetric_extraction_seal_sha256':current['seal_sha256']})
        print(job)
    else:
        job=PRIVATE/f'jobs/{args.call_id}'; payload=read(job/'source/INPUT.json'); mapping=read(job/'mapping.json')
        raw=read(NIGHT/f'evidence/server/{args.call_id}/final.txt')
        if set(raw)!={'protocol_version','evaluations','calibration'} or raw['protocol_version']!='directional_judge_v1':
            raise ValueError('Judge envelope mismatch')
        expected={v['evaluation_id'] for v in payload['evaluations']}
        actual=[v['evaluation_id'] for v in raw['evaluations']]
        if set(actual)!=expected or len(actual)!=len(expected): raise ValueError('Judge omitted/duplicated evaluation')
        target=PRIVATE/f'evaluations/{args.call_id}'; target.mkdir(parents=True,exist_ok=False)
        summaries=[]
        for result in raw['evaluations']:
            item=next(v for v in payload['evaluations'] if v['evaluation_id']==result['evaluation_id'])
            episode=next(v['episode'] for v in mapping['documents'] if v['document_id']==result['evaluation_id'])
            score=score_directional(item['agent_claims'],item['reference_claims'],result['matches'],run_id=episode)
            write_atomic(target/(episode+'-score.json'),score)
            write_atomic(target/(episode+'-judge-notes.json'),{k:result.get(k,[]) for k in ('uncertainty','alternative_findings')})
            summaries.append({'episode':episode,'status':score['status'],'scores':score['scores'],
                              'agent_claims':score['counts']['agent_claims'],'reference_claims':score['counts']['reference_claims'],
                              'review_items':len(score['review_items'])})
        write_atomic(target/'SUMMARY.json',summaries); print(json.dumps(summaries,indent=2))


if __name__=='__main__': main()
