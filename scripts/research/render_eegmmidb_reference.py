"""Aggregate-only figure from the completed private EEGMMIDB reference."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    root=Path(__file__).resolve().parents[2]
    reference=root/'.local/research/2026-10-30-extension/eegmmidb/private_builder/reference'
    result=json.loads((reference/'REFERENCE_TEST_RESULT.json').read_text(encoding='utf-8'))
    dev=json.loads((reference/'DEVELOPMENT_RESULT.json').read_text(encoding='utf-8'))
    fig=plt.figure(figsize=(12,6),layout='constrained')
    grid=fig.add_gridspec(2,2,width_ratios=[1.35,1])
    heat=fig.add_subplot(grid[:,0])
    labels=[r['feature'] for r in result['q1'][:12]]
    values=np.asarray([[next(r['r2'] for r in result['q1'] if r['feature']==f and r['layer']==layer) for layer in (6,12)] for f in labels])
    art=heat.imshow(values,cmap='RdBu',vmin=-1,vmax=1,aspect='auto')
    heat.set_xticks([0,1],['Layer 6','Layer 12'])
    heat.set_yticks(range(12),labels,fontsize=8)
    for i in range(12):
        for j in range(2):
            heat.text(j,i,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=9,color='white' if abs(values[i,j])>.6 else 'black')
    heat.set_title('Q1: held-out feature recovery (raw R²)',fontsize=12)
    fig.colorbar(art,ax=heat,shrink=.6,label='R²; point estimates only')
    head=fig.add_subplot(grid[0,1])
    head.bar(['Validation','Held-out test'],[100*dev['head']['balanced_accuracy'],100*result['head']['balanced_accuracy']],color=['#72879b','#213e57'])
    head.set_ylim(0,100)
    head.set_ylabel('Balanced accuracy (%)')
    head.set_title('Frozen backbone + new linear head',fontsize=12)
    for x,y in enumerate([100*dev['head']['balanced_accuracy'],100*result['head']['balanced_accuracy']]):
        head.text(x,y+2,f'{y:.1f}%',ha='center')
    q2=fig.add_subplot(grid[1,1])
    points=np.asarray([r['learned_minus_mean_random_balanced_accuracy']*100 for r in result['q2_q3']])
    intervals=np.asarray([r['contrast_ci95'] for r in result['q2_q3']])*100
    q2.errorbar(points,[1,0],xerr=np.stack((points-intervals[:,0],intervals[:,1]-points)),fmt='o',capsize=5,color='#213e57')
    q2.axvline(0,color='gray',linestyle='--',linewidth=1)
    q2.set_yticks([1,0],['Theta, L6','Delta, L6'])
    q2.set_ylim(-.5,1.5)
    q2.set_xlabel('Learned minus mean random control BA (pp)')
    q2.set_title('Q2: participant bootstrap 95% intervals',fontsize=12)
    fig.suptitle('EEGMMIDB baseline conditions · Builder reference, not Actor results',fontsize=14)
    fig.supxlabel('6 held-out participants / 144 windows · Q1: 20/24 positive point estimates; 2/24 family-adjusted lower bounds > 0\nFixed R01/R02 order and artifacts limit causal interpretation; both intervention contrasts include zero.',fontsize=9)
    dest=root/'docs/research/2026-10-30-extension/eegmmidb-reference-summary.png'
    fig.savefig(dest,dpi=180)
    plt.close(fig)
    print(dest)


if __name__=='__main__':
    main()
