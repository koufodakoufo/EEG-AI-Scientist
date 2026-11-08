from pathlib import Path

import numpy as np
import pytest

from eegfm.eeg.motor_imagery import admitted_split, prepare_record, read_record


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
