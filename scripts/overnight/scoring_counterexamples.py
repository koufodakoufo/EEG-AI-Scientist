"""Offline synthetic controls. Labels are Builder fixtures, never LLM calibration."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'framework'))
sys.path.insert(0,str(ROOT/'framework/tests/research_bench'))
from test_claims import claim, edge, PAIR_FIXTURES
from eegfm.research_bench.scoring import score_directional
from eegfm.research_bench.evidence import audit_evidence


def main() -> None:
    rows=[]
    for name,agent,reference,pr,rr,p,r in PAIR_FIXTURES:
        score=score_directional([claim('a',agent)],[claim('r',reference)],
            [edge(relation=pr),edge(direction='agent_covers_reference',relation=rr)])
        assert score['scores']['precision']==p and score['scores']['recall']==r
        rows.append({'name':name,'scores':score['scores'],'status':score['status'],
                     'expected_relations':{'precision':pr,'recall':rr}})
    graphs: dict[str, Any] = {}
    for name,agents,refs,matches in [
        ('one_to_many',[claim('a')],[claim('r','R1'),claim('r2','R2')],
            [edge(reference=r,direction=d) for r in ('r','r2') for d in ('reference_supports_agent','agent_covers_reference')]),
        ('many_to_one',[claim('a','A1'),claim('a2','A2')],[claim('r')],
            [edge(agent=a,direction=d) for a in ('a','a2') for d in ('reference_supports_agent','agent_covers_reference')]),
        ('duplicates',[claim('a'),claim('a2')],[claim('r'),claim('r2')],
            [edge(agent=a,reference=r,direction=d) for a in ('a','a2') for r in ('r','r2') for d in ('reference_supports_agent','agent_covers_reference')]),
        ('empty_submission',[],[claim('r')],[]),('empty_reference',[claim('a')],[],[]),('both_empty',[],[],[])]:
        score=score_directional(agents,refs,matches)
        reversed_score=score_directional(list(reversed(agents)),list(reversed(refs)),list(reversed(matches)))
        assert reversed_score['scores']==score['scores']
        assert all(value is None or 0<=value<=1 for value in score['scores'].values())
        graphs[name]={'scores':score['scores'],'status':score['status'],'counts':score['counts'],'order_invariant':True}
    # Separate deliberate leak fixture: neither private holdout text nor real task identifiers.
    answer=b'SYNTHETIC_LEAK_CANARY_20261029: toy accuracy is 0.75.'
    secret_hash=hashlib.sha256(answer).hexdigest()
    private_inventory={'toy_reference.txt':secret_hash}
    exposed_inventory={'renamed_public_hint.txt':secret_hash}
    overlap=sorted(set(private_inventory.values()) & set(exposed_inventory.values()))
    assert overlap==[secret_hash]
    score=score_directional([claim('a','Toy accuracy is 0.75.')],[claim('r','Toy accuracy is 0.75.')],
        [edge(),edge(direction='agent_covers_reference')])
    with tempfile.TemporaryDirectory(dir=ROOT/'.local/overnight-20261029') as folder:
        audit=audit_evidence([],Path(folder),[])
    assert score['scores']['f1']==1 and not audit['valid']
    # Same substantive content, different claim packaging under a closed reference.
    refs=[claim('r','C0 accuracy is 95.83%.'),claim('r2','C1 accuracy is 12.50%.')]
    atomic=score_directional([claim('a','C0 accuracy is 95.83%.'),claim('a2','C1 accuracy is 12.50%.'),
        claim('a3','The confidence interval is [51.04%,57.81%].')],refs,
        [edge(),edge(direction='agent_covers_reference'),edge(agent='a2',reference='r2'),
         edge(agent='a2',reference='r2',direction='agent_covers_reference'),edge(agent='a3',relation='not_supported')])
    packed=score_directional([claim('a','C0 accuracy is 95.83%. C1 accuracy is 12.50%. The confidence interval is [51.04%,57.81%].')],refs,
        [edge(relation='not_supported'),edge(reference='r2',relation='not_supported'),
         edge(direction='agent_covers_reference'),edge(reference='r2',direction='agent_covers_reference')])
    assert abs(atomic['scores']['f1']-.8)<1e-12 and packed['scores']['f1']==0
    report={'schema_version':'counterexamples_v1','model_calls':0,'builder_authored_labels':True,
        'semantic_judge_calibrated':False,'pair_fixtures':rows,'graph_fixtures':graphs,
        'granularity_sensitivity':{'atomic_scores':atomic['scores'],'packed_scores':packed['scores'],
            'labels':'Builder-authored; not additional judge calls or rescored holdout.',
            'conclusion':'Reference omits the interval. Packing it with supported estimates changes F1 from 0.8 to 0 without changing the report content. Complete-report extraction granularity is a material measurement choice.'},
        'deliberate_leak_positive_control':{'separate_toy_fixture':True,'holdout_touched':False,
            'public_private_byte_hash_overlap_detected':bool(overlap),'reference_agreement':score['scores'],
            'evidence_status':audit['status'],'evidence_valid':audit['valid'],
            'conclusion':'Perfect agreement does not detect a leaked answer. Inventory overlap detects this exact copied artifact; evidence audit rejects no-evidence output.',
            'limitations':['No leaked model episode was run. This is an offline positive control.',
                           'Byte matching cannot detect paraphrases, memorized knowledge, or all leakage routes.',
                           'Live isolation negative controls are separately recorded in ISOLATION_REPORT.json.']},
        'interpretation':'Twenty pair labels plus six graph cases verify arithmetic and inert data handling; they are not 26 independently annotated semantic judgments.'}
    (ROOT/'docs/overnight/2026-10-29/SCORING_COUNTEREXAMPLES.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pair_cases':len(rows),'graph_cases':len(graphs),'leak_detected':bool(overlap),'agreement_f1':1,'evidence':audit['status']}))


if __name__=='__main__':
    main()
