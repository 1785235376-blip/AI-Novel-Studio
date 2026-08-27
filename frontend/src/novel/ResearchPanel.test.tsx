// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {ResearchPanel} from './ResearchPanel';
import {api} from '../api';

afterEach(()=>{cleanup();vi.restoreAllMocks()});

describe('research panel',()=>{
  it('creates a research record from the window form',async()=>{
    vi.spyOn(api,'listResearch').mockResolvedValue({items:[],total:0,storage:'durable_sidecar',external_fetch:false});
    const create=vi.spyOn(api,'createResearch').mockResolvedValue({id:'r1',title:'Phase1 Desktop 验收资料',version:1});
    render(<QueryClientProvider client={new QueryClient()}><ResearchPanel novelId="n1"/></QueryClientProvider>);
    fireEvent.change(await screen.findByLabelText('标题'),{target:{value:'Phase1 Desktop 验收资料'}});
    fireEvent.click(screen.getByRole('button',{name:'新建资料'}));
    await waitFor(()=>expect(create).toHaveBeenCalled());
  });
});
