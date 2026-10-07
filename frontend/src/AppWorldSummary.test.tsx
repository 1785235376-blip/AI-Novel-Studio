// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {StoryDatabasePanel} from './App';
import {api,setCollaborationContext,type Chapter} from './api';
const chapter:Chapter={id:'n:1',novel_id:'n',number:1,title:'Synthetic',content:'Stored',document:null,word_count:6,version:2,status:'DRAFT'};
const clients:QueryClient[]=[];
beforeEach(()=>{setCollaborationContext({sessionToken:''});vi.spyOn(api,'resource').mockResolvedValue([]);vi.spyOn(api,'outline').mockResolvedValue({});vi.spyOn(api,'chapters').mockResolvedValue([chapter]);vi.spyOn(api,'storyRoutes').mockResolvedValue([]);vi.spyOn(api,'worldRules').mockResolvedValue({items:[],storage:'file'});vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({features:{}}),{status:200})))});
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals()});
async function mount(meta:Record<string,unknown>){
 vi.spyOn(api,'novel').mockResolvedValue({id:'n',title:'Synthetic',genre:'Mystery',word_count:6,chapter_count:1,status:'DRAFT',...meta} as any);
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 render(<QueryClientProvider client={client}><StoryDatabasePanel chapter={chapter} onOpenChapter={vi.fn()}/></QueryClientProvider>);
 fireEvent.click(await screen.findByRole('tab',{name:/世界观/}));return client;
}
it('shows and edits the same world_summary owner used by an adopted model proposal',async()=>{
 const save=vi.spyOn(api,'updateNovel').mockResolvedValue({id:'n',world_summary:'Edited world'} as any);
 await mount({world_summary:'Generated world',long_term_summary:'Chapter memory summary'});
 await waitFor(()=>expect((screen.getByLabelText('核心设定') as HTMLTextAreaElement).value).toBe('Generated world'));
 fireEvent.change(screen.getByLabelText('核心设定'),{target:{value:'Edited world'}});fireEvent.click(screen.getByRole('button',{name:'保存世界观概要'}));
 await waitFor(()=>expect(save).toHaveBeenCalledWith('n',{world_summary:'Edited world'}));
});
it('keeps legacy summaries readable when the world_summary field has not been created',async()=>{
 await mount({long_term_summary:'Legacy setting'});await waitFor(()=>expect((screen.getByLabelText('核心设定') as HTMLTextAreaElement).value).toBe('Legacy setting'));
});
it('does not replace an explicitly empty world_summary with chapter memory',async()=>{
 await mount({world_summary:'',long_term_summary:'Chapter memory summary'});await waitFor(()=>expect(api.novel).toHaveBeenCalled());
 expect((screen.getByLabelText('核心设定') as HTMLTextAreaElement).value).toBe('');
});
