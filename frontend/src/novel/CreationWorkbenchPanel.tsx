import {useEffect,useRef,useState} from 'react';
import {api,apiErrorView,type Chapter,type CreationRecord,type ReviewThread,type CollaborationContext} from '../api';
import {useStudio} from '../store';
import {Badge,Button,EmptyState,Panel,StatusMessage} from '../ui/primitives';
import './creationWorkbench.css';

const kinds:Record<string,string>={STYLE:'风格档案',PLOT:'三幕与结局',HISTORY:'历史事件',GEOGRAPHY:'地理关系',CIVILIZATION:'文明与组织',ABILITY:'能力规则',PSYCHOLOGY:'人物心理记录'};
const blank=(kind='STYLE')=>({kind,title:'',description:'',instructions:'',acts:['','',''],conflict:'',climax:'',ending:'',rules:[] as string[],privacy_level:'LOCAL_ONLY',chapter_ids:[] as string[],character_ids:[] as string[],location_ids:[] as string[],related_record_ids:[] as string[],story_route_id:null as string|null});
type Draft=ReturnType<typeof blank>;
const editable=(row:CreationRecord):Draft=>Object.fromEntries(Object.keys(blank()).map(k=>[k,(row as any)[k]])) as Draft;

export function CreationWorkbenchPanel({novelId,chapter,initialComments=false,context}:{novelId:string;chapter?:Chapter;initialComments?:boolean;context?:CollaborationContext}){
 const [comments,setComments]=useState(initialComments),[records,setRecords]=useState<CreationRecord[]>([]),[threads,setThreads]=useState<ReviewThread[]>([]),[draft,setDraft]=useState<Draft>(blank),[editing,setEditing]=useState<CreationRecord>(),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[message,setMessage]=useState(''),[text,setText]=useState(''),[quote,setQuote]=useState(''),[reply,setReply]=useState<Record<string,string>>({}),[compare,setCompare]=useState<string[]>([]);
 const [references,setReferences]=useState<{characters:{id:string;name:string}[];locations:{id:string;name:string}[];story_routes:{id:string;name:string}[]}>({characters:[],locations:[],story_routes:[]});
 const mounted=useRef(true),generation=useRef(0),flight=useRef(false);
 const selected=useStudio(s=>s.writingInputs),setSelected=useStudio(s=>s.setWritingInputs);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++}},[]);
 useEffect(()=>{setComments(initialComments)},[initialComments]);
 async function reload(){const ticket=++generation.current;setLoading(true);try{const [a,b,c]=await Promise.all([api.creationRecords(novelId,undefined,context),api.reviewThreads(novelId,context),api.creationReferenceData(novelId,context)]);if(mounted.current&&ticket===generation.current){setRecords(a.items);setThreads(b.items);setReferences(c)}}catch(reason){if(mounted.current&&ticket===generation.current)setError(apiErrorView(reason).message)}finally{if(mounted.current&&ticket===generation.current)setLoading(false)}}
 useEffect(()=>{if(novelId)void reload();else setLoading(false)},[novelId]);
 async function run(action:()=>Promise<unknown>,success:string){if(flight.current)return;flight.current=true;setBusy(true);setError('');setMessage('');try{await action();if(mounted.current){setMessage(success);await reload()}}catch(reason){if(mounted.current)setError(apiErrorView(reason).message)}finally{flight.current=false;if(mounted.current)setBusy(false)}}
 const change=(key:keyof Draft,value:unknown)=>setDraft(current=>({...current,[key]:value}));
 const reset=(kind=draft.kind)=>{setEditing(undefined);setDraft(blank(kind))};
 const selectedRecords=records.filter(r=>compare.includes(r.id));
 const visible=records.filter(r=>r.kind===draft.kind);
 return <Panel title={comments?'评论与审核':'创作方案与风格'} className="creation-workbench">
 <div className="novel-tabs" role="tablist" aria-label="创作工作台"><button role="tab" aria-selected={!comments} onClick={()=>setComments(false)}>方案与风格</button><button role="tab" aria-selected={comments} onClick={()=>setComments(true)}>评论与审核</button></div>
 {!novelId?<EmptyState title="先打开小说项目" detail="从工作区选择小说后可创建方案。"/>:<>
 {error&&<StatusMessage tone="error">{error}。输入仍保留，可刷新后重试。</StatusMessage>}{message&&<p role="status">{message}</p>}
 <Button disabled={busy||loading} onClick={()=>void reload()}>刷新记录</Button>
 {loading?<p role="status">正在读取持久化记录…</p>:comments?<>
 <p className="novel-help">评论绑定章节版本；正文更新后会标记锚点过期。评论、解决和重新打开均保留操作者记录。</p>
 <form onSubmit={e=>{e.preventDefault();if(!chapter)return;void run(async()=>{await api.createReviewThread(novelId,{chapter_id:chapter.id,chapter_version:chapter.version,quote,text},context);if(mounted.current){setText('');setQuote('')}},'评论已保存')}}>
 <p>{chapter?`${chapter.title} · 版本 ${chapter.version}`:'请选择章节后发表评论。'}</p>
 <label>引用原文（可选）<textarea value={quote} maxLength={2000} onChange={e=>setQuote(e.target.value)}/></label>
 <label>评论内容<textarea required value={text} maxLength={8000} onChange={e=>setText(e.target.value)}/></label>
 <Button type="submit" disabled={busy||!chapter||!text.trim()}>保存评论</Button>
 </form>
 {!threads.length?<EmptyState title="还没有评论" detail="提交第一条带版本锚点的审核意见。"/>:threads.map(thread=><article key={thread.id} className="creation-workbench__record">
 <header><strong>章节 {thread.anchor.chapter_id} · 版本 {thread.anchor.chapter_version}</strong><Badge tone={thread.anchor_state==='CURRENT'?'neutral':'warning'}>{thread.anchor_state==='CURRENT'?'当前版本':thread.anchor_state==='MISSING'?'来源已不存在':'来源已更新，请重新核对'}</Badge><Badge tone={thread.status==='RESOLVED'?'success':'info'}>{thread.status==='RESOLVED'?'已解决':'待处理'}</Badge></header>
 {thread.anchor.quote&&<p>{thread.anchor.quote}</p>}{thread.messages.map(item=><div key={item.id}><small>{item.actor_id} · {item.at}</small><p>{item.text}</p></div>)}
 {thread.status==='OPEN'&&<><label>回复<textarea value={reply[thread.id]||''} maxLength={8000} onChange={e=>setReply({...reply,[thread.id]:e.target.value})}/></label><Button disabled={busy||!reply[thread.id]?.trim()} onClick={()=>void run(async()=>{await api.reviewThreadAction(novelId,thread.id,'reply',thread.version,reply[thread.id],context);if(mounted.current)setReply(current=>({...current,[thread.id]:''}))},'回复已保存')}>提交回复</Button></>}
 <Button disabled={busy} onClick={()=>void run(()=>api.reviewThreadAction(novelId,thread.id,thread.status==='OPEN'?'resolve':'reopen',thread.version,'',context),'审核状态已保存')}>{thread.status==='OPEN'?'标记已解决':'重新打开'}</Button>
 <details><summary>审核记录（{thread.history.length}）</summary>{thread.history.map((event,i)=><p key={i}>{event.action} · {event.actor_id} · {event.at}</p>)}</details>
 </article>)}
 </>:<>
 <p className="novel-help">手工方案保存为草稿，审核后可复用。风格与三幕方案可加入 AI 写作输入；AI 输出仍需预览、Diff 和明确采用。其他世界结构保留独立版本与关联记录。</p>
 {(selected?.styleProfileId||selected?.plotPlanId)&&<p role="status">已选写作输入：{records.filter(r=>r.id===selected.styleProfileId||r.id===selected.plotPlanId).map(r=>r.title).join('、')} <Button onClick={()=>setSelected({})}>清除选择</Button></p>}
 <label>记录类型<select value={draft.kind} disabled={!!editing||busy} onChange={e=>reset(e.target.value)}>{Object.entries(kinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
 <form onSubmit={e=>{e.preventDefault();const body={...draft,acts:draft.kind==='PLOT'?draft.acts:[]};void run(async()=>{await api.saveCreationRecord(novelId,body,editing?.id,editing?.version,context);if(mounted.current)reset()},'草稿已保存，等待审核')}}>
 <label>名称<input required value={draft.title} maxLength={200} onChange={e=>change('title',e.target.value)}/></label>
 <label>说明<textarea required={!['STYLE','PLOT'].includes(draft.kind)} maxLength={12000} value={draft.description} onChange={e=>change('description',e.target.value)}/></label>
 {draft.kind==='STYLE'&&<label>可复用风格指令（最多 120 字）<textarea required maxLength={120} value={draft.instructions} onChange={e=>change('instructions',e.target.value)}/></label>}
 {draft.kind==='PLOT'&&<>{['第一幕：设局','第二幕：对抗','第三幕：解决'].map((label,i)=><label key={label}>{label}<textarea required maxLength={4000} value={draft.acts[i]||''} onChange={e=>change('acts',draft.acts.map((v,j)=>i===j?e.target.value:v))}/></label>)}{([['conflict','核心冲突'],['climax','高潮'],['ending','结局方案']] as const).map(([key,label])=><label key={key}>{label}<textarea required maxLength={4000} value={draft[key]} onChange={e=>change(key,e.target.value)}/></label>)}</>}
 {!['STYLE','PLOT'].includes(draft.kind)&&<label>规则与约束（每行一条）<textarea value={draft.rules.join('\n')} onChange={e=>change('rules',e.target.value.split('\n').filter(Boolean))}/></label>}
 <label>隐私策略<select value={draft.privacy_level} onChange={e=>change('privacy_level',e.target.value)}><option value="LOCAL_ONLY">仅本地（默认）</option><option value="REDACT_BEFORE_CLOUD">云端脱敏（写作引用暂限本地）</option><option value="CLOUD_ALLOWED">允许所选模型接收</option></select></label>
 {(['characters','locations'] as const).map(group=><label key={group}>{group==='characters'?'关联人物':'关联地点'}<select multiple value={group==='characters'?draft.character_ids:draft.location_ids} onChange={e=>change(group==='characters'?'character_ids':'location_ids',[...e.target.selectedOptions].map(o=>o.value))}>{references[group].map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>)}
 {draft.kind==='PLOT'&&<label>关联故事路线<select value={draft.story_route_id||''} onChange={e=>change('story_route_id',e.target.value||null)}><option value="">尚未关联</option>{references.story_routes.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
 <label>关联或比较的已有方案<select multiple value={draft.related_record_ids} onChange={e=>change('related_record_ids',[...e.target.selectedOptions].map(o=>o.value))}>{records.filter(r=>r.id!==editing?.id).map(item=><option key={item.id} value={item.id}>{item.title} · v{item.version}</option>)}</select></label>
 {chapter&&<label><input type="checkbox" checked={draft.chapter_ids.includes(chapter.id)} onChange={e=>change('chapter_ids',e.target.checked?[...new Set([...draft.chapter_ids,chapter.id])]:draft.chapter_ids.filter(id=>id!==chapter.id))}/>关联当前章节及版本：{chapter.title}</label>}
 <Button type="submit" variant="primary" disabled={busy}>{busy?'正在保存…':editing?'保存新版本':'保存草稿'}</Button>{editing&&<Button disabled={busy} onClick={()=>reset()}>取消编辑</Button>}
 </form>
 {!visible.length?<EmptyState title="此类型还没有记录" detail="填写上面的表单，保存第一份草稿。"/>:visible.map(row=><article className="creation-workbench__record" key={row.id}>
 <header><strong>{row.title}</strong><Badge tone={row.status==='APPROVED'?'success':'neutral'}>{row.status==='APPROVED'?'已审核':row.status==='ARCHIVED'?'已归档':'草稿'} · v{row.version}</Badge></header>
 <p>{row.instructions||row.description||row.ending}</p><small>{row.privacy_level} · 来源章节 {Object.entries(row.source_versions).map(([id,v])=>`${id} v${v}`).join('、')||'无'} · {row.actor_id}</small>
 <div className="novel-actions"><Button disabled={busy} onClick={()=>{setEditing(row);setDraft(editable(row))}}>编辑</Button>{row.status==='DRAFT'&&<Button disabled={busy} onClick={()=>void run(()=>api.creationRecordAction(novelId,row.id,'approve',row.version,undefined,context),'方案已审核')}>审核通过</Button>}{row.status==='APPROVED'&&['STYLE','PLOT'].includes(row.kind)&&<Button onClick={()=>{setSelected({...selected,[row.kind==='STYLE'?'styleProfileId':'plotPlanId']:row.id});setMessage('已加入写作输入。选择模型生成后，仍需审阅 AI 草稿。')}}>用于写作</Button>}{row.status!=='ARCHIVED'&&<Button disabled={busy} onClick={()=>void run(()=>api.creationRecordAction(novelId,row.id,'archive',row.version,undefined,context),'记录已归档，历史仍保留')}>归档</Button>}</div>
 <label><input type="checkbox" checked={compare.includes(row.id)} disabled={!compare.includes(row.id)&&compare.length>=2} onChange={e=>setCompare(current=>e.target.checked?[...current,row.id]:current.filter(id=>id!==row.id))}/>加入比较（最多两项）</label>
 <details><summary>版本历史（{row.history.length}）</summary>{row.history.map(old=><div key={old.version}><p>v{old.version} · {old.title} · {old.instructions||old.ending||old.description}</p><Button disabled={busy} onClick={()=>void run(()=>api.creationRecordAction(novelId,row.id,'restore',row.version,old.version,context),'历史已恢复为新草稿版本，需重新审核')}>恢复 v{old.version} 为新草稿</Button></div>)}</details>
 </article>)}
 {selectedRecords.length>0&&<section aria-label="方案比较" className="creation-workbench__compare">{selectedRecords.map(row=><article key={row.id}><h3>{row.title} · v{row.version}</h3><p>{row.instructions||row.description}</p>{row.acts.map((act,i)=><p key={i}>第 {i+1} 幕：{act}</p>)}{row.conflict&&<p>冲突：{row.conflict}</p>}{row.climax&&<p>高潮：{row.climax}</p>}{row.ending&&<p>结局：{row.ending}</p>}</article>)}</section>}
 </>}
 </>}
 </Panel>
}
