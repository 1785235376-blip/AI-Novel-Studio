"""Fresh real h11 pipelined requests; no transport context-reset option."""
import json
import socket
import threading
import time
import pytest
import uvicorn
from app.creative.asset_usage_request import AssetUsageRequestBudgetMiddleware
from app.creative.asset_usage_budget import current_usage_budget
from app.repositories.file.mutation_coordinator import strict_coordination_active
pytestmark=pytest.mark.file_backend_only

def responses(raw):
 result=[]
 while raw:
  header,raw=raw.split(b'\r\n\r\n',1)
  assert header.split(b'\r\n',1)[0].split()[1]==b'200'
  fields=dict(line.split(b':',1) for line in header.lower().split(b'\r\n')[1:])
  size=int(fields[b'content-length']);result.append(json.loads(raw[:size]));raw=raw[size:]
 return result

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
@pytest.mark.parametrize('next_kind',['chapter_post','taskcenter_get','health_get','ordinary_asset_get'])
def test_pipelined_transport_request_context_isolation(prefix,next_kind):
 selected=prefix+'/novels/synthetic/experimental/production/assets/synthetic/studio-asset-usages'
 choices={'chapter_post':('POST',prefix+'/novels/synthetic/chapters'),
          'taskcenter_get':('GET',prefix+'/novels/synthetic/experimental/workspace/tasks'),
          'health_get':('GET','/health'),'ordinary_asset_get':('GET',selected+'?limit=1')}
 method,path=choices[next_kind]
 async def endpoint(scope,receive,send):
  budget=current_usage_budget()
  if b'strict_read_only=true' in scope.get('query_string',b''):
   assert budget is not None;budget.deadline=0
  body=json.dumps(dict(budget=budget is not None,strict=strict_coordination_active(),expired=budget is not None and budget.deadline==0)).encode()
  await send({'type':'http.response.start','status':200,'headers':[(b'content-length',str(len(body)).encode())]})
  await send({'type':'http.response.body','body':body})
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(AssetUsageRequestBudgetMiddleware(endpoint),host='127.0.0.1',port=port,http='h11',lifespan='off',log_level='error'))
 thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
 try:
  deadline=time.monotonic()+10
  while not server.started:
   assert thread.is_alive() and time.monotonic()<deadline;time.sleep(.01)
  first=f'GET {selected}?limit=1&strict_read_only=true HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n'
  second=f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
  with socket.create_connection(('127.0.0.1',port),timeout=10) as client:
   client.sendall((first+second).encode());raw=b''
   while True:
    piece=client.recv(65536)
    if not piece:break
    raw+=piece
  got=responses(raw);assert len(got)==2
  assert got[0]==dict(budget=True,strict=True,expired=True)
  assert got[1]==dict(budget=next_kind=='ordinary_asset_get',strict=False,expired=False)
 finally:
  server.should_exit=True;thread.join(10);sock.close();assert not thread.is_alive()
