/** Synthetic UI-only original-component check. No API, CPU processor, Job, or execution. */
import {createRoot} from 'react-dom/client';
import {AppShell} from '../../ui/AppShell';
import {SavedCanvasVideoDraftPanel} from './SavedCanvasVideoDraftPanel';
import {savedDraftFixture} from './savedDraft.testFixtures';
import '../../ui/ui.css';import '../../ui/fixture.css';import '../../ui/desktop-craft.css';import '../creative.css';
export function mount(){
 const calls={list:0,resume:0};const row=savedDraftFixture();const owner={fixture:'saved-input-only'};
 (window as any).__savedVideoDraft={calls};
 const host=document.createElement('div');document.body.replaceChildren(host);
 createRoot(host).render(<AppShell module="VIDEO" onModuleChange={()=>{}} actor="本地组件检查" scope={{workspace:'创作工作区',project:'已保存视频输入',storyline:'主线',branch:'合成组件检查'}}
 sidebar={<p>本次任务的输入与来源。这里只验证选择与确认，不创建或执行任务。</p>}
 main={<div style={{height:'100%',overflow:'auto',minWidth:0}}><SavedCanvasVideoDraftPanel owner={owner} current canMutate busy={false} isCurrent={()=>true}
 onList={async()=>{calls.list++;return [row];}} onResume={async value=>{if(value!==row)throw new Error('Wrong original input');calls.resume++;}}/></div>}
 inspector={<p>恢复后由原入口重新读取权限、FAILED 状态、来源 pin、画布版本，再明确预览确认。此组件无执行能力。</p>} status="输入草稿组件合成检查 · 无任务派发"/>);
}
