"""Compile exact observer boundary only; never import its global audit hooks."""
import ast
import asyncio
import contextvars
from pathlib import Path
import pytest
pytestmark=pytest.mark.file_backend_only

@pytest.mark.parametrize('case',['POST','PUT','websocket','GET','background','exception'])
def test_observer_request_attribution_and_get_owned_background(case):
 async def scenario():
  active=contextvars.ContextVar('independent_observer',default=None)
  records=[];seen=[];pending=[];gate=asyncio.Event()
  async def inner(scope,receive,send):
   r=active.get()
   if scope['type']!='http' or scope['method']!='GET':
    seen.append(r)
    if r is not None:r['command_calls'].append('synthetic-nonget-write')
    if case=='exception':raise RuntimeError('synthetic')
    return
   if case=='background':
    async def owned():
     await gate.wait();r=active.get();seen.append(r)
     if r is not None:r['command_calls'].append('synthetic-get-owned-write')
    pending.append(asyncio.create_task(owned()))
   await send({'type':'http.response.start','status':200})
   await send({'type':'http.response.body','body':b'ok'})
  source=Path(__file__).with_name('file_safety_http_server.py')
  node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.AsyncFunctionDef) and n.name=='app')
  ns=dict(active=active,records=records,save=lambda:None,original_app=inner)
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
  app=ns['app']
  def scope(method='GET',path='/first',kind='http'):
   return dict(type=kind,method=method,path=path,query_string=b'')
  async def receive():return {'type':'http.request','body':b''}
  async def noop(message):pass
  async def send(message):
   if message['type']=='http.response.body' and case not in {'background','exception'}:
    async def following():
     await gate.wait();await app(scope(case,'/next','websocket' if case=='websocket' else 'http'),receive,noop)
    pending.append(asyncio.create_task(following()))
  if case=='exception':
   marker={'command_calls':[]};t=active.set(marker)
   try:
    with pytest.raises(RuntimeError):await app(scope('POST'),receive,noop)
    assert active.get() is marker
   finally:active.reset(t)
   assert seen==[None] and marker['command_calls']==[]
  else:
   await app(scope(),receive,send);assert active.get() is None
   gate.set();await asyncio.gather(*pending)
   if case=='background':assert seen==[records[0]] and records[0]['command_calls']==['synthetic-get-owned-write']
   elif case=='GET':assert [r['path'] for r in records]==['/first','/next']
   else:assert seen==[None] and records[0]['command_calls']==[]
 asyncio.run(scenario())
