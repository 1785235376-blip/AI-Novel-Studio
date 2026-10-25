// @vitest-environment jsdom
// [HERMIA-FE-20261025 VERA-FIX MF-1/MF-4] Vera re-review: one state per screen.
// 章节列表 500 / 加载中 时，中间与右侧都不得出现「新建/选择章节」主行动；写作台/版本徽章仅专业模式。
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import App from './App';
import {api,type Chapter} from './api';
import {useStudio} from './store';
const mode:{v:'basic'|'pro'|null}={v:null};
vi.mock('./workbench/useWorkbenchLayout',async original=>{const o=await original<typeof import('./workbench/useWorkbenchLayout')>();return {...o,useWorkbenchLayout:(...a:Parameters<typeof o.useWorkbenchLayout>)=>{const r=o.useWorkbenchLayout(...a);return mode.v?{...r,mode:mode.v}:r}}});
vi.mock('./Editor',async original=>({...await original<typeof import('./Editor')>(),ChapterEditor:()=><textarea aria-label="ed"/>}));
vi.mock('./ui/AppShell',()=>({AppShell:({main,inspector,sidebar}:any)=><div><aside>{sidebar}</aside><main>{main}</main><aside data-testid="insp">{inspector}</aside></div>}));
vi.mock('./novel/AiWritingPanel',()=>({AiWritingPanel:()=>null}));
vi.mock('./novel/SourcePrivacyControl',()=>({SourcePrivacyControl:()=>null}));
vi.mock('./ui/FeatureLauncher',async o=>({...await o<typeof import('./ui/FeatureLauncher')>(),FeatureLauncher:()=>null}));
const chapter:Chapter={id:'n:1',novel_id:'n',number:1,title:'Synthetic',content:'p',document:{type:'doc',content:[]},word_count:1,version:2,status:'DRAFT'} as Chapter;
const clients:QueryClient[]=[];
beforeEach(()=>{mode.v=null;localStorage.clear();useStudio.getState().setCollaboration('');vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({features:{}}),{status:200})));vi.spyOn(api,'legacyHistory').mockResolvedValue([])});
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear()});
function mount(withChapter:boolean){
 const client=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity},mutations:{retry:false}}});clients.push(client);
 client.setQueryData(['novels'],[{id:'n',title:'Synthetic novel'}]);client.setQueryData(['archived-chapters','file','n'],[]);client.setQueryData(['text-models'],[]);client.setQueryData(['media-tasks','n'],{audiobook:[],motion:[]});client.setQueryData(['writing-goal','n'],{items:[]});
 if(withChapter){client.setQueryData(['chapter','file','n:1'],chapter);client.setQueryData(['chapters','file','n'],[chapter]);}
 return render(<QueryClientProvider client={client}><App/></QueryClientProvider>);
}
function expectNoCreateCta(c:HTMLElement){
 expect(c.querySelector('[data-primary-cta]')).toBeNull();
 expect(c.querySelector('.nv-assist__next')).toBeNull();
 expect(screen.queryByText(/在左侧选择或新建章节/)).toBeNull();
 expect(screen.queryByText(/当前还没有打开的章节/)).toBeNull();
 expect(screen.queryByRole('button',{name:/新建章节/})).toBeNull();
}
it('chapters 500: single error state, no create/select CTA anywhere, no raw error text',async()=>{
 useStudio.setState({novelId:'n',chapterId:'',textModel:null});
 vi.spyOn(api,'chapters').mockRejectedValue(new Error('{"detail":"boom"}'));
 const r=mount(false);
 await waitFor(()=>expect(r.container.querySelector('[data-desk-state="error"]')).not.toBeNull(),{timeout:5000}); // retry:1 → ~1s
 expectNoCreateCta(r.container);
 expect(r.container.textContent).not.toContain('boom');
});
it('chapters loading: single loading state, no create/select CTA',async()=>{
 useStudio.setState({novelId:'n',chapterId:'',textModel:null});
 vi.spyOn(api,'chapters').mockReturnValue(new Promise(()=>{}) as any);
 const r=mount(false);
 await waitFor(()=>expect(r.container.querySelector('[data-desk-state="loading"]')).not.toBeNull());
 expectNoCreateCta(r.container);
});
it.each([['basic',false],['pro',true]] as const)('写作台/版本 badges gated by mode=%s',async(m,shown)=>{
 mode.v=m;useStudio.setState({novelId:'n',chapterId:'n:1',textModel:null});
 vi.spyOn(api,'chapters').mockResolvedValue([chapter]);
 const r=mount(true);
 await waitFor(()=>expect(screen.getByLabelText('ed')).toBeTruthy());
 const badges=[...r.container.querySelectorAll('main .nv-badge')].map(b=>b.textContent);
 expect(badges.includes('写作台')).toBe(shown);
 expect(badges.some(b=>/v2|版本\s*2|2/.test(b||'')&&b!=='写作台')).toBe(shown);
});
