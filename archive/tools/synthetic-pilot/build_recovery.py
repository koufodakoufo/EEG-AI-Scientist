"""Create and verify a local-only recovery bundle, excluding live controls/auth."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]
NIGHT=ROOT/'.local/overnight-20261029'


def sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def main() -> None:
    target=NIGHT/'recovery'
    if sys.argv[1:]==['--finalize-git']:
        manifest=target/'RECOVERY_MANIFEST.json'
        report=json.loads(manifest.read_text(encoding='utf-8'))
        if sha(target/'private-evidence.tar.gz')!=report['archive_sha256']:
            raise ValueError('Archived evidence changed')
        bundle=target/'repository.bundle'
        if bundle.exists():raise FileExistsError('No overwrite of recovery Git history')
        subprocess.run(['git','bundle','create',str(bundle),'--all'],cwd=ROOT,check=True,timeout=120)
        subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,timeout=30,capture_output=True)
        report.update(git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                      bundle_sha256=sha(bundle),git_bundle_status='verified',finalized_at=datetime.now(timezone.utc).isoformat())
        manifest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2)); return
    if sys.argv[1:]:raise ValueError('Only --finalize-git is accepted')
    target.mkdir(exist_ok=False)
    entries=[]
    for folder in [NIGHT/'private',NIGHT/'public-bundles',NIGHT/'submissions',NIGHT/'evidence']:
        for path in sorted(folder.rglob('*')):
            if path.is_symlink():raise ValueError('Recovery refuses symlink: '+str(path))
            if not path.is_file() or path.suffix=='.lock':continue
            if path.name.lower() in {'auth.json','.env'} or 'credentials' in path.parts:
                raise ValueError('Credential file in export allowlist')
            if path.stat().st_nlink!=1:raise ValueError('Recovery refuses hardlink')
            entries.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    inventory=target/'FILES.json'
    inventory.write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    archive=target/'private-evidence.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
        for entry in entries:tar.add(ROOT/entry['path'],arcname=entry['path'],recursive=False)
    expected={e['path']:e for e in entries}; verified=set()
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            if not member.isfile() or member.name not in expected or member.name in verified:
                raise ValueError('Unexpected recovery member')
            handle=tar.extractfile(member)
            if handle is None:raise ValueError('Missing archive stream')
            digest=hashlib.sha256()
            for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
            if digest.hexdigest()!=expected[member.name]['sha256']:raise ValueError('Archive hash mismatch')
            if sha(ROOT/member.name)!=expected[member.name]['sha256']:raise ValueError('Source changed while archiving')
            verified.add(member.name)
    if verified!=set(expected):raise ValueError('Missing archive entries')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'git_head_at_evidence_archive':head,'files':len(entries),
        'source_bytes':sum(e['bytes'] for e in entries),'archive_bytes':archive.stat().st_size,
        'archive_sha256':sha(archive),'inventory_sha256':sha(inventory),'git_bundle_status':'pending_final_commit',
        'verification':'All tar members streamed, hashed and compared with unchanged source. Final Git bundle is separately verified with --finalize-git.',
        'privacy':'Local-only; contains private reference/evaluation material. Do not upload to GitHub or mount into Actors.',
        'excluded':'No control homes, auth, environment files, dataset, model weights or runtime binary installation.',
        'restore':'Clone repository.bundle into a new empty recovery location only if needed. Restore explicit evidence paths from tar without overwriting a live workspace; verify FILES.json hashes.'}
    (target/'RECOVERY_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
