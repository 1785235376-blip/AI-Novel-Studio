import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";
import { AssetTaskExecutionPanel } from "./AssetTaskExecutionPanel";
import { PipelineStatusPanel } from "./PipelineStatusPanel";
import { ScreenplayPipelinePanel } from "./ScreenplayPipelinePanel";
import { FOCUS_FAILED_TASKS_EVENT } from "../ui/taskSummary";
import type { VideoInspection } from "./VideoTaskInspector";
import { MotionTaskWorkspace } from "./MotionTaskWorkspace";
export function motionTaskInspection(task:any,screenplayId?:string):VideoInspection{return{id:String(task.id),status:task.status,screenplayId,transitionId:task.transition_id,providerId:task.provider_id,modelId:task.model_id,progress:task.progress,startFrame:task.start_frame,endFrame:task.end_frame,resultUrl:task.result?.url,assetId:task.result?.asset_id,error:task.error};}
export function ScreenplayPanel({ novelId, onInspect }: { novelId?: string; onInspect?: (inspection: VideoInspection) => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const q = useQuery({
    queryKey: ["screenplays", novelId],
    queryFn: () => api.screenplays(novelId!),
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
  const approve = useMutation({
    mutationFn: (id: string) => api.approveScreenplay(novelId!, id),
    onSuccess: refresh,
  });
  const plan = useMutation({
    mutationFn: (id: string) => api.planScreenplayShots(novelId!, id),
    onSuccess: refresh,
  });
  const approveShots = useMutation({
    mutationFn: (id: string) => api.approveScreenplayShots(novelId!, id),
    onSuccess: refresh,
  });
  const update = useMutation({
    mutationFn: (v: any) =>
      api.updateScreenplayScene(novelId!, v.screenplayId, v.sceneId, v.body),
    onSuccess: refresh,
  });
  const updateShot = useMutation({
    mutationFn: (v: any) =>
      api.updateScreenplayShot(novelId!, v.screenplayId, v.shotId, v.body),
    onSuccess: refresh,
  });
  const board = useMutation({
    mutationFn: (id: string) => api.planStoryboard(novelId!, id),
    onSuccess: refresh,
  });
  const boardApprove = useMutation({
    mutationFn: (id: string) => api.approveStoryboard(novelId!, id),
    onSuccess: refresh,
  });
  const boardUpdate = useMutation({
    mutationFn: (v: any) =>
      api.updateStoryboardCard(novelId!, v.sid, v.cid, v.body),
    onSuccess: refresh,
  });
  const transitionPlan = useMutation({
    mutationFn: (id: string) => api.planTransitions(novelId!, id),
    onSuccess: refresh,
  });
  const transitionApprove = useMutation({
    mutationFn: (id: string) => api.approveTransitions(novelId!, id),
    onSuccess: refresh,
  });
  const transitionUpdate = useMutation({
    mutationFn: (v: any) =>
      api.updateTransition(novelId!, v.sid, v.tid, v.body),
    onSuccess: refresh,
  });
  const motionTasks = useMutation({mutationFn:(id:string)=>api.createMotionTasks(novelId!,id),onSuccess:refresh});
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
        disabled={!title.trim()}
        onClick={() => create.mutate()}
      >
        创建剧本
      </Button>
      <ul>
        {q.data?.map((s: any) => (
          <li key={s.id}>
            <strong>{s.title}</strong> <Badge>{s.status}</Badge>
            <p>{s.scenes.length} 个场景</p>
            <ScreenplayPipelinePanel novelId={novelId} screenplayId={s.id}/>
            {s.scenes.map((x: any) => (
              <Scene
                key={x.id}
                scene={x}
                disabled={s.status !== "DRAFT"}
                onSave={(b) =>
                  update.mutate({ screenplayId: s.id, sceneId: x.id, body: b })
                }
              />
            ))}
            {s.status === "DRAFT" ? (
              <Button onClick={() => approve.mutate(s.id)}>
                批准剧本并进入镜头规划
              </Button>
            ) : (
              <Shots
                s={s}
                plan={() => plan.mutate(s.id)}
                approve={() => approveShots.mutate(s.id)}
                save={(id, b) =>
                  updateShot.mutate({ screenplayId: s.id, shotId: id, body: b })
                }
              />
            )}{" "}
            {s.shot_status === "APPROVED" && (
              <>
                <Storyboard
                  s={s}
                  plan={() => board.mutate(s.id)}
                  approve={() => boardApprove.mutate(s.id)}
                  save={(id, b) =>
                    boardUpdate.mutate({ sid: s.id, cid: id, body: b })
                  }
                />
                <Transitions
                  novelId={novelId}
                  screenplayId={s.id}
                  s={s}
                  plan={() => transitionPlan.mutate(s.id)}
                  approve={() => transitionApprove.mutate(s.id)}
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
      </ul>
    </Panel>
  );
}
function Scene({
  scene,
  disabled,
  onSave,
}: {
  scene: any;
  disabled: boolean;
  onSave: (b: any) => void;
}) {
  const [d, setD] = useState(scene);
  return (
    <details>
      <summary>
        {scene.sequence}. {scene.heading}
      </summary>
      <textarea
        disabled={disabled}
        value={d.action || ""}
        onChange={(e) => setD({ ...d, action: e.target.value })}
      />
      {!disabled && <Button onClick={() => onSave(d)}>保存场景</Button>}
    </details>
  );
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
  return (
    <section>
      <h3>镜头规划</h3>
      {!shots.length ? (
        <Button onClick={plan}>生成初始镜头</Button>
      ) : (
        <>
          {shots.map((x: any) => (
            <Shot key={x.id} shot={x} save={(b) => save(x.id, b)} />
          ))}
          <Button onClick={approve}>批准镜头计划并冻结</Button>
        </>
      )}
    </section>
  );
}
function Shot({ shot, save }: { shot: any; save: (b: any) => void }) {
  const [d, setD] = useState(shot);
  return (
    <details>
      <summary>
        镜头 {shot.number} <Badge>{shot.status}</Badge>
      </summary>
      <input
        value={d.shot_size || ""}
        onChange={(e) => setD({ ...d, shot_size: e.target.value })}
      />
      <input
        value={d.camera_angle || ""}
        onChange={(e) => setD({ ...d, camera_angle: e.target.value })}
      />
      <textarea
        value={d.action || ""}
        onChange={(e) => setD({ ...d, action: e.target.value })}
      />
      <Button onClick={() => save(d)}>保存镜头</Button>
    </details>
  );
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
                card={c}
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
  const [d, setD] = useState(card);
  return (
    <article>
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
              row={x}
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
  const [d, setD] = useState(row);
  const [prompt, setPrompt] = useState(row.prompt || "");
  const [promptMeta, setPromptMeta] = useState<{template_version:string;generated_at:string}>();
  const [promptError, setPromptError] = useState("");
  const [suggestion, setSuggestion] = useState<{suggested_type:string;reason:string}>();
  const [suggestionApplied,setSuggestionApplied]=useState(false);
  const [motionPrompt,setMotionPrompt]=useState('');
  async function generatePrompt() {
    if (!novelId) return;
    try { setPromptError(""); const result = await api.transitionPrompt(novelId, screenplayId || "", row.id); setPrompt(result.prompt); setPromptMeta({template_version:result.template_version,generated_at:result.generated_at}); }
    catch { setPromptError("Prompt 生成失败，请确认剧本已保存。"); }
  }
  async function suggest() { if (!novelId || !screenplayId) return; try { setSuggestion(await api.transitionSuggestion(novelId, screenplayId, row.id)); } catch { setPromptError("转场建议生成失败。"); } }
  async function generateMotion(){if(!novelId||!screenplayId)return;try{const result=await api.motionPrompt(novelId,screenplayId,row.id);setMotionPrompt(result.motion_prompt)}catch{setPromptError('Motion Prompt 生成失败。')}}
  return (
    <article>
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
      <Button variant="ghost" onClick={generateMotion}>生成 Motion Prompt</Button>
      {suggestion && <p className="novel-help">建议：{suggestion.suggested_type} · {suggestion.reason} <Button variant="ghost" disabled={disabled} onClick={()=>{setD({...d,type:suggestion.suggested_type});setSuggestionApplied(true)}}>采用建议</Button>{suggestionApplied&&<small> 已应用，点击保存转场后生效</small>}</p>}
      {motionPrompt&&<><label>Motion Prompt<textarea value={motionPrompt} onChange={e=>setMotionPrompt(e.target.value)} rows={4}/></label>{!disabled&&<Button onClick={async()=>{if(novelId&&screenplayId){await api.saveMotionPrompt(novelId,screenplayId,row.id,motionPrompt)}}}>保存 Motion Prompt</Button>}</>}
      {prompt && <><label>Transition Prompt<textarea disabled={disabled} value={prompt} onChange={(e)=>setPrompt(e.target.value)} rows={4}/></label>{promptMeta&&<small className="novel-help">模板 {promptMeta.template_version} · {new Date(promptMeta.generated_at).toLocaleString()}</small>}{!disabled&&<Button onClick={()=>save({type:d.type,duration_seconds:d.duration_seconds,note:d.note,prompt})}>保存 Prompt</Button>}</>}
      {row.prompt_history?.length>0&&<details><summary>Prompt 历史（{row.prompt_history.length}）</summary>{row.prompt_history.slice().reverse().map((item:any,index:number)=><p key={`${item.saved_at}-${index}`} className="novel-help">{new Date(item.saved_at).toLocaleString()} · {item.prompt} <Button variant="ghost" disabled={disabled} onClick={()=>setPrompt(item.prompt)}>恢复此版本</Button></p>)}</details>}
      {promptError && <p role="alert">{promptError}</p>}
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
  const q = useQuery({
    queryKey: ["screenplays", novelId],
    queryFn: () => api.screenplays(novelId),
  });
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: ["screenplays", novelId] });
  const s = q.data?.find((x: any) => x.id === screenplayId);
  const plan = useMutation({
    mutationFn: () => api.planAssets(novelId, screenplayId),
    onSuccess: refresh,
  });
  const approve = useMutation({
    mutationFn: () => api.approveAssets(novelId, screenplayId),
    onSuccess: refresh,
  });
  const save = useMutation({
    mutationFn: (v: any) =>
      api.updateAsset(novelId, screenplayId, v.id, v.body),
    onSuccess: refresh,
  });
  const queue = useMutation({
    mutationFn: () => api.createAssetTasks(novelId, screenplayId),
    onSuccess: refresh,
  });
  const task = useMutation({
    mutationFn: (v: any) =>
      api.updateAssetTask(novelId, screenplayId, v.id, v.body),
    onSuccess: refresh,
  });
  const assets = s?.asset_requirements;
  const locked = s?.asset_status === "APPROVED";
  const tasks = s?.asset_tasks;
  return (
    <section className="novel-draft-review">
      <h3>素材资产需求</h3>
      {assets === undefined ? (
        <Button disabled={plan.isPending} onClick={() => plan.mutate()}>
          生成资产清单
        </Button>
      ) : (
        <>
          {assets.map((a: any) => (
            <AssetRow
              key={a.id}
              asset={a}
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
  const [d, setD] = useState(asset);
  return (
    <article>
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
