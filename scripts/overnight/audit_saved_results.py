"""Independent arithmetic on public rows and frozen predictions; execute no Actor code."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
NIGHT = ROOT / '.local/overnight-20261029'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accuracy(predictions: list[int], rows: list[dict[str, str]]) -> float:
    if len(predictions) != len(rows) or any(p not in (0, 1) for p in predictions):
        raise ValueError('Invalid prediction length or class')
    return sum(p == int(r['target']) for p, r in zip(predictions, rows)) / len(rows)


def main() -> None:
    result: dict[str, Any] = {'kind': 'builder_independent_arithmetic', 'model_calls': 0,
        'executes_actor_code': False, 'uses_private_test': False, 'cases': {}, 'episodes': {},
        'limits': ['Recounting predictions does not prove training-only fitting or validate all intervals.',
                   'Fixed-head edits are computational sensitivity checks, not physiological causality.']}
    for group in ('dev', 'holdout'):
        public = NIGHT / 'public-bundles' / group
        train = list(csv.DictReader((public / 'train.csv').open(encoding='utf-8', newline='')))
        rows = list(csv.DictReader((public / 'validation.csv').open(encoding='utf-8', newline='')))
        overlap = set(r['group_id'] for r in train) & set(r['group_id'] for r in rows)
        if overlap:
            raise ValueError('Groups cross train/validation boundary')
        means = {k: sum(float(r[k]) for r in train)/len(train) for k in ('r1','r2','r3','r4','r5')}
        def predict(row: dict[str, str | float]) -> int:
            score = (1.2 * float(row['r1']) + .5 * float(row['r3'])) if group == 'dev' else (
                .7 * float(row['r1']) * float(row['r2']) + 1.25 * float(row['r3']))
            return int(score >= 0)
        base = [predict(r) for r in rows]
        scope = {'pooled': list(range(len(rows)))}
        scope.update({c: [i for i,r in enumerate(rows) if r['context']==c] for c in sorted({r['context'] for r in rows})})
        metrics = {'fixed': {c: accuracy([base[i] for i in ix], [rows[i] for i in ix]) for c,ix in scope.items()}}
        for coordinate in means:
            edited = [predict({**r, coordinate: means[coordinate]}) for r in rows]
            metrics['mean_replace_'+coordinate] = {'accuracy': accuracy(edited, rows),
                'flips': sum(a!=b for a,b in zip(base,edited)),
                'corrected': sum(a!=int(r['target']) and b==int(r['target']) for a,b,r in zip(base,edited,rows)),
                'introduced': sum(a==int(r['target']) and b!=int(r['target']) for a,b,r in zip(base,edited,rows))}
        result['cases'][group] = {'n_train':len(train), 'n_validation':len(rows), 'group_overlap':len(overlap),
            'train_sha256':digest(public/'train.csv'), 'validation_sha256':digest(public/'validation.csv'),
            'fixed_model_sha256':digest(public/'fixed_model.py'), 'recomputed':metrics}
        for episode in (['M12'] if group=='dev' else ['M17','M20','M21']):
            folder = NIGHT/'submissions'/episode/'output'
            prediction_path = folder/'predictions.json'
            if episode=='M20' and (folder/'fit_results.json').is_file():
                fit=json.loads((folder/'fit_results.json').read_text(encoding='utf-8'))
                predictions=fit['predictions']
                recount={name:{c:accuracy([pred[i] for i in ix],[rows[i] for i in ix]) for c,ix in scope.items()}
                         for name,pred in predictions.items()}
                comparison=[{'model':name,'context':c,'recomputed':value,
                    'reported':fit['accuracy'][name]['all' if c=='pooled' else c],
                    'matches':abs(value-fit['accuracy'][name]['all' if c=='pooled' else c])<1e-12}
                    for name,values in recount.items() for c,value in values.items()]
                if predictions['fixed_head']!=base:
                    raise ValueError('M20 fixed predictions differ')
                result['episodes'][episode]={'status':'recounted','sha256':digest(folder/'fit_results.json'),
                    'fixed_predictions_match':True,'accuracy_recounts':recount,'reported_comparisons':comparison,
                    'row_order_basis':'CSV order inferred from saved analysis.py read/fit path; predictions lack explicit row IDs. Fixed-head sequence matches.',
                    'all_available_comparisons_match':all(c['matches'] for c in comparison)}
                continue
            if not prediction_path.is_file():
                result['episodes'][episode] = {'status':'predictions_not_available'}
                continue
            saved = json.loads(prediction_path.read_text(encoding='utf-8'))
            if not isinstance(saved,dict) or 'classification' not in saved or 'row_ids' not in saved:
                result['episodes'][episode] = {'status':'different_schema_requires_separate_audit', 'sha256':digest(prediction_path)}
                continue
            if saved['row_ids'] != [r['row_id'] for r in rows]:
                raise ValueError('Prediction row order mismatch: '+episode)
            recount = {name:{c:accuracy([pred[i] for i in ix],[rows[i] for i in ix]) for c,ix in scope.items()}
                       for name,pred in saved['classification'].items()}
            fixed_key = 'fixed_head' if 'fixed_head' in saved['classification'] else 'fixed'
            if saved['classification'].get(fixed_key) != base:
                raise ValueError('Fixed-head predictions mismatch: '+episode)
            comparison = []
            metric_path = folder/('metrics.json' if episode=='M12' else 'fit.json')
            if metric_path.is_file():
                reported = json.loads(metric_path.read_text(encoding='utf-8')).get('classification',{})
                for name,values in recount.items():
                    for context,value in values.items():
                        candidate = reported.get(name,{})
                        expected = candidate.get('accuracy') if episode=='M12' and context=='pooled' else candidate.get(context,{}).get('accuracy')
                        if expected is not None:
                            comparison.append({'model':name,'context':context,'recomputed':value,'reported':expected,'matches':abs(value-expected)<1e-12})
            result['episodes'][episode] = {'status':'recounted', 'sha256':digest(prediction_path),
                'fixed_predictions_match':True, 'accuracy_recounts':recount, 'reported_comparisons':comparison,
                'all_available_comparisons_match':all(c['matches'] for c in comparison)}
    target = ROOT/'docs/overnight/2026-10-29/NUMERICAL_AUDIT.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{'status':v['status'],'comparisons':len(v.get('reported_comparisons',[])),
                         'match':v.get('all_available_comparisons_match')} for k,v in result['episodes'].items()}))


if __name__ == '__main__':
    main()
