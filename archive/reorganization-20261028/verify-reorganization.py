from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path('X:/projects/EEG-AI-Scientist')
TEMP = Path('C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI')
RECORD = ROOT / 'archive/reorganization-20261028'
EVIDENCE = ROOT / 'archive/setup-20261028/evidence'

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8-sig'))

errors: list[str] = []
mapping: list[dict[str, str]] = read_json(RECORD / 'original-files-map.json')
for item in mapping:
    current = Path(item['current'])
    if not current.is_file() or digest(current) != item['sha256']:
        errors.append('Original preservation mismatch: ' + item['original'])
source: list[dict[str, Any]] = read_json(EVIDENCE / 'source-provenance/source-file-manifest.json')
for item in source:
    target = ROOT / 'framework' / item['path']
    if not target.is_file() or digest(target) != item['sha256']:
        errors.append('Framework mismatch: ' + item['path'])
for relative in ['docs', 'scripts', 'workspaces', 'reports/environment-20261028']:
    if (TEMP / relative).exists():
        errors.append('C task-created content remains: ' + relative)
if (TEMP / '.git').exists() or (ROOT / 'framework/.git').exists():
    errors.append('Unexpected nested/temporary Git repository')
if not (TEMP / 'reports/ncclab-server-report.md').is_file():
    errors.append('Pre-existing C server report missing')
baseline: dict[str, Any] = read_json(RECORD / 'completed.json')
for name in ['index', 'config']:
    if digest(ROOT / '.git' / name) != baseline[name + '_sha256']:
        errors.append('Original Git ' + name + ' changed')
head = subprocess.check_output(['git', '--no-optional-locks', '-c', 'safe.directory=X:/projects/EEG-AI-Scientist', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
if head != baseline['head']:
    errors.append('Original Git HEAD changed')
new_ignore = (ROOT / '.gitignore').read_bytes()
old_ignore = (RECORD / 'gitignore-before.txt').read_bytes()
new_normalized = new_ignore.replace(b'\r\n', b'\n')
old_normalized = old_ignore.replace(b'\r\n', b'\n').rstrip(b'\n')
if not new_normalized.startswith(old_normalized):
    errors.append('Original gitignore content was not retained as a prefix')
result = {'original_business_files_verified': len(mapping), 'framework_files_verified': len(source),
          'git_index_config_head_preserved': not any('Git' in e for e in errors),
          'c_task_created_workspaces_retired': not any('C task' in e for e in errors),
          'preexisting_c_reports_retained': not any('report missing' in e for e in errors),
          'original_gitignore_preserved_in_archive_and_prefix': not any('gitignore' in e for e in errors),
          'errors': errors, 'ok': not errors}
(RECORD / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
if errors:
    raise SystemExit(1)
