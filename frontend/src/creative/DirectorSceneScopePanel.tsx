import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { directorSceneScopeBody } from './directorSceneScope';
import type { CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
type Props={source:CreativeDocument;snapshot:PlanningSnapshot;available:boolean;busy:boolean;isCurrent:()=>boolean;
  request:(source:CreativeDocument,snapshot:PlanningSnapshot,responsibility:string,scenes:string[])=>Promise<CreativeDocument>;
  mutate:<T>(work:()=>Promise<T>)=>Promise<T>;onPending:(value:boolean)=>void;onOpen:(id:string)=>void};
export function DirectorSceneScopePanel(props:Props){
  return <ScopeSession key={JSON.stringify([props.source.id,props.source.version,props.snapshot])} {...props}/>;
}
function ScopeSession(props:Props){
  const [responsibility,setResponsibility]=useState(''),[selected,setSelected]=useState<string[]>([]),[confirmed,setConfirmed]=useState(false);
  const [working,setWorking]=useState(false),[uncertain,setUncertain]=useState(false),[resetConsent,setResetConsent]=useState(false),[error,setError]=useState(''),[created,setCreated]=useState<CreativeDocument>();
  const alive=useRef(true),lock=useRef(false),live=useRef(props);live.current=props;
  const consumedForm=useRef<object>(),consentLive=useRef(confirmed);consentLive.current=confirmed;
  const authority=[props.request,props.source,props.snapshot.id,props.snapshot.version,props.snapshot.digest,props.available],fence=useRef({authority,token:{}});
  if(authority.some((value,index)=>!Object.is(value,fence.current.authority[index])))fence.current={authority,token:{}};
  const formKey=JSON.stringify([responsibility,selected]),form=useRef({key:formKey,token:{}});
  if(form.current.key!==formKey)form.current={key:formKey,token:{}};
  const formToken=form.current.token;
  const token=fence.current.token,current=()=>alive.current&&fence.current.token===token&&live.current.isCurrent();
  const pending=working||uncertain||!!responsibility||selected.length>0;
  useEffect(()=>props.onPending(pending),[pending,props.onPending]);
  useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;props.onPending(false);};},[]);
  const editable=props.available&&!props.busy&&!working&&!uncertain;
  async function create(){
    if(!current()||form.current.token!==formToken||consumedForm.current===formToken||!editable||!live.current.available||live.current.busy||lock.current||!confirmed||!consentLive.current)return;
    const label=responsibility.trim(),ids=[...selected];
    try{directorSceneScopeBody(props.source,props.snapshot,label,ids);}catch{setError('请明确填写职责并选择场景。');return;}
    consumedForm.current=formToken;consentLive.current=false;lock.current=true;setWorking(true);setUncertain(true);setConfirmed(false);setError('');setCreated(undefined);props.onPending(true);
    try{const result=await props.mutate(()=>props.request(props.source,props.snapshot,label,ids));
      if(!current()||form.current.token!==formToken)return;setCreated(result);setUncertain(false);setResponsibility('');setSelected([]);
    }catch{if(current())setError('创建结果未确认，请先读取原导演目录核对，不能自动重复创建。');}
    finally{lock.current=false;if(alive.current)setWorking(false);}
  }
  return <section aria-label="按场景建立子导演"><h4>按场景建立子导演草稿</h4><p>复制所选场景及其已有导演备注，保留原版本来源。职责名称只标识作者分工，不扩大权限；不会复制审核许可、运行模型或改写原导演。</p>
    <label>子导演职责<input value={responsibility} maxLength={120} disabled={!editable} onChange={e=>{if(!current()||!editable)return;setResponsibility(e.target.value);setConfirmed(false);props.onPending(true);}}/></label>
    <fieldset disabled={!editable}><legend>负责场景</legend>{props.source.scenes.map(scene=><label key={scene.id}><input type="checkbox" checked={selected.includes(scene.id)} onChange={e=>{if(!current()||!editable)return;setSelected(previous=>e.target.checked?[...previous,scene.id]:previous.filter(id=>id!==scene.id));setConfirmed(false);props.onPending(true);}}/>{scene.sequence} · {scene.heading}</label>)}</fieldset>
    <p>将按原顺序复制 {selected.length} 个场景，创建独立 DRAFT 文档；后续编辑仍受原来源变更检查。</p>
    <label><input type="checkbox" checked={confirmed} disabled={!editable||!responsibility.trim()||!selected.length} onChange={e=>{if(current()&&form.current.token===formToken&&editable){consentLive.current=e.target.checked;setConfirmed(e.target.checked);}}}/>已核对职责与场景，同意创建一个新子导演草稿</label>
    <Button disabled={!editable||!confirmed} onClick={()=>void create()}>创建所选场景子导演</Button>
    {!working&&pending&&<><label><input type="checkbox" checked={resetConsent} onChange={e=>setResetConsent(e.target.checked)}/>{uncertain?'已核对原目录，仅清除本地创建意图，不自动重试':'放弃本次子导演输入'}</label><Button disabled={!resetConsent} onClick={()=>{if(!current()||lock.current||!resetConsent)return;setResponsibility('');setSelected([]);setConfirmed(false);setUncertain(false);setResetConsent(false);setError('');}}>清除子导演创建意图</Button></>}
    {created&&<div><p>已创建 {created.title} · {created.id} · v{created.version}。原图绑定保持不变。</p><Button disabled={props.busy||pending} onClick={()=>{if(current()&&!pending)props.onOpen(created.id);}}>读取新子导演原文档</Button></div>}
    {working&&<StatusMessage>正在保存独立子导演草稿…</StatusMessage>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
