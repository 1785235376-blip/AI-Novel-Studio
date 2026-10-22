// [HERMIA-FE-20261022 REBUILD-4] 顶栏统一「任务」：合并 media-tasks / asset-tasks(stats) / workspace/tasks / exports，
// 加资产回收站 asset-trash。每个来源单独读，单个来源失败只标它自己，不整体假绿。
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Popover, StateTag, Tabs, WithQuery, type Tone } from './primitives';
import { rb, rbError } from './rebuildApi';

type Row = { id: string; source: string; label: string; status: string };
const norm = (s: string) => s.toLowerCase();
const tone = (s: string): Tone => /fail|error|cancel/.test(norm(s)) ? 'err' : /succe|complete|done|ready/.test(norm(s)) ? 'ok' : 'warn';
const zh = (s: string) => ({ pending: '排队', queued: '排队', running: '进行中', succeeded: '完成', completed: '完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[norm(s)] || s;

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
  const s = useSources(novelId, tab === 'tasks');
  const trash = useQuery({ queryKey: ['rb', 'trash', novelId], queryFn: () => rb.assetTrash(novelId), enabled: !!novelId && tab === 'trash', retry: false });
  if (!novelId) return <p className="rb-empty">先打开一部作品。</p>;
  const rows: Row[] = [
    ...(s.media.data?.audiobook || []).map(t => ({ id: t.id, source: '有声书', label: t.chapter_id ? `章节 ${t.chapter_id.slice(0, 6)}` : t.id.slice(0, 8), status: t.status })),
    ...(s.media.data?.motion || []).map(t => ({ id: t.id, source: '动态', label: t.id.slice(0, 8), status: t.status })),
    ...(s.ws.data?.items || []).map(t => ({ id: `${t.authority}:${t.id}`, source: '工作区', label: t.title || t.id.slice(0, 8), status: t.status })),
    ...(s.exports.data?.items || []).map(t => ({ id: t.id, source: '导出', label: t.format.toUpperCase(), status: t.status })),
  ];
  const errs = ([['媒体任务', s.media], ['资产任务', s.asset], ['工作区任务', s.ws], ['导出', s.exports]] as const).filter(([, q]) => q.isError);
  const loading = [s.media, s.asset, s.ws, s.exports].some(q => q.isLoading);
  const st = s.asset.data?.by_status;
  return <div data-rebuild="tasks">
    <Tabs label="任务视图" value={tab} onChange={setTab} items={[{ id: 'tasks', label: '任务' }, { id: 'trash', label: '回收站' }]} />
    {tab === 'tasks' ? <div style={{ display: 'grid', gap: 8 }}>
      {st ? <div className="rb-field" style={{ flexWrap: 'wrap' }} aria-label="资产任务统计"><span className="rb-sub">资产任务</span>
        <StateTag tone="muted">共 {s.asset.data!.total}</StateTag>{st.RUNNING ? <StateTag tone="warn">进行 {st.RUNNING}</StateTag> : null}{st.PENDING ? <StateTag tone="warn">排队 {st.PENDING}</StateTag> : null}{st.FAILED ? <StateTag tone="err">失败 {st.FAILED}</StateTag> : null}</div> : null}
      {rows.length ? <ul className="rb-list" aria-label="任务列表">{rows.map(r => <li key={`${r.source}:${r.id}`} className="rb-row"><StateTag tone="muted">{r.source}</StateTag><span className="rb-row__main">{r.label}</span><StateTag tone={tone(r.status)}>{zh(r.status)}</StateTag></li>)}</ul>
        : loading ? <p className="rb-empty">读取中…</p> : <p className="rb-empty">当前没有进行中或最近的任务。</p>}
      {errs.map(([name, q]) => <p key={name} className="rb-note" data-tone="err">{name}：{rbError(q.error)}</p>)}
    </div> : trash.isError ? <p className="rb-note" data-tone="err">回收站读取失败：{rbError(trash.error)}</p>
      : trash.isLoading ? <p className="rb-empty">读取中…</p>
      : (trash.data?.items.length ?? 0) === 0 ? <p className="rb-empty">回收站是空的。</p>
      : <ul className="rb-list" aria-label="回收站">{trash.data!.items.map(t => <li key={t.id} className="rb-row"><span className="rb-row__main">{t.name || t.title || t.id}</span>{t.kind ? <StateTag tone="muted">{t.kind}</StateTag> : null}{t.deleted_at ? <span className="rb-sub">{new Date(t.deleted_at).toLocaleString('zh-CN', { hour12: false })}</span> : null}</li>)}</ul>}
  </div>;
}

// [HERMIA-FE-20261022 R1] 任务计数徽标：用外壳已有的任务汇总（运行 + 排队），不额外发请求；0 或未知时不显示数字。
export function TasksMenu({ novelId, count }: { novelId: string; count?: number }) {
  return <Popover label="任务" count={count || undefined} testId="rb-tasks">{() => <WithQuery><TasksBody novelId={novelId} /></WithQuery>}</Popover>;
}
