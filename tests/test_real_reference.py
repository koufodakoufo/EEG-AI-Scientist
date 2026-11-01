from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest


def test_reference_test_reservation_is_once_and_checks_frozen_bytes(tmp_path: Path) -> None:
    from eegfm.eeg.reference import reserve_reference_test
    source=tmp_path/'parameters.json'
    source.write_text('{}')
    receipt={'schema':'real_reference_lock_v1','files':[{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
    (tmp_path/'REFERENCE_LOCK.json').write_text(json.dumps(receipt))
    reserve_reference_test(tmp_path)
    with pytest.raises(FileExistsError):
        reserve_reference_test(tmp_path)


def test_reference_test_denied_after_parameter_change(tmp_path: Path) -> None:
    from eegfm.eeg.reference import reserve_reference_test
    source=tmp_path/'parameters.json'
    source.write_text('{}')
    receipt={'schema':'real_reference_lock_v1','files':[{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
    (tmp_path/'REFERENCE_LOCK.json').write_text(json.dumps(receipt))
    source.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='changed'):
        reserve_reference_test(tmp_path)
    assert not (tmp_path/'TEST_RESERVATION.json').exists()


def test_head_uses_train_transform_and_paired_ba_is_symmetric() -> None:
    from eegfm.eeg.statistics import fit_head
    from eegfm.eeg.statistics import head_logits
    from eegfm.eeg.reference import balanced_accuracy
    x=np.arange(40,dtype=float).reshape(20,2)
    y=np.tile([0,1],10)
    fit=fit_head(x,y,x+1000,y,c_grid=(0.1,1.0))
    np.testing.assert_allclose(fit['x_mean'],x.mean(0))
    logits=head_logits(fit,x)
    assert balanced_accuracy(y,logits)+balanced_accuracy(y,-logits) == pytest.approx(1.0)


def test_representation_cache_refuses_changed_producer(tmp_path: Path) -> None:
    from unittest.mock import patch
    from eegfm.eeg import reference
    prepared=tmp_path/'prepared'
    output=tmp_path/'output'
    prepared.mkdir()
    output.mkdir()
    source=prepared/'train.npz'
    source.write_bytes(b'input fixture')
    target=output/'train-representations.npz'
    target.write_bytes(b'cache fixture')
    receipt={'sha256':reference.sha256_file(target),'input_sha256':reference.sha256_file(source),'producer':{'version':'old'}}
    (output/'train-representations.json').write_text(json.dumps(receipt))
    with patch.object(reference,'cache_provenance',return_value={'version':'new'},create=True):
        with pytest.raises(ValueError,match='producer'):
            reference.cache_split(tmp_path,prepared,output,'train')


def test_empty_or_zero_rank_interventions_do_not_claim_q2_q3_complete() -> None:
    from eegfm.eeg.reference import reference_coverage
    q1=[{'r2':0.4} for _ in range(24)]
    assert reference_coverage(q1,[])['scope']=='Q1 only'
    assert reference_coverage(q1,[{'rank':0}])['status']=='real_reference_partial'
    assert reference_coverage(q1,[{'rank':2},{'rank':3}])['status']=='real_reference_complete'
    assert reference_coverage([{'r2':float('nan')}],[])['scope']=='not estimable'
