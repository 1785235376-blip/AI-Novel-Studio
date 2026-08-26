import {describe,expect,it,vi} from 'vitest';
import {importChaptersWithRecovery,type ImportRecovery} from './importRecovery';

const plan={format:'txt',title:'测试小说',chapters:[{number:1,title:'第一章',content:'甲'},{number:2,title:'第二章',content:'乙'}]};

describe('collaboration import recovery',()=>{
  it('resumes a failed save without creating the chapter twice',async()=>{
    const recovery:ImportRecovery={nextIndex:0};const create=vi.fn(async(title:string)=>({id:title,version:1}));let fail=true;
    const save=vi.fn(async()=>{if(fail){fail=false;throw new Error('network')}});const persist=vi.fn();
    await expect(importChaptersWithRecovery({plan,recovery,persist,create,save})).rejects.toThrow('network');
    expect(recovery.pending?.chapter.id).toBe('第一章');expect(recovery.nextIndex).toBe(0);
    await importChaptersWithRecovery({plan,recovery,persist,create,save});
    expect(create).toHaveBeenCalledTimes(2);expect(create.mock.calls.map(call=>call[0])).toEqual(['第一章','第二章']);
    expect(recovery).toEqual({nextIndex:2});
  });

  it('skips chapters completed before recovery',async()=>{
    const recovery:ImportRecovery={nextIndex:1};const create=vi.fn(async(title:string)=>({id:title,version:1}));const save=vi.fn(async()=>{});
    await importChaptersWithRecovery({plan,recovery,persist:vi.fn(),create,save});
    expect(create).toHaveBeenCalledOnce();expect(create).toHaveBeenCalledWith('第二章');expect(save).toHaveBeenCalledOnce();
  });
});
