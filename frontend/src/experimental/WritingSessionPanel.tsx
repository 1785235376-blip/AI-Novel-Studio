import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
import { Field, ResourceState, useAction, useResource } from './shared';
import { writingSessionsClient, defaultNoticePreferences, nextReminderAt, watchNoticeSettings, noticeSettingsChanged, type Session, type ChecklistItem, type NoticePreferences } from './writingSessionsClient';
let sequence = 0;
const capture = () => crypto.randomUUID();
type Props = { client: ExperimentalClient; onNavigate?: (target: WorkspaceNavigation) => void };
export function WritingSessionPanel(props: Props) {
  const identity = useMemo(() => ++sequence, [props.client]);
  return <SessionBody key={identity} {...props} />;
}
function SessionBody({ client, onNavigate }: Props) {
  const api = useMemo(() => writingSessionsClient(client), [client]);
  const overview = useResource(signal => api.overview(signal), [api]);
  const [goal, setGoal] = useState(''), [target, setTarget] = useState(''), [taskText, setTaskText] = useState('');
  const [draftTasks, setDraftTasks] = useState<ChecklistItem[]>([]), [session, setSession] = useState<Session>();
  const captureId = useRef(capture()), touched = useRef(false), alive = useRef(true), draftEpoch = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { const active = overview.data?.items.find(s => s.status === 'ACTIVE'); if (active && !touched.current) setSession(active); }, [overview.data]);
  const action = useAction(overview.reload);
  const currentTasks = session?.tasks || draftTasks;
  const updateTasks = (tasks: ChecklistItem[]) => { draftEpoch.current++; touched.current = true; if (session) setSession({ ...session, tasks }); else setDraftTasks(tasks); };
  const start = () => action.run(async () => { const result = await api.start({ capture_id: captureId.current, goal, target_characters: target ? Number(target) : null, tasks: draftTasks }); if (alive.current) { setSession(result); touched.current = false; } }, '本次目标已开始。统计只读取已持久化章节与历史。');
  const save = (complete: boolean) => action.run(async () => { if (!session) return; const ticket = draftEpoch.current; const result = await api.update(session, complete); if (alive.current && ticket === draftEpoch.current) { touched.current = false; setSession(complete ? undefined : result); if (complete) { setGoal(''); setTarget(''); setDraftTasks([]); captureId.current = capture(); } } }, complete ? '本次写作已结束，停止点与真实保存回顾已记录。' : '清单与停止点已保存。');
  return <section className="experimental-section" aria-label="写作目标与本次回顾">
    <div className="experimental-actions"><h3>本次写作</h3><Badge>可选 · 无打卡惩罚 · 不执行模型</Badge></div>
    <ResourceState loading={overview.loading} error={overview.error} />
    <Button disabled={overview.loading || action.busy} onClick={overview.reload}>核对服务器会话（保留未保存笔记）</Button>
    {overview.data?.project_goal ? <p>原项目目标：{overview.data.project_goal.current_words} / {overview.data.project_goal.target_words} 字；{overview.data.project_goal.current_chapters} / {overview.data.project_goal.target_chapters} 章。</p> : !overview.loading && <p>当前分支未接入项目目标统计，未借用主分支总数。</p>}
    <Button disabled={!onNavigate} onClick={() => onNavigate?.({ kind: 'feature', id: 'creation', feature: 'creation' })}>打开原项目目标入口</Button>
    {!session && overview.data?.items.some(x => x.status === 'ACTIVE') && <Button onClick={() => { touched.current = false; setSession(overview.data?.items.find(x => x.status === 'ACTIVE')); }}>载入服务器进行中会话（替换本地未开始清单）</Button>}
    <Panel title={session ? '进行中的写作会话' : '可选的本次目标'}>
      {session ? <><p>{session.goal || '未设置文字目标'} · v{session.version}</p>{session.target_characters && <p>本次希望净增 {session.target_characters} 个非空白字符。</p>}</> : <><Field label="本次写作目标（可选）"><input maxLength={1000} value={goal} onChange={e => { captureId.current = capture(); setGoal(e.target.value); }} /></Field><Field label="本次目标字符数（可选）"><input type="number" min={1} max={1000000} value={target} onChange={e => { captureId.current = capture(); setTarget(e.target.value); }} /></Field></>}
      <p>清单只供手工勾选，不是任务执行器。净增统计含会话期间项目中的实际保存，不能当成个人打字量。</p>
      <Field label="添加本次待办"><input maxLength={300} value={taskText} onChange={e => setTaskText(e.target.value)} /></Field><Button disabled={!taskText.trim() || currentTasks.length >= 30} onClick={() => { updateTasks([...currentTasks, { id: capture(), text: taskText, done: false }]); setTaskText(''); captureId.current = capture(); }}>添加待办</Button>
      {currentTasks.map(t => <div key={t.id} className="experimental-actions"><label><input type="checkbox" checked={t.done} onChange={e => updateTasks(currentTasks.map(x => x.id === t.id ? { ...x, done: e.target.checked } : x))} />{t.text}</label><Button onClick={() => updateTasks(currentTasks.filter(x => x.id !== t.id))}>移除 {t.text}</Button></div>)}
      {session && <Field label="本次停止点笔记"><textarea maxLength={2000} value={session.stopping_note} onChange={e => { draftEpoch.current++; touched.current = true; setSession({ ...session, stopping_note: e.target.value }); }} /></Field>}
      <div className="experimental-actions">{session ? <><Button disabled={action.busy || overview.loading || !!overview.error} onClick={() => save(false)}>保存本次停止点</Button><Button disabled={action.busy || overview.loading || !!overview.error} onClick={() => save(true)}>结束本次写作并回顾</Button><Button disabled={overview.loading || action.busy} onClick={() => { touched.current = false; setSession(overview.data?.items.find(x => x.status === 'ACTIVE')); }}>放弃未保存会话修改</Button></> : <Button disabled={action.busy || overview.loading || !!overview.error || !!overview.data?.items.find(x => x.status === 'ACTIVE') || !!target && (!Number.isInteger(Number(target)) || Number(target) < 1 || Number(target) > 1000000)} onClick={start}>开始本次写作</Button>}</div>
      {session && overview.data?.items.find(s => s.id === session.id)?.version !== session.version && <StatusMessage tone="warning">服务器会话版本已变化；当前笔记保留，请比较后放弃本地修改再继续。</StatusMessage>}
    </Panel>
    <Panel title="已持久化的完成回顾">
      {overview.data?.truncated && <p>仅显示最近 50 次会话。</p>}
      {overview.data?.items.filter(s => s.status === 'COMPLETED').map(s => <article key={s.id} className="experimental-record"><strong>{s.goal || '无文字目标的写作会话'}</strong><p>结束：{s.completed_at}</p><p>当前仍可访问章节净增 {s.recap?.net_characters ?? '未知'} 字符；实际保存历史事件 {s.recap?.persisted_revision_events ?? '不可核实'} 次；完成待办 {s.recap?.completed_checklist_items ?? 0} 项。</p><p>停止点：{s.stopping_note || '未填写'}</p>{s.target_characters && <p>自定目标 {s.target_characters} 字符；{(s.recap?.net_characters || 0) >= s.target_characters ? '达到' : '未达到'}，无处罚或排名。</p>}</article>)}
    </Panel>
    {action.feedback}
    <NoticeSettings client={client} />
  </section>;
}
function NoticeSettings({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => writingSessionsClient(client), [client]);
  const resource = useResource(signal => api.preferences(signal), [api]);
  const [saved, setSaved] = useState<NoticePreferences>(), [editing, setEditing] = useState(defaultNoticePreferences);
  const touched = useRef(false), alive = useRef(true), draftEpoch = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { if (resource.data) { setSaved(resource.data); if (!touched.current) setEditing(resource.data); } }, [resource.data]);
  const action = useAction();
  const change = (patch: Partial<NoticePreferences>) => { draftEpoch.current++; touched.current = true; setEditing({ ...editing, ...patch }); };
  return <Panel title="通知与可控提醒">
    <ResourceState loading={resource.loading} error={resource.error} />
    <p>默认关闭。仅此项目和分支的任务中心打开期间运行应用内计时器；关闭任务中心、刷新或退出应用即停止。重新打开只等待下一次，不补发错过提醒。没有邮件、网络推送、后台监测或行为追踪，不启动模型。</p>
    <label><input type="checkbox" checked={editing.reminder.enabled} onChange={e => change({ reminder: { ...editing.reminder, enabled: e.target.checked } })} />启用自定应用内提醒</label>
    <Field label="下一次提醒时刻"><input type="time" value={editing.reminder.time} onChange={e => change({ reminder: { ...editing.reminder, time: e.target.value } })} /></Field>
    <Field label="提醒 IANA 时区"><input value={editing.reminder.timezone} maxLength={80} onChange={e => change({ reminder: { ...editing.reminder, timezone: e.target.value } })} /></Field>
    <p>夏令时跳过的时刻当天不触发；重复时刻每次打开任务中心最多触发一次。保存关闭后清除当前自有计时器；其他窗口需要重新读取设置。</p>
    <Field label="完成通知优先级"><select value={editing.completion_priority} onChange={e => change({ completion_priority: e.target.value as 'normal' | 'low' })}><option value="normal">普通</option><option value="low">低</option></select></Field>
    <Field label="待审核通知优先级"><select value={editing.review_priority} onChange={e => change({ review_priority: e.target.value as 'normal' | 'low' })}><option value="normal">普通</option><option value="low">低</option></select></Field>
    <Field label="任务失败通知优先级"><select value={editing.failure_priority} onChange={e => change({ failure_priority: e.target.value as 'urgent' | 'normal' })}><option value="urgent">紧急</option><option value="normal">普通</option></select></Field>
    <p>专注时延后非紧急通知；正文保存失败始终由原编辑器和任务中心直接显示。</p>
    <div className="experimental-actions"><Button disabled={!saved || editing.version !== saved.version || resource.loading || !!resource.error || action.busy} onClick={() => action.run(async () => { const ticket = draftEpoch.current; const result = await api.savePreferences(editing); noticeSettingsChanged(client); if (alive.current) { setSaved(result); if (ticket === draftEpoch.current) { setEditing(result); touched.current = false; } else setEditing(previous => ({ ...previous, version: result.version })); } }, '通知偏好已保存。提醒不执行任何创作任务。')}>保存通知与提醒设置</Button><Button onClick={resource.reload} disabled={resource.loading}>核对通知设置</Button></div>
    {saved && editing.version !== saved.version && <StatusMessage tone="warning">服务器设置版本已变化，当前输入保留。请先恢复服务器版本，避免覆盖其他窗口修改。</StatusMessage>}
    <Button disabled={!saved} onClick={() => { setEditing(saved!); touched.current = false; }}>恢复服务器通知设置</Button>
    {action.feedback}
  </Panel>;
}
export type NoticeCenterProps = Props & { focusActive?: boolean; saveFailure?: boolean };
/** Mount only inside the original task center while U15 is authorized. */
export function NoticeCenterAddon(props: NoticeCenterProps) {
  const identity = useMemo(() => ++sequence, [props.client]);
  return <NoticeCenterBody key={identity} {...props} />;
}
function NoticeCenterBody({ client, focusActive = false, saveFailure = false, onNavigate }: NoticeCenterProps) {
  const api = useMemo(() => writingSessionsClient(client), [client]);
  const settings = useResource(signal => api.preferences(signal), [api]);
  const notices = useResource(signal => api.notices(focusActive, signal), [api, focusActive]);
  const [reminder, setReminder] = useState(false), [timerError, setTimerError] = useState(false);
  const [settingsEpoch, setSettingsEpoch] = useState(0);
  useEffect(() => watchNoticeSettings(client, () => { setReminder(false); setSettingsEpoch(value => value + 1); settings.reload(); }), [client, settings.reload]);
  const action = useAction(() => { notices.reload(); settings.reload(); });
  useEffect(() => {
    setReminder(false); setTimerError(false);
    if (settings.loading || settings.error || !settings.data?.reminder.enabled) return;
    try {
      const value = settings.data.reminder; const at = nextReminderAt(value.time, value.timezone, Date.now());
      if (!at) { setTimerError(true); return; }
      // One owned timer. No missed-time replay, notification API or network.
      const timer = window.setTimeout(() => setReminder(true), at - Date.now());
      return () => window.clearTimeout(timer);
    } catch { setTimerError(true); }
  }, [settings.data?.version, settings.loading, settings.error, settingsEpoch]);
  return <Panel title="聚合通知（原任务中心）">
    {saveFailure && <StatusMessage tone="error">正文保存失败。请回到编辑器保留本地草稿并重试；专注模式不会隐藏此错误。</StatusMessage>}
    <ResourceState loading={notices.loading || settings.loading} error={notices.error || settings.error} />
    <Button disabled={notices.loading || settings.loading} onClick={() => { notices.reload(); settings.reload(); }}>刷新聚合通知与提醒</Button>
    <p>手动读取已有任务事件，不是持续后台监测。相同任务、版本和结果只显示一次。专注结束后重新显示延后通知。</p>
    {!!notices.data?.deferred_count && <p>专注模式延后 {notices.data.deferred_count} 条非紧急提示。</p>}
    {(notices.data?.truncated || !!notices.data?.unavailable.length) && <StatusMessage tone="warning">部分任务来源未完整读取，请到原任务入口核对。</StatusMessage>}
    {settings.data?.reminder.enabled && <p>当前打开期间等待 {settings.data.reminder.time}（{settings.data.reminder.timezone}）；每次打开最多一次。关闭此中心将清除计时器。</p>}
    {timerError && <StatusMessage tone="warning">提醒时间或时区无法计算，计时器未启动。请核对设置。</StatusMessage>}
    {reminder && !focusActive && <StatusMessage>这是你设置的写作提醒。可以继续写作，也可以自由略过。</StatusMessage>}
    {reminder && focusActive && <p>自定提醒已延后，退出专注后显示。</p>}
    {!notices.loading && !notices.error && notices.data?.items.map(n => <article key={n.event_id} className="experimental-record"><Badge tone={n.priority === 'urgent' ? 'error' : 'neutral'}>{n.priority}</Badge> {n.label} · {n.status}<div className="experimental-actions"><Button disabled={!onNavigate} onClick={() => onNavigate?.({ kind: 'feature', id: n.task_id, feature: n.feature })}>打开原任务 {n.task_id}</Button><Button disabled={!settings.data || action.busy} onClick={() => action.run(() => api.acknowledge(settings.data!.version, n.event_id), '已确认这一次任务事件。')}>知道了 {n.task_id}</Button></div></article>)}
    {action.feedback}
  </Panel>;
}
