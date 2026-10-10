import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, apiErrorView, getCollaborationContext, CollaborationContext, Scope } from "../api";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";
import { AssetTaskExecutionPanel } from "./AssetTaskExecutionPanel";
import { PipelineStatusPanel } from "./PipelineStatusPanel";
import { ScreenplayPipelinePanel } from "./ScreenplayPipelinePanel";
import { FOCUS_FAILED_TASKS_EVENT } from "../ui/taskSummary";
import type { VideoInspection } from "./VideoTaskInspector";
import { MotionTaskWorkspace } from "./MotionTaskWorkspace";
import "./screenplay.css";
export function motionTaskInspection(task:any,screenplayId?:string):VideoInspection{return{id:String(task.id),status:task.status,screenplayId,transitionId:task.transition_id,providerId:task.provider_id,modelId:task.model_id,progress:task.progress,startFrame:task.start_frame,endFrame:task.end_frame,resultUrl:task.result?.url,assetId:task.result?.asset_id,error:task.error};}
type ScreenplayPanelProps={novelId?:string;onInspect?:(inspection:VideoInspection)=>void;scope?:Scope|null;sessionToken?:string};
export function ScreenplayPanel(props:ScreenplayPanelProps){
  const context=getCollaborationContext();
  const scope=props.scope===undefined?context.scope:props.scope;
  const identity=JSON.stringify([props.novelId,scope?.workspaceId,scope?.projectId,scope?.storylineId,scope?.branchId,props.sessionToken??context.sessionToken]);
  return <ScopedScreenplayPanel key={identity} {...props} requestContext={{sessionToken:props.sessionToken??context.sessionToken,scope:scope??undefined,actor:context.actor}}/>;
}
function ScopedScreenplayPanel({ novelId, onInspect,requestContext }: ScreenplayPanelProps&{requestContext:CollaborationContext}) {
  const qc = useQueryClient();
  const [observerId]=useState(()=>globalThis.crypto?.randomUUID?.()||Math.random().toString(36));
  const [title, setTitle] = useState("");
  const q = useQuery({
    queryKey: ["screenplays", novelId, observerId],
    queryFn: () => api.screenplays(novelId!,requestContext),
    enabled: !!novelId,
  });
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: ["screenplays", novelId] });
  useEffect(() => { const handle = (event: Event) => { const detail = (event as CustomEvent).detail; if (!novelId || detail?.novelId === novelId) refresh(); }; window.addEventListener('motion-tasks-created', handle); return () => window.removeEventListener('motion-tasks-created', handle); }, [novelId]);
  const create = useMutation({
    mutationFn: () => api.createScreenplay(novelId!, title),
    onSuccess: () => {
      setTitle("");
      refresh();
    },
  });
  const onConflict=(error:unknown)=>{if(error instanceof ApiError&&error.status===409)refresh()};
  const approve = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.approveScreenplay(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const revise = useMutation({mutationFn:(target:{id:string;version:number;sourceVersion?:number})=>api.reviseScreenplay(novelId!,target.id,target.version,target.sourceVersion),onSuccess:refresh,onError:onConflict});
  const plan = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.planScreenplayShots(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const approveShots = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.approveScreenplayShots(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const update = useMutation({
    mutationFn: (v: any) =>
      api.updateScreenplayScene(novelId!, v.screenplayId, v.sceneId, v.body),
    onSuccess: refresh,onError:onConflict,
  });
  const updateShot = useMutation({
    mutationFn: (v: any) =>
      api.updateScreenplayShot(novelId!, v.screenplayId, v.shotId, v.body),
    onSuccess: refresh,onError:onConflict,
  });
  const board = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.planStoryboard(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const boardApprove = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.approveStoryboard(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const boardUpdate = useMutation({
    mutationFn: (v: any) =>
      api.updateStoryboardCard(novelId!, v.sid, v.cid, v.body),
    onSuccess: refresh,onError:onConflict,
  });
  const transitionPlan = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.planTransitions(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const transitionApprove = useMutation({
    mutationFn: (target: {id:string;version:number}) => api.approveTransitions(novelId!, target.id,target.version),
    onSuccess: refresh,onError:onConflict,
  });
  const transitionUpdate = useMutation({
    mutationFn: (v: any) =>
      api.updateTransition(novelId!, v.sid, v.tid, v.body),
    onSuccess: refresh,onError:onConflict,
  });
  const motionTasks = useMutation({mutationFn:(id:string)=>api.createMotionTasks(novelId!,id),onSuccess:refresh});
  const mutationError=[create,approve,revise,plan,approveShots,update,updateShot,board,boardApprove,boardUpdate,transitionPlan,transitionApprove,transitionUpdate,motionTasks].find(mutation=>mutation.error)?.error;
  const busy=[create,approve,revise,plan,approveShots,update,updateShot,board,boardApprove,boardUpdate,transitionPlan,transitionApprove,transitionUpdate,motionTasks].some(mutation=>mutation.isPending);
  if (!novelId)
    return (
      <Panel title="影视剧本">
        <EmptyState title="尚未打开小说" detail="打开小说后建立影视剧本。" />
      </Panel>
    );
  return (
    <Panel title="影视剧本">
      <label>
        剧本名称
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <Button
        variant="primary"
        disabled={!title.trim()||create.isPending||q.isError}
        onClick={() => create.mutate()}
      >
        创建剧本
      </Button>
      {q.isPending&&<p className="novel-help" role="status">正在读取剧本…</p>}
      {q.error&&<p className="novel-error" role="alert">{apiErrorView(q.error,'无法读取剧本').message} <Button onClick={()=>void q.refetch()} disabled={q.isFetching}>重新读取剧本</Button></p>}
      {!!mutationError&&<p className="novel-error" role="alert">{mutationError instanceof ApiError&&mutationError.status===409?'剧本已有新版本。本地编辑已保留，请对照最新内容后再保存。':apiErrorView(mutationError,'操作失败，请重试').message}</p>}
      {!q.isPending&&!q.isError&&!q.data?.length&&<EmptyState title="暂无剧本" detail="创建剧本后逐场编辑并审批，小说正文保持独立。"/>}
      <fieldset disabled={busy} className="screenplay-controls"><ul>
        {!q.isError&&q.data?.map((s: any) => (
          <li key={s.id}>
            <strong>{s.title}</strong> <Badge>{s.status}</Badge>
            <p>{s.scenes.length} 个场景 · 剧本版本 {s.revision||1} · 编辑版本 {s.edit_version??0}</p>
            {s.derived_from&&<p className="novel-help">修订自剧本 {s.derived_from.screenplay_id} · 版本 {s.derived_from.revision}</p>}
            {s.status==='APPROVED'&&<><p className="novel-help">批准版本及其资产已保留。创建修订草稿后，镜头和资产需重新审核。</p><Button onClick={()=>revise.mutate({id:s.id,version:s.edit_version??0})}>创建修订草稿</Button></>}
            <ScreenplayHistory novelId={novelId} screenplay={s} requestContext={requestContext} onFork={sourceVersion=>revise.mutate({id:s.id,version:s.edit_version??0,sourceVersion})}/>
            <ScreenplayPipelinePanel novelId={novelId} screenplayId={s.id}/>
            {s.scenes.map((x: any) => (
              <Scene
                key={x.id}
                scene={{...x,expected_version:s.edit_version??0}}
                disabled={s.status !== "DRAFT"}
                onSave={(b) =>
                  update.mutate({ screenplayId: s.id, sceneId: x.id, body: b })
                }
              />
            ))}
            {s.status === "DRAFT" ? (
              <Button onClick={() => approve.mutate({id:s.id,version:s.edit_version??0})}>
                批准剧本并进入镜头规划
              </Button>
            ) : (
              <Shots
                s={s}
                plan={() => plan.mutate({id:s.id,version:s.edit_version??0})}
                approve={() => approveShots.mutate({id:s.id,version:s.edit_version??0})}
                save={(id, b) =>
                  updateShot.mutate({ screenplayId: s.id, shotId: id, body: b })
                }
              />
            )}{" "}
            {s.shot_status === "APPROVED" && (
              <>
                <Storyboard
                  s={s}
                  plan={() => board.mutate({id:s.id,version:s.edit_version??0})}
                  approve={() => boardApprove.mutate({id:s.id,version:s.edit_version??0})}
                  save={(id, b) =>
                    boardUpdate.mutate({ sid: s.id, cid: id, body: b })
                  }
                />
                <Transitions
                  novelId={novelId}
                  screenplayId={s.id}
                  s={s}
                  plan={() => transitionPlan.mutate({id:s.id,version:s.edit_version??0})}
                  approve={() => transitionApprove.mutate({id:s.id,version:s.edit_version??0})}
                  createMotionTasks={() => motionTasks.mutate(s.id)}
                  onInspect={onInspect}
                  save={(id, b) =>
                    transitionUpdate.mutate({ sid: s.id, tid: id, body: b })
                  }
                />
              </>
            )}
          </li>
        ))}
      </ul></fieldset>
    </Panel>
  );
}
function useVersionedDraft(value:any,keys:string[]):[any,(value:any)=>void]{
  const [draft,setDraft]=useState(value);
  useEffect(()=>{
    if(draft.expected_version!==value.expected_version&&keys.every(key=>JSON.stringify(draft[key])===JSON.stringify(value[key])))setDraft((current:any)=>({...current,expected_version:value.expected_version}));
  },[value,draft]);
  return [draft,setDraft];
}
function DraftVersionReview({draft,latest,onChange}:{draft:any;latest:any;onChange:(value:any)=>void}){
  if(draft.expected_version===latest.expected_version)return null;
  return <section className="novel-draft-review" role="alert"><p>服务器已有编辑版本 {latest.expected_version}，本地内容仍基于版本 {draft.expected_version}，尚未覆盖。</p><details><summary>查看最新内容</summary><pre>{JSON.stringify(latest,null,2)}</pre></details><Button variant="ghost" onClick={()=>onChange({...latest})}>载入最新内容（替换本地编辑）</Button><Button variant="secondary" onClick={()=>onChange({...draft,expected_version:latest.expected_version})}>保留本地内容，按最新版本继续编辑</Button></section>;
}
function ScreenplayHistory({novelId,screenplay,requestContext,onFork}:{novelId:string;screenplay:any;requestContext:CollaborationContext;onFork:(version:number)=>void}){
  const [open,setOpen]=useState(false);
  const [observerId]=useState(()=>globalThis.crypto?.randomUUID?.()||Math.random().toString(36));
  const history=useQuery({queryKey:['screenplay-revisions',screenplay.id,observerId,screenplay.edit_version],queryFn:()=>api.screenplayRevisions(novelId,screenplay.id,requestContext),enabled:open});
  return <details onToggle={event=>setOpen(event.currentTarget.open)}><summary>剧本版本历史</summary>{history.isPending&&open&&<p>正在读取版本…</p>}{history.error&&<p className="novel-error" role="alert">{apiErrorView(history.error,'无法读取版本历史').message}</p>}{!history.isError&&history.data?.items.slice().reverse().map(row=><article key={row.edit_version??0}><p>编辑版本 {row.edit_version??0} · {row.status} · {row.updated_at}</p><details><summary>查看场景与镜头快照</summary><pre>{JSON.stringify({scenes:row.scenes,shots:row.shots},null,2)}</pre></details>{screenplay.status==='APPROVED'&&<Button variant="ghost" onClick={()=>onFork(row.edit_version??0)}>从编辑版本 {row.edit_version??0} 创建修订草稿</Button>}</article>)}</details>;
}
function DialogueFields({rows,onChange,disabled}:{rows:any[];onChange:(rows:any[])=>void;disabled:boolean}){
  return <section aria-label="对白"><h4>对白</h4>{rows.map((row,index)=><div key={index}><label>角色<input disabled={disabled} value={row.character||''} onChange={event=>onChange(rows.map((value,i)=>i===index?{...value,character:event.target.value}:value))}/></label><label>对白内容<textarea disabled={disabled} value={row.text||''} onChange={event=>onChange(rows.map((value,i)=>i===index?{...value,text:event.target.value}:value))}/></label>{!disabled&&<Button variant="ghost" onClick={()=>onChange(rows.filter((_,i)=>i!==index))}>移除对白 {index+1}</Button>}</div>)}{!disabled&&<Button variant="ghost" onClick={()=>onChange([...rows,{character:'',text:''}])}>添加对白</Button>}</section>;
}
function Scene({scene,disabled,onSave}:{scene:any;disabled:boolean;onSave:(body:any)=>void}){
  const [d,setD]=useVersionedDraft(scene,['heading','time','location','characters','emotion','action','dialogue']);
  return <details><summary>{scene.sequence}. {scene.heading}</summary>
    <DraftVersionReview draft={d} latest={scene} onChange={setD}/>
    <p className="novel-help">来源章节 {scene.source_chapter_id} · 版本 {scene.source_version}</p>
    {[['heading','场景标题'],['time','时间'],['location','地点'],['emotion','情绪']].map(([key,label])=><label key={key}>{label}<input disabled={disabled} value={d[key]||''} onChange={event=>setD({...d,[key]:event.target.value})}/></label>)}
    <label>出场人物（逗号分隔）<input disabled={disabled} value={(d.characters||[]).join(', ')} onChange={event=>setD({...d,characters:event.target.value.split(/[,，]/).map(name=>name.trim()).filter(Boolean)})}/></label>
    <label>场景动作<textarea disabled={disabled} value={d.action||''} onChange={event=>setD({...d,action:event.target.value})}/></label>
    <DialogueFields rows={d.dialogue||[]} disabled={disabled} onChange={dialogue=>setD({...d,dialogue})}/>
    {!disabled&&<Button onClick={()=>onSave(d)}>保存场景</Button>}
  </details>;
}
function Shots({
  s,
  plan,
  approve,
  save,
}: {
  s: any;
  plan: () => void;
  approve: () => void;
  save: (id: string, b: any) => void;
}) {
  const shots = s.shots || [];
  const locked=s.shot_status==='APPROVED';
  return (
    <section>
      <h3>镜头规划</h3>
      {!shots.length ? (
        <Button onClick={plan}>生成初始镜头</Button>
      ) : (
        <>
          {shots.map((x: any) => (
            <Shot key={x.id} shot={{...x,expected_version:s.edit_version??0}} disabled={locked} save={(b) => save(x.id, b)} />
          ))}
          {locked?<p className="novel-help">镜头计划已批准并冻结。</p>:<Button onClick={approve}>批准镜头计划并冻结</Button>}
        </>
      )}
    </section>
  );
}
function Shot({shot,save,disabled}:{shot:any;save:(body:any)=>void;disabled:boolean}){
  const [d,setD]=useVersionedDraft(shot,['shot_size','camera_angle','camera_motion','subject_position','sound_effect','duration_seconds','action','dialogue']);
  return <details><summary>镜头 {shot.number} <Badge>{disabled?'APPROVED':shot.status}</Badge></summary><DraftVersionReview draft={d} latest={shot} onChange={setD}/>
    {[['shot_size','景别'],['camera_angle','机位角度'],['camera_motion','摄影机运动'],['subject_position','主体构图'],['sound_effect','音效']].map(([key,label])=><label key={key}>{label}<input disabled={disabled} value={d[key]||''} onChange={event=>setD({...d,[key]:event.target.value})}/></label>)}
    <label>时长（秒）<input type="number" min={1} max={600} disabled={disabled} value={d.duration_seconds||1} onChange={event=>setD({...d,duration_seconds:Number(event.target.value)})}/></label>
    <label>镜头动作<textarea disabled={disabled} value={d.action||''} onChange={event=>setD({...d,action:event.target.value})}/></label>
    <DialogueFields rows={d.dialogue||[]} disabled={disabled} onChange={dialogue=>setD({...d,dialogue})}/>
    {!disabled&&<Button onClick={()=>save(d)}>保存镜头</Button>}
  </details>;
}
function Storyboard({
  s,
  plan,
  approve,
  save,
}: {
  s: any;
  plan: () => void;
  approve: () => void;
  save: (id: string, b: any) => void;
}) {
  const cards = s.storyboard || [];
  const locked = s.storyboard_status === "APPROVED";
  return (
    <section className="novel-draft-review">
      <h3>Storyboard 分镜板</h3>
      {!cards.length ? (
        <Button onClick={plan}>生成分镜板</Button>
      ) : (
        <>
          <div className="novel-record-list">
            {cards.map((c: any) => (
              <StoryboardCard
                key={c.id}
                card={{...c,expected_version:s.edit_version??0}}
                disabled={locked}
                save={(b) => save(c.id, b)}
              />
            ))}
          </div>
          {locked ? (
            <p className="novel-help">分镜板已批准并冻结。</p>
          ) : (
            <Button onClick={approve}>批准分镜板并冻结</Button>
          )}
          <AssetRequirementsPanel novelId={s.novel_id} screenplayId={s.id} />
        </>
      )}
    </section>
  );
}
function StoryboardCard({
  card,
  disabled,
  save,
}: {
  card: any;
  disabled: boolean;
  save: (b: any) => void;
}) {
  const [d,setD]=useVersionedDraft(card,['frame_prompt','composition','color']);
  return (
    <article>
      <DraftVersionReview draft={d} latest={card} onChange={setD}/>
      <header>
        <strong>分镜 {card.number}</strong>
        <Badge>{card.status}</Badge>
      </header>
      <label>
        画面提示
        <textarea
          disabled={disabled}
          value={d.frame_prompt || ""}
          onChange={(e) => setD({ ...d, frame_prompt: e.target.value })}
        />
      </label>
      <label>
        构图
        <input
          disabled={disabled}
          value={d.composition || ""}
          onChange={(e) => setD({ ...d, composition: e.target.value })}
        />
      </label>
      <label>
        色彩
        <input
          disabled={disabled}
          value={d.color || ""}
          onChange={(e) => setD({ ...d, color: e.target.value })}
        />
      </label>
      {!disabled && (
        <Button
          onClick={() =>
            save({
              expected_version:d.expected_version,
              frame_prompt: d.frame_prompt,
              composition: d.composition,
              color: d.color,
            })
          }
        >
          保存分镜
        </Button>
      )}
    </article>
  );
}
export function bindMotionTaskToDirector(novelId: string, screenplayId: string, taskId: string) {
  localStorage.setItem(`multimodal-selected-motion:${novelId}`, JSON.stringify({ screenplay_id: screenplayId, motion_task_id: taskId }));
  window.dispatchEvent(new CustomEvent('multimodal-motion-binding', { detail: { novelId, screenplay_id: screenplayId, motion_task_id: taskId } }));
}

function MotionTaskDirectorBinding({ novelId, screenplayId, taskId }: { novelId?: string; screenplayId?: string; taskId: string }) {
  const [bound, setBound] = useState(false);
  return <Button variant="ghost" disabled={!novelId || !screenplayId} onClick={() => { if (novelId && screenplayId) { bindMotionTaskToDirector(novelId, screenplayId, taskId); setBound(true); } }}>{bound ? '已绑定导演台' : '绑定到导演台'}</Button>;
}

function Transitions({
  novelId,
  screenplayId,
  s,
  plan,
  approve,
  createMotionTasks,
  save,
  onInspect,
}: {
  novelId?: string;
  screenplayId?: string;
  s: any;
  plan: () => void;
  approve: () => void;
  createMotionTasks: () => void;
  save: (id: string, b: any) => void;
  onInspect?: (inspection: VideoInspection) => void;
}) {
  const rows = s.transitions || [];
  const locked = s.transition_status === "APPROVED";
  const [continuity,setContinuity]=useState<any>();
  const handledKey=`visual-continuity-handled:${novelId}:${screenplayId}`;
  const [handled,setHandled]=useState<Record<string,boolean>>(()=>{try{return JSON.parse(localStorage.getItem(handledKey)||'{}')}catch{return{}}});
  const inspectTask=(task:any)=>onInspect?.(motionTaskInspection(task,screenplayId));
  useEffect(()=>{const listener=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail?.source!=="motion")return;const task=s.motion_tasks?.find((item:any)=>String(item.id)===String(detail.taskId));if(task)inspectTask(task);else if(detail.taskId)onInspect?.({id:String(detail.taskId),status:"FAILED",screenplayId,pendingRefresh:true});};window.addEventListener(FOCUS_FAILED_TASKS_EVENT,listener);return()=>window.removeEventListener(FOCUS_FAILED_TASKS_EVENT,listener);},[s.motion_tasks,screenplayId,onInspect]);
  function toggleHandled(id:string){setHandled(current=>{const next={...current,[id]:!current[id]};localStorage.setItem(handledKey,JSON.stringify(next));return next;});}
  async function checkContinuity(){if(!novelId||!screenplayId)return;setContinuity(await api.visualContinuity(novelId,screenplayId));}
  return (
    <section className="novel-draft-review">
      {novelId && screenplayId && <MotionTaskWorkspace novelId={novelId} screenplayId={screenplayId} onInspect={onInspect} />}
      <h3>转场设计</h3>
      <Button variant="ghost" onClick={checkContinuity}>检查视觉连续性</Button>
      <Button variant="ghost" onClick={createMotionTasks}>创建视频任务</Button>
      {continuity && <div className="novel-help"><strong>发现 {continuity.findings.filter((finding:any) => !handled[`${finding.code}-${finding.from_shot_id}-${finding.to_shot_id}`]).length} 项未处理提示</strong>{continuity.findings.map((finding:any) => { const id=`${finding.code}-${finding.from_shot_id}-${finding.to_shot_id}`; return <p key={id} className="notice">[{finding.severity}] {finding.code} · {finding.message}<br/><small>镜头 {finding.from_shot_id} → {finding.to_shot_id}</small> <Button variant="ghost" onClick={() => toggleHandled(id)}>{handled[id] ? '恢复' : '忽略'}</Button>{handled[id] && <small> 已忽略</small>}</p>; })}</div>}
      {s.transitions === undefined ? (
        <Button onClick={plan}>生成转场清单</Button>
      ) : (
        <>
          {rows.map((x: any) => (
            <Transition
              novelId={novelId}
              screenplayId={screenplayId}
              key={x.id}
              row={{...x,expected_version:s.edit_version??0}}
              disabled={locked}
              save={(b) => save(x.id, b)}
            />
          ))}
          {locked ? (
            <p className="novel-help">转场计划已批准并冻结。</p>
          ) : (
            <Button onClick={approve}>批准转场计划并冻结</Button>
          )}
        </>
      )}
    </section>
  );
}
function Transition({
  novelId,
  screenplayId,
  row,
  disabled,
  save,
}: {
  novelId?: string;
  screenplayId?: string;
  row: any;
  disabled: boolean;
  save: (b: any) => void;
}) {
  const [d,setD]=useVersionedDraft(row,['type','duration_seconds','note','prompt']);
  const [prompt, setPrompt] = useState(row.prompt || "");
  const [promptMeta, setPromptMeta] = useState<{template_version:string;generated_at:string}>();
  const [transitionPromptError, setTransitionPromptError] = useState("");
  const [suggestionError, setSuggestionError] = useState("");
  const [motionPromptError, setMotionPromptError] = useState("");
  const [suggestion, setSuggestion] = useState<{suggested_type:string;reason:string}>();
  const [suggestionApplied,setSuggestionApplied]=useState(false);
  const [motionPrompt,setMotionPrompt]=useState(() => String(row.motion_prompt || ""));
  const [motionOperation,setMotionOperation]=useState<"generate"|"save"|null>(null);
  const motionOperationRef=useRef<"generate"|"save"|null>(null);
  const motionRequestRef=useRef(0);
  const qc=useQueryClient();
  useEffect(() => {
    setMotionPrompt(String(row.motion_prompt || ""));
    setMotionPromptError("");
    motionRequestRef.current+=1;
    motionOperationRef.current=null;
    setMotionOperation(null);
  }, [row.id, row.motion_prompt]);
  async function generatePrompt() {
    if (!novelId) return;
    try { setTransitionPromptError(""); const result = await api.transitionPrompt(novelId, screenplayId || "", row.id); setPrompt(result.prompt); setD((current:any)=>({...current,prompt:result.prompt})); setPromptMeta({template_version:result.template_version,generated_at:result.generated_at}); }
    catch { setTransitionPromptError("Prompt 生成失败，请确认剧本已保存。"); }
  }
  async function suggest() {
    if (!novelId || !screenplayId) return;
    try { setSuggestionError(""); setSuggestion(await api.transitionSuggestion(novelId, screenplayId, row.id)); }
    catch { setSuggestionError("转场建议生成失败。"); }
  }
  async function generateMotion() {
    if (disabled || motionOperationRef.current) return;
    if (!novelId || !screenplayId || !String(row.id || "").trim()) {
      setMotionPromptError("Motion Prompt 生成失败。");
      return;
    }
    const request=++motionRequestRef.current;
    motionOperationRef.current="generate"; setMotionOperation("generate"); setMotionPromptError("");
    try {
      const result=await api.motionPrompt(novelId,screenplayId,row.id);
      if (request !== motionRequestRef.current) return;
      if (typeof result?.motion_prompt !== "string" || !result.motion_prompt.trim()) {
        setMotionPromptError("Motion Prompt 生成失败：返回内容为空。");
        return;
      }
      setMotionPrompt(result.motion_prompt);
      setMotionPromptError("");
    } catch {
      if (request === motionRequestRef.current) setMotionPromptError("Motion Prompt 生成失败。");
    } finally {
      if (request === motionRequestRef.current) { motionOperationRef.current=null; setMotionOperation(null); }
    }
  }
  async function saveMotion() {
    if (disabled || motionOperationRef.current) return;
    if (!novelId || !screenplayId || !String(row.id || "").trim() || !motionPrompt.trim()) {
      setMotionPromptError("Motion Prompt 保存失败。");
      return;
    }
    const request=++motionRequestRef.current;
    motionOperationRef.current="save"; setMotionOperation("save"); setMotionPromptError("");
    try {
      await api.saveMotionPrompt(novelId,screenplayId,row.id,motionPrompt);
      if (request === motionRequestRef.current) setMotionPromptError("");
    } catch {
      if (request === motionRequestRef.current) setMotionPromptError("Motion Prompt 保存失败。");
      return;
    } finally {
      if (request === motionRequestRef.current) { motionOperationRef.current=null; setMotionOperation(null); }
    }
    void qc.invalidateQueries({queryKey:["screenplays",novelId]}).catch(() => undefined);
  }
  return (
    <article>
      <DraftVersionReview draft={{...d,prompt}} latest={row} onChange={value=>{setD(value);setPrompt(value.prompt||'')}}/>
      <header>
        <strong>
          {row.type} · {row.duration_seconds}s
        </strong>
        <Badge>{row.prompt_status || row.status}</Badge>
      </header>
      <label>
        类型
        <input
          disabled={disabled}
          value={d.type || ""}
          onChange={(e) => setD({ ...d, type: e.target.value })}
        />
      </label>
      <label>
        时长（秒）
        <input
          type="number"
          min="0"
          max="30"
          disabled={disabled}
          value={d.duration_seconds}
          onChange={(e) =>
            setD({ ...d, duration_seconds: Number(e.target.value) })
          }
        />
      </label>
      <label>
        说明
        <textarea
          disabled={disabled}
          value={d.note || ""}
          onChange={(e) => setD({ ...d, note: e.target.value })}
        />
      </label>
      {!disabled && (
        <Button
          onClick={() =>
            save({
              expected_version:d.expected_version,
              type: d.type,
              duration_seconds: d.duration_seconds,
              note: d.note,
            })
          }
        >
          保存转场
        </Button>
      )}
      <Button variant="ghost" onClick={generatePrompt}>生成 Transition Prompt</Button>
      <Button variant="ghost" onClick={suggest}>获取类型建议</Button>
      <Button variant="ghost" disabled={disabled || motionOperation !== null} onClick={generateMotion}>生成 Motion Prompt</Button>
      {suggestion && <p className="novel-help">建议：{suggestion.suggested_type} · {suggestion.reason} <Button variant="ghost" disabled={disabled} onClick={()=>{setD({...d,type:suggestion.suggested_type});setSuggestionApplied(true)}}>采用建议</Button>{suggestionApplied&&<small> 已应用，点击保存转场后生效</small>}</p>}
      <label>Motion Prompt<textarea readOnly={disabled} value={motionPrompt} onChange={e=>setMotionPrompt(e.target.value)} rows={4}/></label>
      {!disabled&&<Button disabled={motionOperation !== null || !motionPrompt.trim()} onClick={saveMotion}>保存 Motion Prompt</Button>}
      {prompt && <><label>Transition Prompt<textarea disabled={disabled} value={prompt} onChange={(e)=>{setPrompt(e.target.value);setD({...d,prompt:e.target.value})}} rows={4}/></label>{promptMeta&&<small className="novel-help">模板 {promptMeta.template_version} · {new Date(promptMeta.generated_at).toLocaleString()}</small>}{!disabled&&<Button onClick={()=>save({expected_version:d.expected_version,type:d.type,duration_seconds:d.duration_seconds,note:d.note,prompt})}>保存 Prompt</Button>}</>}
      {row.prompt_history?.length>0&&<details><summary>Prompt 历史（{row.prompt_history.length}）</summary>{row.prompt_history.slice().reverse().map((item:any,index:number)=><p key={`${item.saved_at}-${index}`} className="novel-help">{new Date(item.saved_at).toLocaleString()} · {item.prompt} <Button variant="ghost" disabled={disabled} onClick={()=>{setPrompt(item.prompt);setD({...d,prompt:item.prompt})}}>恢复此版本</Button></p>)}</details>}
      {transitionPromptError && <p role="alert">{transitionPromptError}</p>}
      {suggestionError && <p role="alert">{suggestionError}</p>}
      {motionPromptError && <p role="alert">{motionPromptError}</p>}
    </article>
  );
}
export function AssetRequirementsPanel({
  novelId,
  screenplayId,
}: {
  novelId: string;
  screenplayId: string;
}) {
  const qc = useQueryClient();
  const [observerId]=useState(()=>globalThis.crypto?.randomUUID?.()||Math.random().toString(36));
  const q = useQuery({
    queryKey: ["screenplays", novelId, observerId],
    queryFn: () => api.screenplays(novelId),
  });
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: ["screenplays", novelId] });
  const s = q.data?.find((x: any) => x.id === screenplayId);
  const plan = useMutation({
    mutationFn: () => api.planAssets(novelId, screenplayId,s?.edit_version??0),
    onSuccess: refresh,onError:(error)=>{if(error instanceof ApiError&&error.status===409)refresh()},
  });
  const approve = useMutation({
    mutationFn: () => api.approveAssets(novelId, screenplayId,s?.edit_version??0),
    onSuccess: refresh,onError:(error)=>{if(error instanceof ApiError&&error.status===409)refresh()},
  });
  const save = useMutation({
    mutationFn: (v: any) =>
      api.updateAsset(novelId, screenplayId, v.id, v.body),
    onSuccess: refresh,onError:(error)=>{if(error instanceof ApiError&&error.status===409)refresh()},
  });
  const queue = useMutation({
    mutationFn: () => api.createAssetTasks(novelId, screenplayId),
    onSuccess: refresh,onError:(error)=>{if(error instanceof ApiError&&error.status===409)refresh()},
  });
  const task = useMutation({
    mutationFn: (v: any) =>
      api.updateAssetTask(novelId, screenplayId, v.id, v.body),
    onSuccess: refresh,onError:(error)=>{if(error instanceof ApiError&&error.status===409)refresh()},
  });
  const assets = s?.asset_requirements;
  const locked = s?.asset_status === "APPROVED";
  const tasks = s?.asset_tasks;
  return (
    <section className="novel-draft-review">
      <h3>素材资产需求</h3>
      {!!(save.error||plan.error||approve.error)&&<p className="novel-error" role="alert">{apiErrorView(save.error||plan.error||approve.error,"保存失败，本地编辑已保留").message}</p>}
      {assets === undefined ? (
        <Button disabled={plan.isPending} onClick={() => plan.mutate()}>
          生成资产清单
        </Button>
      ) : (
        <>
          {assets.map((a: any) => (
            <AssetRow
              key={a.id}
              asset={{...a,expected_version:s?.edit_version??0}}
              disabled={locked}
              save={(b) => save.mutate({ id: a.id, body: b })}
            />
          ))}
          {locked ? (
            <p className="novel-help">资产需求已批准并冻结。</p>
          ) : (
            <Button onClick={() => approve.mutate()}>批准资产需求并冻结</Button>
          )}
          {locked && tasks === undefined && (
            <Button onClick={() => queue.mutate()}>创建生成任务</Button>
          )}
          {tasks && (
            <section>
              <h4>生成任务队列</h4>
              {tasks.map((t: any) => (
                <article key={t.id}>
                  <Badge>{t.status}</Badge>
                  <label>
                    Provider
                    <input
                      value={t.provider_id || ""}
                      onChange={(e) =>
                        task.mutate({
                          id: t.id,
                          body: {
                            status: t.status,
                            provider_id: e.target.value,
                            model_id: t.model_id,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    模型
                    <input
                      value={t.model_id || ""}
                      onChange={(e) =>
                        task.mutate({
                          id: t.id,
                          body: {
                            status: t.status,
                            provider_id: t.provider_id,
                            model_id: e.target.value,
                          },
                        })
                      }
                    />
                  </label>
                  <Button
                    disabled={!t.provider_id || !t.model_id}
                    onClick={() =>
                      task.mutate({
                        id: t.id,
                        body: {
                          status: "RUNNING",
                          provider_id: t.provider_id,
                          model_id: t.model_id,
                        },
                      })
                    }
                  >
                    启动任务
                  </Button>
                </article>
              ))}
            </section>
          )}
          {tasks && <AssetTaskExecutionPanel novelId={novelId} screenplayId={screenplayId} tasks={tasks} />}
        </>
      )}
    </section>
  );
}
function AssetRow({
  asset,
  disabled,
  save,
}: {
  asset: any;
  disabled: boolean;
  save: (b: any) => void;
}) {
  const [d,setD]=useVersionedDraft(asset,['kind','description','status','notes']);
  return (
    <article>
      <DraftVersionReview draft={d} latest={asset} onChange={setD}/>
      <header>
        <strong>{d.kind}</strong>
        <Badge>{d.status}</Badge>
      </header>
      <label>
        类型
        <input
          disabled={disabled}
          value={d.kind || ""}
          onChange={(e) => setD({ ...d, kind: e.target.value })}
        />
      </label>
      <label>
        描述
        <textarea
          disabled={disabled}
          value={d.description || ""}
          onChange={(e) => setD({ ...d, description: e.target.value })}
        />
      </label>
      <label>
        备注
        <input
          disabled={disabled}
          value={d.notes || ""}
          onChange={(e) => setD({ ...d, notes: e.target.value })}
        />
      </label>
      {!disabled && (
        <Button
          onClick={() =>
            save({
              expected_version:d.expected_version,
              kind: d.kind,
              description: d.description,
              status: d.status,
              notes: d.notes,
            })
          }
        >
          保存资产需求
        </Button>
      )}
    </article>
  );
}
