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
// [HERMIA-FE-20261022 U5] 普通模式「人物」页签不显示人物一致性检查；状态英文只做中文显示
async function mountChars(pro:boolean){
 vi.spyOn(api,'novel').mockResolvedValue({id:'n',title:'Synthetic',status:'DRAFT'} as any);
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});clients.push(client);
 render(<QueryClientProvider client={client}><StoryDatabasePanel pro={pro} chapter={chapter} onOpenChapter={vi.fn()}/></QueryClientProvider>);
 fireEvent.click((await screen.findAllByRole('tab',{name:/^角色/}))[0]!);
}
it('normal mode hides 人物一致性检查 / 检查当前章节',async()=>{
 await mountChars(false);await screen.findByText('新建人物');
 expect(screen.queryByText('人物一致性检查')).toBeNull();expect(screen.queryByRole('button',{name:'检查当前章节'})).toBeNull();
});
it('pro mode keeps 人物一致性检查',async()=>{
 await mountChars(true);expect(await screen.findByText('人物一致性检查')).toBeTruthy();
 expect(screen.getByRole('button',{name:'检查当前章节'})).toBeTruthy();
});
