// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ScriptScreenplayBridge,scriptScenePreview} from './ScriptScreenplayBridge';
import {newDocument,type CreativeDocument} from './types';
afterEach(cleanup);
const source=():CreativeDocument=>({...newDocument('SCRIPT'),id:'script',version:1,status:'DRAFT',title:'Script',script:{purpose:'PODCAST',body:'甲'.repeat(31999)+'🙂'+'尾'},actor_id:'actor',created_at:'',updated_at:'',source_evidence:{}});
it('previews Unicode code-point chunks without inventing scene analysis or changing text',()=>{const row=source(),before=structuredClone(row),parts=scriptScenePreview(row);expect(parts.map(p=>p.characters)).toEqual([16000,16000,1]);expect(parts[2].snippet).toBe('尾');expect(row).toEqual(before);expect(()=>scriptScenePreview({...row,script:{purpose:'PODCAST',body:'a'.repeat(64001)}})).toThrow();});
function retained<T>(element:HTMLElement,name:string):T{const key=Object.keys(element).find(k=>k.startsWith('__reactProps$'))!;return (element as any)[key][name];}
it.each(['uncheck','source','availability ABA','unmount','current'])('retires staging consent across %s',mode=>{let current=true;const props={source:source(),available:true,isCurrent:()=>current,onCreate:vi.fn()};const view=render(<ScriptScreenplayBridge {...props}/>);fireEvent.click(screen.getByLabelText('确认从此已保存版本建立独立的新剧本底稿'));const action=retained<()=>void>(screen.getByText('确认建立剧本底稿'),'onClick');
 if(mode==='uncheck'){const uncheck=retained<(e:any)=>void>(screen.getByLabelText('确认从此已保存版本建立独立的新剧本底稿'),'onChange');act(()=>{uncheck({target:{checked:false}});action();});}
 else{if(mode==='source')view.rerender(<ScriptScreenplayBridge {...props} source={{...props.source,version:2}}/>);else if(mode==='availability ABA'){view.rerender(<ScriptScreenplayBridge {...props} available={false}/>);view.rerender(<ScriptScreenplayBridge {...props}/>);}else if(mode==='unmount')view.unmount();else current=false;act(action);}expect(props.onCreate).not.toHaveBeenCalled();
});
it('consumes a confirmed choice once even before a parent rerender',()=>{const onCreate=vi.fn();render(<ScriptScreenplayBridge source={source()} available isCurrent={()=>true} onCreate={onCreate}/>);fireEvent.click(screen.getByLabelText('确认从此已保存版本建立独立的新剧本底稿'));const action=retained<()=>void>(screen.getByText('确认建立剧本底稿'),'onClick');act(()=>{action();action();});expect(onCreate).toHaveBeenCalledTimes(1);});
