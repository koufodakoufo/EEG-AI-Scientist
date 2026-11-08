"""Opt-in delegated episode admission, no model/science/provider starts."""
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from eegfm.eeg import episode
from eegfm.evaluation.bundle import digest_file


def config(tmp_path):
    roles=['public_train','public_validation','inference_train','inference_validation','inference_test','truth_train','truth_validation','truth_test','cohort','split_manifest']
    bindings={}
    for role in roles:
        p=tmp_path/f'{role}.npz';p.write_bytes(role.encode());bindings[role]={'path':str(p),'sha256':digest_file(p)}
    proof=tmp_path/'historical.json';proof.write_text(json.dumps({'status':'exact_historical_readout_inputs_qualified_for_development_replay','not_project_unseen_confirmation':True,'previous_successful_test_job':'old-success-test','bindings':[{'role':name,'sha256':value['sha256']} for name,value in bindings.items()]}))
    return {'schema_version':'audited_coding_episode_v1','task_id':episode.READOUT_TASK,'model':'gpt-6.1-sol','reasoning_effort':'high','session_timeout_seconds':180,'episode_timeout_seconds':2700,'call_ids':['coding-1','coding-2'],
      'historical_data_qualification':{'path':str(proof),'sha256':digest_file(proof)},'train_input':bindings['public_train'],'public_validation_input':bindings['public_validation'],
      'validation_input':bindings['inference_validation'],'test_input':bindings['inference_test'],'inference_by_split':{s:bindings['inference_'+s] for s in ('train','validation','test')},
      'train_truth':bindings['truth_train'],'truth_by_split':{s:bindings['truth_'+s] for s in ('validation','test')},'test_cohort':bindings['cohort'],'split_manifest':bindings['split_manifest']}


def test_new_provider_schema_explicitly_routes_without_native_auth_path(tmp_path):
    value=config(tmp_path)
    with patch.object(episode,'run_delegated_episode',return_value={'typed_provider':True}):
        assert episode.run_episode(value)=={'typed_provider':True}


def test_historical_exact_roles_and_allocation_are_required(tmp_path):
    value=config(tmp_path)
    result=episode.validate_delegated_config(value)
    assert result['previous_successful_test_job']=='old-success-test'
    for update in ({'session_timeout_seconds':900},{'auth_source':'never-read'},{'task_id':'unknown'},{'test_input':value['validation_input']}):
        with pytest.raises(ValueError):episode.validate_delegated_config({**value,**update})
