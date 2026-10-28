"""Research benchmark tools; semantic judging remains an explicit input."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .bundle import create_public_bundle, verify_public_bundle, freeze_experiment, verify_seal
from .claims import extract_structured_claims, parse_claim_output
from .evidence import audit_evidence
from .scoring import score_directional


def load(path: Path) -> Any:
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Structured input exceeds 8 MiB')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_new(path: Path | None, value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if path is None:
        print(text, end='')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            handle.write(text)


def parser() -> argparse.ArgumentParser:
    result=argparse.ArgumentParser(prog='eegfm research-bench',description=__doc__)
    commands=result.add_subparsers(dest='command',required=True)
    p=commands.add_parser('validate-claims'); p.add_argument('input',type=Path)
    p=commands.add_parser('score'); p.add_argument('--agent',type=Path,required=True); p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--matches',type=Path,required=True); p.add_argument('--task-id'); p.add_argument('--run-id'); p.add_argument('--out',type=Path)
    p=commands.add_parser('audit-evidence'); p.add_argument('--records',type=Path,required=True); p.add_argument('--artifacts',type=Path,required=True)
    p.add_argument('--commands',type=Path,required=True); p.add_argument('--run-id'); p.add_argument('--data-split'); p.add_argument('--out',type=Path)
    p=commands.add_parser('export-public'); p.add_argument('--source',type=Path,required=True); p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--allowlist',type=Path,required=True,help='JSON array of exact relative filenames'); p.add_argument('--task-id',required=True)
    p.add_argument('--tier',required=True,choices=['real_eeg','intermediate_features','synthetic_mechanism'])
    p=commands.add_parser('verify-public'); p.add_argument('root',type=Path)
    for name in ('freeze','verify-freeze'):
        p=commands.add_parser(name); p.add_argument('--public',type=Path,required=True); p.add_argument('--reference',type=Path,required=True); p.add_argument('--seal',type=Path,required=True)
        if name=='freeze':
            p.add_argument('--policy',type=Path,required=True); p.add_argument('--budget',type=Path,required=True); p.add_argument('--routes',type=Path,required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args=parser().parse_args(argv)
    try:
        if args.command=='validate-claims':
            claims=extract_structured_claims(load(args.input)); save_new(None,{'valid':True,'count':len(claims)})
        elif args.command=='score':
            value=score_directional(extract_structured_claims(load(args.agent)),extract_structured_claims(load(args.reference)),load(args.matches),task_id=args.task_id,run_id=args.run_id)
            save_new(args.out,value)
        elif args.command=='audit-evidence':
            value=audit_evidence(load(args.records),args.artifacts,load(args.commands),expected_run_id=args.run_id,expected_data_split=args.data_split)
            save_new(args.out,value)
        elif args.command=='export-public':
            save_new(None,create_public_bundle(args.source,args.destination,load(args.allowlist),task_id=args.task_id,tier=args.tier))
        elif args.command=='verify-public': save_new(None,verify_public_bundle(args.root))
        elif args.command=='freeze': save_new(None,freeze_experiment(args.public,args.reference,load(args.policy),load(args.budget),load(args.routes),args.seal))
        elif args.command=='verify-freeze': save_new(None,verify_seal(args.public,args.reference,args.seal))
        return 0
    except (ValueError,OSError,TypeError,KeyError) as error:
        print(json.dumps({'status':'invalid','error_type':type(error).__name__,'error':str(error)}),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
