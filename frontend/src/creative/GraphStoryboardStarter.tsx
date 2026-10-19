import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { MAX_STORYBOARD_VIDEO_BRANCHES } from './graphStoryboardStarter';
import { apiErrorView } from '../api';
import type { PlanningDocument } from './studioProductionGraphContract';
import type { StoryboardReceipt } from './studioStoryboardContract';
type Props={scope:object;disabled:boolean;loading:boolean;documents:PlanningDocument[];
 onLoad:()=>Promise<void>;onRead:(id:string,scope:object)=>Promise<StoryboardReceipt|undefined>;
 onApply:(receipt:StoryboardReceipt,shotId:string|string[],scope:object)=>boolean};
export function GraphStoryboardStarter(props:Props){
 const [choice,setChoice]=useState(''),[shot,setShot]=useState<string[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [proof,setProof]=useState<{owner:object;scope:object;selection:number;receipt:StoryboardReceipt}>();
 const proofRef=useRef(proof);proofRef.current=proof;const shotEpoch=useRef(0),shotInput=useRef<HTMLSelectElement>(null);const capturedShotEpoch=shotEpoch.current;
 const alive=useRef(true),pending=useRef(false),selection=useRef(0),consumed=useRef<object>();
 const live=useRef(props);live.current=props;
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;selection.current++;};},[]);
 const values=[props.scope,props.documents,props.disabled,props.loading];const owner=useRef({values,token:{}});if(values.some((value,index)=>value!==owner.current.values[index]))owner.current={values,token:{}};const token=owner.current.token;
 const current=()=>alive.current&&!live.current.disabled&&!live.current.loading&&owner.current.token===token;
 const visible=proof&&proof.owner===token&&proof.scope===props.scope&&proof.selection===selection.current&&!props.disabled?proof.receipt:undefined;
 async function read(){if(!current()||pending.current||!choice)return;const ticket=selection.current;pending.current=true;setBusy(true);setError('');proofRef.current=undefined;setProof(undefined);shotEpoch.current++;setShot([]);
  try{const receipt=await props.onRead(choice,props.scope);if(current()&&ticket===selection.current&&receipt){const next={owner:token,scope:props.scope,selection:ticket,receipt};proofRef.current=next;setProof(next);}}
  catch(reason){if(current()&&ticket===selection.current)setError(apiErrorView(reason,'分镜读取或审核状态不符合要求。').message);}
  finally{pending.current=false;if(alive.current)setBusy(false);}
 }
 return <section aria-label="分镜到视频起步方案"><h3>从已审核分镜搭好视频链</h3><p>读取原分镜和镜头版本，明确选择 1–4 个原镜头，共用分镜来源，分别组装“镜头 → 视频候选 → 人工审核”。不复制原文档、不生成视频；服务商和模型仍需明确配置。</p>
  <Button disabled={props.disabled||props.loading||busy} onClick={()=>{if(!current())return;selection.current++;proofRef.current=undefined;setProof(undefined);setShot([]);setChoice('');void props.onLoad();}}>读取起步分镜目录</Button>
  <label>起步来源分镜<select value={choice} disabled={props.disabled||props.loading||busy} onChange={event=>{if(!current())return;selection.current++;proofRef.current=undefined;setProof(undefined);setShot([]);setError('');setChoice(event.target.value);}}><option value="">选择已保存的原分镜</option>{props.documents.filter(row=>row.mode==='STORYBOARD').map(row=><option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></label>
  <Button disabled={props.disabled||props.loading||busy||!choice} onClick={()=>void read()}>核对起步分镜镜头与审核</Button>
  {busy&&<StatusMessage>正在读取原分镜…</StatusMessage>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
  {visible&&<section aria-label="起步分镜精确来源"><p>{visible.document_snapshot.id} · v{visible.document_snapshot.version} · {visible.document_snapshot.digest} · 当前分镜已审核</p>
   <label>起步分镜镜头<select multiple size={5} ref={shotInput} value={shot} disabled={props.disabled||busy} onChange={event=>{if(current()){shotEpoch.current++;setShot(Array.from(event.target.selectedOptions,option=>option.value));}}}>{[...visible.shots].sort((a,b)=>a.shot.number-b.shot.number).map(row=><option key={row.shot_id} value={row.shot_id}>SHOT {row.shot.number} · {row.shot_id} · v{row.shot_version}</option>)}</select></label>
   <p>按住 Ctrl / Command 可多选，最多 {MAX_STORYBOARD_VIDEO_BRANCHES} 个；不自动截断。已选 {shot.length} 个分支。</p>
   {shot.length>MAX_STORYBOARD_VIDEO_BRANCHES&&<StatusMessage tone="warning">超过 4 个镜头，请减少选择后再应用。</StatusMessage>}
   {!!shot.length&&<section aria-label="分镜视频链应用预览"><p>{1+3*shot.length} 个节点 · {3*shot.length} 条连线 · {shot.length} 个视频生成器 · LOCAL_ONLY</p>
    <ul>{[...visible.shots].filter(row=>shot.includes(row.shot_id)).sort((a,b)=>a.shot.number-b.shot.number).map(row=><li key={row.shot_id}>SHOT {row.shot.number} · {row.shot_id} · v{row.shot_version} · {row.shot_digest}</li>)}</ul>
    <p>每个分支仍需配置服务商和模型；本次仅应用到本地空图，可一次撤销或重做。</p></section>}
   <p>原镜头 ID、版本和摘要会保留。配置模型后才能保存；保存及执行会重新核对来源、人工审核和预算。</p>
   <Button disabled={props.disabled||busy||!shot.length||shot.length>MAX_STORYBOARD_VIDEO_BRANCHES} onClick={()=>{if(!current()||pending.current||!proof||proofRef.current!==proof||shotEpoch.current!==capturedShotEpoch||JSON.stringify(Array.from(shotInput.current?.selectedOptions??[],option=>option.value))!==JSON.stringify(shot)||consumed.current===proof||proof.selection!==selection.current||!shot.length||shot.length>MAX_STORYBOARD_VIDEO_BRANCHES||shot.some(id=>!visible.shots.some(row=>row.shot_id===id)))return;consumed.current=proof;selection.current++;proofRef.current=undefined;setProof(undefined);if(!props.onApply(visible,shot.length===1?shot[0]:shot,props.scope))setError('当前图、来源或权限已变化，未应用；请重新核对。');}}>应用分镜视频链到本地空图</Button>
  </section>}
 </section>;
}
