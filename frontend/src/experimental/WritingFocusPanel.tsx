import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Chapter } from '../api';
import type { WorkspaceNavigation } from './uxClient';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { enabled, type ExperimentalClient, type ExperimentalFlags } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { defaultWritingPreferences, writingFocusClient, type WritingFocusPreferences, type WritingPreferenceResult, type ReferenceCard, type ReferencePin, type InspirationNote, type CopyInput, type CopyPreview } from './writingFocusClient';
import './writingFocus.css';
export { defaultWritingPreferences } from './writingFocusClient';
export type { WritingFocusPreferences } from './writingFocusClient';

type Props = { client: ExperimentalClient; chapter?: Chapter; flags?: ExperimentalFlags; focusActive?: boolean; onFocusChange?: (active: boolean) => void; onPreferencesChange?: (preferences: WritingFocusPreferences) => void; onReferencesChange?: () => void; onNavigate?: (target: WorkspaceNavigation) => void };
let scopeSequence = 0;
const freshCapture = () => globalThis.crypto?.randomUUID?.() || `note-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const kindLabel = { character: '人物', location: '地点', chapter: '章节参考' };

export function WritingFocusPanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <WritingFocusBody key={identity} {...props} />;
}

function WritingFocusBody({ client, chapter, flags, focusActive, onFocusChange, onPreferencesChange, onReferencesChange, onNavigate }: Props) {
  const api = useMemo(() => writingFocusClient(client), [client]);
  const resource = useResource(signal => api.preferences(signal), [api]);
  const [saved, setSaved] = useState<WritingPreferenceResult>();
  const [preferences, setPreferences] = useState(defaultWritingPreferences);
  const touched = useRef(false), initialized = useRef(false), alive = useRef(true);
  const callbacks = useRef({ onPreferencesChange, onReferencesChange }); callbacks.current = { onPreferencesChange, onReferencesChange };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    if (!resource.data) return;
    setSaved(resource.data);
    if (!initialized.current) {
      initialized.current = true;
      if (!touched.current) {
        setPreferences(resource.data.preferences);
        callbacks.current.onPreferencesChange?.(resource.data.preferences);
      }
    }
  }, [resource.data]);
  const action = useAction();
  const navigation = useAction(), navigationEpoch = useRef(0);
  useLayoutEffect(() => { navigationEpoch.current++; }, [chapter?.id]);
  const openBookmark = onNavigate ? (id: string, revision: string, current = false) => navigation.run(async () => {
    const ticket = ++navigationEpoch.current;
    const target = await api.openBookmark(id, revision, current);
    if (alive.current && ticket === navigationEpoch.current) onNavigate(target);
  }, '已请求打开核对过的章节书签。') : undefined;
  const update = (patch: Partial<WritingFocusPreferences>) => {
    touched.current = true;
    const value = { ...preferences, ...patch };
    setPreferences(value); callbacks.current.onPreferencesChange?.(value);
  };
  const save = (pins: ReferencePin[], typography = preferences, message = '阅读偏好已保存。正文和选区未改变。') => action.run(async () => {
    if (!saved) return;
    const result = await api.savePreferences(saved.version, typography, pins);
    if (!alive.current) return;
    setSaved(result); callbacks.current.onReferencesChange?.();
  }, message);
  return <section className="experimental-section" aria-label="专注写作与灵感">
    <div className="experimental-actions"><h3>专注写作</h3><Badge>不调用模型 · 原编辑器</Badge></div>
    <Panel title="阅读与专注">
      <ResourceState loading={resource.loading} error={resource.error} />
      {saved?.recovery_required && <StatusMessage tone="warning">阅读偏好记录损坏，当前使用默认值。核对后保存可修复，不改正文。</StatusMessage>}
      {!onPreferencesChange && <StatusMessage tone="warning">当前宿主未接入编辑器样式；偏好可以保存，尚不会改变正文显示。</StatusMessage>}
      <div className="experimental-grid">
        <Field label="阅读列宽"><select value={preferences.column_width} onChange={e => update({ column_width: e.target.value as WritingFocusPreferences['column_width'] })}><option value="narrow">窄列</option><option value="comfortable">舒适</option><option value="wide">宽列</option></select></Field>
        <Field label="正文字号"><select value={preferences.font_size} onChange={e => update({ font_size: Number(e.target.value) as WritingFocusPreferences['font_size'] })}>{[16, 18, 20, 24].map(value => <option key={value} value={value}>{value} px</option>)}</select></Field>
        <Field label="正文行距"><select value={preferences.line_height} onChange={e => update({ line_height: Number(e.target.value) as WritingFocusPreferences['line_height'] })}>{[1.5, 1.75, 2].map(value => <option key={value} value={value}>{value} 倍</option>)}</select></Field>
      </div>
      <label className="experimental-check"><input type="checkbox" checked={preferences.paragraph_focus} onChange={e => update({ paragraph_focus: e.target.checked })} />段落聚焦（突出光标所在段落）</label>
      <p>专注模式折叠 AI 检查器；保存状态、冲突和错误仍保留。不会保存正文，也不锁定 AI 编辑。</p>
      <div className="experimental-actions">
        <Button disabled={!onFocusChange} aria-pressed={Boolean(focusActive)} onMouseDown={e => e.preventDefault()} onClick={() => onFocusChange?.(!focusActive)}>{focusActive ? '退出专注' : '进入专注'}</Button>
        <Button disabled={!saved || resource.loading || !!resource.error || action.busy} onClick={() => save(saved!.pins)}>保存阅读偏好</Button>
        <Button disabled={resource.loading || action.busy} onClick={resource.reload}>核对服务器偏好</Button>
        <Button disabled={action.busy} onClick={() => update(defaultWritingPreferences)}>预览默认阅读样式</Button>
      </div>
      <p>仅保存当前作者、项目和分支的偏好。核对服务器不会覆盖尚未保存的阅读设置。</p>
      {action.feedback}
    </Panel>
    <ReferencePicker api={api} saved={saved} busy={action.busy || resource.loading || !!resource.error} save={save} onOpen={openBookmark} navigationBusy={navigation.busy} />
    {navigation.feedback}
    <ChapterSceneOverview api={api} chapter={chapter} saved={saved} busy={action.busy || resource.loading || !!resource.error} save={save} onOpen={openBookmark} navigationBusy={navigation.busy} onNavigate={onNavigate} />
    <InspirationNotes api={api} chapter={chapter} planningEnabled={enabled(flags, 'advanced_planning_v2')} />
  </section>;
}

type FocusApi = ReturnType<typeof writingFocusClient>;
function ReferenceCardBody({ card }: { card: ReferenceCard }) {
  return <><div className="experimental-actions"><strong>{card.title}</strong><Badge>{kindLabel[card.kind]} · 只读</Badge>{card.version && <Badge>v{card.version}</Badge>}</div><p className="writing-reference-text">{card.text || '此资料暂无可展示的描述。'}</p>{card.truncated && <StatusMessage tone="warning">仅展示前 12,000 字，完整内容请到来源查看。</StatusMessage>}</>;
}
type BookmarkOpen = (id: string, revision: string, current?: boolean) => Promise<void>;
function ReferencePicker({ api, saved, busy, save, onOpen, navigationBusy }: { api: FocusApi; saved?: WritingPreferenceResult; busy: boolean; save: (pins: ReferencePin[], typography?: WritingFocusPreferences, message?: string) => Promise<void>; onOpen?: BookmarkOpen; navigationBusy: boolean }) {
  const [input, setInput] = useState(''), [query, setQuery] = useState(''), [kind, setKind] = useState('');
  const references = useResource(signal => api.references(query, kind, signal), [api, query, kind]);
  const pins = useResource(signal => api.pins(signal), [api, saved?.version]);
  const pin = (card: ReferenceCard) => save([...(saved?.pins || []).filter(row => row.kind !== card.kind || row.id !== card.id), { kind: card.kind, id: card.id, revision: card.revision }], saved?.preferences, '已固定核对过的资料。仅保存来源 ID 和版本，不复制资料库。');
  return <Panel title="分屏只读参考">
    <p>固定既有人物、地点或章节卡，最多六张。章节固定卡同时作为章首书签。来源变化后暂停展示旧卡，需要重新核对并固定。不会写入 AI 上下文。</p>
    <ResourceState loading={pins.loading} error={pins.error} />
    {!!pins.error && <Button onClick={pins.reload}>重读固定资料</Button>}
    <div className="experimental-list">{!pins.loading && !pins.error && pins.data?.items.map(row => <article className="experimental-record" key={`${row.kind}:${row.id}`}>
      {row.card ? <ReferenceCardBody card={row.card} /> : <><strong>{row.title}</strong><StatusMessage tone="warning">{row.state === 'STALE' ? '来源已变化。请从下方当前资料重新固定。' : '来源已删除、隐藏或当前无权访问。'}</StatusMessage></>}
      {row.kind === 'chapter' && row.state !== 'UNAVAILABLE' && <Button disabled={!onOpen || navigationBusy} onClick={() => onOpen?.(row.id, row.revision, row.state === 'STALE')}>{row.state === 'STALE' ? '核对并打开当前版本' : '打开章节书签'} {row.title}</Button>}
      <Button disabled={!saved || busy} onClick={() => save(saved!.pins.filter(pin => pin.kind !== row.kind || pin.id !== row.id), saved!.preferences, '已取消固定；来源资料未改变。')}>取消固定 {row.title}</Button>
    </article>)}</div>
    <form className="experimental-form" onSubmit={e => { e.preventDefault(); setQuery(input); references.reload(); }}>
      <Field label="按资料标题查找"><input maxLength={160} value={input} onChange={e => setInput(e.target.value)} /></Field>
      <div className="experimental-actions"><Field label="参考类型"><select value={kind} onChange={e => setKind(e.target.value)}><option value="">全部</option><option value="character">人物</option><option value="location">地点</option><option value="chapter">章节</option></select></Field><Button type="submit">查找参考资料</Button><Button type="button" disabled={references.loading} onClick={references.reload}>刷新当前资料</Button></div>
    </form>
    <ResourceState loading={references.loading} error={references.error} empty={!references.data?.items.length} />
    {references.data && !references.data.branch_sources_available && <StatusMessage tone="warning">当前分支没有已授权的来源适配器，不会展示主分支资料。</StatusMessage>}
    {references.data?.truncated && <StatusMessage tone="warning">最多展示 50 条，请按标题缩小范围。</StatusMessage>}
    {!references.loading && !references.error && <div className="experimental-grid">{references.data?.items.map(card => {
      const existing = saved?.pins.find(row => row.id === card.id && row.kind === card.kind);
      return <article className="experimental-record" key={`${card.kind}:${card.id}`}><ReferenceCardBody card={card} /><Button disabled={!saved || busy || existing?.revision === card.revision || (!existing && saved.pins.length >= 6)} onClick={() => pin(card)}>{existing ? '核对并重新固定' : '固定'} {card.title}</Button></article>;
    })}</div>}
  </Panel>;
}

function ChapterSceneOverview({ api, chapter, saved, busy, save, onOpen, navigationBusy, onNavigate }: { api: FocusApi; chapter?: Chapter; saved?: WritingPreferenceResult; busy: boolean; save: (pins: ReferencePin[], typography?: WritingFocusPreferences, message?: string) => Promise<void>; onOpen?: BookmarkOpen; navigationBusy: boolean; onNavigate?: (target: WorkspaceNavigation) => void }) {
  const [currentOnly, setCurrentOnly] = useState(true);
  const overview = useResource(signal => api.overview(currentOnly ? chapter?.id || '' : '', signal), [api, currentOnly, chapter?.id]);
  return <Panel title="章节与场景概览">
    <p>复用章节树和故事资料库的真实章节、场景 ID。这里仅供阅读；编辑场景仍在故事资料库。章节书签定位到章首，不伪称段落书签。</p>
    <div className="experimental-actions"><label className="experimental-check"><input type="checkbox" checked={currentOnly} disabled={!chapter} onChange={e => setCurrentOnly(e.target.checked)} />仅当前章节</label><Button disabled={overview.loading} onClick={overview.reload}>刷新章节场景概览</Button><Button disabled={!onNavigate} onClick={() => onNavigate?.({ kind: 'feature', id: 'story', feature: 'story' })}>打开故事资料库</Button></div>
    <ResourceState loading={overview.loading} error={overview.error} empty={!overview.data?.items.length} />
    {overview.data && !overview.data.chapter_sources_available && <StatusMessage tone="warning">当前分支没有已授权的章节来源，概览不会借用主分支正文。</StatusMessage>}
    {overview.data && !overview.data.scene_sources_available && <StatusMessage tone="warning">当前分支的场景来源尚未接入。</StatusMessage>}
    {overview.data?.truncated && <StatusMessage tone="warning">最多显示 100 章，请从章节树选择当前章节后查看。</StatusMessage>}
    {!overview.loading && !overview.error && <div className="experimental-list">{overview.data?.items.map(row => {
      const pinned = saved?.pins.find(pin => pin.kind === 'chapter' && pin.id === row.id);
      return <article className="experimental-record" key={row.id}>
        <div className="experimental-actions"><strong>{row.title}</strong><Badge>章节 v{row.version}</Badge><span>{row.word_count} 字 · {row.scene_count} 个已关联场景</span></div>
        <div className="experimental-actions"><Button disabled={!saved || busy || pinned?.revision === row.revision || (!pinned && saved.pins.length >= 6)} onClick={() => save([...(saved?.pins || []).filter(pin => pin.kind !== 'chapter' || pin.id !== row.id), { kind: 'chapter', id: row.id, revision: row.revision }], saved?.preferences, '章节书签已保存，共用固定资料，不复制正文。')}>{pinned ? '更新章节书签' : '设为章节书签'} {row.title}</Button><Button disabled={!onOpen || navigationBusy} onClick={() => onOpen?.(row.id, row.revision)}>打开概览章节 {row.title}</Button></div>
        {!row.scenes.length && <p>此章尚无已关联的场景规划；可到故事资料库关联现有场景。</p>}
        {row.scenes.map(scene => <section key={scene.id} aria-label={`场景概览 ${scene.title}`}><h4>{scene.sequence ? `${scene.sequence}. ` : ''}{scene.title}</h4><dl className="experimental-meta"><dt>场景目标</dt><dd>{scene.purpose || '未填写'}</dd><dt>冲突</dt><dd>{scene.conflict || '未填写'}</dd><dt>结果</dt><dd>{scene.outcome || '未填写'}</dd></dl>{scene.details_truncated && <StatusMessage tone="warning">场景字段仅显示前 2,000 字，完整内容请到故事资料库查看。</StatusMessage>}</section>)}
        {row.scenes_truncated && <StatusMessage tone="warning">仅展示此章前 20 个场景，其余请到故事资料库查看。</StatusMessage>}
      </article>;
    })}</div>}
  </Panel>;
}

export function WritingReferenceRail({ client, revision = 0 }: { client: ExperimentalClient; revision?: number }) {
  const identity = useMemo(() => ++scopeSequence, [client]);
  return <ReferenceRailBody key={identity} client={client} revision={revision} />;
}
function ReferenceRailBody({ client, revision }: { client: ExperimentalClient; revision: number }) {
  const api = useMemo(() => writingFocusClient(client), [client]);
  const pins = useResource(signal => api.pins(signal), [api, revision]);
  if (!pins.loading && !pins.error && !pins.data?.items.length) return null;
  return <aside className="writing-reference-rail" aria-label="写作分屏只读参考">
    <div className="experimental-actions"><strong>只读参考</strong><Button disabled={pins.loading} onClick={pins.reload}>刷新参考</Button></div>
    <ResourceState loading={pins.loading} error={pins.error} />
    {!pins.loading && !pins.error && pins.data?.items.map(row => <article className="experimental-record" key={`${row.kind}:${row.id}`}>{row.card ? <ReferenceCardBody card={row.card} /> : <><strong>{row.title}</strong><StatusMessage tone="warning">{row.state === 'STALE' ? '来源已变化，请到“专注写作”重新核对并固定。' : '资料不可用，请到“专注写作”取消固定或另选来源。'}</StatusMessage></>}</article>)}
  </aside>;
}

function InspirationNotes({ api, chapter, planningEnabled }: { api: FocusApi; chapter?: Chapter; planningEnabled: boolean }) {
  const [archived, setArchived] = useState(false);
  const notes = useResource(signal => api.notes(archived, signal), [api, archived]);
  const [title, setTitle] = useState(''), [text, setText] = useState(''), [linkChapter, setLinkChapter] = useState(false);
  const [editing, setEditing] = useState<InspirationNote>();
  const [copying, setCopying] = useState<InspirationNote>();
  const captureId = useRef(freshCapture()), alive = useRef(true), draftEpoch = useRef(0);
  const action = useAction(notes.reload);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const reset = () => { draftEpoch.current++; setTitle(''); setText(''); setLinkChapter(false); setEditing(undefined); captureId.current = freshCapture(); };
  const save = () => {
    if (!text.trim()) return;
    const epoch = draftEpoch.current;
    const body = { capture_id: editing?.capture_id || captureId.current, title, text, chapter_id: linkChapter ? chapter?.id || null : null, chapter_version: linkChapter ? chapter?.version || null : null };
    return action.run(async () => {
      if (editing) await api.editNote(editing.id, editing.version, body); else await api.createNote(body);
      if (alive.current && draftEpoch.current === epoch) reset();
    }, '灵感已保存为本项目草稿。未进入 Canon、正文或 AI 上下文。');
  };
  const edit = (note: InspirationNote) => { draftEpoch.current++; setEditing(note); setTitle(note.title); setText(note.text); setLinkChapter(Boolean(note.chapter_id && note.chapter_id === chapter?.id)); };
  return <Panel title="快速收集灵感">
    <p>草稿仅当前作者在此项目与分支可见。输入尚未保存时请勿关闭页面；保存不调用模型、不进入 Canon 或 AI 上下文。</p>
    {editing && <StatusMessage>正在编辑「{editing.title || '无标题灵感'}」v{editing.version}。若来源过期，可取消章节关联或核对后关联当前已保存章节。</StatusMessage>}
    <form className="experimental-form" onSubmit={e => { e.preventDefault(); void save(); }}>
      <Field label="灵感标题（可选）"><input maxLength={160} value={title} onChange={e => { draftEpoch.current++; captureId.current = freshCapture(); setTitle(e.target.value); }} /></Field>
      <Field label="灵感内容"><textarea maxLength={10000} value={text} onChange={e => { draftEpoch.current++; captureId.current = freshCapture(); setText(e.target.value); }} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing && e.keyCode !== 229) { e.preventDefault(); void save(); } }} placeholder="随手记录，再决定是否加入规划。Ctrl / ⌘ + Enter 保存。" /></Field>
      <label className="experimental-check"><input type="checkbox" checked={linkChapter} disabled={!chapter} onChange={e => { draftEpoch.current++; captureId.current = freshCapture(); setLinkChapter(e.target.checked); }} />关联当前已保存章节{chapter ? `「${chapter.title}」v${chapter.version}` : '（尚未选择章节）'}</label>
      <div className="experimental-actions"><Button type="submit" disabled={action.busy || !text.trim() || (linkChapter && !chapter)}>{editing ? '保存灵感修改' : '保存灵感草稿'}</Button>{editing && <Button type="button" disabled={action.busy} onClick={reset}>放弃本次编辑</Button>}</div>
    </form>
    {action.feedback}
    <div className="experimental-actions"><Button aria-pressed={!archived} onClick={() => setArchived(false)}>当前草稿</Button><Button aria-pressed={archived} onClick={() => setArchived(true)}>已归档灵感</Button><Button disabled={notes.loading || action.busy} onClick={notes.reload}>核对服务器草稿（保留输入）</Button></div>
    <ResourceState loading={notes.loading} error={notes.error} empty={!notes.data?.items.length} />
    {notes.data?.truncated && <StatusMessage tone="warning">当前最多展示最近 100 条；较早记录仍保留在项目数据中。</StatusMessage>}
    {!notes.loading && !notes.error && <div className="experimental-list">{notes.data?.items.map(note => <article className="experimental-record" key={note.id}>
      <div className="experimental-actions"><strong>{note.title || '无标题灵感'}</strong><Badge>{note.status === 'ARCHIVED' ? '已归档' : '草稿'} · v{note.version}</Badge></div>
      <p className="writing-reference-text">{note.text}</p>
      {['STALE', 'UNAVAILABLE'].includes(note.source_state) && <StatusMessage tone="warning">关联章节已变化或不可用。请先编辑并核对关联，再复制到规划。</StatusMessage>}
      {!!note.copies.length && <p>已复制到 {note.copies.length} 条待审规划；原灵感仍保留。</p>}
      <div className="experimental-actions">{note.status === 'DRAFT' ? <><Button disabled={action.busy} onClick={() => edit(note)}>编辑 {note.title || '灵感'}</Button><Button disabled={action.busy || !planningEnabled || ['STALE', 'UNAVAILABLE'].includes(note.source_state)} onClick={() => setCopying(note)}>核对并复制到规划 {note.title || '灵感'}</Button><Button disabled={action.busy} onClick={() => action.run(() => api.transition(note, 'archive'), '已归档，可从已归档灵感中恢复。')}>归档 {note.title || '灵感'}</Button></> : <Button disabled={action.busy} onClick={() => action.run(() => api.transition(note, 'restore'), '已恢复为草稿。')}>恢复 {note.title || '灵感'}</Button>}</div>
    </article>)}</div>}
    {!planningEnabled && <StatusMessage>分层规划未启用；灵感仍可独立保存和编辑。</StatusMessage>}
    {copying && planningEnabled && <PlanningCopyReview key={`${copying.id}:${copying.version}`} api={api} note={copying} onClose={() => setCopying(undefined)} onCopied={() => { if (alive.current) { setCopying(undefined); notes.reload(); } }} />}
  </Panel>;
}

function PlanningCopyReview({ api, note, onClose, onCopied }: { api: FocusApi; note: InspirationNote; onClose: () => void; onCopied: () => void }) {
  const targets = useResource(signal => api.targets(signal), [api]);
  const [targetId, setTargetId] = useState(''), [field, setField] = useState<CopyInput['field']>('goal');
  const [preview, setPreview] = useState<CopyPreview>();
  const [reviewed, setReviewed] = useState(false);
  const alive = useRef(true), epoch = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const action = useAction();
  const target = targets.data?.items.find(row => row.id === targetId);
  const body = (): CopyInput => ({ expected_version: note.version, node_id: target!.id, expected_node_version: target!.version, field });
  const invalidate = () => { epoch.current++; setPreview(undefined); setReviewed(false); };
  return <section className="experimental-record" aria-label="灵感复制审核">
    <h3>核对复制到规划</h3><p>只创建既有规划服务的 REVIEW 草稿，不替换规划节点、不批准 Canon，也不改正文。</p>
    <ResourceState loading={targets.loading} error={targets.error} />
    <Field label="目标规划节点"><select disabled={action.busy} value={targetId} onChange={e => { invalidate(); setTargetId(e.target.value); }}><option value="">请选择已有规划</option>{targets.data?.items.map(row => <option key={row.id} value={row.id}>{row.title} · {row.level} · v{row.version}</option>)}</select></Field>
    {!targets.loading && !targets.error && !targets.data?.items.length && <EmptyState title="没有可用规划节点" detail="请先在分层规划建立项目或章节规划，然后返回刷新。" />}
    <Field label="追加到规划字段"><select disabled={action.busy} value={field} onChange={e => { invalidate(); setField(e.target.value as CopyInput['field']); }}><option value="goal">目标</option><option value="conflict">冲突</option><option value="turning_point">转折</option></select></Field>
    <div className="experimental-actions"><Button disabled={!target || action.busy || targets.loading || !!targets.error} onClick={() => action.run(async () => { const ticket = ++epoch.current; const result = await api.preview(note.id, body()); if (alive.current && ticket === epoch.current) { setPreview(result); setReviewed(false); } }, '复制预览已生成，请核对追加后的内容。')}>预览规划草稿</Button><Button disabled={action.busy} onClick={() => { invalidate(); targets.reload(); }}>刷新规划版本</Button><Button disabled={action.busy} onClick={onClose}>关闭审核</Button></div>
    {preview && <><div className="experimental-grid"><section><h4>当前规划字段</h4><p className="writing-reference-text">{preview.before || '空'}</p></section><section><h4>待审草稿字段</h4><p className="writing-reference-text">{preview.after}</p></section></div><label className="experimental-check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对「{preview.target_title}」v{preview.target_version} 和上述内容</label><Button disabled={!reviewed || action.busy || !target} onClick={() => action.run(async () => { const ticket = ++epoch.current; try { await api.copy(note.id, body(), preview.preview_digest); if (alive.current && ticket === epoch.current) onCopied(); } catch (error) { if (alive.current) invalidate(); throw error; } }, '已复制为待审规划。')}>确认复制为待审规划</Button></>}
    {action.feedback}
  </section>;
}
