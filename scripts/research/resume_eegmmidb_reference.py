"""Single audited continuation after the pre-result OpenMP initialization crash.

The original source, choices, reservation and representation cache are immutable.
Importing sklearn before torch initializes the existing runtime consistently with
the successful prepare process. No unsafe duplicate-OpenMP override is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from sklearn.linear_model import LogisticRegression  # runtime initialization only

import eegmmidb_reference as ref


def resume_reservation(output: Path) -> dict:
    lock_path = output/'REFERENCE_LOCK.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if lock.get('schema') != 'eegmmidb_reference_lock_v1':
        raise ValueError('Wrong source reference schema')
    for row in lock['files']:
        if ref.sha256_file(Path(row['path'])) != row['sha256']:
            raise ValueError('Original frozen source/input changed')
    reservation_path = output/'TEST_RESERVATION.json'
    reservation = json.loads(reservation_path.read_text(encoding='utf-8'))
    if reservation['reference_lock_sha256'] != ref.sha256_file(lock_path):
        raise ValueError('Original reservation/freeze mismatch')
    if any((output/name).exists() for name in ('REFERENCE_TEST_RESULT.json','REFERENCE_TEST_ARRAYS.npz')):
        raise FileExistsError('Cannot resume a reference with scientific output')
    cache = output/'test-representations.npz'
    receipt = output/'test-representations.json'
    metadata = json.loads(receipt.read_text(encoding='utf-8'))
    if ref.sha256_file(cache) != metadata['sha256'] or metadata['input_sha256'] != ref.EXPECTED['test']:
        raise ValueError('Interrupted test cache changed')
    ref.save_json(output/'TEST_RECOVERY_RESERVATION.json', {
        'schema':'eegmmidb_interrupted_reference_continuation_v1',
        'reserved_at_unix':time.time(), 'source_sha256':ref.sha256_file(Path(__file__)),
        'reference_lock_sha256':ref.sha256_file(lock_path),
        'original_reservation_sha256':ref.sha256_file(reservation_path),
        'test_cache_sha256':ref.sha256_file(cache),
        'test_cache_receipt_sha256':ref.sha256_file(receipt),
        'reason':'Original process exit 1, OMP Error 15 duplicate libiomp5md.dll after test cache publication and before scientific output publication',
        'synthetic_reproduction':'numpy then torch then matrix multiplication exits 1; preimport sklearn then torch then same multiplication exits 0',
        'change':'Initialize sklearn runtime before frozen reference import; no change to frozen numerical code, inputs, fits or decisions',
        'unsafe_duplicate_omp_override':False, 'one_continuation_only':True,
        'not_an_independent_new_test':True})
    return reservation


def main() -> None:
    parser = argparse.ArgumentParser()
    for key in ('resources','prepared','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args = parser.parse_args()
    # Override only the reservation gate in memory, after replacing it with a
    # stricter existing-reservation/cache/output guard. Frozen file stays intact.
    ref.reserve_reference_test = resume_reservation
    result = ref.evaluate_reference(args.resources,args.prepared,args.output)
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
