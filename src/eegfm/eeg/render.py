"""Render a curated aggregate report; private arrays and gold remain private."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'


def main() -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    result_path = args.reference / 'REFERENCE_TEST_RESULT.json'
    result = json.loads(result_path.read_text(encoding='utf-8'))
    arrays_path = args.reference / 'REFERENCE_TEST_ARRAYS.npz'
    assert hashlib.sha256(arrays_path.read_bytes()).hexdigest() == result['arrays_sha256']
    with np.load(arrays_path, allow_pickle=False) as archive:
        data = dict(archive)
    def ba(logits: np.ndarray) -> float:
        predicted = logits >= 0
        return float(np.mean([np.mean(predicted[data['y'] == c] == c) for c in (0, 1)]))
    errors = [abs(ba(data['original_logits']) - result['head']['balanced_accuracy'])]
    for i, group in enumerate(result['q1']):
        offset = i % 12
        columns = list(range(offset * 6, offset * 6 + 6)) if offset < 10 else [60 + offset - 10]
        truth = data['features'][:, columns].astype(np.float64)
        prediction = data[f'probe_{i}_predictions'].astype(np.float64)
        score = 1 - np.sum((truth - prediction)**2, axis=0) / np.sum((truth - truth.mean(axis=0))**2, axis=0)
        errors.append(abs(float(np.mean(score)) - group['r2']))
    for i, group in enumerate(result['q2_q3']):
        values = [ba(data[f'intervention_{i}_{v}_logits']) for v in range(4)]
        errors.extend(abs(values[v] - group['variants'][v]['balanced_accuracy']) for v in range(4))
        errors.append(abs(values[0] - np.mean(values[1:]) - group['learned_minus_mean_random_balanced_accuracy']))
    if max(errors) > 1e-10:
        raise ValueError('Independent direct-math audit disagrees')
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps({'status': 'passed', 'scope': 'independent raw-array point estimates, not full-model replay or CI verification',
        'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(), 'arrays_sha256': result['arrays_sha256'],
        'checked_scalar_count': len(errors), 'maximum_absolute_difference': max(errors)}, indent=2), encoding='utf-8')
    args.output.mkdir(parents=True, exist_ok=True)
    names = [row['feature'] for row in result['q1'][:12]]
    values = np.asarray([[result['q1'][i]['r2'], result['q1'][i+12]['r2']] for i in range(12)])
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig, (left, right) = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={'width_ratios': [1.05, 1]}, constrained_layout=True)
    heat = left.imshow(values, cmap='RdBu', vmin=-1, vmax=1, aspect='auto')
    left.set_xticks([0, 1], ['Layer 6', 'Layer 12'])
    left.set_yticks(range(12), names)
    for i in range(12):
        for j in range(2):
            row = result['q1'][i + j * 12]
            star = '*' if row['r2_family_adjusted_ci'][0] > 0 else ''
            left.text(j, i, f'{values[i,j]:.3f}{star}', ha='center', va='center',
                      color='white' if abs(values[i,j]) > .65 else 'black')
    left.set_title('A  Held-out feature recovery (raw R²)')
    left.set_xlabel('Color saturates at ±1; annotations retain actual R².\n* Adjusted bootstrap lower bound > 0; 24-group family.')
    fig.colorbar(heat, ax=left, shrink=.7, label='R²')
    colors = ['#175c9b', '#b66b25']
    for i, group in enumerate(result['q2_q3']):
        point = 100 * group['learned_minus_mean_random_balanced_accuracy']
        low, high = np.asarray(group['contrast_family_adjusted_ci']) * 100
        right.errorbar(point, i, xerr=[[point-low], [high-point]], fmt='o', color=colors[i], capsize=5, markersize=8)
        learned = group['variants'][0]
        right.annotate(f"Residual R² = {learned['residual_r2']:.3f}\nRank = {group['rank']}",
                       (point, i), xytext=(0, 22), textcoords='offset points', ha='center')
    right.axvline(0, color='#999999', linewidth=1, linestyle='--')
    right.set_yticks([0, 1], ['Wavelet detail variance', 'Sample-entropy proxy'])
    right.set_ylim(-.65, 1.65)
    right.set_xlim(-6, 4)
    right.set_xlabel('Learned minus mean matched-random balanced accuracy\n(percentage points; 97.5% participant-bootstrap intervals)')
    right.set_title('B  Selected layer-6 interventions versus controls')
    right.grid(axis='x', alpha=.2)
    fig.suptitle('EEGMAT × frozen pretrained CBraMod + new linear head\nReference analysis; 6 held-out participants / 144 windows; not an Actor result', fontsize=13)
    fig.savefig(args.output / 'reference-science.png', dpi=180)
    fig.savefig(args.output / 'reference-science.pdf')
    plt.close(fig)
    print(json.dumps({'status': 'rendered', 'point_audit_max_error': max(errors)}))


if __name__ == '__main__':
    main()
