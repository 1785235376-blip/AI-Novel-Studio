import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, getCollaborationContext, type CollaborationContext } from '../api';
import { enabled, experimentalClient, experimentalFeatures } from '../experimental/api';
import { Button, StatusMessage } from '../ui/primitives';

type Row = Record<string, any>;
type StoryKind = 'timeline' | 'foreshadowing' | 'characters' | 'locations' | 'relationships';
const editableFields: Record<StoryKind, string[]> = {
  timeline: ['title', 'sequence', 'time', 'description', 'location', 'characters', 'chapter_id', 'status', 'privacy_level'],
  foreshadowing: ['title', 'description', 'planted_chapter', 'target_chapter', 'status', 'characters', 'events', 'privacy_level'],
  characters: ['name', 'age', 'role', 'personality', 'goal', 'current_location', 'status', 'privacy_level'],
  locations: ['name', 'location_type', 'description', 'rules', 'atmosphere', 'status', 'privacy_level'],
  relationships: ['source_character_id', 'target_character_id', 'relationship_type', 'description', 'status', 'valid_from_event_id', 'valid_to_event_id', 'certainty', 'privacy_level'],
};
const fieldLabels: Record<string, string> = { title: '标题', name: '名称', age: '年龄', role: '身份 / 定位', personality: '性格', goal: '当前目标', current_location: '当前位置', location_type: '地点类型', description: '描述', rules: '特殊规则', atmosphere: '氛围', source_character_id: '人物 A', target_character_id: '人物 B', relationship_type: '关系类型', status: '状态', valid_from_event_id: '关系开始事件', valid_to_event_id: '关系结束事件', certainty: '可信度', sequence: '顺序', time: '故事时间', location: '地点', characters: '关联人物', events: '关联事件', chapter_id: '关联章节', planted_chapter: '埋设章节', target_chapter: '目标回收章节', privacy_level: '隐私级别' };
function recordTitle(record: Row) { return record.name || record.title || [record.source_character_id, record.relationship_type, record.target_character_id].filter(Boolean).join(' · ') || record.id; }
function RecordSummary({ record, kind }: { record: Row; kind: StoryKind }) {
  return <><p>{recordTitle(record)}</p>{editableFields[kind].filter(key => !['name', 'title'].includes(key) && record[key] !== undefined && record[key] !== null && record[key] !== '').map(key => <p key={key}>{fieldLabels[key]}：{Array.isArray(record[key]) ? record[key].join('、') : String(record[key])}</p>)}</>;
}
function contextIdentity(context: CollaborationContext) {
  return JSON.stringify([context.sessionToken, context.actor?.id || '', context.actor?.workspaceId || '', context.scope?.workspaceId || '', context.scope?.projectId || '', context.scope?.storylineId || '', context.scope?.branchId || '']);
}
type Snapshot = { record: Row; digest: string; version: number; history: Array<{ version: number; record: Row; action: string }>; source_versions?: Array<{ kind: string; id: string; version?: number }>; source_state?: string; stale_sources?: string[]; feedback?: { decision: string; note: string; evidence?: string }; feedback_stale?: boolean };
type Draft = { record: Row; digest: string | null; version: number };
export type StoryEditorProps = { disabled?: boolean; novelId?: string; onDraftChange?: (row: Row) => void; onOpenChapter?: (id: string, signal?: AbortSignal) => void };
type Props = { onOpenChapter?: (id: string, signal?: AbortSignal) => void; novelId: string; kind: StoryKind; value?: Row; saving: boolean; onSave: (row: any) => Promise<void> | void; renderEditor: (value: Row | undefined, saving: boolean, save: (row: any) => Promise<void> | void, change?: (row: Row) => void, disabled?: boolean) => ReactNode };

/** Existing Story editor consumer. Feature OFF retains the original V1 call. */
export function StoryRecordVersionEditor(props: Props) {
  const context = getCollaborationContext();
  const identity = JSON.stringify([props.novelId, props.kind, props.value?.id || null, contextIdentity(context)]);
  return <StoryRecordBody key={identity} {...props} />;
}
function StoryRecordBody({ novelId, kind, value, saving, onSave, renderEditor, onOpenChapter }: Props) {
  const queryClient = useQueryClient();
  const context = useMemo(() => { const c = getCollaborationContext(); return { ...c, actor: c.actor ? { ...c.actor } : undefined, scope: c.scope ? { ...c.scope } : undefined }; }, []);
  const client = useMemo(() => experimentalClient(novelId, context), [novelId, context]);
  const base = `/story-records/${kind}/`;
  const [mode, setMode] = useState<'loading' | 'off' | 'on' | 'error'>('loading');
  const [catalog, setCatalog] = useState<{ can_write: boolean; can_review: boolean }>();
  const [current, setCurrent] = useState<Snapshot>();
  const [draft, setDraft] = useState<Draft>({ record: value || {}, digest: null, version: 0 });
  const [recovery, setRecovery] = useState<Draft>();
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false); const [conflict, setConflict] = useState(false);
  const [baselineRead, setBaselineRead] = useState(false);
  const [restore, setRestore] = useState<number>(); const [refreshSources, setRefreshSources] = useState(false);
  const [decision, setDecision] = useState('ACKNOWLEDGED'); const [note, setNote] = useState(''); const [evidence, setEvidence] = useState('');
  const epoch = useRef(0); const lock = useRef(false); const sourceNavigation = useRef<AbortController>();
  const initialized = useRef(false); const dirty = useRef(false);
  const ownerIdentity = contextIdentity(context);
  const active = (ticket: number) => ticket === epoch.current && ownerIdentity === contextIdentity(getCollaborationContext());
  // Unscoped local keys remain compatible; collaboration drafts never share this
  // namespace or persist authentication tokens. Reopening always checks access first.
  const storageKey = context.sessionToken && !context.actor?.id ? undefined : !context.sessionToken && !context.actor && !context.scope && value?.id !== 'new' && ['timeline', 'foreshadowing'].includes(kind)
    ? `story-record-draft:local:${novelId}:${kind}:${value?.id || 'new'}`
    : `story-record-draft:v2:${JSON.stringify([context.actor?.id || 'local', context.actor?.workspaceId || '', novelId, kind, value?.id || null, context.scope?.workspaceId || '', context.scope?.projectId || '', context.scope?.storylineId || '', context.scope?.branchId || ''])}`;
  const describe = (reason: unknown) => reason instanceof ApiError ? reason.status === 409 ? '版本或来源冲突。草稿已保留，请读取最新版本后核对。' : reason.status === 401 || reason.status === 403 ? '当前身份无权访问或权限已撤销。' : reason.status === 404 ? '功能已关闭或原记录不可读。' : '操作未完成，草稿已保留。请重试读取当前版本。' : '网络不可用，草稿已保留。请重试读取当前版本。';
  function persist(next: Draft) { if (storageKey) { try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { setNotice('本地草稿无法持久保存，请保留此页面。'); } } }
  function discard() { if (storageKey) { try { localStorage.removeItem(storageKey); } catch { /* Storage denial never triggers a server mutation. */ } } setRecovery(undefined); }
  function readRecovery() {
    if (!storageKey) return;
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (!stored?.record || typeof stored.record !== 'object' || Array.isArray(stored.record) || !Number.isInteger(stored.version) || stored.version < 0 || !(stored.digest === null && stored.version === 0 || typeof stored.digest === 'string' && stored.digest.length > 0)) return;
      if (stored.record.id !== undefined && (typeof stored.record.id !== 'string' || value?.id && stored.record.id !== value.id)) return;
      for (const key of editableFields[kind]) {
        const field = stored.record[key];
        if (field === undefined || field === null && ['age', 'sequence', 'planted_chapter', 'target_chapter'].includes(key)) continue;
        if (['characters', 'events'].includes(key) ? !Array.isArray(field) || field.some((item: unknown) => typeof item !== 'string') : ['age', 'sequence', 'planted_chapter', 'target_chapter'].includes(key) ? typeof field !== 'number' || !Number.isFinite(field) : typeof field !== 'string') return;
      }
      // Do not let a corrupted draft replace the selected record's identity.
      setRecovery({ record: { ...stored.record, ...(value?.id ? { id: value.id } : {}) }, digest: stored.digest, version: stored.version });
    } catch { /* Invalid local data cannot become an API request. */ }
  }
  useEffect(() => {
    const ticket = ++epoch.current; const controller = new AbortController();
    void (async () => {
      try {
        const flags = await experimentalFeatures(controller.signal, context);
        if (!active(ticket)) return;
        if (!enabled(flags, 'story_record_versions_v1')) { setMode('off'); return; }
        const caps = await client.get<{ can_write: boolean; can_review: boolean }>('/story-records/catalog', controller.signal);
        if (!active(ticket)) return;
        const row = value?.id ? await client.get<Snapshot>(base + encodeURIComponent(value.id), controller.signal) : undefined;
        if (!active(ticket)) return;
        initialized.current = true; setCatalog(caps); setCurrent(row); setDraft({ record: row?.record || value || {}, digest: row?.digest || null, version: row?.version || 0 }); setMode('on');
        readRecovery();
      } catch (reason) { if (active(ticket) && !controller.signal.aborted) { setError(describe(reason)); setMode('error'); } }
    })();
    return () => { ++epoch.current; controller.abort(); sourceNavigation.current?.abort(); };
  }, [client]); // The keyed owner captures one project, record and session.

  async function run(operation: () => Promise<void>) {
    if (lock.current || !active(epoch.current)) return;
    lock.current = true; setBusy(true); setError(''); setNotice(''); const ticket = epoch.current;
    try { await operation(); }
    catch (reason) { if (active(ticket)) { setError(describe(reason)); if (reason instanceof ApiError && reason.status === 409) { setConflict(true); setBaselineRead(false); } if (reason instanceof ApiError && [401,403,404].includes(reason.status)) { sourceNavigation.current?.abort(); setMode('error'); setCurrent(undefined); setCatalog(undefined); setRestore(undefined); setRefreshSources(false); } } }
    finally { lock.current = false; if (active(ticket)) setBusy(false); }
  }
  async function reload(keepDraft = true) {
    const ticket = epoch.current;
    const [flags, caps] = await Promise.all([experimentalFeatures(undefined, context), client.get<{ can_write: boolean; can_review: boolean }>('/story-records/catalog')]);
    if (!active(ticket)) return;
    if (!enabled(flags, 'story_record_versions_v1')) throw new ApiError({ status: 404, code: 'STORY_VERSIONS_DISABLED', message: 'Disabled' });
    const id = current?.record.id || value?.id || draft.record.id;
    const row = id ? await client.get<Snapshot>(base + encodeURIComponent(id)) : undefined;
    if (!active(ticket)) return;
    setCatalog(caps); setCurrent(row); setMode('on'); setRestore(undefined); setRefreshSources(false); setBaselineRead(true);
    if (!initialized.current) { initialized.current = true; setDraft({ record: row?.record || value || {}, digest: row?.digest || null, version: row?.version || 0 }); readRecovery(); return; }
    if (keepDraft && row && (draft.digest !== row.digest || draft.version !== row.version)) setConflict(true);
    if (!keepDraft) { setDraft({ record: row?.record || value || {}, digest: row?.digest || null, version: row?.version || 0 }); setConflict(false); discard(); }
  }
  function recover() {
    if (!recovery || lock.current || !active(epoch.current)) return;
    const recovered = recovery;
    const apply = (row?: Snapshot) => {
      if (row) setCurrent(row);
      dirty.current = true; setDraft(recovered); setBaselineRead(true);
      setConflict(!!row && (recovered.digest !== row.digest || recovered.version !== row.version)); setRecovery(undefined);
    };
    if (current || recovered.version === 0) { apply(current); return; }
    // A draft left in the new-record editor can already have a saved identity.
    // Resolve its current owner before exposing a recovered nonzero baseline.
    void run(async () => {
      const ticket = epoch.current;
      if (!recovered.record.id) throw new ApiError({ status: 404, code: 'STORY_RECORD_MISSING', message: 'Missing' });
      const row = await client.get<Snapshot>(base + encodeURIComponent(recovered.record.id));
      if (active(ticket)) apply(row);
    });
  }
  async function committed(row: Snapshot, ticket: number, keepEdits = false) {
    if (!active(ticket)) return;
    const retain = keepEdits && dirty.current;
    const next = { record: retain ? draft.record : row.record, digest: row.digest, version: row.version };
    setCurrent(row); setDraft(next); setConflict(false); setRestore(undefined);
    if (retain) persist(next); else { dirty.current = false; discard(); }
    setRefreshSources(false);
    setNotice(`已保存版本 ${row.version}。`);
    await queryClient.invalidateQueries({ queryKey: ['story-database'] });
  }
  async function save(record: Row) {
    if (lock.current || !active(epoch.current) || mode !== 'on' || !catalog?.can_write || conflict || saving) return;
    record = { ...record, id: current?.record.id || value?.id || draft.record.id || record.id };
    const pending = { ...draft, record }; setDraft(pending); persist(pending);
    await run(async () => {
      const ticket = epoch.current; const { id, privacy_status, _story_record, ...payload } = record;
      // Opaque imports remain server-owned. Only the established editor fields
      // are sent, so unknown extensions cannot be silently discarded.
      const fields = editableFields[kind];
      const known = Object.fromEntries(Object.entries(payload).filter(([key]) => fields.includes(key)));
      if (kind === 'characters') known.age = record.age ?? null;
      // These forms do not review privacy policy. A derived fail-closed value
      // must not accidentally acknowledge an imported UNKNOWN policy.
      if (privacy_status === 'UNKNOWN') delete known.privacy_level;
      const row = await client.put<Snapshot>(base + encodeURIComponent(id), { record: known, expected_digest: draft.digest, expected_version: draft.version, refresh_sources: refreshSources });
      await committed(row, ticket);
    });
  }
  if (mode === 'off') return <>{renderEditor(value, saving, onSave)}</>;
  if (mode === 'loading') return <p role="status">正在读取资料版本配置…</p>;
  if (mode === 'error') return <><p role="alert">{error}</p><Button disabled={busy} onClick={() => void run(() => reload(true))}>重试读取资料版本</Button></>;
  const blocked = busy || !catalog?.can_write || conflict;
  return <section aria-label="故事资料版本与恢复">
    <StatusMessage>项目共享资料 · {current ? `版本 ${current.version}` : '新记录'} · {current?.source_state || '来源随保存记录'}</StatusMessage>
    {!storageKey && <StatusMessage tone="warning">当前会话尚未确认作者身份，草稿只保留在本页，请勿关闭。</StatusMessage>}
    {!catalog?.can_write && <StatusMessage tone="warning">只读身份：保存与恢复需要项目写入权限。</StatusMessage>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {recovery && <><StatusMessage tone="warning">发现尚未提交的本地草稿。</StatusMessage><Button disabled={busy} onClick={recover}>恢复本地草稿</Button></>}
    {renderEditor(draft.record, busy, save, record => { if (lock.current || !active(epoch.current)) return; dirty.current = true; const next = { ...draft, record }; setDraft(next); persist(next); }, !catalog?.can_write || conflict)}
    <div className="novel-actions">
      <Button disabled={busy} onClick={() => { sourceNavigation.current?.abort(); dirty.current = false; setRefreshSources(false); setDraft({ record: current?.record || value || {}, digest: current?.digest || null, version: current?.version || 0 }); setConflict(false); setBaselineRead(false); setError(''); setRestore(undefined); discard(); setNotice('已取消未提交的编辑。'); }}>取消编辑</Button>
      <Button disabled={busy} onClick={() => void run(() => reload(true))}>读取最新版本</Button>
      {conflict && baselineRead && current && <Button disabled={busy || !catalog?.can_write} onClick={() => { const next = { ...draft, digest: current.digest, version: current.version }; setDraft(next); persist(next); setConflict(false); setNotice('已保留草稿并采用显示的最新版本基线，请核对后再保存。'); }}>核对后保留草稿并采用最新基线</Button>}
    </div>
    {conflict && baselineRead && current && <details open><summary>最新服务器记录，版本 {current.version}</summary><RecordSummary record={current.record} kind={kind}/></details>}
    {current?.source_state === 'STALE' && <label><input type="checkbox" disabled={busy || !catalog?.can_write} checked={refreshSources} onChange={e => setRefreshSources(e.target.checked)} />我已核对来源变化，下次保存刷新来源版本</label>}
    {current?.source_versions?.map(source => <p className="novel-help" key={`${source.kind}:${source.id}`}>来源：{source.kind} · {source.id}{source.version !== undefined ? ` · v${source.version}` : ''}{source.kind === 'chapter' && <Button disabled={busy || !onOpenChapter || current.stale_sources?.includes(source.id)} onClick={() => { sourceNavigation.current?.abort(); const controller = new AbortController(); sourceNavigation.current = controller; onOpenChapter?.(source.id, controller.signal); }}>打开来源章节 {source.id}</Button>}{current.stale_sources?.includes(source.id) && ' · 来源已改变或不可用，请重新核对'}</p>)}
    {current && <details><summary>版本历史与人工反馈（最多 20 版）</summary>
      {!current.history.length && <p>尚无历史版本。首次修改后会保留原记录。</p>}
      {current.history.map(row => <div key={row.version}><span>v{row.version} · {recordTitle(row.record)} · {row.action}</span><Button disabled={blocked} onClick={() => setRestore(row.version)}>预览恢复 v{row.version}</Button></div>)}
      {restore !== undefined && <div role="region" aria-label="恢复版本确认"><p>恢复 v{restore} 会创建新当前版本，不删除历史。来源可能已过期。</p><RecordSummary record={current.history.find(row => row.version === restore)?.record || {}} kind={kind}/><p>恢复的隐私级别：{current.history.find(row => row.version === restore)?.record.privacy_level || 'LOCAL_ONLY'}</p><Button disabled={blocked} onClick={() => void run(async () => { const ticket = epoch.current; const row = await client.post<Snapshot>(base + encodeURIComponent(current.record.id) + '/restore', { expected_digest: current.digest, expected_version: current.version, restore_version: restore, confirmed: true }); await committed(row, ticket); })}>确认恢复为新版本</Button><Button disabled={busy} onClick={() => setRestore(undefined)}>取消恢复</Button></div>}
      {current.feedback && <p>人工反馈：{current.feedback.decision} · {current.feedback.note}{current.feedback.evidence ? ` · 依据：${current.feedback.evidence}` : ''} {current.feedback_stale && '（已过期）'}</p>}
      <label>反馈决定<select value={decision} onChange={e => setDecision(e.target.value)}><option value="ACKNOWLEDGED">已核对</option><option value="INTENTIONAL">有意安排</option><option value="NEEDS_REVIEW">需要复查</option><option value="DISMISSED">忽略此版本</option></select></label>
      <label>反馈说明<textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)} /></label>
      <label>反馈依据<textarea maxLength={4000} value={evidence} onChange={e => setEvidence(e.target.value)} /></label>
      <Button disabled={busy || conflict || !catalog?.can_review || !!current.feedback && !current.feedback_stale || current.source_state === 'STALE'} onClick={() => void run(async () => { const ticket = epoch.current; const row = await client.post<Snapshot>(base + encodeURIComponent(current.record.id) + '/feedback', { expected_digest: current.digest, expected_version: current.version, decision, note, evidence }); await committed(row, ticket, true); })}>提交此版本人工反馈</Button>
      <p className="novel-help">人工反馈是此来源版本的最终决定。资料改变后会显示过期，不会改写原决定。</p>
    </details>}
  </section>;
}
