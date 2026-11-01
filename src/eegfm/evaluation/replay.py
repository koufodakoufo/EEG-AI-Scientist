"""Freeze submissions and independently replay declared Python analyses in sandbox.

Reproducibility is distinct from scientific validity and from original execution
provenance. A successful replay cannot prove an analysis was well designed.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from eegfm.agent.actor import build_profile
from eegfm.agent.budget import run_bounded
from eegfm.agent.budget import write_atomic
from eegfm.evaluation.bundle import checked_file
from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.bundle import safe_relative
from eegfm.evaluation.bundle import verify_public_bundle


def validate_commands(value: Any) -> list[dict[str,Any]]:
    if not isinstance(value,list) or not 0<len(value)<=8:
        raise ValueError('COMMANDS.json needs 1–8 analysis commands')
    identifiers:set[str]=set(); owners:set[str]=set()
    records=[]
    for item in value:
        if not isinstance(item,dict) or set(item)!={'command_id','argv','artifacts'}:
            raise ValueError('Command requires exactly command_id, argv and artifacts')
        identifier=item['command_id']; argv=item['argv']; artifacts=item['artifacts']
        if not isinstance(identifier,str) or not identifier.strip() or len(identifier)>100 or identifier in identifiers:
            raise ValueError('Command IDs must be short, nonempty and unique')
        identifiers.add(identifier)
        if not isinstance(argv,list) or not 2<=len(argv)<=24 or any(not isinstance(v,str) or len(v)>4096 or '\x00' in v for v in argv):
            raise ValueError('Invalid command argv')
        if argv[0] not in {'python3','/usr/bin/python3'}:
            raise ValueError('Replay only accepts explicit Python script entry points')
        script=safe_relative(argv[1])
        if script.parts[0]!='output' or script.suffix!='.py':
            raise ValueError('Replay entry script must be output/*.py; no shell or -c')
        if not isinstance(artifacts,list) or not 0<len(artifacts)<=32 or len(set(artifacts))!=len(artifacts):
            raise ValueError('Each command needs unique output artifact paths')
        for name in artifacts:
            if not isinstance(name,str): raise ValueError('Artifact path is not text')
            safe_relative(name)
            if name in owners:
                raise ValueError('An artifact cannot be claimed by multiple commands; preserve distinct stage outputs')
            owners.add(name)
        records.append({'command_id':identifier,'argv':list(argv),'artifacts':list(artifacts)})
    return records


def freeze_submission(output: Path,destination: Path) -> dict[str,Any]:
    if output.is_symlink() or destination.exists(): raise ValueError('Submission source/destination is unsafe or already frozen')
    files=[]; total=0
    for path in sorted(output.rglob('*')):
        if path.is_symlink(): raise ValueError('Submission contains a symlink')
        if not path.is_file(): continue
        if path.stat().st_nlink!=1: raise ValueError('Submission contains a hardlink')
        total+=path.stat().st_size
        if total>64*1024**2 or len(files)>=256: raise ValueError('Submission storage/file-count cap exceeded')
        name=path.relative_to(output).as_posix(); checked_file(output,name)
        files.append({'path':name,'bytes':path.stat().st_size,'sha256':digest_file(path)})
    destination.mkdir(parents=True)
    for entry in files:
        target=destination/safe_relative(entry['path']); target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(output/entry['path'],target)
        if digest_file(target)!=entry['sha256'] or digest_file(output/entry['path'])!=entry['sha256']:
            raise ValueError('Submission changed during freeze')
    manifest={'schema_version':'submission_freeze_v1','files':files,'bytes':total}
    write_atomic(destination.parent/(destination.name+'-manifest.json'),manifest)
    return manifest


def replay_submission(*,frozen_output: Path,public: Path,replay_case: Path,control_home: Path,
                      native_binary: Path,bwrap_dir: Path,run_id: str,evidence_dir: Path) -> dict[str,Any]:
    if os.name!='posix': raise RuntimeError('Sandbox replay requires Linux')
    verify_public_bundle(public)
    commands_path=checked_file(frozen_output,'COMMANDS.json')
    if commands_path.stat().st_size>65536: raise ValueError('Command manifest too large')
    commands=validate_commands(json.loads(commands_path.read_text()))
    for directory in (replay_case,control_home,evidence_dir):
        if directory.exists(): raise FileExistsError(directory)
    replay_case.mkdir(parents=True); control_home.mkdir(parents=True,mode=0o700); evidence_dir.mkdir(parents=True)
    shutil.copytree(public,replay_case/'public')
    for name in ('output','home','tmp'): (replay_case/name).mkdir()
    # Source and the two preregistration inputs are supplied, never prior metrics
    # or reports. These input bytes are explicitly distinguished from regenerated
    # results; a code artifact copied here cannot count as independently produced.
    seeded=[]
    for path in frozen_output.rglob('*.py'):
        name=path.relative_to(frozen_output).as_posix(); checked_file(frozen_output,name)
        destination=replay_case/'output'/safe_relative(name); destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        seeded.append(name)
    declared_outputs={name for command in commands for name in command['artifacts']}
    for name in ('PLAN.md','LOCKED_ANALYSIS.json','COMMANDS.json'):
        if name not in declared_outputs and (frozen_output/name).exists():
            source=checked_file(frozen_output,name)
            shutil.copyfile(source,replay_case/'output'/name); seeded.append(name)
    runtime=control_home.parent/(control_home.name+'-runtime'); runtime.mkdir(mode=0o700)
    for name in ('codex-linux-sandbox','apply_patch','applypatch'): (runtime/name).symlink_to(native_binary)
    profile=build_profile(case=replay_case,public=replay_case/'public',control_home=control_home,runtime=runtime,
                          native_binary=native_binary,bwrap_dir=bwrap_dir)
    (control_home/'actor.config.toml').write_text(profile)
    env={'CODEX_HOME':str(control_home),'HOME':str(control_home),'PATH':str(bwrap_dir)+':/usr/bin:/bin','LANG':'C.UTF-8'}
    ledger=[]; comparisons=[]
    for index,command in enumerate(commands):
        checked_file(replay_case,command['argv'][1])
        argv=[str(native_binary),'sandbox','-C',str(replay_case),'-p','actor','-P','actor','--',
              '/usr/bin/python3','-B',*command['argv'][1:]]
        result=run_bounded(argv,cwd=replay_case,output_dir=evidence_dir/f'command-{index+1:02d}',timeout_seconds=60,
                           env=env,storage_limit_bytes=64*1024**2)
        artifacts=[]
        for name in command['artifacts']:
            try:
                actual=checked_file(replay_case/'output',name); original=checked_file(frozen_output,name)
                actual_hash=digest_file(actual); original_hash=digest_file(original)
                artifacts.append({'artifact_path':name,'sha256':actual_hash})
                comparisons.append({'command_id':command['command_id'],'artifact_path':name,
                                    'replay_sha256':actual_hash,'submission_sha256':original_hash,'matches':actual_hash==original_hash,
                                    'seeded_input':name in seeded,'independently_regenerated':name not in seeded})
            except (ValueError,OSError) as error:
                comparisons.append({'command_id':command['command_id'],'artifact_path':name,'matches':False,'error':str(error)})
        ledger.append({'command_id':command['command_id'],'run_id':run_id,'status':result['status'],
                       'exit_code':result['exit_code'],'data_split':'validation','artifacts':artifacts,
                       'artifact_data_splits':{name:('not_applicable' if Path(name).suffix in {'.py','.md'} or name=='LOCKED_ANALYSIS.json' else 'validation') for name in command['artifacts']},
                       'provenance':'independent_sandbox_replay','argv':command['argv'],'execution_evidence':str(evidence_dir/f'command-{index+1:02d}')})
        if result['status']!='completed': break
    success=len(ledger)==len(commands) and all(r['status']=='completed' for r in ledger) and all(r['matches'] for r in comparisons)
    report={'schema_version':'replay_report_v2','status':'passed' if success else 'failed','run_id':run_id,
            'comparisons':comparisons,'command_ledger':ledger,'profile_sha256':hashlib.sha256(profile.encode()).hexdigest(),
            'seeded_inputs':seeded,'all_commands_completed':len(ledger)==len(commands) and all(r['status']=='completed' for r in ledger),
            'auth_present':False,'model_calls':0,'scientific_validity':'not established by replay',
            'original_execution_provenance':'consult separate Codex event trace; replay does not retroactively certify original execution'}
    write_atomic(evidence_dir/'replay-report.json',report)
    return report
