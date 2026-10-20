import type {StudioGraphRecord,StudioGraphRun} from '../creative/studioGraphTypes';
import {useLayoutEffect,useRef,useState} from 'react';
import {Button,StatusMessage} from '../ui/primitives';
import {briefFields,type BriefText} from './personalSkillBrief';
import {readReviewedGraphBrief,type BriefGraphReader,type ReviewedGraphBrief} from './reviewedGraphBrief';
type Props={reader:BriefGraphReader;active:boolean;disabled:boolean;current:BriefText;onApply:(value:ReviewedGraphBrief)=>void};
export function ReviewedGraphBriefImport(props:Props){
 const [run,setRun]=useState(''),[node,setNode]=useState(''),[preview,setPreview]=useState<ReviewedGraphBrief>(),[error,setError]=useState(''),[pending,setPending]=useState(false);
 const [graphId,setGraphId]=useState(''),[catalog,setCatalog]=useState<{owner:object;items:StudioGraphRecord[]}>(),[runs,setRuns]=useState<{owner:object;graphId:string;items:StudioGraphRun[]}>();
 const alive=useRef(true),busy=useRef(false),epoch=useRef(0),live=useRef(props),owner=useRef({reader:props.reader,active:props.active,disabled:props.disabled,base:props.current});live.current=props;
 if(owner.current.reader!==props.reader||owner.current.active!==props.active||owner.current.disabled!==props.disabled||owner.current.base!==props.current){epoch.current++;owner.current={reader:props.reader,active:props.active,disabled:props.disabled,base:props.current};}
 const [previewEpoch,setPreviewEpoch]=useState(-1);
 useLayoutEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;};},[]);
 const invalidate=()=>{epoch.current++;setPreview(undefined);setError('');};
 const current=(ticket:number)=>alive.current&&epoch.current===ticket&&live.current.active&&!live.current.disabled;
 const captured=epoch.current;
 async function read(adopt=false){if(epoch.current!==captured||!props.active||props.disabled||busy.current)return;const prior=adopt&&previewEpoch===epoch.current?preview:undefined;if(adopt&&!prior)return;const ticket=epoch.current;busy.current=true;setPending(true);setError('');
  try{const value=await readReviewedGraphBrief(props.reader,run,node);if(!current(ticket))return;
   if(adopt){if(JSON.stringify(value)!==JSON.stringify(prior)){setPreview(undefined);throw new Error('来源已变化，未替换正文。请重新读取并比较。');}setPreview(undefined);epoch.current++;props.onApply(value);}
   else{setPreview(value);setPreviewEpoch(ticket);}
  }catch(reason){if(current(ticket)){setPreview(undefined);setError(reason instanceof Error?reason.message:'原审核结果读取失败。');}}
  finally{busy.current=false;if(alive.current)setPending(false);}
 }
 async function listSources(loadRuns=false){
  if(epoch.current!==captured||!props.active||props.disabled||busy.current||!props.reader.list||!props.reader.runs)return;
  const selected=catalog?.owner===owner.current?catalog.items.find(g=>g.id===graphId):undefined;
  if(loadRuns&&!selected)return;invalidate();const ticket=epoch.current;busy.current=true;setPending(true);
  try{
   if(loadRuns){const fresh=await props.reader.get(graphId);if(!current(ticket))return;if(fresh.version!==selected!.version||fresh.definition_digest!==selected!.definition_digest)throw new Error('创作图已变化，请重新列出来源。');const result=await props.reader.runs(graphId);if(current(ticket))setRuns({owner:owner.current,graphId,items:result.items.filter(r=>r.graph_id===graphId&&r.graph_version===fresh.version&&!r.stale&&r.status==='SUCCEEDED'&&r.reviewed)});}
   else{setRuns(undefined);setGraphId('');const result=await props.reader.list();if(current(ticket))setCatalog({owner:owner.current,items:result.items.filter(g=>g.definition.schema_version===3&&g.definition.nodes.some(n=>n.enabled&&n.definition_id==='human_review'))});}
  }catch(reason){if(current(ticket)){if(loadRuns)setRuns(undefined);else setCatalog(undefined);setError(reason instanceof Error?reason.message:'来源列表读取失败。');}}
  finally{busy.current=false;if(alive.current)setPending(false);}
 }
 const choices=props.active&&!props.disabled&&catalog?.owner===owner.current?catalog.items:undefined;
 const runChoices=choices&&runs?.owner===owner.current&&runs.graphId===graphId?runs.items:undefined;
 const selectedGraph=choices?.find(g=>g.id===graphId),selectedRun=runChoices?.find(r=>r.id===run);
 const reviewChoices=selectedGraph?.definition.nodes.filter(n=>n.enabled&&n.definition_id==='human_review'&&selectedRun?.node_states[n.id]?.status==='SUCCEEDED'&&selectedRun.node_states[n.id].output?.reviewed_draft)||[];
 const visible=props.active&&!props.disabled&&previewEpoch===epoch.current?preview:undefined;
 return <details><summary>读取创作图已审核简报</summary><p>可列出本项目已完成的来源，或填写原运行与审核节点标识。直接读取原 owner 校验的 schema 3 结果。只采用四项文字，不执行模型、插件或安装。最终目录中的来源字段只是引用，不能授予权限或认证发布者。</p>
 {props.reader.list&&props.reader.runs&&<><Button disabled={pending||props.disabled||!props.active} onClick={()=>void listSources()}>列出本项目简报来源图</Button>{choices&&<><label>简报来源创作图<select disabled={pending} value={graphId} onChange={e=>{if(epoch.current!==captured||busy.current)return;invalidate();setGraphId(e.target.value);setRuns(undefined);setRun('');setNode('');}}><option value="">请选择创作图</option>{choices.map(g=><option key={g.id} value={g.id}>{g.definition.title} · v{g.version}</option>)}</select></label>{!choices.length&&<p>暂无可用的 schema 3 人工审核图；不会自动创建或升级。</p>}<Button disabled={pending||!graphId} onClick={()=>void listSources(true)}>列出该图已完成运行</Button></>}{runChoices&&<><label>已完成的简报运行<select disabled={pending} value={selectedRun?run:''} onChange={e=>{if(epoch.current!==captured||busy.current)return;invalidate();setRun(e.target.value);setNode('');}}><option value="">请选择运行</option>{runChoices.map(r=><option key={r.id} value={r.id}>{r.id} · v{r.version}</option>)}</select></label>{!runChoices.length&&<p>没有当前版本已完成并审核的运行；不会执行或批准任务。</p>}{selectedRun&&<label>已完成的文字审核节点<select disabled={pending} value={reviewChoices.some(n=>n.id===node)?node:''} onChange={e=>{if(epoch.current!==captured||busy.current)return;invalidate();setNode(e.target.value);}}><option value="">请选择审核节点</option>{reviewChoices.map(n=><option key={n.id} value={n.id}>{n.id}</option>)}</select></label>}</>}</>}
 <label>简报来源运行 ID<input value={run} maxLength={240} disabled={pending||props.disabled||!props.active} onChange={e=>{invalidate();setRun(e.target.value);}}/></label>
 <label>简报来源审核节点 ID<input value={node} maxLength={128} disabled={pending||props.disabled||!props.active} onChange={e=>{invalidate();setNode(e.target.value);}}/></label>
 <Button disabled={pending||props.disabled||!props.active||!run||!node} onClick={()=>void read()}>读取并比较原审核简报</Button>
 {visible&&<section aria-label="原审核简报差异"><p>运行 {visible.source.run_id} · 版本 {visible.source.run_version} · 原文 SHA-256 {visible.source.text_sha256}</p>{briefFields.map(([key,label])=><div key={key}><h4>{label}</h4><p>当前内容</p><pre>{props.current[key]}</pre><p>已审核来源</p><pre>{visible.text[key]}</pre></div>)}<Button disabled={pending} onClick={()=>void read(true)}>重新核对来源并替换四项正文</Button></section>}
 {pending&&<StatusMessage>正在核对原图与审核结果…</StatusMessage>}{error&&<StatusMessage tone="warning">{error}</StatusMessage>}
 </details>;
}
