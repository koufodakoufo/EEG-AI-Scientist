"""Generic EEG signal and frozen classifier helpers.

Input: float32 (N,20,5,200), samples expressed in microvolts / 100.
CPU only, at most four PyTorch threads. No fitting or scientific decision rules.
Generic feature source pin: 982b1df393a846e6418cee715bdfaa57d041cee3.
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

import hashlib
import json
import math
from pathlib import Path
import stat
import sys
import types
from typing import Any, Mapping, Sequence

import numpy as np

FEATURE_IDS = (
    'T001_hjorth_activity', 'T002_hjorth_mobility', 'F001_delta_log_power',
    'F002_theta_log_power', 'TF001_wavelet_entropy', 'TF002_wavelet_detail_var_l1',
    'C001_permutation_entropy', 'C002_sample_entropy', 'X001_pac_delta_beta',
    'X002_pac_theta_gamma', 'R001_corr_abs_mean', 'R002_corr_abs_std')

AGGREGATIONS = ('mean', 'std', 'median', 'q25', 'q75', 'max')

FEATURE_COLUMNS = tuple(f'{name}:{agg}' for name in FEATURE_IDS[:10] for agg in AGGREGATIONS) + FEATURE_IDS[10:]

_EPS = 1e-12

def _validate_x(x: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=np.float32)
    if values.ndim != 4 or values.shape[1:] != (20, 5, 200) or values.shape[0] < 1:
        raise ValueError('Expected shape (N,20,5,200), N >= 1')
    if not np.isfinite(values).all():
        raise ValueError('Input contains non-finite values')
    return values

def compute_feature_panel(x: np.ndarray) -> np.ndarray:
    """Exact twelve registered generic features (62 columns), on uV/100 input.

    PyTorch float32 operators match the source median, quantile and FFT semantics.
    Input shape and finite values are validated; physical units are a caller contract.
    """
    import torch
    torch.set_num_threads(4)
    values = _validate_x(x)
    with torch.inference_mode():
        signal = torch.from_numpy(values).reshape(len(values), 20, 1000)

        def aggregate(value: Any) -> Any:
            value = torch.nan_to_num(value.float(), nan=0., posinf=0., neginf=0.)
            return torch.stack((value.mean(1), value.std(1, unbiased=False), value.median(1).values,
                                torch.quantile(value, .25, dim=1), torch.quantile(value, .75, dim=1),
                                value.max(1).values), dim=1)

        dx = signal[..., 1:] - signal[..., :-1]
        var = signal.var(-1, unbiased=False).clamp_min(_EPS)
        output = [aggregate(var), aggregate(torch.sqrt(dx.var(-1, unbiased=False).clamp_min(_EPS) / var))]
        frequencies = torch.fft.rfftfreq(1000, d=1 / 200)
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
            filtered = torch.fft.irfft(spectrum * mask, n=1000, dim=-1)
            h = torch.zeros(1000, dtype=signal.dtype)
            h[0] = h[500] = 1
            h[1:500] = 2
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

def _load_strict_backbone(model: Any, checkpoint_path: Path) -> None:
    import torch
    state = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    model.proj_out = torch.nn.Identity()
    model.requires_grad_(False).cpu().eval()

class _CPUBackbone:
    """CPU frozen backbone; all layer numbers are one-based, post-layer outputs.

    Full activations are returned on explicit request. Continue an intervention
    through the remaining layers before applying the separately frozen task head.
    """
    def __init__(self, model: Any) -> None:
        self.model = model.cpu().eval().requires_grad_(False)
        self.n_layers = len(model.encoder.layers)

    def activations(self, x: np.ndarray, *, layers: Sequence[int] | None = None) -> dict[int, np.ndarray]:
        import torch
        chosen = tuple(range(1, self.n_layers + 1)) if layers is None else tuple(layers)
        if not chosen or any(layer < 1 or layer > self.n_layers for layer in chosen):
            raise ValueError('Invalid one-based layer selection')
        with torch.inference_mode():
            activation = self.model.patch_embedding(torch.from_numpy(_validate_x(x)))
            result = {}
            for number, layer in enumerate(self.model.encoder.layers, start=1):
                activation = layer(activation)
                if number in chosen:
                    result[number] = activation.numpy().copy()
            return result

    def continue_from(self, activation: np.ndarray, *, layer: int) -> np.ndarray:
        import torch
        if not 1 <= layer <= self.n_layers:
            raise ValueError('Invalid one-based continuation layer')
        with torch.inference_mode():
            current = torch.from_numpy(_validate_x(activation).copy())
            for following in self.model.encoder.layers[layer:]:
                current = following(current)
            if self.model.encoder.norm is not None:
                current = self.model.encoder.norm(current)
            return self.model.proj_out(current).numpy().copy()

    def encode(self, x: np.ndarray) -> np.ndarray:
        last = self.activations(x, layers=(self.n_layers,))[self.n_layers]
        return self.continue_from(last, layer=self.n_layers).mean(axis=(1, 2))


_OFFICIAL_FILES = {
    'vendor/models/cbramod.py': ('caa7c5a0e4acd488a6f625b56f7b54dc4e7190d6b68ef5b76dff2cef86874a14',4593),
    'vendor/models/criss_cross_transformer.py': ('90e90b8c98ca7eb543c44e32afc29674d3f71cb090692ad9f82db3a43edf334c',8521),
    'vendor/LICENSE': ('eb839b706e4d7219842e96d7dc33285844abc794292602deb3498be7b699537c',1068),
    'pretrained_weights.pth': ('0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178',19775842),
}


def _checked(path: Path, expected_sha256: str | None = None, maximum_bytes: int = 32*1024**2) -> Path:
    path = path.absolute()
    for item in (path,*path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('Resource links are forbidden')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>maximum_bytes:
        raise ValueError('Invalid resource file type or size')
    if expected_sha256 is not None:
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                hasher.update(block)
        digest = hasher.hexdigest()
        if digest!=expected_sha256:
            raise ValueError('Frozen resource SHA256 mismatch')
    return path


def _head_parameters(head: Mapping[str,Any]) -> dict[str,Any]:
    if set(head)!={'schema_version','x_mean','x_scale','coefficient','intercept'} or head['schema_version']!='frozen_linear_head_v1':
        raise ValueError('Unexpected frozen-head schema or extra fields')
    result = {}
    for name in ('x_mean','x_scale','coefficient'):
        value = np.asarray(head[name],dtype=np.float64)
        if value.shape!=(200,) or not np.isfinite(value).all() or (name=='x_scale' and np.any(value<=0)):
            raise ValueError('Invalid frozen-head parameter vector')
        result[name] = value
    result['intercept'] = float(head['intercept'])
    if not np.isfinite(result['intercept']):
        raise ValueError('Invalid frozen-head intercept')
    return result


def head_logits(head: Mapping[str,Any], embedding: np.ndarray) -> np.ndarray:
    """Apply the supplied frozen normalized linear head; return binary logits."""
    parameters = _head_parameters(head)
    values = np.asarray(embedding,dtype=np.float64)
    if values.ndim!=2 or values.shape[1]!=200 or values.shape[0]<1 or not np.isfinite(values).all():
        raise ValueError('Expected finite (N,200) embeddings')
    return ((values-parameters['x_mean'])/parameters['x_scale']) @ parameters['coefficient'] + parameters['intercept']


class EEGModel(_CPUBackbone):
    """Strictly loaded frozen CPU backbone and frozen prediction head.

    Resources default to the resources/ directory beside this file. Layers are
    one-based post-layer activations. continue_from returns complete token
    activations; average axes (1,2), then call head_logits for predictions.
    """
    def __init__(self, resource_dir: Path | str | None = None) -> None:
        import torch
        torch.set_num_threads(4)
        root = Path(resource_dir) if resource_dir is not None else Path(__file__).resolve().parent/'resources'
        manifest_path = _checked(root/'API_RESOURCES.json',maximum_bytes=65536)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if set(manifest)!={'schema_version','files'} or manifest['schema_version']!='public_eeg_resources_v1':
            raise ValueError('Unexpected resource manifest schema')
        if set(manifest['files']) != set(_OFFICIAL_FILES)|{'FROZEN_HEAD.json'}:
            raise ValueError('Public resource allowlist mismatch')
        for name,(digest,size) in _OFFICIAL_FILES.items():
            if manifest['files'][name] != {'sha256':digest,'bytes':size}:
                raise ValueError('Official resource identity mismatch')
            path = _checked(root/name,digest,maximum_bytes=size)
            if path.stat().st_size != size:
                raise ValueError('Official resource size mismatch')
        head_info = manifest['files']['FROZEN_HEAD.json']
        if set(head_info)!={'sha256','bytes'} or type(head_info['bytes']) is not int or not 0<head_info['bytes']<=65536:
            raise ValueError('Invalid public head resource identity')
        head_path = _checked(root/'FROZEN_HEAD.json',head_info['sha256'],maximum_bytes=65536)
        if head_path.stat().st_size != head_info['bytes']:
            raise ValueError('Head resource size mismatch')
        self.head = json.loads(head_path.read_text(encoding='utf-8'))
        _head_parameters(self.head)
        package_name = '_public_eeg_backbone_b9e961003214'
        transformer_name = package_name+'.criss_cross_transformer'
        package = types.ModuleType(package_name)
        package.__path__ = [str(root/'vendor/models')]
        sys.modules[package_name] = package
        transformer_path = root/'vendor/models/criss_cross_transformer.py'
        transformer = types.ModuleType(transformer_name)
        transformer.__file__ = str(transformer_path)
        transformer.__package__ = package_name
        sys.modules[transformer_name] = transformer
        exec(compile(transformer_path.read_text(encoding='utf-8'),str(transformer_path),'exec'),transformer.__dict__)
        source_path = root/'vendor/models/cbramod.py'
        source = source_path.read_text(encoding='utf-8')
        old = 'from models.criss_cross_transformer import TransformerEncoderLayer, TransformerEncoder'
        if source.count(old)!=1:
            raise ValueError('Unexpected frozen backbone source import')
        source = source.replace(old,f'from {transformer_name} import TransformerEncoderLayer, TransformerEncoder')
        module = types.ModuleType(package_name+'.cbramod')
        module.__file__ = str(source_path)
        module.__package__ = package_name
        exec(compile(source,str(source_path),'exec'),module.__dict__)
        model = module.CBraMod()
        _load_strict_backbone(model,root/'pretrained_weights.pth')
        super().__init__(model)

    def head_logits(self, embedding: np.ndarray) -> np.ndarray:
        return head_logits(self.head,embedding)

    def logits(self, x: np.ndarray) -> np.ndarray:
        return self.head_logits(self.encode(x))
