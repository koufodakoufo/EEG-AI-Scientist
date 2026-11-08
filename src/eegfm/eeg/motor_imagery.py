"""Scoped EEGMMIDB imagined left/right fist preparation.

PhysioNet EEGMMIDB 1.0.0 and official MNE EEGBCI documentation identify
runs 4/8/12 as imagined unilateral fists, T1=left and T2=right. This
default entry points never admit reserved final-test participants. A separate
trusted entry requires an explicit immutable protocol admission. Admission is
not isolation: the trusted controller owns review, freezes and file access.

Generic feature adaptation copyright (c) 2026 Kian Chen, MIT License:
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any

import numpy as np

from eegfm.eeg.eegmmidb import CHANNELS, read_header, select_channels


RUNS = (4, 8, 12)
EVENT_LABELS = {'T1': 0, 'T2': 1}


@dataclass(frozen=True)
class TrustedRecordAdmission:
    """Immutable declared protocol inventory, not permission inferred from a path.

    Construction does no filesystem I/O. The trusted controller must bind this
    exact inventory/root and the preparer bytes before admitting held-out access.
    Development defaults are unchanged and do not consult this inventory.
    """
    protocol_sha256: str
    raw_root: Path
    records: tuple[tuple[int, int, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.protocol_sha256,str) or not re.fullmatch('[0-9a-f]{64}',self.protocol_sha256):
            raise ValueError('Trusted admission requires a frozen protocol SHA256')
        if not isinstance(self.raw_root,Path) or not self.raw_root.is_absolute() or '..' in self.raw_root.parts:
            raise ValueError('Trusted raw root must be an absolute lexical path without parent traversal')
        if type(self.records) is not tuple or not self.records:
            raise ValueError('Trusted inventory must be a nonempty immutable tuple')
        seen: set[tuple[int,int,str]] = set()
        for entry in self.records:
            if type(entry) is not tuple or len(entry)!=3:
                raise ValueError('Trusted record entries must be immutable triples')
            subject,run,split=entry
            if type(subject) is not int or not 1<=subject<=60 or type(run) is not int or run not in RUNS:
                raise ValueError('Trusted record outside supported participant/run bounds')
            expected='train' if subject<=24 else ('validation' if subject<=30 else 'test')
            if split!=expected or entry in seen:
                raise ValueError('Trusted split mismatch or duplicate record')
            seen.add(entry)

    def authorize(self,subject: int,run: int,split: str) -> None:
        if type(subject) is not int or type(run) is not int or (subject,run,split) not in self.records:
            raise ValueError('Record not in immutable trusted protocol inventory')

    def authorize_path(self,path: Path,*,subject: int,run: int,split: str) -> None:
        """Lexical admission check before open, hash, stat or header decoding."""
        self.authorize(subject,run,split)
        expected=self.raw_root/f'S{subject:03d}'/f'S{subject:03d}R{run:02d}.edf'
        if '..' in path.parts or path!=expected:
            raise ValueError('Trusted path/root/participant/run mismatch')


def admitted_split(subject: int, run: int, split: str) -> None:
    """Guard before any raw path is opened, including header/hash reads."""
    if type(subject) is not int or not 1 <= subject <= 30:
        raise ValueError('Only S001-S030 development records are admitted; test forbidden')
    if type(run) is not int or run not in RUNS:
        raise ValueError('Only imagined unilateral fist runs 4/8/12 are admitted')
    expected = 'train' if subject <= 24 else 'validation'
    if split != expected:
        raise ValueError('Participant/split mismatch')


def prepare_record(signal_uv: np.ndarray, annotations: Sequence[Mapping[str, Any]], *,
                   subject: int, run: int, split: str, sample_rate: float = 160.0) -> dict[str, Any]:
    """Return strict-schema windows, labels, onsets and technical provenance.

    Signal must already contain CHANNELS in their declared order, in physical
    microvolts. Every T1/T2 yields [onset+.5,onset+3.5), wholly inside its
    annotation and before the next annotation. Invalid events reject the entire
    record; there is no silent event dropping, replacement or truncation.
    """
    admitted_split(subject, run, split)
    return _prepare_record_core(signal_uv,annotations,subject=subject,run=run,split=split,sample_rate=sample_rate)


def prepare_record_trusted(signal_uv: np.ndarray,annotations: Sequence[Mapping[str,Any]],*,
                           subject: int,run: int,split: str,admission: TrustedRecordAdmission,
                           sample_rate: float=160.0) -> dict[str,Any]:
    """Pure shared preparation after explicit trusted protocol inventory check."""
    if type(admission) is not TrustedRecordAdmission:
        raise ValueError('Explicit immutable trusted admission required')
    admission.authorize(subject,run,split)
    prepared=_prepare_record_core(signal_uv,annotations,subject=subject,run=run,split=split,sample_rate=sample_rate)
    prepared['metadata']['admission_protocol_sha256']=admission.protocol_sha256
    return prepared


def _prepare_record_core(signal_uv: np.ndarray,annotations: Sequence[Mapping[str,Any]],*,
                         subject: int,run: int,split: str,sample_rate: float) -> dict[str,Any]:
    """Identical signal/annotation core shared by separately guarded entries."""
    signal = np.asarray(signal_uv)
    if sample_rate != 160 or signal.ndim != 2 or signal.shape[0] != len(CHANNELS):
        raise ValueError('Expected 20 ordered measured channels at native 160 Hz')
    if signal.shape[1] == 0 or not np.issubdtype(signal.dtype, np.floating) or not np.isfinite(signal).all():
        raise ValueError('Signal must be nonempty finite floating microvolts')
    events = []
    duration_seconds = signal.shape[1] / 160
    for entry in annotations:
        if not isinstance(entry, Mapping) or set(entry) != {'onset', 'duration', 'description'}:
            raise ValueError('Unexpected annotation schema')
        if isinstance(entry['onset'], (bool, str)) or isinstance(entry['duration'], (bool, str)):
            raise ValueError('Annotation times must be numeric')
        onset, duration = float(entry['onset']), float(entry['duration'])
        description = entry['description']
        if description not in ('T0', 'T1', 'T2'):
            raise ValueError('Unknown event code')
        if not np.isfinite([onset, duration]).all() or onset < 0 or duration <= 0:
            raise ValueError('Invalid annotation time bounds')
        if onset + duration > duration_seconds + 1e-9:
            raise ValueError('Annotation extends beyond record')
        if events and onset <= events[-1][0]:
            raise ValueError('Annotations must have strictly increasing onsets')
        if events and events[-1][0] + events[-1][1] > onset + 1e-9:
            raise ValueError('Overlapping annotation bounds')
        events.append((onset, duration, description))
    native, labels, event_onsets, window_onsets, durations = [], [], [], [], []
    for onset, duration, description in events:
        if description == 'T0':
            continue
        begin, end = onset + .5, onset + 3.5
        if end > onset + duration + 1e-9 or end > duration_seconds + 1e-9:
            raise ValueError('Task window does not lie wholly inside its event/record')
        start_sample = round(begin * 160)
        if abs(start_sample / 160 - begin) > 1e-9:
            raise ValueError('Task window onset is not aligned to native samples')
        stop_sample = start_sample + 480
        window = signal[:, start_sample:stop_sample]
        if window.shape != (20, 480):
            raise ValueError('Truncated native task window')
        native.append(window)
        labels.append(EVENT_LABELS[description])
        event_onsets.append(onset)
        window_onsets.append(begin)
        durations.append(duration)
    if not native:
        raise ValueError('No imagined left/right task events')
    import mne
    resampled = mne.filter.resample(np.asarray(native, dtype=np.float64), up=5, down=4,
                                   npad='auto', n_jobs=1, verbose='ERROR')
    if resampled.shape != (len(native), 20, 600) or not np.isfinite(resampled).all():
        raise ValueError('Resampling returned invalid windows')
    windows = (resampled / 100).reshape(-1, 20, 3, 200).astype(np.float32)
    return {'schema_version': 'motor_imagery_record_v1', 'windows': windows,
            'y': np.asarray(labels, dtype=np.int64),
            'event_onsets_seconds': np.asarray(event_onsets, dtype=np.float64),
            'window_onsets_seconds': np.asarray(window_onsets, dtype=np.float64),
            'metadata': {'subject': f'S{subject:03d}', 'run': run, 'split': split,
                         'channels': list(CHANNELS), 'native_hz': 160, 'target_hz': 200,
                         'input_unit': 'uV/100', 'annotation_count': len(events),
                         'event_durations_seconds': durations,
                         'label_names': ['imagined_left_fist', 'imagined_right_fist'],
                         'resample': 'mne.filter.resample up=5 down=4 npad=auto n_jobs=1 FFT per event',
                         'mne_version': mne.__version__, 'extra_filter': None,
                         'rereference': None, 'signal_normalization': None}}


def read_record(path: Path, *, subject: int, run: int, split: str) -> dict[str, Any]:
    """Thin EDF reader; split/run guards precede all file access."""
    admitted_split(subject, run, split)
    if path.name != f'S{subject:03d}R{run:02d}.edf' or path.parent.name != f'S{subject:03d}':
        raise ValueError('Record path does not match declared participant/run')
    return _read_record_core(path,subject=subject,run=run,split=split)


def read_record_trusted(path: Path,*,subject: int,run: int,split: str,
                        admission: TrustedRecordAdmission) -> dict[str,Any]:
    """Read only an explicitly admitted exact raw path; no I/O before guards."""
    if type(admission) is not TrustedRecordAdmission:
        raise ValueError('Explicit immutable trusted admission required')
    admission.authorize_path(path,subject=subject,run=run,split=split)
    prepared=_read_record_core(path,subject=subject,run=run,split=split)
    prepared['metadata']['admission_protocol_sha256']=admission.protocol_sha256
    return prepared


def _read_record_core(path: Path,*,subject: int,run: int,split: str) -> dict[str,Any]:
    """Read/decode only after a caller-specific inventory and path check."""
    header = read_header(path)
    import mne
    raw = mne.io.read_raw_edf(path, preload=False, verbose='ERROR')
    try:
        labels = select_channels(raw.ch_names)
        annotations = [{'onset': float(onset), 'duration': float(duration), 'description': str(description)}
                       for onset, duration, description in zip(raw.annotations.onset,
                                                             raw.annotations.duration,
                                                             raw.annotations.description)]
        prepared = _prepare_record_core(raw.get_data(picks=labels, units='uV'), annotations,
                                  subject=subject, run=run, split=split,
                                  sample_rate=raw.info['sfreq'])
    finally:
        raw.close()
    prepared['metadata']['edf_header'] = header
    return prepared


def compute_duration_feature_panel(x: np.ndarray) -> np.ndarray:
    """Explicit duration adaptation of the frozen public 62-column panel.

    Version motor-imagery-duration-feature-panel-v1. Supports3seconds and
    5seconds;5second outputs retain the original float32 Torch math exactly.
    Three-second windows use600samples (FFT spacing1/3Hz versus1/5Hz), retain
    unnormalized summed spectral power, recompute Hilbert masks at600samples,
    and retain five Haar levels with odd tail truncation at each level.
    Consequently duration-sensitive values are not numerically interchangeable
    with the original5second panel. No signal padding or fitted normalization.
    Underlying generic definitions and MIT attribution are in eegfm.eeg.api.
    """
    import torch
    torch.set_num_threads(4)
    values = np.asarray(x, dtype=np.float32)
    if values.ndim != 4 or values.shape[0] < 1 or values.shape[1] != 20 or values.shape[2] not in (3,5) or values.shape[3] != 200:
        raise ValueError('Expected finite (N,20,3,200) or (N,20,5,200) duration panel input')
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite duration-panel input')
    sample_count = values.shape[2] * 200
    _EPS = 1e-12
    with torch.inference_mode():
        signal = torch.from_numpy(values).reshape(len(values), 20, sample_count)

        def aggregate(value: Any) -> Any:
            value = torch.nan_to_num(value.float(), nan=0., posinf=0., neginf=0.)
            return torch.stack((value.mean(1), value.std(1, unbiased=False), value.median(1).values,
                                torch.quantile(value, .25, dim=1), torch.quantile(value, .75, dim=1),
                                value.max(1).values), dim=1)

        dx = signal[..., 1:] - signal[..., :-1]
        var = signal.var(-1, unbiased=False).clamp_min(_EPS)
        output = [aggregate(var), aggregate(torch.sqrt(dx.var(-1, unbiased=False).clamp_min(_EPS) / var))]
        frequencies = torch.fft.rfftfreq(sample_count, d=1 / 200)
        spectrum = torch.fft.rfft(signal, dim=-1)
        for low, high in ((.5, 4.), (4., 8.)):
            power = spectrum.abs().square()[..., (frequencies >= low) & (frequencies < high)].sum(-1).clamp_min(_EPS)
            output.append(aggregate(torch.log(power)))
        approximation = signal
        details = []
        for _ in range(5):
            if approximation.shape[-1] % 2:
                approximation = approximation[..., :-1]
            even, odd = approximation[..., 0::2], approximation[..., 1::2]
            details.append((even - odd) * (1.0 / math.sqrt(2)))
            approximation = (even + odd) * (1.0 / math.sqrt(2))
        energies = torch.stack([d.square().mean(-1).clamp_min(_EPS) for d in details] +
                               [approximation.square().mean(-1).clamp_min(_EPS)], dim=-1)
        probability = energies / energies.sum(-1, keepdim=True).clamp_min(_EPS)
        output.extend((aggregate(-(probability * probability.log()).sum(-1) / math.log(6)),
                       aggregate(details[0].var(-1, unbiased=False))))
        a, b, c = signal[..., :-2], signal[..., 1:-1], signal[..., 2:]
        pattern = torch.zeros_like(a, dtype=torch.long)
        for mask, code in (((a <= b) & (b <= c), 0), ((a <= c) & (c < b), 1),
                           ((b < a) & (a <= c), 2), ((b <= c) & (c < a), 3),
                           ((c < a) & (a <= b), 4), ((c < b) & (b < a), 5)):
            pattern = torch.where(mask, torch.full_like(pattern, code), pattern)
        probabilities = torch.stack([(pattern == index).float().mean(-1) for index in range(6)], -1).clamp_min(_EPS)
        probabilities /= probabilities.sum(-1, keepdim=True)
        output.append(aggregate(-(probabilities * probabilities.log()).sum(-1) / math.log(6)))
        radius = .2 * signal.std(-1, unbiased=False).clamp_min(1e-6)
        close1 = (dx.abs().mean(-1) / radius).clamp_min(_EPS)
        close2 = ((dx[..., 1:] - dx[..., :-1]).abs().mean(-1) / radius).clamp_min(_EPS)
        output.append(aggregate(torch.log1p(close2) - torch.log1p(close1)))

        def analytic_band(low: float, high: float) -> Any:
            mask = ((frequencies >= low) & (frequencies < high)).to(signal.dtype)
            filtered = torch.fft.irfft(spectrum * mask, n=sample_count, dim=-1)
            h = torch.zeros(sample_count, dtype=signal.dtype)
            h[0] = h[sample_count//2] = 1
            h[1:sample_count//2] = 2
            return torch.fft.ifft(torch.fft.fft(filtered, dim=-1) * h, dim=-1)

        for (phase_low, phase_high), (amp_low, amp_high) in (((.5, 4.), (13., 30.)), ((4., 8.), (30., 45.))):
            phase = torch.angle(analytic_band(phase_low, phase_high))
            amplitude = analytic_band(amp_low, amp_high).abs()
            edges = torch.linspace(-torch.pi, torch.pi, 19, dtype=signal.dtype)
            means = []
            for index in range(18):
                mask = (phase >= edges[index]) & (phase < edges[index + 1])
                means.append((amplitude * mask).sum(-1) / mask.sum(-1).clamp_min(1))
            weighted = torch.stack(means, dim=-1).clamp_min(_EPS)
            probability = weighted / weighted.sum(-1, keepdim=True).clamp_min(_EPS)
            output.append(aggregate((math.log(18) + (probability * probability.log()).sum(-1)) / math.log(18)))
        centered = signal - signal.mean(-1, keepdim=True)
        centered /= centered.std(-1, unbiased=False, keepdim=True).clamp_min(1e-6)
        correlation = (centered[:, :, None, :] * centered[:, None, :, :]).mean(-1).clamp(-1., 1.)
        rows, columns = torch.triu_indices(20, 20, offset=1)
        pairs = correlation.abs()[:, rows, columns]
        output.extend((pairs.mean(1, keepdim=True), pairs.std(1, unbiased=False, keepdim=True)))
        return torch.cat(output, dim=1).numpy().astype(np.float32)

