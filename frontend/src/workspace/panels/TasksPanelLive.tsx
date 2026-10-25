/**
 * [HERMIA-FE-20261025 U3-M3/M4] Live task panel over existing owners (TaskFeed) + read-only navigation (TaskNavigator).
 * States: not-connected / loading / empty / error(+next step) / revoked / ready(+bounded client paging, stale marks).
 * Navigation buttons only read and move focus/selection; nothing here can generate, adopt, cancel or enqueue.
 * Raw ids appear only in data-* attributes.
 */
import {useEffect, useRef, useState, useSyncExternalStore, type ReactNode} from 'react';
import type {ProductionJob} from '../../creative/studioProductionClient';
import type {NavReturnPoint, TaskRef} from '../contracts';
import type {TaskFeed} from '../tasks/taskFeed';
import {NAV_TEXT, type LocateResult, type TaskNavigator} from '../tasks/taskNavigation';
import {pageOf, PAGING_GAP_TEXT, statusText} from '../tasks/taskSources';
import {AUDIO_LIST_GAP_TEXT, filterByMedia, MEDIA_FILTER_TEXT, type MediaFilter} from '../media/mediaSlice'; // [HERMIA-FE-20261025 AUDIO-M10]

import {useDz} from '../defaultui/drawerEn';
export interface TasksPanelLiveProps {
  /** [HERMIA-FE-20261025 INT] lead wiring: selected production job (re-read) + host-owned detail extras (params/results). */
  onDetail?: (job: ProductionJob | null, ref: TaskRef | null) => void; detailExtra?: ReactNode;
  feed: TaskFeed;
  navigator: TaskNavigator | null;
  active: boolean;
  hasNode(canvas: 'creative' | 'execution', id: string): boolean;
  captureReturn(): NavReturnPoint;
  onLocate(r: Extract<LocateResult, {kind: 'located'}>): void;
  onOpenExecution(): void;
  onReturn(rp: NavReturnPoint): void;
  /** [HERMIA-FE-20261025 UWPORT-S2] default UI has no canvases: hide locate/execution/return buttons. */
  hideNav?: boolean;
}

export function TasksPanelLive({feed, navigator, active, hasNode, captureReturn, onLocate, onOpenExecution, onReturn, onDetail, detailExtra, hideNav}: TasksPanelLiveProps) {
  const z = useDz(); // [UWPORT-P2] en drawer text
  const state = useSyncExternalStore(f => feed.subscribe(f), () => feed.state);
  const [page, setPage] = useState(0);
  const [media, setMedia] = useState<MediaFilter>('all'); // [HERMIA-FE-20261025 AUDIO-M10] local filter over the SAME list
  const [sel, setSel] = useState<TaskRef | null>(null);
  const [detail, setDetail] = useState<{ref: TaskRef; job: ProductionJob | null; gone: boolean} | null>(null);
  const [msg, setMsg] = useState('');
  const [, force] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);
  const started = useRef<unknown>(null); // [HERMIA-FE-20261025 INT] once PER FEED: a feed built after the project list resolves must still read
  useEffect(() => { if (active && started.current !== feed) { started.current = feed; void feed.refresh(); } }, [active, feed]);
  useEffect(() => { setSel(null); setDetail(null); setMsg(''); setPage(0); }, [feed]);

  const open = async (ref: TaskRef) => { setSel(ref); setMsg(''); setDetail(null); onDetail?.(null, ref); const d = await feed.detail(ref); if (d) { setDetail(d); onDetail?.(d.job, d.ref); } };
  const locate = () => {
    if (!navigator || !sel) return;
    const ref = detail?.ref ?? sel;
    const r = navigator.locate(ref, hasNode);
    if (r.kind === 'missing') { setMsg(r.text); return; }
    navigator.remember(captureReturn()); setMsg(''); onLocate(r); force(x => x + 1);
  };
  const exec = () => { if (!navigator) return; navigator.remember(captureReturn()); onOpenExecution(); force(x => x + 1); };
  const back = () => { const rp = navigator?.takeReturn(); if (rp) onReturn(rp); else setMsg(NAV_TEXT.stale); force(x => x + 1); };

  let body;
  switch (state.kind) {
    case 'not-connected': body = <p data-state="not-connected" role="status">{state.gap}</p>; break;
    case 'loading': body = <p data-state="loading" role="status" aria-busy="true">{z('正在读取任务…')}</p>; break;
    case 'empty': body = <p data-state="empty">{z('这个项目还没有任务。')}</p>; break;
    case 'revoked': body = <p data-state="revoked" role="alert">{state.text}</p>; break;
    case 'error': body = <div data-state="error" role="alert"><p>{state.text}</p><p>{state.next}</p></div>; break;
    case 'ready': {
      const pg = pageOf(filterByMedia(state.items, media), page);
      body = <div data-state="ready">
        <ul ref={listRef} aria-label={z('任务列表')} style={{listStyle: 'none', margin: 0, padding: 0, maxHeight: 240, overflow: 'auto'}}>
          {pg.rows.map(t => <li key={`${t.source}|${t.id}`}>
            <button type="button" data-task-id={t.id} data-task-source={t.source} aria-pressed={sel?.id === t.id && sel.source === t.source}
              onClick={() => void open(t)}>{z(t.title)} · {z(statusText(t))}{t.stale ? z(' · 需核对') : ''}</button>
          </li>)}
        </ul>
        {pg.pages > 1 || state.truncated ? <p data-testid="u3-paging-gap">{z(PAGING_GAP_TEXT)}{state.truncated ? z(' 服务端已截断，部分任务未显示。') : ''}</p> : null}
        {pg.pages > 1 ? <nav aria-label={z('任务分页')}>
          <button type="button" disabled={pg.page === 0} onClick={() => setPage(pg.page - 1)}>{z('上一页')}</button>
          <span>{pg.page + 1} / {pg.pages}</span>
          <button type="button" disabled={pg.page >= pg.pages - 1} onClick={() => setPage(pg.page + 1)}>{z('下一页')}</button>
        </nav> : null}
      </div>;
      break;
    }
  }
  const d = detail?.ref ?? sel;
  return <div data-testid="u3-tasks" style={{padding: 8}}>{/* [HERMIA-FE-20261025 M5-fix] Vera P2 axe landmark-unique: the dock panel is already the "任务" region; no nested same-name landmark */}
    <div><button type="button" data-testid="u3-refresh" onClick={() => void feed.refresh()} disabled={state.kind === 'not-connected'}>{z('刷新')}</button>
      {' '}<span role="group" aria-label={z('按媒介筛选')}>{(['all', 'image', 'audio'] as const).map(m => <button key={m} type="button" data-testid={`aud-filter-${m}`} aria-pressed={media === m} onClick={() => { setMedia(m); setPage(0); }}>{z(MEDIA_FILTER_TEXT[m])}</button>)}</span></div>
    {media !== 'all' && state.kind === 'ready' ? <p data-testid="aud-filter-gap">{AUDIO_LIST_GAP_TEXT}</p> : null}
    {body}
    {d && state.kind === 'ready' ? <div data-testid="u3-detail" data-task-id={d.id} aria-label={z('任务详情')}>
      <h4 style={{margin: '8px 0 4px'}}>{z(d.title)}</h4>
      <p>{z('状态：')}{z(statusText(d))}{d.stale ? z('（状态需核对：请到原任务界面确认，不会自动重试）') : ''}</p>
      {detail?.gone ? <p role="alert">{z('重新读取这个任务失败：它可能已被删除或失效。列表里的信息可能已过时。')}</p> : null}
      <p>{z('来源：')}{z(d.source === 'production-job' ? '生产任务' : '任务中心')}{z(d.link ? '，记录了来源作品节点' : '，没有记录来源作品节点')}</p>
      <p>{z('成本：未知（服务端没有提供估算）')}</p>
{hideNav ? null : <>
      <button type="button" data-testid="u3-locate" onClick={locate} disabled={!navigator}>{z('定位来源节点')}</button>{' '}
      <button type="button" data-testid="u3-exec" onClick={exec} disabled={!navigator}>{z('查看执行画布')}</button>{' '}
      <button type="button" data-testid="u3-back" onClick={back} disabled={!navigator?.canReturn()}>{z('返回原位置')}</button></>}
      {detailExtra}
    </div> : null}
    {msg ? <p data-testid="u3-nav-msg" role="status">{msg}</p> : null}
  </div>;
}
