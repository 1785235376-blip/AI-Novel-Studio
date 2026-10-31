from dataclasses import replace
import os
import subprocess
import sys
import pytest
from test_file_keyed_activation import keyed, memory_settings, queued, finish, post
from app.services.generation_project_binding import FIELD
pytestmark=pytest.mark.file_backend_only


def turn_off(f):
    import app.config as config
    f.monkeypatch.setattr(config,'settings',replace(config.settings,enable_experimental_file_keyed_generation=False))


def test_switch_default_is_off_and_explicit_environment_opt_in():
    env=dict(os.environ); env.pop('ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION',None)
    code='from app.config import Settings; print(Settings().enable_experimental_file_keyed_generation)'
    assert subprocess.check_output([sys.executable,'-c',code],env=env,text=True).strip()=='False'
    env['ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION']='true'
    assert subprocess.check_output([sys.executable,'-c',code],env=env,text=True).strip()=='True'


def test_client_cannot_opt_in_when_switch_off(keyed):
    f=keyed; turn_off(f)
    _,job=queued(f,enable_experimental_file_keyed_generation=True,ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION=True)
    assert FIELD not in f.persistence.get(job.id)
    row=finish(f,job)
    assert FIELD not in row and job._ordinary_execution_capability is None


def test_switch_off_preserves_live_binding_replay_and_cold_no_execution(keyed):
    f=keyed
    result,job=queued(f); binding=dict(f.persistence.get(job.id)[FIELD])
    turn_off(f)
    assert f.client.post(f'/api/generation/{job.id}/cancel').status_code==409
    row=finish(f,job); assert row[FIELD]==binding
    replay=post(f)
    assert replay.status_code==202 and replay.json()==result
    assert f.counts['provider']==f.counts['worker']==1
    cold=f.reopen(); restored=cold.get(job.id)
    assert restored._ordinary_execution_capability is None
    with pytest.raises(Exception): cold.start_prepared(restored)
    with pytest.raises(Exception): cold._run(restored)
    f.monkeypatch.setattr(__import__('app.api',fromlist=['jobs']),'jobs',cold)
    response=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    assert response.status_code==200,response.text
    assert f.memory_finished.wait(10)
    assert f.persistence.get(job.id)[FIELD]==binding
    assert f.counts['provider']==f.counts['worker']==1
