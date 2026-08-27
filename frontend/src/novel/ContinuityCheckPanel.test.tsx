// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ContinuityCheckPanel} from './ContinuityCheckPanel';
import {api} from '../api';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

const chapter={id:'n:1',novel_id:'n',number:1,title:'第一章',content:'周启走进门。',document:null,version:1,word_count:6,status:'Draft'} as any;

describe('continuity check panel',()=>{
  it('asks the author to pick a chapter instead of pasting JSON',()=>{
    vi.spyOn(api,'worldRules').mockResolvedValue({items:[],storage:'file'});
    vi.spyOn(api,'continuityFindings').mockResolvedValue([]);
    render(<QueryClientProvider client={new QueryClient()}><ContinuityCheckPanel projectId="n"/></QueryClientProvider>);
    expect(screen.getByText('请先选择章节')).toBeTruthy();
    expect(screen.getByRole('button',{name:'检查当前章节'})).toBeTruthy();
  });

  it('scans the current chapter and does not treat the result as a model review',async()=>{
    vi.spyOn(api,'worldRules').mockResolvedValue({items:[],storage:'file'});
    vi.spyOn(api,'continuityFindings').mockResolvedValue([]);
    const scan=vi.spyOn(api,'scanChapterContinuity').mockResolvedValue({
      status:'COMPLETED',
      placeholder:false,
      engine_status:'DISABLED',
      execution_label:'契约校验，未调用模型',
      model_called:false,
      chapter:{id:'n:1',number:1,title:'第一章',word_count:6},
      scanned:{characters:1,locations:0,timeline:0,world_rules:1,foreshadowing:1},
      findings:[{id:'CHARACTER:0:DEAD_CHARACTER',finding_type:'CHARACTER_CONSISTENCY',severity:'ERROR',description:'死亡角色周启无解释出场'}],
      foreshadowing:{chapter:1,pending:[],overdue:[{id:'old-port',title:'旧港事故'}],paid_off:[]},
    } as any);
    render(<QueryClientProvider client={new QueryClient()}><ContinuityCheckPanel projectId="n" chapter={chapter}/></QueryClientProvider>);
    fireEvent.click(await screen.findByRole('button',{name:'检查当前章节'}));
    await waitFor(()=>expect(scan).toHaveBeenCalledWith('n',{chapter_id:'n:1',chapter:1}));
    expect(await screen.findByText(/死亡角色周启无解释出场/)).toBeTruthy();
    expect(screen.getByText('旧港事故')).toBeTruthy();
    expect(screen.getByText(/契约校验，未调用模型/)).toBeTruthy();
    expect(screen.getByText(/不是占位结果/)).toBeTruthy();
  });
});
