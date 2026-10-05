import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,planningApi,type Chapter,type CollaborationContext,type CreationRecord,type PlanningRun,type TextModel} from '../api';
import {Badge,Button,EmptyState,StatusMessage} from '../ui/primitives';

const kinds:Record<string,string>={STYLE:'风格建议',PLOT:'三幕与结局建议',HISTORY:'历史建议',GEOGRAPHY:'地理建议',CIVILIZATION:'文明建议',ABILITY:'世界与能力规则',PSYCHOLOGY:'人物心理建议'};
const active=(row:PlanningRun)=>['QUEUED','WORKING'].includes(row.status);
const labels:Record<string,string>={QUEUED:'排队中',WORKING:'处理中',READY:'待审核',FAILED:'失败',CANCELLED:'已取消'};

export function AIPlanningPanel({novelId,chapter,context,onSaved}:{novelId:string;chapter?:Chapter;context?:CollaborationContext;onSaved:(record:CreationRecord)=>void}){
 const [runs,setRuns]=useState<PlanningRun[]>([]),[selected,setSelected]=useState(''),[models,setModels]=useState<TextModel[]>([]),[model,setModel]=useState(''),[mode,setMode]=useState<'MODEL'|'LOCAL_EXPLICIT'>('LOCAL_EXPLICIT'),[kind,setKind]=useState('ABILITY'),[count,setCount]=useState(2),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[message,setMessage]=useState('');
 const epoch=useRef(0),flight=useRef(false);
 const scopeKey=JSON.stringify([novelId,context?.sessionToken,context?.scope]);
 const current=runs.find(row=>row.id===selected)||runs[0],hasActive=runs.some(active);
 useEffect(()=>{const ticket=++epoch.current;setRuns([]);setSelected('');setError('');setLoading(true);flight.current=false;setBusy(false);
  async function read(){try{const result=await planningApi.list(novelId,context);if(ticket!==epoch.current)return;setRuns(result.items);setLoading(false)}catch(reason){if(ticket===epoch.current){setError(apiErrorView(reason).message);setLoading(false)}}}
  void read();void api.textModels().then(rows=>{if(ticket===epoch.current)setModels(rows)}).catch(()=>{if(ticket===epoch.current)setModels([])});
  return()=>{epoch.current++};
 },[scopeKey]);
 async function refresh(){const ticket=epoch.current;try{const result=await planningApi.list(novelId,context);if(ticket===epoch.current){setRuns(result.items);setError('')}}catch(reason){if(ticket===epoch.current)setError(apiErrorView(reason).message)}}
 useEffect(()=>{if(!hasActive)return;const ticket=epoch.current;const timer=setInterval(()=>{if(ticket===epoch.current)void refresh()},2000);return()=>clearInterval(timer)},[hasActive,scopeKey]);
 async function perform(action:()=>Promise<unknown>){if(flight.current)return;flight.current=true;const ticket=epoch.current;setBusy(true);setError('');setMessage('');try{await action()}catch(reason){if(ticket===epoch.current)setError(apiErrorView(reason).message)}finally{if(ticket===epoch.current){flight.current=false;setBusy(false)}}}
 const selectedModel=models.find(row=>JSON.stringify([row.provider_id,row.model_id])===model);
 const update=(row:PlanningRun)=>setRuns(values=>[row,...values.filter(value=>value.id!==row.id)]);
 return <section aria-label="结构化规划候选" className="creation-workbench__planning">
 <p className="novel-help">按当前已保存章节版本生成可比较的结构化候选。保存候选只会建立本地草稿，之后仍须在方案列表编辑和审核；不会自动改正文或 Canon。</p>
 {error&&<StatusMessage tone="error">{error}。输入保留，可刷新状态后重试。</StatusMessage>}{message&&<p role="status">{message}</p>}
 <form onSubmit={event=>{event.preventDefault();if(!chapter)return;const ticket=epoch.current;void perform(async()=>{const row=await planningApi.create(novelId,{kind,mode,sources:[{chapter_id:chapter.id,expected_version:chapter.version}],candidate_count:count,...(mode==='MODEL'&&selectedModel?{provider_id:selectedModel.provider_id,model_id:selectedModel.model_id}:{})},context);if(ticket===epoch.current){update(row);setSelected(row.id);setMessage('任务已保存，可关闭后重新打开查看。')}})}}>
 <p>{chapter?`${chapter.title} · 已保存版本 ${chapter.version}`:'先选择已保存的章节。'}</p>
 <label>规划方式<select value={mode} disabled={busy||hasActive} onChange={event=>{const next=event.target.value as 'MODEL'|'LOCAL_EXPLICIT';setMode(next);if(next==='LOCAL_EXPLICIT'&&!['ABILITY','PLOT'].includes(kind))setKind('ABILITY')}}><option value="LOCAL_EXPLICIT">本地明确标记提取（不调用模型）</option><option value="MODEL">使用所选模型生成建议</option></select></label>
 <label>候选类型<select value={kind} disabled={busy||hasActive} onChange={event=>setKind(event.target.value)}>{Object.entries(kinds).filter(([value])=>mode==='MODEL'||['ABILITY','PLOT'].includes(value)).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
 {mode==='MODEL'?<><label>规划文本模型<select value={model} disabled={busy||hasActive} onChange={event=>setModel(event.target.value)}><option value="">选择已配置的 Provider / 模型</option>{models.map(row=><option key={`${row.provider_id}:${row.model_id}`} value={JSON.stringify([row.provider_id,row.model_id])} disabled={!row.available}>{row.display_name} · {row.provider_id}{row.available?'':'（不可用）'}</option>)}</select></label><label>比较候选数<select value={count} onChange={event=>setCount(Number(event.target.value))}>{[1,2,3].map(value=><option key={value} value={value}>{value}</option>)}</select></label><p className="novel-help">每章最多读取前 16000 字。云端模型需先在正文隐私中审核此版本；选择模型不会改变资料隐私。模型建议可能有误。</p></>:<p className="novel-help">识别独立行“世界规则：…”或“能力规则：…”。剧情要求第一幕、第二幕、第三幕、冲突、高潮、结局六项明确标记；支持对应英文，不会补造缺失内容。</p>}
 <Button type="submit" variant="primary" disabled={busy||loading||hasActive||!chapter||(mode==='MODEL'&&!selectedModel?.available)}>{busy?'正在提交…':mode==='MODEL'?'生成待审建议':'提取明确标记'}</Button>
 </form>
 <div className="novel-actions"><Button disabled={busy} onClick={()=>void refresh()}>刷新规划任务</Button>{current&&active(current)&&<Button disabled={busy} onClick={()=>{const ticket=epoch.current;void perform(async()=>{const result=await planningApi.cancel(novelId,current.id,current.version,context);if(ticket===epoch.current)update(result)})}}>取消规划任务</Button>}</div>
 {loading?<p role="status">正在读取规划历史…</p>:!runs.length?<EmptyState title="暂无规划任务" detail="本地提取与模型建议都会保留来源和处理状态。"/>:<>
 <label>重新打开规划任务<select value={current?.id||''} onChange={event=>setSelected(event.target.value)}>{runs.map(row=><option key={row.id} value={row.id}>{kinds[row.request.kind]} · {labels[row.status]||row.status} · {row.created_at}</option>)}</select></label>
 {current&&<><p role="status"><Badge tone={current.status==='FAILED'?'error':current.status==='READY'?'info':'neutral'}>{labels[current.status]||current.status}</Badge> · {current.execution_mode==='mock_standin'?'模拟测试输出，未调用真实模型':current.execution_mode==='local_explicit'?'明确标记提取，未调用模型':current.execution_mode==='real'?'模型建议，需人工审核':'尚无完成的模型结果'} · 用量 {current.usage_status}</p>
 {current.error&&<StatusMessage tone="error">{current.error}（{current.error_code}）</StatusMessage>}
 <Button disabled={busy||hasActive} onClick={()=>{setKind(current.request.kind);setMode(current.request.mode);setCount(current.request.candidate_count);setModel(current.request.provider_id?JSON.stringify([current.request.provider_id,current.request.model_id]):'');setMessage('配置已载入。明确提交后才会按当前章节新版本生成。')}}>复用配置</Button>
 <details><summary>来源版本与摘要</summary>{current.sources.map(source=><p key={source.chapter_id}>{source.chapter_id} · v{source.chapter_version} · SHA-256 {source.content_sha256}{source.truncated&&current.request.mode==='MODEL'?' · 仅使用前 16000 字':''}</p>)}</details>
 {current.status==='READY'&&!current.candidates.length&&<EmptyState title="未发现完整明确结构" detail="请补充标记或手工创建方案。系统没有生成替代内容。"/>}
 {current.findings.map((finding,index)=><article className="creation-workbench__record" key={index}><strong>{finding.code==='PLOT_MARKERS_INCOMPLETE'?'剧情结构不完整':'剧情标记有多义项'}</strong><p>缺少：{finding.missing_fields.join('、')||'无'}；重复：{finding.duplicate_fields.join('、')||'无'}</p>{Object.entries(finding.fields).map(([key,value])=><p key={key}>{key}：{value}</p>)}</article>)}
 <div className="creation-workbench__compare">{current.candidates.map(candidate=><article key={candidate.id}><h3>{String(candidate.record.title||'候选')}</h3><p>{String(candidate.record.instructions||candidate.record.description||'')}</p>{Array.isArray(candidate.record.acts)&&candidate.record.acts.map((act,index)=><p key={index}>第 {index+1} 幕：{String(act)}</p>)}{['conflict','climax','ending'].map(field=>candidate.record[field]?<p key={field}>{field}：{String(candidate.record[field])}</p>:null)}<details><summary>核对原文证据（{candidate.evidence.length}）</summary>{candidate.evidence.map((evidence,index)=><p key={index}>{evidence.chapter_id} · v{evidence.chapter_version} · 字符 {evidence.start}–{evidence.end}：{evidence.quote}</p>)}</details><Button disabled={busy||!!candidate.record_id||current.status!=='READY'} onClick={()=>{const ticket=epoch.current;void perform(async()=>{const result=await planningApi.save(novelId,current.id,candidate.id,current.version,context);if(ticket===epoch.current){update(result.run);onSaved(result.record);setMessage('候选已保存为草稿。选择对应记录类型后可编辑、比较和审核。')}})}}>{candidate.record_id?'已保存为草稿':'保存此候选为草稿'}</Button></article>)}</div>
 </>}
 </>}
 </section>
}
