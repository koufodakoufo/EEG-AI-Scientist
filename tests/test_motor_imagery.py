from pathlib import Path

import numpy as np
import pytest

from eegfm.eeg.motor_imagery import admitted_split, prepare_record, read_record

TEST_RAW_ROOT=Path(__file__).resolve().parent/"synthetic-raw"


def annotation(onset=0., duration=4., description='T1'):
    return {'onset': onset, 'duration': duration, 'description': description}


def prepare(events, signal=None, **kwargs):
    values = np.ones((20, 1600), dtype=float) * 100 if signal is None else signal
    return prepare_record(values, events, subject=1, run=4, split='train', **kwargs)


def test_event_mapping_shape_scale_and_native_onset_samples():
    result = prepare([annotation(), annotation(4, 4, 'T2'), annotation(8, 2, 'T0')])
    assert set(result) == {'schema_version', 'windows', 'y', 'event_onsets_seconds',
                           'window_onsets_seconds', 'metadata'}
    assert result['windows'].shape == (2, 20, 3, 200)
    assert result['windows'].dtype == np.float32
    np.testing.assert_allclose(result['windows'], 1, atol=1e-6)
    np.testing.assert_array_equal(result['y'], [0, 1])
    np.testing.assert_array_equal(result['event_onsets_seconds'], [0, 4])
    np.testing.assert_array_equal(result['window_onsets_seconds'], [.5, 4.5])


def test_half_open_window_excludes_endpoint_and_outside_event():
    # Any leakage beyond [.5,3.5) would introduce the large sentinel.
    signal = np.ones((20, 1600), dtype=float) * 1e8
    signal[:, 80:560] = 100
    result = prepare([annotation(duration=3.5)], signal)
    np.testing.assert_allclose(result['windows'], 1, atol=1e-6)


@pytest.mark.parametrize('events', [
    [annotation(duration=3.49)],
    [annotation(onset=7, duration=4)],
    [annotation(), annotation(3.8, 4, 'T2')],
    [annotation(), annotation(0, 4, 'T2')],
    [annotation(onset=.001)],
    [annotation(duration=float('nan'))],
    [annotation(description='unknown')],
    [annotation(description='T0')],
    [{'onset': 0., 'duration': 4., 'description': 'T1', 'extra': 1}],
])
def test_invalid_annotation_rejects_whole_record(events):
    with pytest.raises(ValueError):
        prepare(events)


@pytest.mark.parametrize('subject,run,split', [(31,4,'test'), (36,4,'validation'),
    (1,3,'train'), (1,6,'train'), (25,4,'train'), (24,4,'validation'),
    (True,4,'train'), (1,4,'test')])
def test_split_and_run_guard_before_file_access(monkeypatch, subject, run, split):
    def forbidden(*args, **kwargs):
        pytest.fail('File was accessed before participant/run guard')
    monkeypatch.setattr(Path, 'open', forbidden)
    with pytest.raises(ValueError):
        read_record(Path('/unopened/S031/S031R04.edf'), subject=subject, run=run, split=split)


@pytest.mark.parametrize('subject,split', [(1,'train'), (24,'train'),
                                        (25,'validation'), (30,'validation')])
@pytest.mark.parametrize('run', [4,8,12])
def test_development_split_boundaries(subject, split, run):
    admitted_split(subject, run, split)


def test_invalid_signals_and_sampling_rate():
    for signal in [np.zeros((19,1600)), np.full((20,1600), np.nan), np.ones((20,1600), dtype=int)]:
        with pytest.raises(ValueError):
            prepare([annotation()], signal)
    with pytest.raises(ValueError):
        prepare([annotation()], sample_rate=200)


def test_duration_generalized_panel_matches_original_five_second_math():
    from eegfm.eeg import api
    from eegfm.eeg.motor_imagery import compute_duration_feature_panel
    values = np.random.default_rng(492).standard_normal((2,20,5,200)).astype(np.float32)
    expected = api.compute_feature_panel(values)
    actual = compute_duration_feature_panel(values)
    np.testing.assert_array_equal(actual, expected)


def test_three_second_panel_sinusoid_expectations():
    from eegfm.eeg.motor_imagery import compute_duration_feature_panel
    # Exactly six cycles in three seconds: variance=.5; unnormalized DFT
    # delta power=(600/2)**2, identical channels have correlation1.
    signal = np.sin(2*np.pi*2*np.arange(600)/200).astype(np.float32)
    values = np.tile(signal, (1,20,1)).reshape(1,20,3,200)
    actual = compute_duration_feature_panel(values)
    assert actual.shape == (1,62) and actual.dtype == np.float32
    assert np.isfinite(actual).all()
    np.testing.assert_allclose(actual[0,[0,2,3,4,5]], .5, rtol=1e-5)
    np.testing.assert_allclose(actual[0,1], 0, atol=1e-7)
    np.testing.assert_allclose(actual[0,12], np.log(300**2), rtol=1e-5)
    np.testing.assert_allclose(actual[0,60:], [1,0], atol=1e-6)


def test_duration_panel_rejects_unknown_duration_and_nonfinite():
    from eegfm.eeg.motor_imagery import compute_duration_feature_panel
    for values in (np.ones((1,20,4,200)),np.full((1,20,3,200),np.nan)):
        with pytest.raises(ValueError):
            compute_duration_feature_panel(values)


def test_trusted_admission_is_immutable_and_pure_preparation_preserves_identity():
    from dataclasses import FrozenInstanceError
    from eegfm.eeg.motor_imagery import TrustedRecordAdmission, prepare_record_trusted
    admission=TrustedRecordAdmission(protocol_sha256='a'*64,raw_root=TEST_RAW_ROOT,
        records=((31,4,'test'),(1,4,'train')))
    with pytest.raises(FrozenInstanceError):
        admission.records=((32,4,'test'),)
    signal=np.ones((20,1600))*100
    result=prepare_record_trusted(signal,[annotation()],subject=31,run=4,split='test',admission=admission)
    assert result['metadata']['subject']=='S031'
    assert result['metadata']['split']=='test'
    assert result['metadata']['admission_protocol_sha256']=='a'*64
    development=prepare_record(signal,[annotation()],subject=1,run=4,split='train')
    trusted=prepare_record_trusted(signal,[annotation()],subject=1,run=4,split='train',admission=admission)
    for key in ('windows','y','event_onsets_seconds','window_onsets_seconds'):
        np.testing.assert_array_equal(trusted[key],development[key])
    trusted['metadata'].pop('admission_protocol_sha256')
    assert trusted['metadata']==development['metadata']


@pytest.mark.parametrize('records', [((31,4,'train'),),((61,4,'test'),),((31,6,'test'),),
    ((True,4,'train'),),((31,4,'test'),(31,4,'test')),[(31,4,'test')],([31,4,'test'],)])
def test_trusted_admission_rejects_bad_or_mutable_inventory(records):
    from eegfm.eeg.motor_imagery import TrustedRecordAdmission
    with pytest.raises(ValueError):
        TrustedRecordAdmission(protocol_sha256='a'*64,raw_root=TEST_RAW_ROOT,records=records)


@pytest.mark.parametrize('subject,run,split,path', [
    (32,4,'test','/raw/S032/S032R04.edf'),
    (31,8,'test','/raw/S031/S031R08.edf'),
    (31,4,'validation','/raw/S031/S031R04.edf'),
    (31,4,'test','/different/S031/S031R04.edf'),
    (31,4,'test','/raw/S031/S031R08.edf'),
    (31,4,'test','/raw/S030/S031R04.edf'),
    (31,4,'test','/raw/S031/../S031/S031R04.edf'),
])
def test_trusted_reader_rejects_before_file_io(monkeypatch,subject,run,split,path):
    from eegfm.eeg import motor_imagery as module
    admission=module.TrustedRecordAdmission(protocol_sha256='a'*64,raw_root=TEST_RAW_ROOT,records=((31,4,'test'),))
    path=TEST_RAW_ROOT/path[5:] if path.startswith('/raw/') else TEST_RAW_ROOT.parent/'different'/path.lstrip('/')
    def forbidden(*args,**kwargs):
        pytest.fail('I/O occurred before immutable admission/path guard')
    monkeypatch.setattr(Path,'open',forbidden)
    monkeypatch.setattr(module,'read_header',forbidden)
    with pytest.raises(ValueError):
        module.read_record_trusted(Path(path),subject=subject,run=run,split=split,admission=admission)


def test_trusted_reader_dispatches_only_exact_admitted_record(monkeypatch):
    from eegfm.eeg import motor_imagery as module
    admission=module.TrustedRecordAdmission(protocol_sha256='a'*64,raw_root=TEST_RAW_ROOT,records=((31,4,'test'),))
    sentinel=object()
    def core(path,*,subject,run,split):
        assert path==TEST_RAW_ROOT/'S031/S031R04.edf'
        assert (subject,run,split)==(31,4,'test')
        return {'sentinel':sentinel,'metadata':{}}
    monkeypatch.setattr(module,'_read_record_core',core)
    result=module.read_record_trusted(TEST_RAW_ROOT/'S031/S031R04.edf',subject=31,run=4,split='test',admission=admission)
    assert result['sentinel'] is sentinel


def test_trusted_scope_requires_frozen_protocol_and_absolute_root():
    from eegfm.eeg.motor_imagery import TrustedRecordAdmission
    for sha,root in [('invalid',Path('/raw')),('a'*64,Path('relative')),('a'*64,TEST_RAW_ROOT/'../raw')]:
        with pytest.raises(ValueError):
            TrustedRecordAdmission(protocol_sha256=sha,raw_root=root,records=((31,4,'test'),))
