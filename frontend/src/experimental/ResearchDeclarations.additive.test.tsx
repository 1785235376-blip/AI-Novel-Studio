// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ResearchLibraryPanel} from './ResearchLibraryPanel';
import {experimentalClient} from './api';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('preserves declarations in the original edit form and explicitly saves bounded author notes',async()=>{
 const source={id:'source',version:2,status:'ACTIVE',title:'Synthetic reference',author:'',source:'',source_version:'',usage_notes:'',license_statement:'Attribution required',verification_note:'Compared manually',access:'PRIVATE',format:'TXT',origin:'LOCAL_IMPORT',filename:'source.txt',accessed_at:'',extraction_status:'TEXT_EXTRACTED',paragraph_count:0,warnings:[],paragraphs:[]};
 const fetch=vi.fn(async(url:string,init:RequestInit)=>new Response(JSON.stringify(init.method==='PUT'?{...source,version:3}:url.endsWith('/sources/source')?source:url.endsWith('/sources')?{items:[source]}:{items:[]}),{status:200}));
 vi.stubGlobal('fetch',fetch);render(<ResearchLibraryPanel client={experimentalClient('novel',{sessionToken:'synthetic-session'})}/>);
 fireEvent.click(await screen.findByRole('button',{name:'打开来源 Synthetic reference'}));fireEvent.click(await screen.findByRole('button',{name:'编辑来源元数据'}));
 expect((screen.getByLabelText('许可与使用限制声明') as HTMLTextAreaElement).value).toBe('Attribution required');
 expect((screen.getByLabelText('人工核验说明') as HTMLTextAreaElement).value).toBe('Compared manually');
 fireEvent.change(screen.getByLabelText('许可与使用限制声明'),{target:{value:'https://example.invalid/license — synthetic declaration only'}});
 expect(fetch.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'保存资料元数据'}));await waitFor(()=>expect(fetch.mock.calls.filter(([,init])=>init.method==='PUT')).toHaveLength(1));
 const sent=JSON.parse(String(fetch.mock.calls.find(([,init])=>init.method==='PUT')![1].body));
 expect(sent).toMatchObject({license_statement:'https://example.invalid/license — synthetic declaration only',verification_note:'Compared manually',expected_version:2,access:'PRIVATE'});
 expect(fetch.mock.calls.every(([url])=>!url.startsWith('https://example.invalid'))).toBe(true);expect(screen.getByText(/不代表软件已验证授权/)).toBeTruthy();
});
