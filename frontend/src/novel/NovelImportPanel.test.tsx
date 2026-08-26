// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from '../api';
import {NovelImportPanel} from './NovelImportPanel';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement;
afterEach(()=>{vi.restoreAllMocks();host?.remove()});

describe('NovelImportPanel',()=>{
  it('keeps preview order stable and prevents duplicate confirmation',async()=>{
    const preview={title:'测试小说',chapter_count:2,word_count:2,warnings:[],chapters:[{number:1,title:'同名章',word_count:1},{number:1,title:'同名章',word_count:1}]};
    const plan={format:'txt',title:'测试小说',chapters:[{number:1,title:'同名章',content:'甲'},{number:1,title:'同名章',content:'乙'}]};
    vi.spyOn(api,'importNovel').mockResolvedValue({preview,plan} as any);
    let resolveConfirm!:()=>void;const onConfirm=vi.fn(()=>new Promise<void>(resolve=>{resolveConfirm=resolve}));
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>root.render(<NovelImportPanel onConfirm={onConfirm}/>));
    const input=host.querySelector<HTMLInputElement>('input[type=file]')!;
    const file=new File(['第一章\n甲'],'book.txt',{type:'text/plain'});Object.defineProperty(file,'text',{value:async()=>"第一章\n甲"});
    await act(async()=>{Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new Event('change',{bubbles:true}));await Promise.resolve()});
    expect([...host.querySelectorAll('.novel-import-preview li span')].map(item=>item.textContent)).toEqual(['同名章','同名章']);
    const confirm=[...host.querySelectorAll('button')].find(item=>item.textContent?.includes('确认导入'))!;
    act(()=>{confirm.click();confirm.click()});
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await act(async()=>resolveConfirm());
    act(()=>root.unmount());
  });

  it('returns explicitly to file selection without retaining preview',async()=>{
    const preview={title:'测试小说',chapter_count:1,word_count:1,warnings:[],chapters:[{number:1,title:'第一章',word_count:1}]};
    const plan={format:'txt',title:'测试小说',chapters:[{number:1,title:'第一章',content:'甲'}]};
    vi.spyOn(api,'importNovel').mockResolvedValue({preview,plan} as any);
    host=document.createElement('div');document.body.append(host);const root=createRoot(host);
    await act(async()=>root.render(<NovelImportPanel/>));
    const input=host.querySelector<HTMLInputElement>('input[type=file]')!;
    const file=new File(['甲'],'book.txt');Object.defineProperty(file,'text',{value:async()=>"甲"});
    await act(async()=>{Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new Event('change',{bubbles:true}));await Promise.resolve()});
    act(()=>[...host.querySelectorAll('button')].find(item=>item.textContent?.includes('重新选择文件'))!.click());
    expect(host.textContent).toContain('尚未选择文件');expect(host.querySelector('.novel-import-preview')).toBeNull();
    act(()=>root.unmount());
  });
});
