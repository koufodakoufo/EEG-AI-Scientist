"""Synthetic privacy/alignment tests; never read actual EEG or model weights."""
from __future__ import annotations
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np


class PublicViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('eegfm.research_bench.real_public'))
        self.p = importlib.import_module('eegfm.research_bench.real_public')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prepared = self.root/'prepared.npz'
        self.representations = self.root/'repr.npz'
        self.fixture('train')

    def fixture(self, split: str, *, corrupt: bool = False) -> None:
        numbers = {'train':(0,1),'validation':(24,25),'test':(30,31)}[split]
        ids = [f'Subject{s:02d}_{c}-{w}' for c in (1,2) for s in numbers for w in (0,1)]
        subjects = [item.split('_')[0] for item in ids]
        labels = np.repeat([0,1],4).astype(np.int64)
        x = np.broadcast_to(np.arange(8,dtype=np.float32)[:,None,None,None],(8,20,5,200)).copy()
        fields = dict(y=labels,sample_ids=np.array(ids),subject_ids=np.array(subjects),
                      recording_ids=np.array([s.rsplit('-',1)[0] for s in ids]),window_indices=np.tile([0,1],4))
        np.savez(self.prepared,x=x,split=np.array(split),input_unit=np.array('uV/100'),sample_rate=np.array(200),**fields)
        if corrupt:
            fields['sample_ids'] = fields['sample_ids'][::-1]
        np.savez(self.representations,features=np.tile(np.arange(8)[:,None],(1,62)).astype(np.float32),
                 layer_6=x+6,layer_12=x+12,embedding=np.tile(np.arange(8)[:,None],(1,200)).astype(np.float32),**fields)

    def build(self, split: str, **kwargs: object) -> dict:
        return self.p.build_split_view(self.prepared,self.representations,split=split,
            private_dir=self.root/'private',target_npz=(self.root/'private/evaluation/test.npz' if split=='test' else self.root/'public'/f'{split}.npz'),run_id='fixture',
            expected_prepared_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest(),
            expected_repr_sha256=hashlib.sha256(self.representations.read_bytes()).hexdigest(),**kwargs)

    def test_public_rows_are_opaque_and_jointly_shuffled_with_private_truth(self) -> None:
        receipt = self.build('train')
        with np.load(receipt['target_npz'],allow_pickle=False) as view:
            self.assertEqual(set(view.files),{'x','y','features','layer_6','layer_12','embedding','sample_ids','subject_ids'})
            ids = view['sample_ids']; subjects = view['subject_ids']
            self.assertTrue(all(str(s).startswith('s_') and len(str(s))==34 for s in ids))
            self.assertTrue(all(str(s).startswith('p_') and len(str(s))==34 for s in subjects))
            self.assertFalse(any('Subject' in str(s) for s in ids))
            self.assertEqual(len(set(subjects)),2)
            order = view['x'][:,0,0,0].astype(int)
            self.assertFalse(np.array_equal(order,np.arange(8)))
            self.assertGreater(np.count_nonzero(np.diff(view['y'])),1)
            np.testing.assert_array_equal(view['features'][:,0],order)
            np.testing.assert_array_equal(view['layer_6'][:,0,0,0],order+6)
            with np.load(receipt['truth_npz'],allow_pickle=False) as truth:
                np.testing.assert_array_equal(truth['sample_ids'],ids)
                np.testing.assert_array_equal(truth['y'],view['y'])
                np.testing.assert_array_equal(truth['features'],view['features'])
        private = json.loads(Path(receipt['private_manifest']).read_text(encoding='utf-8'))
        self.assertEqual(private['permutation'],order.tolist())
        self.assertEqual(len(private['source_mapping']),8)
        self.assertEqual(set(p.name for p in (self.root/'public').iterdir()),{'train.npz'})

    def test_test_guard_precedes_any_read_and_test_inputs_are_strict_minimum(self) -> None:
        self.prepared.unlink(); self.representations.unlink()
        with self.assertRaises(PermissionError):
            self.p.build_split_view(self.prepared,self.representations,split='test',
                private_dir=self.root/'private',target_npz=self.root/'evaluation.npz',run_id='fixture',
                expected_prepared_sha256='0'*64,expected_repr_sha256='0'*64)
        self.fixture('test')
        with self.assertRaises(PermissionError):
            self.build('test',allow_test=True)
        receipt = self.build('test',allow_test=True,reference_freeze_sha256='a'*64)
        with np.load(receipt['target_npz'],allow_pickle=False) as view:
            self.assertEqual(set(view.files),{'x','sample_ids','subject_ids'})
        with np.load(receipt['truth_npz'],allow_pickle=False) as truth:
            self.assertEqual(set(truth.files),{'y','features','sample_ids','subject_ids'})

    def test_misalignment_wrong_partition_and_hash_tamper_fail_before_export(self) -> None:
        self.fixture('train',corrupt=True)
        with self.assertRaises(ValueError): self.build('train')
        self.fixture('validation')
        with self.assertRaises(ValueError): self.build('train')
        self.fixture('train')
        with self.assertRaises(ValueError):
            self.p.build_split_view(self.prepared,self.representations,split='train',
                private_dir=self.root/'private',target_npz=self.root/'out.npz',run_id='fixture',
                expected_prepared_sha256='0'*64,expected_repr_sha256='0'*64)
        self.assertFalse((self.root/'public/train.npz').exists())

    def test_outputs_are_immutable_and_linked_input_rejected(self) -> None:
        self.build('train')
        with self.assertRaises(FileExistsError): self.build('train')
        extra = self.root/'hardlink.npz'
        try:
            extra.hardlink_to(self.prepared)
        except OSError:
            return
        with self.assertRaises(ValueError):
            self.p.build_split_view(self.prepared,self.representations,split='train',
                private_dir=self.root/'other-private',target_npz=self.root/'other.npz',run_id='fixture',
                expected_prepared_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest(),
                expected_repr_sha256=hashlib.sha256(self.representations.read_bytes()).hexdigest())

    def test_head_export_strips_selection_results_and_rejects_invalid_scale(self) -> None:
        head = {'x_mean':[0.]*200,'x_scale':[1.]*200,'coefficient':[.5]*200,'intercept':.1,
                'validation_balanced_accuracy':.99,'selection_grid':[{'C':1,'validation_balanced_accuracy':.99}]}
        cleaned = self.p.sanitize_head(head)
        self.assertEqual(set(cleaned),{'schema_version','x_mean','x_scale','coefficient','intercept'})
        self.assertNotIn('validation_balanced_accuracy',json.dumps(cleaned))
        head['x_scale'][3]=0
        with self.assertRaises(ValueError): self.p.sanitize_head(head)

    def test_evaluation_view_removes_truth_without_reordering_or_source_mutation(self) -> None:
        self.fixture('validation')
        receipt = self.build('validation')
        source = Path(receipt['target_npz'])
        before = source.read_bytes()
        evaluation = self.p.make_evaluation_view(source,self.root/'worker-input/validation.npz',
                                                 expected_sha256=receipt['target_sha256'])
        with np.load(source,allow_pickle=False) as public, np.load(evaluation['path'],allow_pickle=False) as private_input:
            self.assertEqual(set(private_input.files),{'x','sample_ids','subject_ids'})
            for name in private_input.files:
                np.testing.assert_array_equal(private_input[name],public[name])
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(hashlib.sha256(Path(evaluation['path']).read_bytes()).hexdigest(),evaluation['sha256'])
        with self.assertRaises(FileExistsError):
            self.p.make_evaluation_view(source,evaluation['path'],expected_sha256=receipt['target_sha256'])

    def test_test_cannot_be_exported_to_a_public_destination(self) -> None:
        self.fixture('test')
        with self.assertRaises(ValueError):
            self.p.build_split_view(self.prepared,self.representations,split='test',
                private_dir=self.root/'private',target_npz=self.root/'public/test.npz',run_id='fixture',
                expected_prepared_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest(),
                expected_repr_sha256=hashlib.sha256(self.representations.read_bytes()).hexdigest(),
                allow_test=True,reference_freeze_sha256='a'*64)

    def test_declared_public_mount_cannot_contain_private_mapping(self) -> None:
        with self.assertRaises(ValueError):
            self.p.build_split_view(self.prepared,self.representations,split='train',
                private_dir=self.root/'actor/private',target_npz=self.root/'actor/data/train.npz',
                public_root=self.root/'actor',run_id='fixture',
                expected_prepared_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest(),
                expected_repr_sha256=hashlib.sha256(self.representations.read_bytes()).hexdigest())

    def test_resource_export_uses_explicit_allowlist_and_sanitizes_head(self) -> None:
        from eegfm.research_bench.real_data import ResourceFile
        cache = self.root/'cache'; cache.mkdir()
        payload = b'synthetic approved public source\n'
        (cache/'approved.txt').write_bytes(payload)
        (cache/'private-dataset-secret.txt').write_text('must not be copied',encoding='utf-8')
        spec = ResourceFile('approved.txt','https://example.invalid/unused',
                            hashlib.sha256(payload).hexdigest(),len(payload),len(payload))
        private_head = self.root/'private-head.json'
        private_head.write_text(json.dumps({'x_mean':[0.]*200,'x_scale':[1.]*200,
            'coefficient':[.5]*200,'intercept':.1,'validation_balanced_accuracy':.99,
            'selection_grid':[{'private':'must not be copied'}]}),encoding='utf-8')
        before = private_head.read_bytes()
        with mock.patch.object(self.p,'MODEL_RESOURCES',(spec,)):
            receipt = self.p.export_api_resources(cache,private_head,self.root/'actor',
                        expected_head_sha256=hashlib.sha256(before).hexdigest())
        public_files = {str(p.relative_to(self.root/'actor')).replace('\\','/')
                        for p in (self.root/'actor').rglob('*') if p.is_file()}
        self.assertEqual(public_files,set(receipt['exported_files']))
        self.assertEqual(public_files,{'resources/approved.txt','resources/FROZEN_HEAD.json',
                                     'resources/API_RESOURCES.json','eeg_api.py'})
        head = json.loads((self.root/'actor/resources/FROZEN_HEAD.json').read_text(encoding='utf-8'))
        self.assertEqual(set(head),{'schema_version','x_mean','x_scale','coefficient','intercept'})
        self.assertEqual(private_head.read_bytes(),before)

    def test_evaluation_view_refuses_original_source_identifiers(self) -> None:
        with self.assertRaises(ValueError):
            self.p.make_evaluation_view(self.prepared,self.root/'worker.npz',
                expected_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest())

    def test_symlink_source_is_rejected(self) -> None:
        link = self.root/'alias.npz'
        try:
            link.symlink_to(self.prepared)
        except OSError as exc:
            self.skipTest(f'Host does not permit symlink creation: {exc}')
        with self.assertRaises(ValueError):
            self.p.make_evaluation_view(link,self.root/'worker.npz',
                expected_sha256=hashlib.sha256(self.prepared.read_bytes()).hexdigest())


class PublicApiTests(unittest.TestCase):
    def test_resource_digest_works_without_python311_file_digest(self) -> None:
        api = self.load_api()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'resource.bin'
            path.write_bytes(b'pinned resource')
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            with mock.patch.object(hashlib, 'file_digest', None, create=True):
                self.assertEqual(api._checked(path, expected), path.absolute())
                with self.assertRaises(ValueError):
                    api._checked(path, '0' * 64)

    def load_api(self) -> object:
        path = Path(__file__).resolve().parents[2]/'benchmarks/brainpec_real/eeg_api.py'
        self.assertTrue(path.exists(),'Standalone generic public API must exist')
        spec = importlib.util.spec_from_file_location('standalone_public_eeg_api',path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_standalone_feature_helper_and_frozen_head_match_generic_math(self) -> None:
        api = self.load_api()
        from eegfm.research_bench.real_data import compute_feature_panel
        x = np.random.default_rng(41).normal(size=(2,20,5,200)).astype(np.float32)
        np.testing.assert_array_equal(api.compute_feature_panel(x),compute_feature_panel(x))
        self.assertEqual(len(api.FEATURE_COLUMNS),62)
        head = {'schema_version':'frozen_linear_head_v1','x_mean':[1.]*200,
                'x_scale':[2.]*200,'coefficient':[.5]*200,'intercept':.25}
        np.testing.assert_allclose(api.head_logits(head,np.full((2,200),3.)),100.25)
        with self.assertRaises(ValueError): api.compute_feature_panel(x[:,:19])

    def test_public_checkpoint_load_is_strict_before_output_replacement(self) -> None:
        import torch
        api = self.load_api()
        model = torch.nn.Module()
        model.proj_out = torch.nn.Linear(3,2)
        original = model.proj_out
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary)/'synthetic.pth'
            torch.save({'wrong_key':torch.zeros(1)},checkpoint)
            with self.assertRaises(RuntimeError):
                api._load_strict_backbone(model,checkpoint)
            self.assertIs(model.proj_out,original)
            torch.save(model.state_dict(),checkpoint)
            api._load_strict_backbone(model,checkpoint)
            self.assertIsInstance(model.proj_out,torch.nn.Identity)
            self.assertFalse(model.training)

    def test_post_layer_activation_continuation_has_no_skipped_or_repeated_layer(self) -> None:
        import torch
        api = self.load_api()
        class Add(torch.nn.Module):
            def __init__(self, value):
                super().__init__(); self.value=value
            def forward(self, value):
                return value+self.value
        model = torch.nn.Module()
        model.patch_embedding = torch.nn.Identity()
        model.encoder = torch.nn.Module()
        model.encoder.layers = torch.nn.ModuleList([Add(1),Add(2)])
        model.encoder.norm = torch.nn.Identity()
        model.proj_out = torch.nn.Identity()
        backbone = api._CPUBackbone(model)
        x = np.zeros((2,20,5,200),dtype=np.float32)
        layers = backbone.activations(x,layers=(1,2))
        np.testing.assert_array_equal(layers[1],np.ones_like(x))
        np.testing.assert_array_equal(backbone.continue_from(layers[1],layer=1),layers[2])
        np.testing.assert_array_equal(backbone.continue_from(layers[2],layer=2),layers[2])
        np.testing.assert_array_equal(backbone.encode(x),np.full((2,200),3,dtype=np.float32))
        with self.assertRaises(ValueError): backbone.continue_from(layers[1],layer=0)


if __name__ == '__main__':
    unittest.main()
