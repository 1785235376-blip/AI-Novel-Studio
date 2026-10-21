/** Pure callback fixture; no backend, processor, provider or execution is invoked. */
import {createRoot} from 'react-dom/client';
import {useCallback,useState} from 'react';
import {AppShell} from '../../ui/AppShell';
import {Button} from '../../ui/primitives';
import {SavedCanvasAudioDraftPanel} from './SavedCanvasAudioDraftPanel';
import {audioDraftSummary} from './summary.testFixtures';
import '../../ui/ui.css';import '../../ui/fixture.css';import '../../ui/desktop-craft.css';import '../creative.css';
const owner={project:'audio-fixture',scope:'local',client:{identity:'same-client'}},current=()=>true;
export function mount(){
 const calls={list:0,resume:0},restored:unknown[]=[];(window as any).__audioDraftPanel={calls,restored};
 function Fixture(){
  const[input,setInput]=useState('A');
  const list=useCallback(async()=>{calls.list++;return[audioDraftSummary()];},[]);
  const resume=useCallback(async(summary:unknown)=>{calls.resume++;if(!Object.isFrozen(summary))throw new Error('snapshot not frozen');restored.push(summary);},[]);
  return <AppShell module="AUDIO" onModuleChange={()=>{}} actor="本地组件核对" scope={{workspace:'本地工作区',project:'音频草稿恢复',storyline:'主线',branch:'合成组件'}}
   sidebar={<p>已保存输入与当前会话输入明确区分。此夹具无存储、队列或处理器。</p>}
   main={<div style={{height:'100%',overflow:'auto',minWidth:0}}><Button onClick={()=>setInput(k=>k==='A'?'B':'A')}>修改当前会话输入</Button><SavedCanvasAudioDraftPanel owner={owner} current canMutate busy={false} sessionInputKey={input} isCurrent={current} onList={list} onResume={resume}/></div>}
   inspector={<p>原入口仍须重新读取版本、来源与权限，重新预览并逐阶段确认。</p>} status="仅合成摘要组件核对，无模型或CPU处理"/>;
 }
 const host=document.createElement('div');document.body.replaceChildren(host);createRoot(host).render(<Fixture/>);
}
