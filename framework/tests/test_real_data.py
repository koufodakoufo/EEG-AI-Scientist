"""Boundary tests for the private real EEG resource adapter."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


class RealDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('eegfm.research_bench.real_data'),
                             'The real-data adapter must exist')
        self.rd = importlib.import_module('eegfm.research_bench.real_data')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_condition_and_windows_cannot_split_one_participant(self) -> None:
        for name in ['Subject23_1.edf', 'Subject23_2.edf', 'Subject23_2-17']:
            self.assertEqual(self.rd.subject_id(name), 'Subject23')
            self.assertEqual(self.rd.split_for_subject(self.rd.subject_id(name)), 'train')
        self.assertEqual(self.rd.split_for_subject('Subject24'), 'validation')
        self.assertEqual(self.rd.split_for_subject('Subject29'), 'validation')
        self.assertEqual(self.rd.split_for_subject('Subject30'), 'test')
        for bad in ['../Subject00_1.edf', 'Subject36_1.edf', 'Subject00_3.edf']:
            with self.assertRaises(ValueError):
                self.rd.subject_id(bad)

    def test_window_sampling_is_full_evenly_spaced_and_preserves_source_index(self) -> None:
        self.assertEqual(self.rd.window_indices(999), [])
        self.assertEqual(self.rd.window_indices(3000), [0, 1, 2])
        self.assertEqual(self.rd.window_indices(25000, maximum=3), [0, 12, 24])
        signal = np.repeat(np.arange(3000)[None, :], 20, axis=0).astype(float)
        windows, indices = self.rd.make_windows(signal, unit='uV', maximum=2)
        self.assertEqual(indices, [0, 2])
        self.assertEqual(windows.shape, (2, 20, 5, 200))
        self.assertAlmostEqual(float(windows[1, 0, 0, 0]), 20.0)
        from_volts, _ = self.rd.make_windows(signal * 1e-6, unit='V', maximum=2)
        np.testing.assert_allclose(from_volts, windows)
        with self.assertRaises(ValueError):
            self.rd.make_windows(signal, unit='mV')
        with self.assertRaises(ValueError):
            self.rd.make_windows(signal[:19], unit='uV')

    def test_download_rejects_escape_corruption_and_truncation_without_final_file(self) -> None:
        with self.assertRaises(ValueError):
            self.rd.owned_destination(self.root.parent / 'outside', self.root)
        payload = b'public-source'
        digest = hashlib.sha256(payload).hexdigest()
        spec = self.rd.ResourceFile('small.txt', 'https://example.org/small', digest, len(payload))
        budget = self.rd.DownloadBudget(100)

        class Response(io.BytesIO):
            headers: dict[str, str] = {}
            def geturl(self) -> str:
                return 'https://example.org/small'

        with patch.object(self.rd.urllib.request, 'urlopen', return_value=Response(b'wrong')):
            with self.assertRaises(ValueError):
                self.rd.download_verified(spec, self.root, budget)
        self.assertFalse((self.root / 'small.txt').exists())
        self.assertEqual(list(self.root.glob('*.part')), [])
        with patch.object(self.rd.urllib.request, 'urlopen', return_value=Response(payload)):
            self.rd.download_verified(spec, self.root, self.rd.DownloadBudget(100))
        self.assertEqual((self.root / 'small.txt').read_bytes(), payload)
        # Existing corrupt files must fail; never silently overwrite evidence.
        (self.root / 'small.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.rd.download_verified(spec, self.root, self.rd.DownloadBudget(100))

    def test_download_stream_cap_without_content_length(self) -> None:
        class Response(io.BytesIO):
            headers: dict[str, str] = {}
            def geturl(self) -> str:
                return 'https://example.org/small'
        spec = self.rd.ResourceFile('small.txt', 'https://example.org/small', '0' * 64, None)
        with patch.object(self.rd.urllib.request, 'urlopen', return_value=Response(b'x' * 16)):
            with self.assertRaises(ValueError):
                self.rd.download_verified(spec, self.root, self.rd.DownloadBudget(8))
        self.assertFalse((self.root / 'small.txt').exists())

    def test_existing_resources_count_toward_total_cap(self) -> None:
        payload = b'cached'
        (self.root / 'cached.txt').write_bytes(payload)
        spec = self.rd.ResourceFile('cached.txt', 'https://example.org/cached',
                                    hashlib.sha256(payload).hexdigest(), len(payload))
        with self.assertRaises(ValueError):
            self.rd.download_verified(spec, self.root, self.rd.DownloadBudget(3))

    def test_edf_header_validates_calibration_units_and_real_payload_length(self) -> None:
        path = self.root / 'Subject00_1.edf'

        def build(unit: str = 'uV', physical_max: str = '100') -> bytes:
            def field(value: object, width: int) -> bytes:
                return str(value).encode('ascii').ljust(width)
            fixed = (field(0, 8) + field('not retained', 80) + field('not retained', 80)
                     + field('01.01.00', 8) + field('00.00.00', 8) + field(5376, 8)
                     + field('', 44) + field(1, 8) + field(1, 8) + field(20, 4))
            descriptors = b''.join(
                b''.join(field(v, width) for v in values)
                for width, values in [(16, self.rd.CHANNELS), (80, [''] * 20),
                    (8, [unit] * 20), (8, ['-100'] * 20), (8, [physical_max] * 20),
                    (8, ['-32768'] * 20), (8, ['32767'] * 20),
                    (80, ['HP:0.5 LP:30'] * 20), (8, ['500'] * 20), (32, [''] * 20)])
            return fixed + descriptors + b'\0' * (20 * 500 * 2)

        path.write_bytes(build())
        header = self.rd.read_edf_header(path)
        self.assertEqual(header['original_sample_rate'], 500)
        self.assertEqual(header['duration_seconds'], 1)
        self.assertEqual(header['selected_channels'][0]['prefilter'], 'HP:0.5 LP:30')
        self.assertNotIn('patient', header)
        for data in [build(unit='unknown'), build(physical_max='-100'), build()[:-2]]:
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                self.rd.read_edf_header(path)

    def test_panel_tracks_amplitude_frequency_and_correlation(self) -> None:
        t = np.arange(1000) / 200
        sine = np.sin(2 * np.pi * 6 * t).astype(np.float32)
        x = np.tile(sine, (2, 20, 1)).reshape(2, 20, 5, 200)
        x[1] *= 2
        values = self.rd.compute_feature_panel(x)
        self.assertEqual(values.shape, (2, 62))
        self.assertEqual(len(self.rd.FEATURE_COLUMNS), 62)
        self.assertTrue(np.isfinite(values).all())
        self.assertAlmostEqual(float(values[0, 0]), .5, places=5)
        self.assertAlmostEqual(float(values[1, 0]), 2.0, places=5)
        # Feature order has 6 columns per family entry; theta starts at 18.
        self.assertAlmostEqual(float(values[1, 18] - values[0, 18]), np.log(4), places=5)
        self.assertAlmostEqual(float(values[0, 60]), 1.0, places=5)
        self.assertAlmostEqual(float(values[0, 61]), 0.0, places=5)
        self.assertGreater(values[0, 18], values[0, 12])

    def test_panel_flags_bad_channels_before_zero_substitution(self) -> None:
        x = np.ones((1, 20, 5, 200), dtype=np.float32)
        quality = self.rd.input_quality(x)
        self.assertEqual(quality['zero_variance_channels'], 20)
        x[0, 0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            self.rd.compute_feature_panel(x)

    def test_test_preprocessing_requires_explicit_opt_in_before_read(self) -> None:
        with self.assertRaises(PermissionError):
            self.rd.prepare_eegmat(self.root / 'absent', self.root / 'out',
                                   allowed_parent=self.root, splits=('test',))


class ModelBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import torch
        except (ImportError, OSError) as exc:
            raise unittest.SkipTest(f'PyTorch unavailable: {exc}') from exc
        cls.torch = torch

    def test_strict_load_happens_before_projection_replacement(self) -> None:
        from eegfm.research_bench.real_data import _load_strict_backbone
        torch = self.torch
        model = torch.nn.Module()
        model.proj_out = torch.nn.Linear(2, 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'weights.pth'
            torch.save(model.state_dict(), path)
            _load_strict_backbone(model, path)
            self.assertIsInstance(model.proj_out, torch.nn.Identity)
            broken = torch.nn.Module()
            broken.proj_out = torch.nn.Linear(3, 2)
            with self.assertRaises(RuntimeError):
                _load_strict_backbone(broken, path)
            self.assertIsInstance(broken.proj_out, torch.nn.Linear)

    def test_layer_continuation_matches_uninterrupted_cpu_forward(self) -> None:
        from eegfm.research_bench.real_data import CBraModCPU
        torch = self.torch

        class Add(torch.nn.Module):
            def __init__(self, value: float) -> None:
                super().__init__()
                self.value = value
            def forward(self, x: object) -> object:
                return x + self.value

        model = torch.nn.Module()
        model.patch_embedding = Add(1)
        model.encoder = torch.nn.Module()
        model.encoder.layers = torch.nn.ModuleList([Add(2), Add(3)])
        model.encoder.norm = None
        model.proj_out = torch.nn.Identity()
        adapter = CBraModCPU(model)
        x = np.zeros((1, 20, 5, 200), dtype=np.float32)
        middle = adapter.activations(x, layers=(1,))[1]
        self.assertEqual(middle.shape, (1, 20, 5, 200))
        final = adapter.continue_from(middle, layer=1)
        np.testing.assert_allclose(final, 6)
        np.testing.assert_allclose(adapter.encode(x), final.mean(axis=(1, 2)))
        with self.assertRaises(ValueError):
            adapter.continue_from(middle, layer=0)


if __name__ == '__main__':
    unittest.main()
