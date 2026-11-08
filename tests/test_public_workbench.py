"""Public fit boundary tests: synthetic arrays; never execute candidate source."""
from pathlib import Path
from types import SimpleNamespace
import base64
import io
import json
import zipfile
from unittest.mock import patch
import numpy as np
import pytest
from eegfm.evaluation import public_workbench as public
from eegfm.evaluation.bundle import create_public_bundle,digest_file
from eegfm.evaluation.worker import FileBinding,SplitInputs,RuntimeConfig,SandboxedWorkerEvaluator,candidate_digest
from eegfm.agent.controller import EvaluationSpec


@pytest.fixture
def context(tmp_path):
    source=tmp_path/'source';source.mkdir()
    for name in ('train','validation'):np.savez(source/f'{name}.npz',x=np.ones((4,2)),y=np.array([0,1,0,1]))
    bundle=tmp_path/'case/public';bundle.parent.mkdir()
    create_public_bundle(source,bundle,['train.npz','validation.npz'],task_id='synthetic-public-fit',tier='synthetic_mechanism')
    split=tmp_path/'split.json';split.write_text('{}')
    return tmp_path,bundle,split


def parameters(path,**values):np.savez(path,**(values or {'weights':np.array([1.,2.]),'intercept':np.array(0.)}))


def test_numeric_parameters_are_bounded_and_public_export_is_typed(tmp_path):
    out=tmp_path/'out';out.mkdir();parameters(out/'parameters.npz')
    record=public.encode_parameters(out/'parameters.npz')
    assert public.decode_parameters(record)==(out/'parameters.npz').read_bytes()
    for value in (np.array([float('nan')]),np.array(['secret']),np.array([{}],dtype=object)):
        parameters(out/'bad.npz',weights=value)
        with pytest.raises(ValueError):public.encode_parameters(out/'bad.npz')
    record['sha256']='0'*64
    with pytest.raises(ValueError):public.decode_parameters(record)


def test_zip_keys_oversize_and_unknown_artifact_names_rejected(tmp_path):
    path=tmp_path/'parameters.npz';parameters(path,**{'../weights':np.ones(1)})
    with pytest.raises(ValueError):public.encode_parameters(path)
    parameters(path,weights=np.ones(1))
    record=public.encode_parameters(path);record['name']='results.npz'
    with pytest.raises(ValueError):public.decode_parameters(record)


def make_worker(context,mode=None,splits=frozenset({'validation','test'})):
    root,bundle,split=context
    docker=root/'docker';docker.write_text('fixture binary')
    aggregate=public.PublicFitAggregator(bundle,digest_file(bundle/'PUBLIC_MANIFEST.json'))
    inputs={name:SplitInputs(FileBinding(bundle/'train.npz',digest_file(bundle/'train.npz')),FileBinding(bundle/'validation.npz',digest_file(bundle/'validation.npz'))) for name in splits}
    backend=SimpleNamespace(inspect_image=lambda:{'image':'fixture'})
    with patch('eegfm.evaluation.worker.sys.platform','linux'),patch('eegfm.evaluation.docker_worker.DockerBackend',return_value=backend):
        return SandboxedWorkerEvaluator(private_root=root/'private',public_root=bundle,public_manifest_sha256=digest_file(bundle/'PUBLIC_MANIFEST.json'),split_manifest_path=split,split_manifest_sha256=digest_file(split),inputs_by_split=inputs,runtime=RuntimeConfig(None,Path('/usr/bin/python'),backend='docker',docker=docker.resolve(),docker_image='sha256:'+'a'*64),aggregate=aggregate,released_metrics=aggregate.released_metrics,aggregate_bindings=aggregate.bindings,aggregate_policy_sha256=aggregate.policy_sha256,allowed_splits=splits,public_artifact_mode=mode)


def test_public_fit_admission_requires_validation_only_and_public_input_bindings(context):
    worker=make_worker(context,mode=public.MODE,splits=frozenset({'validation'}))
    assert worker.allowed_splits==frozenset({'validation'})
    assert worker.public_artifact_mode==public.MODE
    with pytest.raises(ValueError):make_worker(context,mode=public.MODE)
    root,bundle,_=context
    (bundle/'train.npz').write_bytes(b'changed')
    with pytest.raises(ValueError):make_worker(context,mode=public.MODE,splits=frozenset({'validation'}))


def test_public_fit_accepts_bound_public_labels_without_relaxing_private_schema(context):
    worker=make_worker(context,mode=public.MODE,splits=frozenset({'validation'}))
    root,_,_=context
    source=root/'source-code';source.mkdir();(source/'main.py').write_text('pass')
    spec=EvaluationSpec('fit-public','episode','run','fit','validation',source,candidate_digest(source),worker.split_hash,worker.public_hash)
    assert worker._verify(spec).evaluation.path.name=='validation.npz'


def test_ordinary_worker_cannot_export_public_artifacts(context):
    with pytest.raises(ValueError):make_worker(context,mode='export-anything',splits=frozenset({'validation'}))


def test_public_fit_test_rpc_denied_before_candidate_staging(context):
    from eegfm.evaluation import ssh_worker
    worker=make_worker(context,mode=public.MODE,splits=frozenset({'validation'}))
    root,bundle,split=context
    config={'episode_id':'episode','run_id':'run','staging_root':str(root/'staging')}
    source=root/'candidate';source.mkdir();(source/'main.py').write_text('raise RuntimeError("not run")')
    digest=candidate_digest(source)
    record={'job_id':'forbidden-test','episode_id':'episode','run_id':'run','attempt_id':'public-fit','split':'test','candidate_digest':digest,'public_manifest_sha256':worker.public_hash,'split_manifest_sha256':worker.split_hash}
    with patch.object(ssh_worker,'load_worker',return_value=(config,worker)):
        with pytest.raises(ValueError):ssh_worker.handle_request(FileBinding(split,digest_file(split)),{'operation':'submit','spec':record,'files':ssh_worker.encode_candidate(source,digest)})
    assert not (root/'staging').exists()


class FakeWorker:
    def __init__(self,public_hash):
        self.public_hash=public_hash;self.submissions=0;self.polls=0;self.spec=None;self.result=None
    def _enrollment(self):return {'allowed_splits':['validation'],'public_artifact_mode':public.MODE,'public_artifact_manifest_sha256':self.public_hash}
    def submit(self,spec):
        self.submissions+=1;self.spec=spec
        return {'job_id':spec.job_id,'candidate_digest':spec.candidate_digest,'split':'validation','status':'waiting'}
    def poll(self,job_id):
        self.polls+=1
        return self.result or {'job_id':job_id,'candidate_digest':self.spec.candidate_digest,'split':'validation','status':'waiting'}


def test_fit_submission_replay_never_resubmits_and_promotion_binds_case(context):
    root,bundle,split=context
    candidate=bundle.parent/'output/candidate';candidate.mkdir(parents=True)
    (candidate/'fit.py').write_text("raise RuntimeError('must never execute on host')")
    (candidate/'main.py').write_text('pass')
    worker=FakeWorker(digest_file(bundle/'PUBLIC_MANIFEST.json'))
    bench=public.PublicWorkbench(evaluator=worker,private_root=root/'workbench',case_root=bundle.parent,episode_id='episode',run_id='run',public_manifest_sha256=worker.public_hash,split_manifest_sha256=digest_file(split))
    first=bench.submit('fit-1','candidate')
    assert first['status']=='waiting' and worker.submissions==1
    bench.submit('fit-1','candidate');assert worker.submissions==1 and worker.polls==1
    params=root/'parameters.npz';parameters(params)
    worker.result={'job_id':'fit-1','candidate_digest':worker.spec.candidate_digest,'split':'validation','status':'succeeded','public_artifacts':[public.encode_parameters(params)]}
    result=bench.poll('fit-1')
    assert result['status']=='succeeded' and (candidate/'parameters.npz').read_bytes()==params.read_bytes()
    worker.result={**worker.result,'job_id':'other-case'}
    with pytest.raises(ValueError):bench.poll('fit-1')


def test_fit_reused_id_with_changed_source_and_ordinary_worker_rejected(context):
    root,bundle,split=context
    candidate=bundle.parent/'output/candidate';candidate.mkdir(parents=True);(candidate/'fit.py').write_text('pass')
    worker=FakeWorker(digest_file(bundle/'PUBLIC_MANIFEST.json'))
    bench=public.PublicWorkbench(evaluator=worker,private_root=root/'fit',case_root=bundle.parent,episode_id='episode',run_id='run',public_manifest_sha256=worker.public_hash,split_manifest_sha256=digest_file(split))
    bench.submit('fit-1','candidate');(candidate/'fit.py').write_text('different')
    with pytest.raises(ValueError):bench.submit('fit-1','candidate')
    worker._enrollment=lambda:{'allowed_splits':['validation','test']}
    with pytest.raises(ValueError):public.PublicWorkbench(evaluator=worker,private_root=root/'other',case_root=bundle.parent,episode_id='episode',run_id='run',public_manifest_sha256=worker.public_hash,split_manifest_sha256=digest_file(split))


def test_fit_journal_cannot_reopen_in_different_case_with_identical_source(context):
    root,bundle,split=context
    candidate=bundle.parent/'output/candidate';candidate.mkdir(parents=True);(candidate/'fit.py').write_text('pass')
    worker=FakeWorker(digest_file(bundle/'PUBLIC_MANIFEST.json'))
    options={'evaluator':worker,'private_root':root/'fit','case_root':bundle.parent,'episode_id':'episode','run_id':'run','public_manifest_sha256':worker.public_hash,'split_manifest_sha256':digest_file(split)}
    bench=public.PublicWorkbench(**options);bench.submit('fit-1','candidate')
    other=root/'different-case';(other/'output/candidate').mkdir(parents=True);(other/'output/candidate/fit.py').write_text('pass')
    with pytest.raises(ValueError):public.PublicWorkbench(**{**options,'case_root':other})
