import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import type { WorkspaceNavigation } from './uxClient';
import { Field, ResourceState, useAction, useResource } from './shared';
import { writerRoomClient, type RoomApi, type RoomMember, type RoomTask, type RoomConflict, type RoomCatalog, type TaskFields, type RoomComment, type PackagePreview, type TaskAction } from './writerRoomClient';
let sequence = 0;
export function WriterRoomPanel(props: { client: ExperimentalClient; onNavigate?: (value: WorkspaceNavigation) => void }) {
  const identity = useMemo(() => ++sequence, [props.client]);
  return <RoomBody key={identity} {...props} />;
}
const taskFields = (task: TaskFields): TaskFields => ({ title: task.title, description: task.description, assignee: task.assignee, reviewer: task.reviewer });
type TaskDrafts = Map<string, { fields: TaskFields; base: number }>;
const statusLabels: Record<string, string> = { ASSIGNED: '已分派', IN_PROGRESS: '处理中', READY_FOR_REVIEW: '待责任人审阅', CHANGES_REQUESTED: '需要修改', CLOSED: '协作任务已完成', CANCELLED: '已取消' };
function People({ members, fields, set, disabled = false }: { members: RoomMember[]; fields: TaskFields; set: (fields: TaskFields) => void; disabled?: boolean }) {
  return <div className="experimental-grid"><Field label="任务负责人"><select value={fields.assignee} disabled={disabled} onChange={e => set({ ...fields, assignee: e.target.value })}><option value="">选择有当前写入权限的成员</option>{members.filter(m => m.can_write).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field><Field label="责任审核人"><select value={fields.reviewer} disabled={disabled} onChange={e => set({ ...fields, reviewer: e.target.value })}><option value="">选择有当前审核权限的成员</option>{members.filter(m => m.can_review).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field></div>;
}
function RoomBody({ client, onNavigate }: { client: ExperimentalClient; onNavigate?: (value: WorkspaceNavigation) => void }) {
  const api = useMemo(() => writerRoomClient(client), [client]);
  const room = useResource(signal => api.overview(signal), [api]), catalog = useResource(signal => api.catalog(signal), [api]);
  const conflicts = useResource(signal => api.conflicts(signal), [api]), notices = useResource(signal => api.notices(signal), [api]);
  const drafts = useRef<TaskDrafts>(new Map());
  useEffect(() => { const guard = (event: BeforeUnloadEvent) => { if (drafts.current.size) { event.preventDefault(); event.returnValue = ''; } }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard); }, []);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState(''), [query, setQuery] = useState(''), [submittedQuery, setSubmittedQuery] = useState('');
  const search = useResource(signal => api.search(submittedQuery, signal), [api, submittedQuery]);
  const reload = () => { setRevision(value => value + 1); room.reload(); catalog.reload(); conflicts.reload(); notices.reload(); search.reload(); };
  const reloadRef = useRef(reload); reloadRef.current = reload;
  useEffect(() => { const focus = () => reloadRef.current(); window.addEventListener('focus', focus); return () => window.removeEventListener('focus', focus); }, []);
  const blocked = room.loading || !!room.error || !room.data;
  const revoked = room.error instanceof ApiError && [401, 403, 404].includes(room.error.problem.status);
  useEffect(() => { if (revoked) drafts.current.clear(); }, [revoked]);
  const task = room.data?.items.find(t => t.id === selected);
  return <section className="experimental-pane" aria-label="Writer Room 异步团队审阅">
    <Panel title="Writer Room · 异步团队审阅"><p>任务分派使用当前工作区、项目与分支权限。加入协作任务不会授予原稿、资产或密钥权限。这里不提供实时光标、在线状态或邀请。</p><p>只读审阅不改正文。完成协作任务不会接受 Canon、正文或媒体；这些操作仍由原领域审核入口执行。</p><Button onClick={reload} disabled={room.loading}>刷新团队当前权限与任务</Button><ResourceState loading={room.loading} error={room.error} /><ResourceState loading={catalog.loading} error={catalog.error} />
      {!blocked && room.data && <><Badge>{room.data.can_write ? '可处理协作任务' : '只读审阅权限'}</Badge><p>当前身份：{room.data.actor}</p>{room.data.truncated && <StatusMessage tone="warning">显示达到上限，不能据此判断全部任务已处理。</StatusMessage>}<details><summary>当前分派提醒</summary><ResourceState loading={notices.loading} error={notices.error} empty={!notices.data?.items.length} />{!notices.loading && !notices.error && notices.data?.items.map(n => <p key={n.id}>{n.title} · {statusLabels[n.status] || n.status}</p>)}</details></>}
    </Panel>
    <div hidden={blocked}>
      {room.data && !revoked && <><Panel title="协作任务"><Field label="搜索协作任务"><input value={query} maxLength={200} onChange={e => setQuery(e.target.value)} /></Field><Button disabled={blocked || search.loading} onClick={() => setSubmittedQuery(query)}>搜索当前授权任务</Button><ResourceState loading={search.loading} error={search.error} empty={!search.data?.items.length} />{!search.loading && !search.error && search.data?.items.map(t => <article className="experimental-record" key={t.id}><Button onClick={() => setSelected(t.id)}>{t.title}</Button> <Badge>{statusLabels[t.status] || t.status} · v{t.version}</Badge></article>)}</Panel>
        {task && <TaskEditor key={task.id} drafts={drafts.current} api={api} task={task} members={room.data.members} actor={room.data.actor} canWrite={room.data.can_write} canReview={room.data.can_review} conflicts={conflicts.data?.items || []} reload={reload} blocked={blocked} />}
        {room.data.can_write && <NewTask api={api} members={room.data.members} catalog={catalog.data} blocked={blocked || catalog.loading || !!catalog.error} done={value => { setSelected(value.id); reload(); }} />}
        <ReadReview revision={revision} api={api} catalog={catalog.data} catalogBlocked={catalog.loading || !!catalog.error} canWrite={room.data.can_write} blocked={blocked} />
        <Panel title="原领域审核入口"><p>责任人确认的是协作进度。原审核收件箱仍会重新检查来源版本与领域权限。</p><Button disabled={!onNavigate || blocked} onClick={() => onNavigate?.({ kind: 'feature', id: 'unified_review_inbox', feature: 'unified_review_inbox' })}>打开统一审核收件箱</Button></Panel>
        <ReviewPackage api={api} catalog={catalog.data} blocked={blocked || catalog.loading || !!catalog.error} />
        <Panel title="冲突候选记录"><ResourceState loading={conflicts.loading} error={conflicts.error} empty={!conflicts.data?.items.length} />{!conflicts.loading && !conflicts.error && conflicts.data?.items.map(c => <article key={c.id} className="experimental-record"><Badge>{c.status}</Badge><p>{c.target.kind} · {c.target.id}</p><p>服务端候选 v{c.current_candidate.version}：{c.current_candidate.title || c.current_candidate.messages?.map(m => m.text).join(' / ')}</p><p>提交候选：{c.submitted_candidate.title || c.submitted_candidate.text || c.submitted_candidate.note || c.submitted_candidate.action}</p><p>两份候选均已保存在当前授权范围；刷新后再选择，不会自动覆盖。</p></article>)}</Panel>
      </>}
    </div>
  </section>;
}
function NewTask({ api, members, catalog, blocked, done }: { api: RoomApi; members: RoomMember[]; catalog?: RoomCatalog; blocked: boolean; done: (task: RoomTask) => void }) {
  const [fields, setFields] = useState<TaskFields>({ title: '', description: '', assignee: members.find(m => m.can_write)?.id || '', reviewer: members.find(m => m.can_review)?.id || '' });
  const [chapter, setChapter] = useState(''), [target, setTarget] = useState(''); const action = useAction();
  const request = useRef<{ key: string; id: string }>();
  const alive = useRef(true); useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  return <Panel title="分派协作任务"><Field label="新任务标题"><input disabled={blocked || action.busy} maxLength={200} value={fields.title} onChange={e => setFields({ ...fields, title: e.target.value })} /></Field><Field label="新任务说明"><textarea disabled={blocked || action.busy} maxLength={8000} value={fields.description} onChange={e => setFields({ ...fields, description: e.target.value })} /></Field><People members={members} fields={fields} set={setFields} disabled={action.busy || blocked} />
    <div className="experimental-grid"><Field label="关联章节版本"><select disabled={blocked || action.busy} value={chapter} onChange={e => setChapter(e.target.value)}><option value="">不关联章节</option>{catalog?.chapters.map(c => <option key={c.id} value={c.id}>{c.title} · v{c.version}</option>)}</select></Field><Field label="关联原领域审核项"><select disabled={blocked || action.busy} value={target} onChange={e => setTarget(e.target.value)}><option value="">不关联审核项</option>{catalog?.review_targets.map((r, i) => <option key={`${r.domain}:${r.id}`} value={String(i)}>{r.domain} · {r.preview}</option>)}</select></Field></div>
    <Button disabled={blocked || action.busy || !fields.title.trim() || !fields.assignee || !fields.reviewer} onClick={() => void action.run(async () => { const source = catalog?.chapters.find(c => c.id === chapter), review = target === '' ? undefined : catalog?.review_targets[Number(target)]; const body = { ...fields, chapter: source ? { id: source.id, revision: source.revision } : null, review_target: review ? { domain: review.domain, id: review.id, version: review.version } : null }; const key = JSON.stringify(body); if (request.current?.key !== key) request.current = { key, id: crypto.randomUUID() }; const row = await api.create({ ...body, request_id: request.current.id }); if (alive.current) { setFields({ ...fields, title: '', description: '' }); request.current = undefined; done(row); } }, '任务已分派，未修改原稿或权限。')}>创建协作任务</Button>{action.feedback}
  </Panel>;
}
function TaskEditor({ api, task, members, actor, canWrite, canReview, conflicts, reload, blocked, drafts }: { drafts: TaskDrafts; api: RoomApi; task: RoomTask; members: RoomMember[]; actor: string; canWrite: boolean; canReview: boolean; conflicts: RoomConflict[]; reload: () => void; blocked: boolean }) {
  const [fields, setFields] = useState(drafts.get(task.id)?.fields || taskFields(task)), [base, setBase] = useState(drafts.get(task.id)?.base || task.version), [note, setNote] = useState(''); const action = useAction();
  const dirty = JSON.stringify(fields) !== JSON.stringify(taskFields(task)), conflict = conflicts.find(c => c.status === 'OPEN' && c.target.kind === 'task' && c.target.id === task.id);
  useEffect(() => { if (dirty) drafts.set(task.id, { fields, base }); else drafts.delete(task.id); }, [dirty, fields, base, task.id, drafts]);
  const stale = base !== task.version; const alive = useRef(true); useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const save = (value: TaskFields, version: number, conflictId?: string) => action.run(async () => { try { const result = await api.save(task.id, version, value, conflictId); if (alive.current) { setFields(taskFields(result)); setBase(result.version); } } finally { reload(); } }, '协作任务已保存。');
  const transitions: { action: TaskAction; label: string; visible: boolean }[] = [
    { action: 'start', label: '开始处理', visible: actor === task.assignee && canWrite && ['ASSIGNED', 'CHANGES_REQUESTED'].includes(task.status) },
    { action: 'submit', label: '提交责任人审阅', visible: actor === task.assignee && canWrite && ['IN_PROGRESS', 'CHANGES_REQUESTED'].includes(task.status) },
    { action: 'request_changes', label: '请求修改并保留理由', visible: actor === task.reviewer && canReview && task.status === 'READY_FOR_REVIEW' },
    { action: 'close', label: '完成协作任务', visible: actor === task.reviewer && canReview && task.status === 'READY_FOR_REVIEW' },
    { action: 'reopen', label: '重新打开协作任务', visible: actor === task.reviewer && canReview && ['CLOSED', 'CANCELLED'].includes(task.status) },
    { action: 'cancel', label: '取消协作任务', visible: actor === task.created_by && canWrite && !['CLOSED', 'CANCELLED'].includes(task.status) },
  ];
  return <Panel title="当前任务与责任"><Badge>{statusLabels[task.status]} · v{task.version}</Badge>{!task.participants_current && <StatusMessage tone="warning">负责人或审核人权限已失效。请重新分派当前有权成员。</StatusMessage>}{task.source_state !== 'CURRENT' && <StatusMessage tone="warning">来源 {task.source_state}；不能提交或完成此旧版本任务。请到原领域处理并关联新任务。</StatusMessage>}
    <Field label="当前任务标题"><input value={fields.title} maxLength={200} disabled={!canWrite || blocked || action.busy} onChange={e => setFields({ ...fields, title: e.target.value })} /></Field><Field label="当前任务说明"><textarea value={fields.description} maxLength={8000} disabled={!canWrite || blocked || action.busy} onChange={e => setFields({ ...fields, description: e.target.value })} /></Field><People members={members} fields={fields} set={setFields} disabled={!canWrite || blocked || action.busy} />
    {dirty && <p>未保存输入仅在当前房间会话内保留；请保存后离开。</p>}{stale && <StatusMessage tone="warning">服务端已有较新版本，当前输入仍保留。核对两份候选后再选择。</StatusMessage>}<div className="experimental-actions"><Button disabled={!canWrite || blocked || action.busy || stale || !fields.title.trim()} onClick={() => void save(fields, base)}>保存任务修改</Button><Button disabled={blocked || action.busy} onClick={() => { setFields(taskFields(task)); setBase(task.version); }}>读取当前服务端候选</Button>
      {conflict && <><Button disabled={!canWrite || blocked || action.busy} onClick={() => void save(taskFields(conflict.submitted_candidate), task.version, conflict.id)}>核对后采用提交候选</Button><Button disabled={!canWrite || blocked || action.busy} onClick={() => void save(taskFields(task), task.version, conflict.id)}>核对后保留服务端候选</Button></>}
    </div><Field label="处理记录或修改理由"><textarea disabled={blocked || action.busy} value={note} maxLength={8000} onChange={e => setNote(e.target.value)} /></Field><div className="experimental-actions">{transitions.filter(t => t.visible).map(t => <Button key={t.action} disabled={blocked || action.busy || dirty || stale || (t.action === 'request_changes' && !note.trim())} onClick={() => void action.run(async () => { try { const result = await api.transition(task, t.action, note); if (alive.current) setBase(result.version); } finally { reload(); } }, '协作状态已更新；领域内容仍由原审核流程处理。')}>{t.label}</Button>)}</div>{task.events.map((event, i) => <p key={i}>{event.actor} · {event.action}：{event.note || '无附加说明'}</p>)}{action.feedback}
  </Panel>;
}
function ReadReview({ api, catalog, catalogBlocked, canWrite, blocked, revision }: { revision: number; api: RoomApi; catalog?: RoomCatalog; catalogBlocked: boolean; canWrite: boolean; blocked: boolean }) {
  const [cid, setCid] = useState(''), [quote, setQuote] = useState(''), [text, setText] = useState('');
  const comments = useResource(signal => api.comments(signal), [api, revision]); const selected = catalog?.chapters.find(c => c.id === cid);
  const reading = useResource(signal => selected ? api.chapter(selected, signal) : Promise.resolve(undefined), [api, selected?.id, selected?.revision, revision]); const action = useAction(comments.reload);
  return <Panel title="只读章节与版本批注">{catalog?.chapter_state === 'BRANCH_SOURCE_UNAVAILABLE' && <StatusMessage tone="warning">原章节仓库尚未提供分支正文权限来源。当前分支只开放协作元数据与原领域审核项，不展示或冒用基础正文。</StatusMessage>}
    <Field label="只读审阅章节"><select value={cid} disabled={catalogBlocked || blocked} onChange={e => { setCid(e.target.value); setQuote(''); setText(''); }}><option value="">选择已授权章节版本</option>{catalog?.chapters.map(c => <option key={c.id} value={c.id}>{c.title} · v{c.version}</option>)}</select></Field><ResourceState loading={reading.loading} error={reading.error} />
    {!blocked && !catalogBlocked && !reading.loading && !reading.error && reading.data && <><Badge>只读 · v{reading.data.version}</Badge><div className="experimental-details"><pre>{reading.data.text}</pre></div>{canWrite && <><Field label="批注原文引用"><input value={quote} maxLength={2000} onChange={e => setQuote(e.target.value)} /></Field><Field label="章节批注"><textarea value={text} maxLength={8000} onChange={e => setText(e.target.value)} /></Field><Button disabled={blocked || action.busy || !text.trim() || !selected} onClick={() => void action.run(() => api.comment(selected!, quote, text), '批注已保存到原评论服务。')}>保存版本批注</Button></>}</>}
    <ResourceState loading={comments.loading} error={comments.error} empty={!comments.data?.items.length} />{!blocked && !catalogBlocked && !comments.loading && !comments.error && comments.data?.items.filter(c => !cid || c.anchor.chapter_id === cid).map(c => <CommentThread key={c.id} api={api} row={c} canWrite={canWrite} blocked={blocked} reload={comments.reload} />)}{action.feedback}
  </Panel>;
}
function CommentThread({ api, row, canWrite, blocked, reload }: { api: RoomApi; row: RoomComment; canWrite: boolean; blocked: boolean; reload: () => void }) {
  const [reply, setReply] = useState(''); const action = useAction();
  const perform = (kind: 'reply' | 'resolve' | 'reopen') => action.run(async () => { try { await api.commentAction(row, kind, reply); } finally { reload(); } }, '原评论线程已更新。');
  return <article className="experimental-record"><Badge>{row.status} · v{row.version} · {row.anchor_state}</Badge><p>{row.anchor.quote}</p>{row.messages.map(m => <p key={m.id}>{m.actor_id}：{m.text}</p>)}{canWrite && <><Field label={`回复批注 ${row.id}`}><textarea value={reply} maxLength={8000} onChange={e => setReply(e.target.value)} /></Field><Button disabled={blocked || action.busy || row.status !== 'OPEN' || !reply.trim()} onClick={() => void perform('reply')}>发送批注回复</Button><Button disabled={blocked || action.busy} onClick={() => void perform(row.status === 'OPEN' ? 'resolve' : 'reopen')}>{row.status === 'OPEN' ? '标记批注已处理' : '重新打开批注'}</Button></>}{action.feedback}</article>;
}
function ReviewPackage({ api, catalog, blocked }: { api: RoomApi; catalog?: RoomCatalog; blocked: boolean }) {
  const [chapters, setChapters] = useState<string[]>([]), [assets, setAssets] = useState<string[]>([]), [preview, setPreview] = useState<PackagePreview>(), [ack, setAck] = useState(false), [file, setFile] = useState<{ url: string; filename: string }>();
  const action = useAction(), epoch = useRef(0), alive = useRef(true), url = useRef<string>();
  const selection = { chapters: (catalog?.chapters || []).filter(c => chapters.includes(c.id)).map(c => ({ id: c.id, revision: c.revision })), asset_ids: assets };
  const selectionKey = JSON.stringify(selection);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; if (url.current) URL.revokeObjectURL(url.current); }; }, []);
  useEffect(() => { epoch.current++; setPreview(undefined); setAck(false); setFile(undefined); if (url.current) URL.revokeObjectURL(url.current); url.current = undefined; }, [selectionKey, blocked]);
  const toggle = (list: string[], id: string, set: (value: string[]) => void) => set(list.includes(id) ? list.filter(v => v !== id) : [...list, id]);
  return <Panel title="受限审阅包 · 本地下载"><p>仅包含明确勾选的章节和资产。不会发送给他人、创建邀请或扩大权限。已下载的永久副本无法通过撤销成员权限远程收回。</p>
    <fieldset disabled={blocked || action.busy}><legend>选择下载内容，默认全部不选</legend>{catalog?.chapters.map(c => <label className="experimental-check" key={c.id}><input type="checkbox" checked={chapters.includes(c.id)} onChange={() => toggle(chapters, c.id, setChapters)} />章节：{c.title} · v{c.version}</label>)}{catalog?.assets.map(a => <label className="experimental-check" key={a.id}><input type="checkbox" checked={assets.includes(a.id)} onChange={() => toggle(assets, a.id, setAssets)} />资产：{a.filename} · {a.size} bytes</label>)}</fieldset>
    {catalog?.asset_state !== 'AVAILABLE' && <p>资产需要原资产库当前权限。</p>}<Button disabled={blocked || action.busy || (!selection.chapters.length && !assets.length)} onClick={() => void action.run(async () => { const ticket = ++epoch.current; const result = await api.packagePreview(selection); if (alive.current && ticket === epoch.current) { setPreview(result); setAck(false); } }, '选定内容已预览，尚未生成下载。')}>预览受限审阅包</Button>
    {preview && <><p>已选 {preview.manifest.chapters.length} 章、{preview.manifest.assets.length} 个资产；源内容 {preview.selected_bytes} bytes。</p><label className="experimental-check"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />我了解下载副本无法远程撤回</label><Button disabled={blocked || action.busy || !ack} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.download(selection, preview); if (alive.current && ticket === epoch.current) { if (url.current) URL.revokeObjectURL(url.current); const bytes = Uint8Array.from(atob(result.content_base64), c => c.charCodeAt(0)); url.current = URL.createObjectURL(new Blob([bytes], { type: result.mime })); setFile({ url: url.current, filename: result.filename }); } }, '受限审阅包已就绪。')}>生成选定内容下载</Button></>}
    {file && <a href={file.url} download={file.filename}>下载受限审阅包</a>}{action.feedback}
  </Panel>;
}
