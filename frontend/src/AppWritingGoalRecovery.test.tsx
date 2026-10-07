// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import App from './App';
import {api,type Chapter} from './api';
import {useStudio} from './store';

vi.mock('./Editor',async original=>({...await original<typeof import('./Editor')>(),ChapterEditor:({content,onChange}:any)=><textarea aria-label="Recovery editor" value={content} onChange={event=>onChange(event.target.value,{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:event.target.value}]}]})}/>}));
vi.mock('./ui/AppShell',()=>({AppShell:({main}:any)=><main>{main}</main>}));
vi.mock('./novel/AiWritingPanel',()=>({AiWritingPanel:()=>null}));
vi.mock('./novel/SourcePrivacyControl',()=>({SourcePrivacyControl:()=>null}));
vi.mock('./novel/ChapterTree',()=>({ChapterTree:()=>null}));
vi.mock('./ui/FeatureLauncher',()=>({FeatureLauncher:()=>null}));
const chapter:Chapter={id:'n:1',novel_id:'n',number:1,title:'Synthetic',content:'Saved prose',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Saved prose'}]}]},word_count:11,version:2,status:'DRAFT'};
const clients:QueryClient[]=[];
beforeEach(()=>{localStorage.clear();useStudio.getState().setCollaboration('');useStudio.setState({novelId:'n',chapterId:'n:1',textModel:null});vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({features:{}}),{status:200})));vi.spyOn(api,'chapters').mockResolvedValue([chapter]);vi.spyOn(api,'legacyHistory').mockResolvedValue([])});
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()});
function mount(goal:unknown){
 const client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity},mutations:{retry:false}}});clients.push(client);
 client.setQueryData(['novels'],[{id:'n',title:'Synthetic novel'}]);client.setQueryData(['chapter','file','n:1'],chapter);client.setQueryData(['chapters','file','n'],[chapter]);client.setQueryData(['archived-chapters','file','n'],[]);client.setQueryData(['text-models'],[]);client.setQueryData(['media-tasks','n'],{audiobook:[],motion:[]});client.setQueryData(['writing-goal','n'],goal);
 render(<QueryClientProvider client={client}><App/></QueryClientProvider>);return client;
}
it.each([{items:[]},{current_words:20,target_words:100,current_chapters:1,target_chapters:2,words_progress:Number.NaN},{current_words:'20',target_words:100,current_chapters:1,target_chapters:2,words_progress:20}])('keeps the actual App editor and save path usable with malformed writing-goal data %#',async goal=>{
 const save=vi.spyOn(api,'saveChapter').mockResolvedValue({...chapter,content:'Retained local prose',version:3});mount(goal);
 expect(await screen.findByText('写作目标数据不完整，请刷新后重试。正文仍可编辑和保存。')).toBeTruthy();
 await waitFor(()=>expect((screen.getByLabelText('Recovery editor') as HTMLTextAreaElement).value).toBe('Saved prose'));
 fireEvent.change(screen.getByLabelText('Recovery editor'),{target:{value:'Retained local prose'}});fireEvent.click(screen.getByRole('button',{name:/保存/}));
 await waitFor(()=>expect(save).toHaveBeenCalledOnce());expect(save.mock.calls[0].slice(0,3)).toEqual(['n:1','Retained local prose',2]);
 expect(screen.queryByLabelText('写作目标进度')).toBeNull();
});
it('keeps accurate progress for a complete writing-goal response',async()=>{
 mount({current_words:20,target_words:100,current_chapters:1,target_chapters:2,words_progress:20});
 expect(await screen.findByText('目标 20 / 100 字')).toBeTruthy();expect(screen.getByText('第 1 / 2 章')).toBeTruthy();expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('20');
 expect(screen.queryByText(/数据不完整/)).toBeNull();
});
