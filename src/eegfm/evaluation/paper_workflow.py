"""Local file boundaries for a paper workflow. Source text is inert data."""

from __future__ import annotations

import hashlib
import json
import math
import re
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from eegfm.evaluation.assessment import ReplayMismatch, ReplayProvider
from eegfm.evaluation.claims import canonical_sha256
from eegfm.evaluation.paper import CONDITION_FIELDS

_RESOURCES_FIELDS = {'schema_version', 'task_id', 'revision', 'paper', 'scope', 'resources',
                     'constraints', 'budget', 'resource_text'}
_CALL_FIELDS = {'request', 'request_sha256', 'raw_response', 'response_sha256', 'status', 'failure'}
_CALL_STATUSES = {'complete', 'truncated', 'service_failure', 'invalid_output'}
_SHA256 = re.compile(r'[0-9a-f]{64}')


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_utf8(path: Path) -> tuple[bytes, str]:
    """Read and strictly decode without newline translation."""
    raw = path.read_bytes()
    return raw, raw.decode('utf-8')


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _fields(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or value.keys() != fields:
        raise ValueError(f'{label} fields mismatch')


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f'Duplicate JSON key: {name}')
        result[name] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('JSON number must be finite')
    return number


def _parse_json(text: str) -> dict[str, Any]:
    value = json.loads(text, object_pairs_hook=_json_object, parse_constant=_finite_float,
                       parse_float=_finite_float)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def read_json(path: Path) -> dict[str, Any]:
    return _parse_json(read_utf8(path)[1])


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def load_resources(path: Path) -> dict[str, Any]:
    """Validate public resources without inferring experimental conditions."""
    resources = read_json(path)
    _fields(resources, _RESOURCES_FIELDS, 'Resource manifest')
    if resources['schema_version'] != 'paper_resources_v1':
        raise ValueError('Unknown resource manifest version')
    paper = resources['paper']
    scope = resources['scope']
    _fields(paper, {'title', 'version', 'uri'}, 'Paper identity')
    _fields(scope, {'dataset', 'model', 'split', 'conditions'}, 'Resource scope')
    text_values = [resources[key] for key in ('task_id', 'revision', 'resource_text')]
    text_values.extend(paper.values())
    text_values.extend(scope[key] for key in ('dataset', 'model', 'split'))
    if not all(map(_is_text, text_values)):
        raise ValueError('Resource identity and description require nonempty text')
    conditions = scope['conditions']
    if not isinstance(conditions, dict) or not CONDITION_FIELDS <= conditions.keys():
        raise ValueError('Experimental conditions missing; use explicit null for unknowns')
    for key in ('resources', 'constraints'):
        values = resources[key]
        if not isinstance(values, list) or not values or not all(map(_is_text, values)):
            raise ValueError(f'{key} must be a nonempty text list')
    budget = resources['budget']
    if not isinstance(budget, dict) or not budget or any(type(cap) not in (int, float) or cap <= 0
                                                        for cap in budget.values()):
        raise ValueError('Resource budget must contain finite positive numeric caps')
    canonical_sha256(resources)  # Reject data that cannot be encoded as UTF-8 JSON.
    return resources


def verbatim_reference(paper: str, span: dict[str, Any]) -> dict[str, Any]:
    """Return the exact reference and its code point interval in the full paper."""
    _fields(span, {'start', 'end', 'quote'}, 'Reference span')
    start, end, quote = span['start'], span['end'], span['quote']
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(paper)
            or paper[start:end] != quote):
        raise ValueError('Reference span must match the exact Unicode substring')
    return {'start': start, 'end': end, 'quote': quote,
            'paper_sha256': bytes_sha256(paper.encode('utf-8')),
            'reference_sha256': bytes_sha256(quote.encode('utf-8'))}


def write_immutable(path: Path, data: bytes) -> None:
    """Create an evidence file exclusively or verify the existing exact bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as handle:
            handle.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError(f'Conflicting existing bytes: {path}')


def _replace_pending(path: Path, data: bytes) -> None:
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def _queue_entry_exists(path: Path, *, directory: bool = False) -> bool:
    """Check the entry itself without following links, including Windows junctions."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ReplayMismatch(f'Queue path could not be inspected: {path}') from exc
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    reparse_point = getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    if reparse_point or not expected_type(info.st_mode):
        raise ReplayMismatch(f'Queue path is redirected or has an unexpected file type: {path}')
    return True


class AwaitingResponse(Exception):
    """The request is queued and no terminal response has been delivered."""


class FileProvider:
    """Bridge requests to local files; no model calls and no implicit retries.

    After a stage, check pending before recording terminal artifacts:
    assessment._invoke catches temporary provider exceptions. Consumed
    response file hashes are available for binding in stage receipts.
    """

    def __init__(self, root: Path, *, max_requests: int):
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError('Request budget must be a positive integer')
        self.root = root.absolute()
        self.max_requests = max_requests
        self._check_layout()
        self._queued: set[str] = set()
        for path in (self.root / 'requests').glob('*.json'):
            if _queue_entry_exists(path):
                self._queued.add(path.stem)
        if any(not _SHA256.fullmatch(key) for key in self._queued):
            raise ReplayMismatch('Queue contains a request without a canonical filename')
        if len(self._queued) > max_requests:
            raise ReplayMismatch('File provider request budget exceeded')
        self.pending = [self._pending_entry(digest) for digest in sorted(self._queued)
                        if not _queue_entry_exists(self.root / 'responses' / (digest + '.json'))]
        self.response_file_hashes: dict[str, str] = {}

    def _check_layout(self) -> None:
        # Walk top down so a path under a redirect is never inspected. This
        # checks the static tree used by the single-writer workflow.
        directories = (*reversed(self.root.parents), self.root,
                       self.root / 'requests', self.root / 'responses')
        for directory in directories:
            _queue_entry_exists(directory, directory=True)
        _queue_entry_exists(self.root / 'pending.json')

    @staticmethod
    def _pending_entry(digest: str) -> dict[str, str]:
        filename = digest + '.json'
        return {'request_sha256': digest, 'request_path': f'requests/{filename}',
                'response_path': f'responses/{filename}'}

    def _save_pending(self, digest: str, waiting: bool) -> None:
        self.pending[:] = [entry for entry in self.pending if entry['request_sha256'] != digest]
        if waiting:
            self.pending.append(self._pending_entry(digest))
            self.pending.sort(key=lambda entry: entry['request_sha256'])
        path = self.root / 'pending.json'
        if waiting or path.exists():
            data = json_bytes({'pending': self.pending})
            if not path.exists() or path.read_bytes() != data:
                _replace_pending(path, data)

    def _queue(self, request: dict[str, Any]) -> str:
        unsigned = dict(request)
        digest = unsigned.pop('request_sha256', None)
        if digest != canonical_sha256(unsigned):
            raise ReplayMismatch('Invalid canonical request hash')
        filename = digest + '.json'
        self._check_layout()
        request_path = self.root / 'requests' / filename
        request_exists = _queue_entry_exists(request_path)
        _queue_entry_exists(self.root / 'responses' / filename)
        if digest in self._queued and not request_exists:
            raise ReplayMismatch('Previously queued request disappeared')
        if digest not in self._queued and len(self._queued) >= self.max_requests:
            raise ReplayMismatch('File provider request budget exceeded')
        write_immutable(request_path, json_bytes(request))
        self._queued.add(digest)
        return digest

    def _read_response(self, request: dict[str, Any], digest: str) -> tuple[ReplayProvider, str] | None:
        path = self.root / 'responses' / (digest + '.json')
        try:
            data, text = read_utf8(path)
        except FileNotFoundError:
            if digest in self.response_file_hashes:
                raise ReplayMismatch('Previously consumed response disappeared') from None
            return None
        file_hash = bytes_sha256(data)
        if digest in self.response_file_hashes and self.response_file_hashes[digest] != file_hash:
            raise ReplayMismatch('Previously consumed response bytes changed')
        record = _parse_json(text)
        _fields(record, _CALL_FIELDS, 'Response call record')
        if not isinstance(record['request'], dict):
            raise ValueError('Response call record request must be an object')
        status, raw, failure = record['status'], record['raw_response'], record['failure']
        if status not in _CALL_STATUSES or (raw is not None and not isinstance(raw, str)):
            raise ValueError('Invalid response call record status or raw response')
        if failure is not None:
            _fields(failure, {'type', 'message'}, 'Response failure')
            if not _is_text(failure['type']) or not isinstance(failure['message'], str):
                raise ValueError('Invalid response failure type or message')
            # JSON escapes can decode to lone surrogates even in a UTF-8 file.
            failure['type'].encode('utf-8')
            failure['message'].encode('utf-8')
        if raw is None and (status != 'service_failure' or failure is None):
            raise ValueError('Missing raw response requires an explicit terminal failure')
        if raw is not None and (status == 'invalid_output') != (failure is not None):
            raise ValueError('Raw response failure metadata disagrees with its status')
        replay = ReplayProvider([record])
        if record['request_sha256'] != digest or record['request'] != request:
            raise ReplayMismatch('Saved request differs from queued request')
        return replay, file_hash

    def __call__(self, request: dict[str, Any]) -> str:
        try:
            digest = self._queue(request)
            response = self._read_response(request, digest)
            self._save_pending(digest, waiting=response is None)
        except ReplayMismatch:
            raise
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise ReplayMismatch(f'Invalid local queue evidence: {exc}') from exc
        if response is None:
            raise AwaitingResponse(f'Awaiting response for {digest}')
        replay, file_hash = response
        # Leave the recorded provider exception intact for assessment._invoke.
        try:
            return replay(request)
        finally:
            replay.assert_consumed()
            self.response_file_hashes[digest] = file_hash
