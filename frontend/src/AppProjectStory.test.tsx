// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import App,{StoryDatabasePanel} from './App';
import {api,setCollaborationContext} from './api';
import {useStudio} from './store';

vi.mock('./novel/AiWritingPanel',()=>({AiWritingPanel:()=>null}));
vi.mock('./novel/SourcePrivacyControl',()=>({SourcePrivacyControl:()=>null}));
const clients:QueryClient[]=[];
beforeEach(()=>{
 localStorage.clear();setCollaborationContext({sessionToken:''});useStudio.getState().setCollaboration('');useStudio.setState({novelId:'n',chapterId:'',textModel:null});
 vi.spyOn(api,'resource').mockResolvedValue([]);vi.spyOn(api,'outline').mockResolvedValue({theme:'Identity',premise:'Lost memory',beginning:'City',middle:'Clues',ending:'Truth'});
 vi.spyOn(api,'chapters').mockResolvedValue([]);vi.spyOn(api,'storyRoutes').mockResolvedValue([]);vi.spyOn(api,'worldRules').mockResolvedValue({items:[],storage:'file'});
 vi.spyOn(api,'novel').mockResolvedValue({id:'n',title:'Synthetic',genre:'Mystery',word_count:0,chapter_count:0,status:'DRAFT',world_summary:'Abandoned city'} as any);
 vi.spyOn(api,'novels').mockResolvedValue([{id:'n',title:'Synthetic',genre:'Mystery',word_count:0,chapter_count:0,status:'DRAFT'}]);
 vi.spyOn(api,'textModels').mockResolvedValue([]);vi.spyOn(api,'writingGoal').mockResolvedValue({current_words:0,target_words:0,current_chapters:0,target_chapters:0,words_progress:0,chapters_progress:0,deadline:''});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({features:{},items:[]}),{status:200})));
});
afterEach(()=>{cleanup();clients.splice(0).forEach(client=>client.clear());vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()});
function mount(app=false){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);render(<QueryClientProvider client={client}>{app?<App/>:<StoryDatabasePanel novelId="n" onOpenChapter={vi.fn()}/>}</QueryClientProvider>)}
it('opens and saves world settings through the project owner before a first chapter exists',async()=>{
 const save=vi.spyOn(api,'updateNovel').mockResolvedValue({id:'n',world_summary:'Edited city'} as any);mount();
 fireEvent.click(await screen.findByRole('tab',{name:/世界观/}));
 await waitFor(()=>expect((screen.getByLabelText('核心设定') as HTMLTextAreaElement).value).toBe('Abandoned city'));
 fireEvent.change(screen.getByLabelText('核心设定'),{target:{value:'Edited city'}});fireEvent.click(screen.getByRole('button',{name:'保存世界观概要'}));
 await waitFor(()=>expect(save).toHaveBeenCalledWith('n',{world_summary:'Edited city'}));
 expect(api.chapters).toHaveBeenCalledWith('n');expect(api.resource).toHaveBeenCalledWith('n','characters');
});
it('edits a character in the same project with no synthetic chapter or chapter consistency request',async()=>{
 const save=vi.spyOn(api,'upsertCharacter').mockResolvedValue({id:'Wanderer',name:'Wanderer'} as any),check=vi.spyOn(api,'characterConsistencyCheck');mount();
 fireEvent.change(await screen.findByLabelText('姓名'),{target:{value:'Wanderer'}});fireEvent.click(screen.getByRole('button',{name:'保存人物'}));
 await waitFor(()=>expect(save).toHaveBeenCalledWith('n','Wanderer',expect.objectContaining({name:'Wanderer'})));
 expect(check).not.toHaveBeenCalled();expect(screen.queryByText('人物一致性检查')).toBeNull();
});
it('loads and edits the adopted outline before chapter generation',async()=>{
 const save=vi.spyOn(api,'updateOutline').mockResolvedValue({theme:'Identity revised'} as any);mount();fireEvent.click(await screen.findByRole('tab',{name:/大纲/}));
 await waitFor(()=>expect((screen.getByLabelText('主题') as HTMLInputElement).value).toBe('Identity'));
 fireEvent.change(screen.getByLabelText('主题'),{target:{value:'Identity revised'}});fireEvent.click(screen.getByRole('button',{name:'保存小说大纲'}));
 await waitFor(()=>expect(save).toHaveBeenCalledWith('n',expect.objectContaining({theme:'Identity revised',premise:'Lost memory'})));
});
it('the actual App navigation opens the project Story database without requiring a chapter',async()=>{
 mount(true);fireEvent.click(await screen.findByRole('button',{name:/^打开功能导航$/}));fireEvent.click(await screen.findByRole('button',{name:/^故事资料库$/}));
 fireEvent.click(await screen.findByRole('tab',{name:/世界观/}));
 await waitFor(()=>expect((screen.getByLabelText('核心设定') as HTMLTextAreaElement).value).toBe('Abandoned city'));
 expect(screen.queryByText('请先新建或选择一个章节，再查看当前小说的人物和世界设定。')).toBeNull();expect(useStudio.getState().chapterId).toBe('');
});
