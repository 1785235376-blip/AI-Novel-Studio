// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {api} from '../api';
import {SourcePrivacyControl} from './SourcePrivacyControl';
vi.mock('../api',()=>({api:{sourcePrivacy:vi.fn(),reviewSourcePrivacy:vi.fn()},apiErrorView:(e:any)=>({message:e.message})}));
const chapter={id:'n:1',novel_id:'n',number:1,title:'Synthetic',content:'text',document:{},version:1,word_count:4,status:'DRAFT'};
const context={sessionToken:'synthetic-session',scope:{workspaceId:'w',projectId:'n',storylineId:'s',branchId:'b'}};
const status={novel_id:'n',chapter_id:'n:1',chapter_version:1,content_sha256:'a'.repeat(64),privacy_level:'LOCAL_ONLY',reviewed:false,stale:false};
afterEach(cleanup);beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.sourcePrivacy).mockResolvedValue(status)});
it('requires explicit review bound to the server revision and captured authority',async()=>{
 vi.mocked(api.reviewSourcePrivacy).mockResolvedValue({...status,privacy_level:'CLOUD_ALLOWED',reviewed:true});
 render(<SourcePrivacyControl chapter={chapter} context={context}/>);
 await waitFor(()=>expect(api.sourcePrivacy).toHaveBeenCalledWith('n','n:1',context));
 fireEvent.click(screen.getByText(/^正文隐私：/));
 await waitFor(()=>expect((screen.getByLabelText('当前章节正文与选区') as HTMLSelectElement).disabled).toBe(false));
 fireEvent.change(screen.getByLabelText('当前章节正文与选区'),{target:{value:'CLOUD_ALLOWED'}});
 fireEvent.click(screen.getByRole('button',{name:'保存正文隐私策略'}));
 await waitFor(()=>expect(api.reviewSourcePrivacy).toHaveBeenCalledWith('n','n:1',{privacy_level:'CLOUD_ALLOWED',expected_version:1,content_sha256:'a'.repeat(64)},context));
 await screen.findByText('正文隐私：当前版本允许云端');
});
it('late approval response cannot replace a newer chapter policy',async()=>{
 let finish!:Function;vi.mocked(api.reviewSourcePrivacy).mockImplementation(()=>new Promise(resolve=>{finish=resolve}));
 const view=render(<SourcePrivacyControl chapter={chapter} context={context}/>);
 await waitFor(()=>expect(api.sourcePrivacy).toHaveBeenCalled());
 fireEvent.click(screen.getByText(/^正文隐私：/));
 await waitFor(()=>expect((screen.getByLabelText('当前章节正文与选区') as HTMLSelectElement).disabled).toBe(false));
 fireEvent.change(screen.getByLabelText('当前章节正文与选区'),{target:{value:'CLOUD_ALLOWED'}});
 fireEvent.click(screen.getByRole('button',{name:'保存正文隐私策略'}));
 vi.mocked(api.sourcePrivacy).mockResolvedValue({...status,chapter_version:2,stale:true});
 view.rerender(<SourcePrivacyControl chapter={{...chapter,version:2}} context={context}/>);
 await screen.findByText('正文已改变，旧授权已失效。');
 finish({...status,privacy_level:'CLOUD_ALLOWED',reviewed:true});
 await new Promise(resolve=>setTimeout(resolve,0));
 expect(screen.queryByText('正文隐私：当前版本允许云端')).toBeNull();
});
