"""A contract declaration is not the original Research runtime admission."""
from copy import deepcopy
import pytest
from app.experimental.research_vision import SyntheticResearchVisionProvider
from test_r3_planning import planning_env
from test_r4_model_broker import env

class UnadmittedVision:
    capability=SyntheticResearchVisionProvider.capability.model_copy(update={'provider_id':'unadmitted-vision','verification':'CONTRACT_VERIFIED'})
    calls=0
    def analyze(self,*args):
        self.calls+=1
        raise AssertionError('Broker preview must not dispatch')

def test_real_vision_available_requires_integrated_original_admission(env):
    provider=UnadmittedVision();env.service.vision_resolver=lambda:provider
    before=deepcopy(env.store.read(env.nid,env.scope))
    route=next(r for r in env.service.candidates() if r['capability']=='VISION')
    assert route['available'] is False
    assert 'VISION_MODEL_ADMISSION_NOT_CONFIGURED' in route['reasons']
    assert provider.calls==0 and env.store.read(env.nid,env.scope)==before

def test_real_vision_preview_cannot_choose_or_reserve_unadmitted_executor(env):
    provider=UnadmittedVision();env.service.vision_resolver=lambda:provider
    route=next(r for r in env.service.candidates() if r['capability']=='VISION')
    result=env.service.preview(env.nid,env.scope,'writer',{'capability':'VISION','chapter_ids':[env.order[0]],
        'policy':'CUSTOM','preferred_route':route['route_id'],'profile':'LOCAL_ONLY','allow_synthetic':True})
    assert result['chosen'] is None and result['execution_authorized'] is False
    candidate=next(r for r in result['candidates'] if r['route_id']==route['route_id'])
    assert not candidate['eligible'] and 'VISION_MODEL_ADMISSION_NOT_CONFIGURED' in candidate['reasons']
    with pytest.raises(ValueError):
        env.service.reserve(env.nid,env.scope,'writer',result['id'],result['version'],'blocked-vision','no-job')
    assert not env.service.ledger(env.nid,env.scope,'writer') and provider.calls==0
