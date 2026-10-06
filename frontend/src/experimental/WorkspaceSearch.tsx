import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError, type Chapter } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { Field, ResourceState, useAction } from './shared';
import { type SearchItem, type SearchOptions, type SearchResult, type WorkspaceLayout, type WorkspaceNavigation, type workspaceClient } from './uxClient';

type SearchAPI = ReturnType<typeof workspaceClient>;
type Command = { id: string; label: string; detail: string; words: string };
const kinds = { review: '审核项', novel: '小说', volume: '卷', scene: '场景', timeline: '时间线', chapter: '章节', character: '人物', location: '地点', foreshadowing: '伏笔', finding: '发现', task: '任务' };
const newRequest = () => globalThis.crypto?.randomUUID?.() || `search-${Date.now()}-${Math.random().toString(16).slice(2)}`;

function useWorkspaceSearch(api: SearchAPI, options: SearchOptions, composing: boolean) {
  const identity = JSON.stringify(options);
  const [state, setState] = useState<{ identity: string; data?: SearchResult; error?: unknown; loading: boolean; cancelled?: boolean }>({ identity, loading: true });
  const alive = useRef(true), sequence = useRef(0), timer = useRef<ReturnType<typeof setTimeout>>();
  const operation = useRef<{ controller: AbortController; id: string }>();
  const stop = () => {
    clearTimeout(timer.current); sequence.current += 1;
    const previous = operation.current; operation.current = undefined;
    if (previous) { previous.controller.abort(); void api.cancelSearch(previous.id).catch(() => {}); }
  };
  const run = (rebuild = false) => {
    stop(); const ticket = sequence.current, id = newRequest(), controller = new AbortController();
    operation.current = { id, controller }; setState({ identity, loading: true });
    const request = { ...options, request_id: id };
    (rebuild ? api.rebuild(request) : api.searchScoped(request, controller.signal)).then(data => {
      if (alive.current && sequence.current === ticket && !controller.signal.aborted) setState({ identity, data, loading: false });
    }).catch(error => {
      if (alive.current && sequence.current === ticket && !controller.signal.aborted)
        setState({ identity, error, loading: false, cancelled: error instanceof ApiError && error.problem.code === 'SEARCH_CANCELLED' });
    }).finally(() => { if (sequence.current === ticket) operation.current = undefined; });
  };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; stop(); }; }, [api]);
  useEffect(() => {
    stop(); setState({ identity, loading: !composing });
    if (!composing) timer.current = setTimeout(() => run(), 180);
    return stop;
  }, [api, identity, composing]);
  return { ...(state.identity === identity ? state : { identity, loading: !composing }),
    reload: () => run(), rebuild: () => run(true),
    cancel: () => { stop(); setState({ identity, loading: false, cancelled: true }); },
    clear: () => { stop(); setState({ identity, loading: false }); } };
}

export function WorkspaceSearch({ api, chapter, commands: choices, navigate, recent, filters, updateFilters }: {
  api: SearchAPI; chapter?: Chapter; commands: readonly Command[]; navigate?: (target: WorkspaceNavigation) => void;
  recent: string[]; filters: WorkspaceLayout; updateFilters: (patch: Partial<WorkspaceLayout>) => void;
}) {
  const [composing, setComposing] = useState(false), [offset, setOffset] = useState(0);
  const options = useMemo<SearchOptions>(() => ({ q: filters.search_query, kind: filters.search_kind,
    chapter_id: filters.search_current_chapter ? chapter?.id || '__no_current_chapter__' : undefined,
    scope: filters.search_current_chapter ? 'project' : filters.search_scope,
    tag: filters.search_tag, recent_days: filters.search_recent_days, unresolved: filters.search_unresolved,
    fulltext: filters.search_fulltext, offset }), [filters, chapter?.id, offset]);
  const search = useWorkspaceSearch(api, options, composing), action = useAction();
  const [stale, setStale] = useState<SearchItem>(), [jumpNotice, setJumpNotice] = useState('');
  const active = useRef(true), operation = useRef(0), jump = useRef<AbortController>();
  const invalidateJump = () => { operation.current += 1; jump.current?.abort(); setStale(undefined); setJumpNotice(''); };
  const change = (patch: Partial<WorkspaceLayout>) => { invalidateJump(); setOffset(0); updateFilters(patch); };
  useLayoutEffect(() => { active.current = true; return () => { active.current = false; operation.current += 1; jump.current?.abort(); }; }, []);
  useLayoutEffect(() => { invalidateJump(); }, [chapter?.id, chapter?.version]);
  const open = (row: SearchItem, current = false) => action.run(async () => {
    const ticket = ++operation.current; jump.current?.abort(); const controller = new AbortController(); jump.current = controller;
    const valid = () => active.current && operation.current === ticket && !controller.signal.aborted;
    try {
      const target = await api.resolve(row, current);
      if (!valid()) return;
      navigate?.({ ...target, signal: controller.signal }); setStale(undefined); setJumpNotice('已请求打开来源');
    } catch (error) {
      if (!valid()) return;
      if (error instanceof ApiError && error.status === 409) setStale(row);
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) { setStale(undefined); search.clear(); }
      throw error;
    }
  }, '');
  const filtered = choices.filter(c => `${c.label} ${c.words}`.toLowerCase().includes(filters.search_query.trim().toLowerCase()))
    .sort((a, b) => Number(recent.includes(b.id)) - Number(recent.includes(a.id)));
  const listRef = useRef<HTMLDivElement>(null), suggestionsId = useId();
  const data = !search.loading && !search.error && !search.cancelled ? search.data : undefined;
  return <Panel title="作品搜索与安全命令">
    <form className="experimental-form" onSubmit={e => { e.preventDefault(); if (!composing) { invalidateJump(); search.reload(); } }}>
      <Field label="搜索中文名称、别名或正文"><input autoFocus maxLength={160} value={filters.search_query} list={suggestionsId}
        onCompositionStart={() => setComposing(true)} onCompositionEnd={() => setComposing(false)}
        onChange={e => change({ search_query: e.target.value })} onKeyDown={e => { if (!composing && !e.nativeEvent.isComposing && e.key === 'ArrowDown') { e.preventDefault(); listRef.current?.querySelector<HTMLButtonElement>('button')?.focus(); } }} /></Field>
      <datalist id={suggestionsId}>{data?.suggestions?.map(value => <option key={value} value={value} />)}</datalist>
      <div className="experimental-actions">
        <Field label="搜索范围"><select value={filters.search_scope} disabled={filters.search_current_chapter} onChange={e => change({ search_scope: e.target.value as WorkspaceLayout['search_scope'] })}><option value="project">当前作品</option><option value="authorized">已授权项目</option></select></Field>
        <Field label="内容类型"><select value={filters.search_kind} onChange={e => change({ search_kind: e.target.value as WorkspaceLayout['search_kind'] })}><option value="">全部</option>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <label className="experimental-check"><input type="checkbox" checked={filters.search_current_chapter} disabled={!chapter} onChange={e => change({ search_current_chapter: e.target.checked })} />只搜当前章</label>
        <Field label="标签（精确匹配）"><input maxLength={80} value={filters.search_tag} onChange={e => change({ search_tag: e.target.value })} /></Field>
        <Field label="最近修改"><select value={filters.search_recent_days} onChange={e => change({ search_recent_days: Number(e.target.value) })}><option value={0}>不限时间</option><option value={1}>最近一天</option><option value={7}>最近七天</option><option value={30}>最近三十天</option></select></Field>
        <label className="experimental-check"><input type="checkbox" checked={filters.search_unresolved} onChange={e => change({ search_unresolved: e.target.checked })} />只看未解决</label>
        <label className="experimental-check"><input type="checkbox" checked={filters.search_fulltext} onChange={e => change({ search_fulltext: e.target.checked })} />只匹配正文</label>
      </div>
      <div className="experimental-actions"><Button type="submit" disabled={composing}>搜索</Button><Button type="button" onClick={() => { invalidateJump(); search.reload(); }}>刷新来源</Button><Button type="button" disabled={search.loading || composing} onClick={() => { invalidateJump(); search.rebuild(); }}>重建索引</Button><Button type="button" disabled={!search.loading} onClick={() => { invalidateJump(); search.cancel(); }}>取消搜索</Button></div>
    </form>
    <p>按字面匹配，不调用模型。名称与别名优先；资料记录只索引名称、别名与安全元数据，不索引私密正文。每页最多 50 条。无更新时间的来源不进入最近修改筛选。</p>
    <div className="experimental-actions" aria-label="安全导航命令">{filtered.map(command => <Button disabled={!navigate} key={command.id} onClick={() => { invalidateJump(); navigate?.({ kind: 'feature', id: command.id, feature: command.id }); }}>{command.label}{recent.includes(command.id) ? ' · 最近使用' : ''}</Button>)}</div>
    <ResourceState loading={search.loading} error={search.cancelled ? undefined : search.error} empty={!!data && !data.items.length} />
    {composing && <StatusMessage>中文输入完成后再搜索。</StatusMessage>}
    {search.cancelled && <StatusMessage>搜索已取消；不会展示迟到的结果。可重新搜索。</StatusMessage>}
    {data && !data.branch_sources_available && <StatusMessage tone="warning">当前分支尚未接入可授权的章节来源；不会借用主分支正文。</StatusMessage>}
    {data?.index_truncated && <StatusMessage tone="warning">已达到单次索引上限，请缩小到当前章或当前作品。</StatusMessage>}
    {data?.match_count !== undefined && <p role="status">当前可读匹配：{data.match_count}{data.index_truncated ? '（索引范围内）' : ''}。本次更新 {data.updated_documents || 0} 条来源。</p>}
    {data && <div ref={listRef} className="experimental-list" onKeyDown={e => { if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return; const buttons = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') || []); const index = buttons.indexOf(document.activeElement as HTMLButtonElement); if (index >= 0 && buttons.length) { e.preventDefault(); buttons[(index + (e.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length].focus(); } }}>{data.items.map(row => <article className="experimental-record" key={`${row.novel_id}:${row.branch_id}:${row.kind}:${row.id}`}><h3>{row.title}</h3><p>{row.snippet || row.aliases.join('、') || '名称匹配'}</p><div className="experimental-actions"><Badge>{kinds[row.kind]}</Badge>{row.version && <Badge>v{row.version}</Badge>}{row.novel_id && filters.search_scope === 'authorized' && <Badge>作品：{row.novel_id}</Badge>}<Button disabled={!navigate || action.busy} onClick={() => open(row)}>{row.kind === 'chapter' ? '打开章节位置' : row.kind === 'task' ? '打开原任务' : '打开资料库来源'}</Button></div></article>)}</div>}
    {data && <div className="experimental-actions"><Button disabled={offset === 0} onClick={() => { invalidateJump(); setOffset(Math.max(0, offset - 50)); }}>上一页</Button><Button disabled={data.next_offset == null} onClick={() => { invalidateJump(); setOffset(data.next_offset!); }}>下一页</Button></div>}
    {stale && <StatusMessage tone="warning">「{stale.title}」来源已经变化，旧位置未跳转。<Button disabled={!navigate || action.busy} onClick={() => open(stale, true)}>核对并打开当前版本</Button></StatusMessage>}
    {action.feedback}{jumpNotice && <StatusMessage tone="success">{jumpNotice}</StatusMessage>}
  </Panel>;
}
