"""Fresh reconstruction: original ASGI admission scopes across request tasks."""
import asyncio
import pytest
from app.creative.asset_usage_request import AssetUsageRequestBudgetMiddleware
from app.creative.asset_usage_budget import current_usage_budget, usage_read_budget
from app.repositories.file.mutation_coordinator import strict_coordination_active, existing_coordination_only
pytestmark = pytest.mark.file_backend_only
ASSET='/api/novels/synthetic/experimental/production/assets/synthetic/studio-asset-usages'
GRAPH='/api/novels/synthetic/experimental/production/assets/synthetic/studio-graph-usages'
CHOICES={
 'chapter_post':('http','POST','/api/novels/synthetic/chapters',b''),
 'taskcenter_get':('http','GET','/api/novels/synthetic/experimental/workspace/tasks',b'page_mode=cursor'),
 'health_get':('http','GET','/health',b''),
 'asset_post':('http','POST',ASSET,b'limit=1'),
 'legacy_graph_get':('http','GET',GRAPH,b''),
 'compat_asset_get':('http','GET',ASSET,b'limit=1'),
 'strict_asset_get':('http','GET',ASSET,b'limit=1&strict_read_only=true'),
 'websocket':('websocket',None,'/ws',b'')}
def scope(values):
 kind,method,path,query=values
 return dict(type=kind,method=method,path=path,query_string=query,state={})
async def receive():return {'type':'http.request','body':b''}
async def noop(message):pass

@pytest.mark.parametrize('case',list(CHOICES)+['background'])
def test_real_middleware_drops_previous_request_but_keeps_owned_background(case):
 async def scenario():
  gate=asyncio.Event(); pending=[]; observed=[]; original=[]
  async def inner(request,receive,send):
   b=current_usage_budget(); strict=strict_coordination_active()
   if request.get('first'):
    assert b is not None and strict;original.append(b);b.deadline=-1
    if case=='background':
     async def child():
      await gate.wait();observed.append((current_usage_budget(),strict_coordination_active()))
     pending.append(asyncio.create_task(child()))
    await send({'type':'http.response.start','status':200,'headers':[]})
    await send({'type':'http.response.body','body':b'ok'})
   else:observed.append((b,strict))
  middleware=AssetUsageRequestBudgetMiddleware(inner)
  async def send(message):
   if message['type']=='http.response.body' and case!='background':
    async def following():
     await gate.wait();await middleware(scope(CHOICES[case]),receive,noop)
    pending.append(asyncio.create_task(following()))
  first=scope(CHOICES['strict_asset_get']);first['first']=True
  await middleware(first,receive,send)
  assert current_usage_budget() is None and not strict_coordination_active()
  gate.set();await asyncio.gather(*pending)
  b,strict=observed[0]
  if case=='background':assert b is original[0] and strict
  else:
   assert b is not original[0], 'prior expired request budget leaked'
   assert (b is not None)==(case in {'compat_asset_get','strict_asset_get'})
   assert strict==(case=='strict_asset_get'), 'prior strict scope leaked'
   if b is not None:b.check()
 asyncio.run(scenario())

@pytest.mark.parametrize('cancel',[False,True])
def test_failed_request_is_clean_and_restores_callers(cancel):
 async def scenario():
  seen=[];error=asyncio.CancelledError if cancel else RuntimeError
  async def inner(request,receive,send):
   seen.append((current_usage_budget(),strict_coordination_active()));raise error('synthetic')
  middleware=AssetUsageRequestBudgetMiddleware(inner)
  with usage_read_budget() as outer,existing_coordination_only():
   with pytest.raises(error):await middleware(scope(CHOICES['chapter_post']),receive,noop)
   assert current_usage_budget() is outer and strict_coordination_active()
  assert seen==[(None,False)]
  assert current_usage_budget() is None and not strict_coordination_active()
 asyncio.run(scenario())

def test_concurrent_requests_isolate_but_nested_operations_reuse():
 async def scenario():
  all_entered=asyncio.Event();entered=[];budgets=[]
  async def inner(request,receive,send):
   b=current_usage_budget(); strict=strict_coordination_active();label=request['label']
   entered.append(label)
   if len(entered)==3:all_entered.set()
   await all_entered.wait()
   assert current_usage_budget() is b and strict_coordination_active()==strict
   assert b is not outer
   assert (b is not None)==(label!='taskcenter_get')
   assert strict==(label=='strict_asset_get')
   if b is not None:
    with usage_read_budget() as nested,existing_coordination_only(False):
     assert nested is b and strict_coordination_active()==strict
    budgets.append(b)
  middleware=AssetUsageRequestBudgetMiddleware(inner)
  with usage_read_budget() as outer,existing_coordination_only():
   tasks=[]
   for label in ('strict_asset_get','compat_asset_get','taskcenter_get'):
    request=scope(CHOICES[label]);request['label']=label
    tasks.append(asyncio.create_task(middleware(request,receive,noop)))
   await asyncio.gather(*tasks)
   assert current_usage_budget() is outer and strict_coordination_active()
  assert len(budgets)==2 and budgets[0] is not budgets[1]
 asyncio.run(scenario())
