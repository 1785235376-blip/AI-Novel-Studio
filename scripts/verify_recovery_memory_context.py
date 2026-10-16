"""Review one actual model-extracted memory and verify original Context reads it."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,default=Path('.runtime/full-recovery/runtime.json'))
    args=parser.parse_args()
    receipt=json.loads(args.receipt.read_text(encoding='utf8'))
    runtime=json.loads(args.runtime.read_text(encoding='utf8'))
    token=json.loads(Path(runtime['session_file']).read_text(encoding='utf8'))['token']
    started=time.perf_counter()
    result={'stage':'12-memory-human-review-context','status':'FAIL','parent_run_id':receipt['run_id']}
    with httpx.Client(base_url=runtime['api_url'],headers={'X-Session-Token':token},trust_env=False,timeout=30) as client:
        def request(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            if not response.is_success:raise RuntimeError(f'{method} {path}: HTTP {response.status_code}')
            return response.json()
        try:
            stages={row['stage']:row for row in receipt['stages']}
            assert all(row['status']=='PASS' for row in receipt['stages']), 'Parent run must be entirely successful'
            nid=stages['01-project']['evidence']['id']
            memory=stages['05b-memory-extraction']['evidence']
            assert memory['persisted_job']['execution_mode']=='real'
            ids=memory['persisted_job']['result']['proposal_ids']
            candidates=request('GET',f'/api/novels/{nid}/lore/proposals')['items']
            proposal=next(row for row in candidates if row['id'] in ids and row['proposal_type']=='CHARACTER_MEMORY' and row['status']=='PENDING')
            approved=request('POST',f'/api/novels/{nid}/lore/proposals/{proposal["id"]}/approve-memory',json={
                **proposal['payload'],'reviewer':'recovery-human-author'})
            assert approved['proposal']['status']=='APPROVED' and approved['memory']['status']=='ACTIVE'
            cid=memory['persisted_job']['chapter_id']
            chapter=request('GET',f'/api/chapters/{cid}')
            context=request('GET','/api/context-preview',params={'novel_id':nid,'chapter':chapter['number'],'chapter_id':cid,'target':'local'})
            assert approved['memory']['id'] in json.dumps(context,ensure_ascii=False), 'Approved memory must be consumed by the existing chapter Context'
            result.update(status='PASS',evidence={'proposal_before_review':proposal,'approved':approved,'chapter_context':context})
        except Exception as exc:
            # Do not stringify transport errors: they may include request headers.
            result['error']=str(exc) if isinstance(exc,(AssertionError,StopIteration,RuntimeError)) else type(exc).__name__
    result['seconds']=round(time.perf_counter()-started,3)
    args.receipt.with_name(receipt['run_id']+'-12-memory-human-review-context.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='evidence'},ensure_ascii=False))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
