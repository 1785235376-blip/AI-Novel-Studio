/**
 * [HERMIA-FE-20261023 M1-s3 / M2 start] Real novel business panels for the ?uw=1 preview.
 * - Registered through the EXISTING workbench PanelRegistry (contract §1) with capability status.
 * - Outline reuses rebuild/novel/NovelStructureRail (the same component LegacyApp mounts) — not a copy.
 * - Inspector shows the selected chapter's real properties; title edit registers a DirtySource so closing
 *   with unsaved edits goes through the dirty-close guard. Save runs the registry action `novel.chapter.rename`
 *   (api.renameChapter, POST with optimistic version) — success only when the server returns the chapter.
 * - `novel.chapters.refresh` is a GET-only action whose success source is the refetch result.
 * - Load path is GET only (/api/novels, /api/novels/{id}/chapters). No model calls.
 */
import {useEffect, useRef, useState} from 'react';
import {useQuery, useQueryClient, type QueryClient} from '@tanstack/react-query';
import {api, ApiError, type Chapter, type Novel} from '../../api';
import {NovelStructureRail} from '../../rebuild/novel/NovelStructureRail';
import {PanelRegistry, type PanelDefinition} from '../../workbench/panels';
import type {ActionContext, ActionRegistry} from '../../workbench/actions';
import type {PanelRenderApi} from '../layout/DockLayout';
import '../../rebuild/novel/novelRebuild.css';

export const NOVEL_PREVIEW_PANELS: PanelDefinition[] = [
  {id: 'outline', kind: 'feature', title: '作品结构', capability: 'connected', instancing: 'singleton', docks: ['left', 'right', 'main'], defaultDock: 'left', minWidth: 180, requiresContext: ['project']},
  {id: 'inspector', kind: 'inspector', title: '章节属性', capability: 'partial', instancing: 'singleton', docks: ['left', 'right', 'bottom'], defaultDock: 'right', minWidth: 240, requiresContext: ['project', 'document']},
];
export function createPreviewPanelRegistry(): PanelRegistry {
  const r = new PanelRegistry(false); for (const d of NOVEL_PREVIEW_PANELS) r.register(d); return r;
}

export const NOVEL_ACTION_IDS = {rename: 'novel.chapter.rename', refresh: 'novel.chapters.refresh'} as const;
export const chaptersKey = (novelId: string) => ['uw-preview', 'chapters', novelId] as const;
export const NOVELS_KEY = ['uw-preview', 'novels'] as const;

/** Honest load-state classification (contract §1: loading / error / empty / not-connected). */
export function classifyError(e: unknown): 'not-connected' | 'error' {
  if (e instanceof ApiError) return e.status === 502 || e.status === 503 || e.status === 504 ? 'not-connected' : 'error';
  return e instanceof TypeError ? 'not-connected' : 'error';
}
const ERR_TEXT = {'not-connected': '后端未连接，无法读取作品数据。请确认本地服务已启动后重试。', error: '读取失败，请稍后重试。'} as const;

export function pickDefaultNovel(novels: Novel[]): Novel | undefined {
  return novels.find(n => n.title.includes('雾港')) ?? novels.find(n => n.chapter_count > 0) ?? novels[0];
}

// [HERMIA-FE-20261023 M1-s3fix] Rename is confirmed only when the server returns the chapter JSON with a
// numeric version strictly greater than the one we sent (and the requested title). Anything else
// (same version, missing version, 204/empty body, non-JSON) is NOT a save: the draft stays dirty.
export const RENAME_UNCONFIRMED_TEXT = '保存没有确认，服务器未返回新版本，修改还在。';
// [HERMIA-FE-20261023 M1-s3fix2] fetch rejection (network down) is a real failure, not "no new version".
// [HERMIA-FE-20261023 M1-flaky2] P4: status line aligned with the close-confirm dialog wording (sentence break, 「面板里」).
export const RENAME_NETWORK_TEXT = '保存失败：网络错误。修改还在面板里。';
export class RenameNetworkError extends Error { constructor() { super(RENAME_NETWORK_TEXT); this.name = 'RenameNetworkError'; } }
export class RenameUnconfirmedError extends Error { constructor() { super(RENAME_UNCONFIRMED_TEXT); this.name = 'RenameUnconfirmedError'; } }
export function isConfirmedRename(saved: unknown, i: {chapterId: string; title: string; version: number}): saved is Chapter {
  if (!saved || typeof saved !== 'object') return false;
  const c = saved as Partial<Chapter>;
  return typeof c.version === 'number' && Number.isFinite(c.version) && c.version > i.version
    && (c.id === undefined || c.id === i.chapterId) && c.title === i.title;
}
export type RenameInput = {chapterId: string; novelId: string; title: string; version: number};
/** Registers the two real business actions. Returns an unregister function. */
export function registerNovelPreviewActions(reg: ActionRegistry, qc: QueryClient, getNovelId: () => string | null): () => void {
  const offs = [
    reg.register({
      id: NOVEL_ACTION_IDS.rename, label: '保存章节标题', surfaces: ['button', 'commandSearch'],
      visible: ctx => !!ctx.input,
      available: ctx => {
        const i = ctx.input as RenameInput | undefined;
        if (!i) return {enabled: false, reason: '请先在属性里选中章节'};
        if (!i.title.trim()) return {enabled: false, reason: '标题不能为空'};
        return {enabled: true};
      },
      run: async ctx => {
        const i = ctx.input as RenameInput;
        let saved: unknown;
        try { saved = await api.renameChapter(i.chapterId, i.title.trim(), i.version); }
        catch (e) {
          if (e instanceof ApiError) throw e;
          if (e instanceof SyntaxError) throw new RenameUnconfirmedError(); // non-JSON body
          throw new RenameNetworkError(); // fetch rejected / network error [HERMIA-FE-20261023 M1-s3fix2]
        }
        if (!isConfirmedRename(saved, {...i, title: i.title.trim()})) throw new RenameUnconfirmedError();
        // Real success source: the server's returned chapter (new version). Refresh the list from the server.
        await qc.invalidateQueries({queryKey: chaptersKey(i.novelId)});
        return saved;
      },
    }),
    reg.register({
      id: NOVEL_ACTION_IDS.refresh, label: '刷新章节列表', surfaces: ['button', 'commandSearch'],
      available: () => getNovelId() ? {enabled: true} : {enabled: false, reason: '还没有选中作品'},
      run: async () => {
        const id = getNovelId()!;
        const r = await qc.refetchQueries({queryKey: chaptersKey(id), exact: true}, {throwOnError: true});
        return r;
      },
    }),
  ];
  return () => offs.forEach(f => f());
}

const STATUS_ZH: Record<string, string> = {Draft: '草稿', Writing: '写作中', Review: '待审', Done: '已完成', Final: '定稿', Published: '已发布'};
export const statusZh = (s?: string) => (s ? STATUS_ZH[s] ?? '其他状态' : '未设置');

/** Outline: existing NovelStructureRail fed by real GET data. */
export function OutlinePanel({novelId, novels, onNovel, selectedId, onSelect, blockedNotice, ctx, actions}: {
  novelId: string | null; novels: {data?: Novel[]; isLoading: boolean; error: unknown}; onNovel: (id: string) => void;
  selectedId?: string; onSelect: (id: string) => void; blockedNotice?: string | null;
  ctx: () => ActionContext; actions: ActionRegistry;
}) {
  const chapters = useQuery({queryKey: chaptersKey(novelId ?? ''), queryFn: () => api.chapters(novelId!), enabled: !!novelId, retry: false});
  const [msg, setMsg] = useState('');
  if (novels.isLoading) return <p className="uw-state" role="status" data-state="loading">正在读取作品…</p>;
  if (novels.error) return <p className="uw-state" role="alert" data-state={classifyError(novels.error)}>{ERR_TEXT[classifyError(novels.error)]}</p>;
  if (!novels.data?.length) return <p className="uw-state" data-state="empty">还没有作品。</p>;
  const errKind = chapters.error ? classifyError(chapters.error) : null;
  const refresh = async () => {
    const r = await actions.execute(NOVEL_ACTION_IDS.refresh, ctx());
    setMsg(r.status === 'done' ? '已刷新' : r.status === 'blocked' ? `无法刷新：${r.reason}` : r.status === 'duplicate' ? '正在刷新…' : '刷新失败，请重试');
  };
  return <div data-testid="uw-outline" style={{display: 'grid', gap: 8, padding: 8}}>
    <label style={{display: 'grid', gap: 4, fontSize: 12}}>作品
      <select value={novelId ?? ''} onChange={e => onNovel(e.target.value)} aria-label="选择作品">
        {novels.data.map(n => <option key={n.id} value={n.id}>{n.title}</option>)}
      </select>
    </label>
    {errKind ? <p className="uw-state" role="alert" data-state={errKind}>{ERR_TEXT[errKind]}</p> : null}
    <NovelStructureRail chapters={(chapters.data ?? []).map(c => ({id: c.id, number: c.number, title: c.title, wordCount: c.word_count}))}
      selectedId={selectedId} loading={chapters.isLoading} error={null} onSelect={onSelect} panels={[]} onOpenPanel={() => {}} />
    {blockedNotice ? <p role="status" className="uw-state" data-testid="uw-outline-blocked">{blockedNotice}</p> : null}
    <div><button type="button" data-action-id={NOVEL_ACTION_IDS.refresh} onClick={() => void refresh()}>刷新章节列表</button> <small role="status">{msg}</small></div>
  </div>;
}

/** Inspector: selected chapter's real properties; title edit is dirty-registered. */
export function InspectorPanel({novelId, chapterId, api: panelApi, ctx, actions, dirtyRef}: {
  novelId: string | null; chapterId: string | null; api: PanelRenderApi;
  ctx: (input?: unknown) => ActionContext; actions: ActionRegistry; dirtyRef: {current: boolean};
}) {
  const qc = useQueryClient();
  const chapters = useQuery({queryKey: chaptersKey(novelId ?? ''), queryFn: () => api.chapters(novelId!), enabled: !!novelId, retry: false});
  const chapter: Chapter | undefined = chapters.data?.find(c => c.id === chapterId);
  const [draft, setDraft] = useState<{id: string; title: string} | null>(null);
  const [msg, setMsg] = useState<{kind: 'ok' | 'err'; text: string} | null>(null);
  const [saving, setSaving] = useState(false);
  const dirty = !!draft && !!chapter && draft.id === chapter.id && draft.title !== chapter.title;
  dirtyRef.current = dirty;
  const live = useRef({dirty, draft, chapter, novelId}); live.current = {dirty, draft, chapter, novelId};

  const save = async (): Promise<void> => {
    const {draft: d, chapter: c, novelId: n} = live.current;
    if (!d || !c || !n) return;
    setSaving(true); setMsg(null);
    try {
      const r = await actions.execute(NOVEL_ACTION_IDS.rename, ctx({chapterId: c.id, novelId: n, title: d.title, version: c.version} satisfies RenameInput));
      if (r.status !== 'done') {
        const text = r.status === 'blocked' ? r.reason : r.status === 'error'
          ? (r.error instanceof ApiError && r.error.status === 409 ? '章节已被其他地方修改，请刷新后再改。'
            : r.error instanceof RenameUnconfirmedError ? RENAME_UNCONFIRMED_TEXT
            : r.error instanceof RenameNetworkError ? RENAME_NETWORK_TEXT : '保存失败，请重试。')
          : r.status === 'duplicate' ? '正在保存，请稍候。' : '项目已切换，本次保存未生效。';
        setMsg({kind: 'err', text}); throw new Error(text);
      }
      const saved = r.value as Chapter;
      qc.setQueryData<Chapter[]>(chaptersKey(n), list => list?.map(x => x.id === saved.id ? {...x, ...saved} : x));
      setDraft(null); setMsg({kind: 'ok', text: `已保存（版本 ${saved.version}）`});
    } finally { setSaving(false); }
  };
  useEffect(() => panelApi.registerDirty({
    isDirty: () => live.current.dirty,
    save,
    discard: () => setDraft(null),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reads through live ref
  }), [panelApi]);

  if (!novelId) return <p className="uw-state" data-state="empty">还没有选中作品。</p>;
  if (chapters.isLoading) return <p className="uw-state" role="status" data-state="loading">正在读取章节…</p>;
  if (chapters.error) { const k = classifyError(chapters.error); return <p className="uw-state" role="alert" data-state={k}>{ERR_TEXT[k]}</p>; }
  if (!chapter) return <p className="uw-state" data-state="empty" data-testid="uw-inspector-empty">在「作品结构」里选一个章节，这里会显示它的属性。</p>;
  const title = draft && draft.id === chapter.id ? draft.title : chapter.title;
  return <form data-testid="uw-inspector" style={{display: 'grid', gap: 8, padding: 12}} onSubmit={e => { e.preventDefault(); void save().catch(() => {}); }}>
    <label style={{display: 'grid', gap: 4}}>章节标题
      <input aria-label="章节标题" value={title} onChange={e => { setMsg(null); setDraft({id: chapter.id, title: e.target.value}); }} />
    </label>
    <dl style={{display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', margin: 0, fontSize: 13}}>
      <dt>章节</dt><dd>第 {chapter.number} 章</dd>
      <dt>字数</dt><dd>{chapter.word_count}</dd>
      <dt>状态</dt><dd>{statusZh(chapter.status)}</dd>
      <dt>版本</dt><dd>{chapter.version}</dd>
    </dl>
    <p style={{fontSize: 12, margin: 0}}>只有标题可以在这里修改；正文请在写作台编辑。</p>
    <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>
      <button type="submit" data-action-id={NOVEL_ACTION_IDS.rename} disabled={!dirty || saving || !title.trim()}>{saving ? '保存中…' : '保存标题'}</button>
      <button type="button" disabled={!dirty || saving} onClick={() => setDraft(null)}>放弃修改</button>
      {dirty ? <small data-testid="uw-inspector-dirty">有未保存的修改</small> : null}
    </div>
    {msg ? <p role={msg.kind === 'err' ? 'alert' : 'status'} style={{margin: 0, fontSize: 12}}>{msg.text}</p> : null}
  </form>;
}

export function useNovels() {
  return useQuery({queryKey: NOVELS_KEY, queryFn: () => api.novels(), retry: false});
}
