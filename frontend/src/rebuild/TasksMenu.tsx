// [HERMIA-FE-20261022 REBUILD-4] 顶栏统一「任务」：合并 media-tasks / asset-tasks(stats) / workspace/tasks / exports，
// 加资产回收站 asset-trash。每个来源单独读，单个来源失败只标它自己，不整体假绿。
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Popover, StateTag, Tabs, WithQuery, type Tone } from './primitives';
import { rb, rbError } from './rebuildApi';
import { useT, formatDate, useLocale } from '../i18n'; // [HERMIA-FE-20261025 I18N P1] task menu body

type Row = { id: string; source: string; label: string; status: string };
const norm = (s: string) => s.toLowerCase();
const tone = (s: string): Tone => /fail|error|cancel/.test(norm(s)) ? 'err' : /succe|complete|done|ready/.test(norm(s)) ? 'ok' : 'warn';
const STATUS_KEY = { pending: 'tk.s.queued', queued: 'tk.s.queued', running: 'tk.s.running', succeeded: 'tk.s.done', completed: 'tk.s.done', failed: 'tk.s.failed', cancelled: 'tk.s.cancelled' } as const;

function useSources(novelId: string, enabled: boolean) {
  const o = { enabled: !!novelId && enabled, retry: false, refetchInterval: enabled ? 5000 : false as const };
  return {
    media: useQuery({ queryKey: ['rb', 'media-tasks', novelId], queryFn: () => rb.mediaTasks(novelId), ...o }),
    asset: useQuery({ queryKey: ['rb', 'asset-stats', novelId], queryFn: () => rb.assetTaskStats(novelId), ...o }),
    ws: useQuery({ queryKey: ['rb', 'ws-tasks', novelId], queryFn: () => rb.workspaceTasks(novelId), ...o }),
    exports: useQuery({ queryKey: ['rb', 'exports', novelId], queryFn: () => rb.listExports(novelId), ...o }),
  };
}

export function TasksBody({ novelId, initialTab = 'tasks' }: { novelId: string; initialTab?: 'tasks' | 'trash' }) {
  const [tab, setTab] = useState<'tasks' | 'trash'>(initialTab);
  const t = useT(); const locale = useLocale();
  const zh = (st: string) => { const k = (STATUS_KEY as Record<string, typeof STATUS_KEY[keyof typeof STATUS_KEY]>)[norm(st)]; return k ? t(k) : st; };
  const s = useSources(novelId, tab === 'tasks');
  const trash = useQuery({ queryKey: ['rb', 'trash', novelId], queryFn: () => rb.assetTrash(novelId), enabled: !!novelId && tab === 'trash', retry: false });
  if (!novelId) return <p className="rb-empty">{t('tk.noWork')}</p>;
  const rows: Row[] = [
    ...(s.media.data?.audiobook || []).map(x => ({ id: x.id, source: t('tk.audiobook'), label: x.chapter_id ? t('tk.chapterN', { id: x.chapter_id.slice(0, 6) }) : x.id.slice(0, 8), status: x.status })),
    ...(s.media.data?.motion || []).map(x => ({ id: x.id, source: t('tk.motion'), label: x.id.slice(0, 8), status: x.status })),
    ...(s.ws.data?.items || []).map(x => ({ id: `${x.authority}:${x.id}`, source: t('tk.ws'), label: x.title || x.id.slice(0, 8), status: x.status })),
    ...(s.exports.data?.items || []).map(x => ({ id: x.id, source: t('tk.export'), label: x.format.toUpperCase(), status: x.status })),
  ];
  const errs = ([[t('tk.media'), s.media], [t('tk.asset'), s.asset], [t('tk.wsTasks'), s.ws], [t('tk.export'), s.exports]] as const).filter(([, q]) => q.isError);
  const loading = [s.media, s.asset, s.ws, s.exports].some(q => q.isLoading);
  const st = s.asset.data?.by_status;
  return <div data-rebuild="tasks">
    <Tabs label={t('tk.view')} value={tab} onChange={setTab} items={[{ id: 'tasks', label: t('tk.tasks') }, { id: 'trash', label: t('tk.trash') }]} />
    {tab === 'tasks' ? <div style={{ display: 'grid', gap: 8 }}>
      {st ? <div className="rb-field" style={{ flexWrap: 'wrap' }} aria-label={t('tk.stats')}><span className="rb-sub">{t('tk.asset')}</span>
        <StateTag tone="muted">{t('tk.total', { n: s.asset.data!.total })}</StateTag>{st.RUNNING ? <StateTag tone="warn">{t('tk.running', { n: st.RUNNING })}</StateTag> : null}{st.PENDING ? <StateTag tone="warn">{t('tk.pending', { n: st.PENDING })}</StateTag> : null}{st.FAILED ? <StateTag tone="err">{t('tk.failed', { n: st.FAILED })}</StateTag> : null}</div> : null}
      {rows.length ? <ul className="rb-list" aria-label={t('tk.list')}>{rows.map(r => <li key={`${r.source}:${r.id}`} className="rb-row"><StateTag tone="muted">{r.source}</StateTag><span className="rb-row__main">{r.label}</span><StateTag tone={tone(r.status)}>{zh(r.status)}</StateTag></li>)}</ul>
        : loading ? <p className="rb-empty">{t('tk.loading')}</p> : <p className="rb-empty">{t('tk.none')}</p>}
      {errs.map(([name, q]) => <p key={name} className="rb-note" data-tone="err">{t('tk.errOf', { name, err: rbError(q.error) })}</p>)}
    </div> : trash.isError ? <p className="rb-note" data-tone="err">{t('tk.trashErr', { err: rbError(trash.error) })}</p>
      : trash.isLoading ? <p className="rb-empty">{t('tk.loading')}</p>
      : (trash.data?.items.length ?? 0) === 0 ? <p className="rb-empty">{t('tk.trashEmpty')}</p>
      : <ul className="rb-list" aria-label={t('tk.trash')}>{trash.data!.items.map(x => <li key={x.id} className="rb-row"><span className="rb-row__main">{x.name || x.title || x.id}</span>{x.kind ? <StateTag tone="muted">{x.kind}</StateTag> : null}{x.deleted_at ? <span className="rb-sub">{formatDate(x.deleted_at, locale, { year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false })}</span> : null}</li>)}</ul>}
  </div>;
}

// [HERMIA-FE-20261022 R1] 任务计数徽标：用外壳已有的任务汇总（运行 + 排队），不额外发请求；0 或未知时不显示数字。
export function TasksMenu({ novelId, count }: { novelId: string; count?: number }) {
  const t = useT(); // [HERMIA-FE-20261025 I18N P0] header trigger label only
  return <Popover label={t('header.tasks')} count={count || undefined} testId="rb-tasks">{() => <WithQuery><TasksBody novelId={novelId} /></WithQuery>}</Popover>;
}
