// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {NovelOverviewPanel} from './NovelOverviewPanel';
import {api} from '../api';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

describe('novel overview panel',()=>{
  it('renders real counts instead of a reserved-service placeholder',async()=>{
    vi.spyOn(api,'novelOverview').mockResolvedValue({
      novel:{id:'n1',title:'雾港'},
      counts:{chapters:2,characters:3,locations:1,timeline:4,foreshadowing:2,world_rules:1,research:1},
      content:{word_count:1200,has_chapters:true,latest_chapter:null},
      writing_goal:{target_words:5000,target_chapters:10,words_progress:0.24,chapters_progress:0.2,deadline:''},
      pending_items:[{kind:'missing',label:'outline'}],
      recent_activity:[{id:'a1',action:'RESEARCH_CREATED',target_type:'ResearchRecord',target_id:'r1',created_at:'2026-08-28'}],
      readiness:{state:'CONTENT_READY',missing:[]},
      storage:'durable_sidecar',
      placeholder:false,
    } as any);
    vi.spyOn(api,'writingGoal').mockResolvedValue({target_words:5000,target_chapters:10,current_words:1200,current_chapters:2,words_progress:0.24,chapters_progress:0.2,deadline:''});
    render(<QueryClientProvider client={new QueryClient()}><NovelOverviewPanel novelId="n1"/></QueryClientProvider>);
    expect(await screen.findByText('1200')).toBeTruthy();
    expect(screen.getByText('研究资料')).toBeTruthy();
    expect(screen.getByText('待处理项')).toBeTruthy();
    expect(screen.getByText('outline')).toBeTruthy();
    expect(screen.getByText(/不是“服务尚未接入”占位/)).toBeTruthy();
  });
});
