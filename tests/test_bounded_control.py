"""Explicit trusted controller wall-time ceiling; ordinary launches stay1800s."""
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from eegfm.agent.budget import run_bounded

@pytest.mark.parametrize('timeout,ceiling',[(3600,3600),(1800,1800),(2,2)])
def test_explicit_ceiling_reaches_existing_evidence_guard_without_spawning(tmp_path,timeout,ceiling):
    with patch('eegfm.agent.budget.sys.platform','linux'):
        with pytest.raises(FileExistsError):
            run_bounded(['unused'],cwd=tmp_path,output_dir=tmp_path,timeout_seconds=timeout,timeout_ceiling_seconds=ceiling)

@pytest.mark.parametrize('timeout,kwargs',[(1801,{}),(3600,{}),(3601,{'timeout_ceiling_seconds':3600}),(3600,{'timeout_ceiling_seconds':1800})])
def test_default_ceiling_and_explicit_upper_boundary_reject_before_output(tmp_path,timeout,kwargs):
    output=tmp_path/'unused'
    with patch('eegfm.agent.budget.sys.platform','linux'):
        with pytest.raises(ValueError,match='resources'):
            run_bounded(['unused'],cwd=tmp_path,output_dir=output,timeout_seconds=timeout,**kwargs)
    assert not output.exists()

@pytest.mark.parametrize('ceiling',[0,-1,3601,True,3600.0,'3600'])
def test_ceiling_must_be_explicit_positive_integer_at_most3600(tmp_path,ceiling):
    with patch('eegfm.agent.budget.sys.platform','linux'):
        with pytest.raises(ValueError,match='ceiling'):
            run_bounded(['unused'],cwd=tmp_path,output_dir=tmp_path/'unused',timeout_seconds=1,timeout_ceiling_seconds=ceiling)

@pytest.mark.skipif(sys.platform!='linux',reason='Actual bounded Linux child and cleanup')
def test_explicit3600_ceiling_runs_short_actual_child_and_records_allocation(tmp_path):
    output=tmp_path/'control'
    result=run_bounded([sys.executable,'-B','-c','print("control-started")'],cwd=tmp_path,output_dir=output,
                       timeout_seconds=3600,timeout_ceiling_seconds=3600,minimum_free_bytes=0)
    assert result['status']=='completed' and result['exit_code']==0
    assert result['timeout_seconds']==3600 and result['timeout_ceiling_seconds']==3600
    assert result['process_cleanup']['surviving_owned_pids']==[]
    assert (output/'stdout.jsonl').read_text().strip()=='control-started'
