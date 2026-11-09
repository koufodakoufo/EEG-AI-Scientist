"""Canonical stdlib-only argument definitions shared by help and execution."""
from __future__ import annotations
import argparse
from pathlib import Path


def task_parser(command: str, *, description: str | None = None) -> argparse.ArgumentParser:
    """Build task arguments without importing a scientific implementation."""
    parser = argparse.ArgumentParser(prog="eegfm " + command, description=description,
        epilog="Scientific execution requires optional dependencies. From the source checkout: python -m pip install -e '.[science]'.")
    if command == 'paper':
        parser.description = 'Prepare, freeze and compare a paper-derived research task locally.'
        parser.epilog = 'Requests are queued as files. Re-run the same command after an external bridge delivers responses.'
        commands = parser.add_subparsers(dest='command', required=True)
        prepare = commands.add_parser('prepare', help='draft a task and extract its private reference')
        prepare.add_argument('--paper', type=Path, required=True, help='complete paper as UTF-8 text')
        prepare.add_argument('--resources', type=Path, required=True, help='available resources and execution scope as JSON')
        prepare.add_argument('--out', type=Path, required=True, help='preparation directory')
        prepare.add_argument('--policy', type=Path, required=True, help='policy JSON outside the preparation directory')
        prepare.add_argument('--parent', type=Path, help='previous work directory when starting a new revision')
        freeze = commands.add_parser('freeze', help='bind an independent review and export the public task')
        freeze.add_argument('--work', type=Path, required=True, help='prepared work directory')
        freeze.add_argument('--review', type=Path, required=True, help='independent review JSON')
        compare = commands.add_parser('compare', help='assess a complete report against a frozen reference')
        compare.add_argument('--work', type=Path, required=True, help='frozen work directory')
        compare.add_argument('--report', type=Path, required=True, help='complete final report as UTF-8 text')
        compare.add_argument('--out', type=Path, required=True, help='separate comparison directory')
        compare.add_argument('--evidence', type=Path, help='trusted numerical verdicts and process checks as JSON')
    elif command == 'driver':
        parser.add_argument('command', choices=['run', 'start'])
        parser.add_argument('--run', required=True)
        parser.add_argument('--agent', choices=['claude', 'codex', 'script'], required=True)
        parser.add_argument('--model')
        parser.add_argument('--script', help='offline test agent')
        parser.add_argument('--poll', type=float, default=60.0)
        parser.add_argument('--session-timeout', type=float, default=4 * 3600)
        parser.add_argument('--max-sessions', type=int, default=100)
        parser.add_argument('--stall-limit', type=int, default=3)
        parser.add_argument('--backoff', type=float, default=60.0)
        parser.add_argument('--once', action='store_true', help='at most one agent session or poll, then exit')
        parser.add_argument('--writable', action='append', default=None, help='extra writable directory for the agent (repeatable); defaults to WRITABLE_DEFAULTS')
        parser.add_argument('--agent-arg', action='append', default=[], help='extra CLI argument passed to the agent, e.g. --agent-arg=-c --agent-arg=model_reasoning_effort="xhigh"')
    elif command == 'episode':
        parser.add_argument('--config', required=True, type=Path)
    elif command == 'reference':
        parser.add_argument('command', choices=['prepare', 'test'])
        parser.add_argument('--resources', type=Path, required=True)
        parser.add_argument('--prepared', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--protocol', type=Path)
    elif command == 'export':
        for name in ('resources', 'prepared', 'reference', 'public', 'private'):
            parser.add_argument('--' + name, type=Path, required=True)
    elif command == 'prepare-eegmmidb':
        parser.add_argument('--phase', choices=['freeze', 'probe', 'download', 'prepare', 'verify', 'feature-smoke', 'all'], required=True)
        parser.add_argument('--proxy', default=None, help='Optional existing HTTP proxy, e.g. http://127.0.0.1:10808')
        parser.add_argument('--workers', type=int, default=4)
        parser.add_argument('--allow-test', action='store_true')
        parser.add_argument('--root', type=Path, required=True, help='New or existing owned EEGMMIDB preparation directory')
        parser.add_argument('--parent', type=Path, required=True, help='Explicit authorized parent of the preparation directory')
    elif command == 'eegmmidb-reference':
        parser.add_argument('command', choices=['prepare', 'test'])
        parser.add_argument('--resources', type=Path, required=True)
        parser.add_argument('--prepared', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--protocol', type=Path)
    elif command == 'eegmmidb-export':
        for name in ('resources', 'prepared', 'reference', 'public', 'private'):
            parser.add_argument('--' + name, type=Path, required=True)
    elif command == 'baselines':
        parser.add_argument('phase', choices=('prepare', 'test'))
        parser.add_argument('--resources', required=True, type=Path)
        parser.add_argument('--prepared', required=True, type=Path)
        parser.add_argument('--reference', required=True, type=Path)
        parser.add_argument('--output', required=True, type=Path)
    elif command == 'bootstrap':
        parser.add_argument('--reference', type=Path, required=True)
        parser.add_argument('--baseline', type=Path, required=True)
        parser.add_argument('--output', type=Path, required=True)
        parser.add_argument('--report', type=Path, required=True)
    elif command == 'replay':
        parser.add_argument('--config', type=Path, required=True)
        parser.add_argument('--replay-root', type=Path, required=True)
        parser.add_argument('--candidate', type=Path, required=True)
        parser.add_argument('--attempt', default='A2')
        parser.add_argument('--cpus', default='4,5,6,7')
        parser.add_argument('--audit-e05-q1', action='store_true')
    elif command == 'calibrate':
        commands = parser.add_subparsers(dest='command', required=True)
        check = commands.add_parser('check')
        check.add_argument('--fixtures', type=Path, required=True)
        staging = commands.add_parser('stage')
        staging.add_argument('--fixtures', type=Path, required=True)
        staging.add_argument('--destination', type=Path, required=True)
        staging.add_argument('--extract-call', required=True)
        staging.add_argument('--judge-call', required=True)
        staging.add_argument('--runtime', type=Path, help='Explicit native runtime JSON, required before any run-native invocation')
        native = commands.add_parser('run-native')
        native.add_argument('--job', type=Path, required=True)
        native.add_argument('--freeze-sha256', required=True)
        scoring = commands.add_parser('score')
        scoring.add_argument('--stage', type=Path, required=True)
        scoring.add_argument('--freeze-sha256', required=True)
        scoring.add_argument('--extraction-evidence', type=Path, required=True)
        scoring.add_argument('--judge-evidence', type=Path, required=True)
        scoring.add_argument('--output', type=Path, required=True)
    elif command == 'legacy-score':
        commands = parser.add_subparsers(dest='command', required=True)
        p = commands.add_parser('validate-claims')
        p.add_argument('input', type=Path)
        p = commands.add_parser('score')
        p.add_argument('--agent', type=Path, required=True)
        p.add_argument('--reference', type=Path, required=True)
        p.add_argument('--matches', type=Path, required=True)
        p.add_argument('--task-id')
        p.add_argument('--run-id')
        p.add_argument('--out', type=Path)
        p = commands.add_parser('audit-evidence')
        p.add_argument('--records', type=Path, required=True)
        p.add_argument('--artifacts', type=Path, required=True)
        p.add_argument('--commands', type=Path, required=True)
        p.add_argument('--run-id')
        p.add_argument('--data-split')
        p.add_argument('--out', type=Path)
        p = commands.add_parser('export-public')
        p.add_argument('--source', type=Path, required=True)
        p.add_argument('--destination', type=Path, required=True)
        p.add_argument('--allowlist', type=Path, required=True, help='JSON array of exact relative filenames')
        p.add_argument('--task-id', required=True)
        p.add_argument('--tier', required=True, choices=['real_eeg', 'intermediate_features', 'synthetic_mechanism'])
        p = commands.add_parser('verify-public')
        p.add_argument('root', type=Path)
        for name in ('freeze', 'verify-freeze'):
            p = commands.add_parser(name)
            p.add_argument('--public', type=Path, required=True)
            p.add_argument('--reference', type=Path, required=True)
            p.add_argument('--seal', type=Path, required=True)
            if name == 'freeze':
                p.add_argument('--policy', type=Path, required=True)
                p.add_argument('--budget', type=Path, required=True)
                p.add_argument('--routes', type=Path, required=True)
    else:
        raise ValueError(f"Unknown task command: {command}")
    return parser
