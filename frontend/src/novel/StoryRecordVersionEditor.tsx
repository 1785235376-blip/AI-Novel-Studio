import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, getCollaborationContext } from '../api';
import { enabled, experimentalClient, experimentalFeatures } from '../experimental/api';
import { Button, StatusMessage } from '../ui/primitives';

type Row = Record<string, any>;
type Snapshot = { record: Row; digest: string; version: number; history: Array<{ version: number; record: Row; action: string }>; source_versions?: Array<{ kind: string; id: string; version?: number }>; source_state?: string; stale_sources?: string[]; feedback?: { decision: string; note: string; evidence?: string }; feedback_stale?: boolean };
type Draft = { record: Row; digest: string | null; version: number };
export type StoryEditorProps = { disabled?: boolean; novelId?: string; onDraftChange?: (row: Row) => void; onOpenChapter?: (id: string, signal?: AbortSignal) => void };
type Props = { onOpenChapter?: (id: string, signal?: AbortSignal) => void; novelId: string; kind: 'timeline' | 'foreshadowing'; value?: Row; saving: boolean; onSave: (row: any) => Promise<void> | void; renderEditor: (value: Row | undefined, saving: boolean, save: (row: any) => Promise<void> | void, change?: (row: Row) => void, disabled?: boolean) => ReactNode };

/** Existing Story editor consumer. Feature OFF retains the original V1 call. */
export function StoryRecordVersionEditor(props: Props) {
  const context = getCollaborationContext();
  const identity = [props.novelId, props.kind, props.value?.id || 'new', context.sessionToken, context.actor?.id || '', context.scope?.workspaceId || '', context.scope?.projectId || '', context.scope?.storylineId || '', context.scope?.branchId || ''].join('|');
  return <StoryRecordBody key={identity} {...props} />;
}
function StoryRecordBody({ novelId, kind, value, saving, onSave, renderEditor, onOpenChapter }: Props) {
  const queryClient = useQueryClient();
  const context = useMemo(() => { const c = getCollaborationContext(); return { ...c, scope: c.scope ? { ...c.scope } : undefined }; }, []);
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
  const storageKey = (!context.sessionToken || context.actor?.id) ? `story-record-draft:${context.actor?.id || 'local'}:${novelId}:${kind}:${value?.id || 'new'}` : undefined;
  const describe = (reason: unknown) => reason instanceof ApiError ? reason.status === 409 ? '版本或来源冲突。草稿已保留，请读取最新版本后核对。' : reason.status === 401 || reason.status === 403 ? '当前身份无权访问或权限已撤销。' : reason.status === 404 ? '功能已关闭或原记录不可读。' : '操作未完成，草稿已保留。请重试读取当前版本。' : '网络不可用，草稿已保留。请重试读取当前版本。';
  function persist(next: Draft) { if (storageKey) { try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { setNotice('本地草稿无法持久保存，请保留此页面。'); } } }
  function discard() { if (storageKey) { try { localStorage.removeItem(storageKey); } catch { /* Storage denial never triggers a server mutation. */ } } setRecovery(undefined); }
  useEffect(() => {
    const ticket = ++epoch.current; const controller = new AbortController();
    void (async () => {
      try {
        const flags = await experimentalFeatures(controller.signal, context);
        if (ticket !== epoch.current) return;
        if (!enabled(flags, 'story_record_versions_v1')) { setMode('off'); return; }
        const caps = await client.get<{ can_write: boolean; can_review: boolean }>('/story-records/catalog', controller.signal);
        const row = value?.id ? await client.get<Snapshot>(base + encodeURIComponent(value.id), controller.signal) : undefined;
        if (ticket !== epoch.current) return;
        setCatalog(caps); setCurrent(row); setDraft({ record: row?.record || value || {}, digest: row?.digest || null, version: row?.version || 0 }); setMode('on');
        if (storageKey) { try { const stored = JSON.parse(localStorage.getItem(storageKey) || 'null'); if (stored?.record && typeof stored.version === 'number' && ('digest' in stored)) setRecovery(stored); } catch { /* Invalid local draft cannot become an API request. */ } }
      } catch (reason) { if (ticket === epoch.current && !controller.signal.aborted) { setError(describe(reason)); setMode('error'); } }
    })();
    return () => { ++epoch.current; controller.abort(); sourceNavigation.current?.abort(); };
  }, [client]); // The keyed owner captures one project, record and session.

  async function run(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice(''); const ticket = epoch.current;
    try { await operation(); }
    catch (reason) { if (ticket === epoch.current) { setError(describe(reason)); if (reason instanceof ApiError && reason.status === 409) { setConflict(true); setBaselineRead(false); } if (reason instanceof ApiError && [401,403,404].includes(reason.status)) { setMode('error'); setCurrent(undefined); } } }
    finally { lock.current = false; if (ticket === epoch.current) setBusy(false); }
  }
  async function reload(keepDraft = true) {
    const ticket = epoch.current;
    const caps = await client.get<{ can_write: boolean; can_review: boolean }>('/story-records/catalog');
    const id = current?.record.id || value?.id || draft.record.id;
    const row = id ? await client.get<Snapshot>(base + encodeURIComponent(id)) : undefined;
    if (ticket !== epoch.current) return;
    setCatalog(caps); setCurrent(row); setMode('on'); setRestore(undefined); setBaselineRead(true);
    if (keepDraft && row && (draft.digest !== row.digest || draft.version !== row.version)) setConflict(true);
    if (!keepDraft) { setDraft({ record: row?.record || value || {}, digest: row?.digest || null, version: row?.version || 0 }); setConflict(false); discard(); }
  }
  async function committed(row: Snapshot, ticket: number) {
    if (ticket !== epoch.current) return;
    setCurrent(row); setDraft({ record: row.record, digest: row.digest, version: row.version }); setConflict(false); setRestore(undefined); discard(); setRefreshSources(false);
    setNotice(`已保存版本 ${row.version}。`);
    await queryClient.invalidateQueries({ queryKey: ['story-database'] });
  }
  async function save(record: Row) {
    const pending = { ...draft, record }; setDraft(pending); persist(pending);
    await run(async () => {
      const ticket = epoch.current; const { id, privacy_status, _story_record, ...payload } = record;
      // Opaque imports remain server-owned. Only the established editor fields
      // are sent, so unknown extensions cannot be silently discarded.
      const fields = kind === 'timeline' ? ['title','sequence','time','description','location','characters','chapter_id','status','privacy_level'] : ['title','description','planted_chapter','target_chapter','status','characters','events','privacy_level'];
      const known = Object.fromEntries(Object.entries(payload).filter(([key]) => fields.includes(key)));
      const row = await client.put<Snapshot>(base + encodeURIComponent(id), { record: known, expected_digest: draft.digest, expected_version: draft.version, refresh_sources: refreshSources });
      await committed(row, ticket);
    });
  }
  if (mode === 'off') return <>{renderEditor(value, saving, onSave)}</>;
  if (mode === 'loading') return <p role="status">正在读取资料版本配置…</p>;
  if (mode === 'error') return <><p role="alert">{error}</p><Button disabled={busy} onClick={() => void run(() => reload(true))}>重试读取资料版本</Button></>;
  const blocked = busy || !catalog?.can_write;
  return <section aria-label="故事资料版本与恢复">
    <StatusMessage>项目共享资料 · {current ? `版本 ${current.version}` : '新记录'} · {current?.source_state || '来源随保存记录'}</StatusMessage>
    {!storageKey && <StatusMessage tone="warning">当前会话尚未确认作者身份，草稿只保留在本页，请勿关闭。</StatusMessage>}
    {!catalog?.can_write && <StatusMessage tone="warning">只读身份：保存与恢复需要项目写入权限。</StatusMessage>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {recovery && <><StatusMessage tone="warning">发现尚未提交的本地草稿。</StatusMessage><Button disabled={busy} onClick={() => { setDraft(recovery); setBaselineRead(true); setConflict(!!current && (recovery.digest !== current.digest || recovery.version !== current.version)); setRecovery(undefined); }}>恢复本地草稿</Button></>}
    {renderEditor(draft.record, busy, save, record => { const next = { ...draft, record }; setDraft(next); persist(next); }, !catalog?.can_write || conflict)}
    <div className="novel-actions">
      <Button disabled={busy} onClick={() => { sourceNavigation.current?.abort(); setDraft({ record: current?.record || value || {}, digest: current?.digest || null, version: current?.version || 0 }); setConflict(false); setBaselineRead(false); setError(''); setRestore(undefined); discard(); setNotice('已取消未提交的编辑。'); }}>取消编辑</Button>
      <Button disabled={busy} onClick={() => void run(() => reload(true))}>读取最新版本</Button>
      {conflict && baselineRead && current && <Button disabled={busy || !catalog?.can_write} onClick={() => { const next = { ...draft, digest: current.digest, version: current.version }; setDraft(next); persist(next); setConflict(false); setNotice('已保留草稿并采用显示的最新版本基线，请核对后再保存。'); }}>核对后保留草稿并采用最新基线</Button>}
    </div>
    {conflict && baselineRead && current && <details open><summary>最新服务器记录，版本 {current.version}</summary><p>{current.record.title}</p><p>{current.record.description}</p></details>}
    {current?.source_state === 'STALE' && <label><input type="checkbox" checked={refreshSources} onChange={e => setRefreshSources(e.target.checked)} />我已核对来源变化，下次保存刷新来源版本</label>}
    {current?.source_versions?.map(source => <p className="novel-help" key={`${source.kind}:${source.id}`}>来源：{source.kind} · {source.id}{source.version !== undefined ? ` · v${source.version}` : ''}{source.kind === 'chapter' && <Button disabled={busy || !onOpenChapter || current.stale_sources?.includes(source.id)} onClick={() => { sourceNavigation.current?.abort(); const controller = new AbortController(); sourceNavigation.current = controller; onOpenChapter?.(source.id, controller.signal); }}>打开来源章节 {source.id}</Button>}{current.stale_sources?.includes(source.id) && ' · 来源已改变或不可用，请重新核对'}</p>)}
    {current && <details><summary>版本历史与人工反馈（最多 20 版）</summary>
      {!current.history.length && <p>尚无历史版本。首次修改后会保留原记录。</p>}
      {current.history.map(row => <div key={row.version}><span>v{row.version} · {row.record.title} · {row.action}</span><Button disabled={blocked} onClick={() => setRestore(row.version)}>预览恢复 v{row.version}</Button></div>)}
      {restore !== undefined && <div role="region" aria-label="恢复版本确认"><p>恢复 v{restore} 会创建新当前版本，不删除历史。来源可能已过期。</p><p>{current.history.find(row => row.version === restore)?.record.description}</p><p>恢复的隐私级别：{current.history.find(row => row.version === restore)?.record.privacy_level || 'LOCAL_ONLY'}</p><Button disabled={blocked} onClick={() => void run(async () => { const ticket = epoch.current; const row = await client.post<Snapshot>(base + encodeURIComponent(current.record.id) + '/restore', { expected_digest: current.digest, expected_version: current.version, restore_version: restore, confirmed: true }); await committed(row, ticket); })}>确认恢复为新版本</Button><Button disabled={busy} onClick={() => setRestore(undefined)}>取消恢复</Button></div>}
      {current.feedback && <p>人工反馈：{current.feedback.decision} · {current.feedback.note}{current.feedback.evidence ? ` · 依据：${current.feedback.evidence}` : ''} {current.feedback_stale && '（已过期）'}</p>}
      <label>反馈决定<select value={decision} onChange={e => setDecision(e.target.value)}><option value="ACKNOWLEDGED">已核对</option><option value="INTENTIONAL">有意安排</option><option value="NEEDS_REVIEW">需要复查</option><option value="DISMISSED">忽略此版本</option></select></label>
      <label>反馈说明<textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)} /></label>
      <label>反馈依据<textarea maxLength={4000} value={evidence} onChange={e => setEvidence(e.target.value)} /></label>
      <Button disabled={busy || !catalog?.can_review || !!current.feedback && !current.feedback_stale || current.source_state === 'STALE'} onClick={() => void run(async () => { const ticket = epoch.current; const row = await client.post<Snapshot>(base + encodeURIComponent(current.record.id) + '/feedback', { expected_digest: current.digest, expected_version: current.version, decision, note, evidence }); await committed(row, ticket); })}>提交此版本人工反馈</Button>
      <p className="novel-help">人工反馈是此来源版本的最终决定。资料改变后会显示过期，不会改写原决定。</p>
    </details>}
  </section>;
}
