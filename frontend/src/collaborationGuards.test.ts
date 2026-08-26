import {describe,expect,it} from 'vitest';
import {classifyCollaborationFailure,isCurrentScope,preserveConflict,rebaseNewerDraft,recoveryKey,requiresHydrationConflict,scopeKey,SingleFlight} from './collaborationGuards';

const a={workspaceId:'w',projectId:'p',storylineId:'s',branchId:'a'};
const b={...a,branchId:'b'};

describe('collaboration transport contract',()=>{
  it('isolates recovery namespaces by opaque session without exposing the token',()=>{
    const first=recoveryKey(a,'token-a'),second=recoveryKey(a,'token-b');
    expect(first).not.toBe(second);
    expect(first).not.toContain('token-a');
    expect(recoveryKey(a,'token-a')).toBe(first);
  });
  it('maps authorization and version failures without conflating them',()=>{
    expect(classifyCollaborationFailure({status:403,code:'FORBIDDEN'})).toBe('FORBIDDEN');
    expect(classifyCollaborationFailure({status:409,code:'VERSION_CONFLICT'})).toBe('VERSION_CONFLICT');
    expect(classifyCollaborationFailure({status:500,code:'HTTP_ERROR'})).toBe('OTHER');
  });

  it('drops a stale response after a scope switch',()=>{
    const dispatched=scopeKey(a);
    expect(isCurrentScope(dispatched,a)).toBe(true);
    expect(isCurrentScope(dispatched,b)).toBe(false);
    expect(isCurrentScope(dispatched,undefined)).toBe(false);
  });

  it('preserves local draft and server state as separate immutable conflict inputs',()=>{
    const local={chapterId:'novel:1',content:'local',baseVersion:4,updatedAt:'2026-01-01'};
    const conflict=preserveConflict(local,{version:5,content:'server'},'2026-01-02');
    expect(conflict.local).toEqual(local);
    expect(conflict.server).toEqual({version:5,content:'server'});
    expect(conflict.local).not.toBe(local);
  });
  it('requires conflict hydration when a draft base is stale',()=>{
    const draft={chapterId:'c',content:'local',baseVersion:4,updatedAt:'now'};
    expect(requiresHydrationConflict(draft,5)).toBe(true);
    expect(requiresHydrationConflict(draft,4)).toBe(false);
  });
  it('retains and rebases durable edit B after in-flight save A succeeds',()=>{
    const durableB={chapterId:'c',content:'B',document:{text:'B'},baseVersion:4,updatedAt:'later'};
    expect(rebaseNewerDraft(durableB,{content:'A',document:{text:'A'}},5)).toEqual({...durableB,baseVersion:5});
    expect(rebaseNewerDraft({...durableB,content:'A',document:{text:'A'}},{content:'A',document:{text:'A'}},5)).toBeUndefined();
  });
  it('coalesces rapid double save while the first request is in flight',async()=>{
    let release!:(value:number)=>void,calls=0;const controlled=new Promise<number>(ok=>release=ok),gate=new SingleFlight<number>();
    const first=gate.run(()=>{calls++;return controlled}),second=gate.run(()=>{calls++;return Promise.resolve(2)});
    expect(calls).toBe(1);expect(second).toBe(first);release(1);expect(await second).toBe(1);expect(gate.active).toBe(false);
  });
});
