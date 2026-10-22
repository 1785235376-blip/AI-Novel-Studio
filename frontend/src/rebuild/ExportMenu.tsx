// [HERMIA-FE-20261022 REBUILD-1] 导出：小说导出 GET /novels/{nid}/export + 成片导出 /exports（列表/新建/下载）。
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { WithQuery, Popover, StateTag, Tabs, downloadText, type Tone } from './primitives';
import { rb, rbError, NOVEL_EXPORT_FORMATS, RENDER_EXPORT_FORMATS, type ExportJob } from './rebuildApi';

const jobTone = (s: string): Tone => s === 'completed' || s === 'succeeded' ? 'ok' : s === 'failed' || s === 'cancelled' ? 'err' : 'warn';
const jobLabel: Record<string, string> = { queued: '排队中', running: '进行中', completed: '已完成', succeeded: '已完成', failed: '失败', cancelled: '已取消' };

export function ExportBody({ novelId, initialTab = 'novel' }: { novelId: string; initialTab?: 'novel' | 'render' }) {
  const [tab, setTab] = useState<'novel' | 'render'>(initialTab);
  const [fmt, setFmt] = useState<string>('txt');
  const [rfmt, setRfmt] = useState<string>('docx');
  const [msg, setMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
  const qc = useQueryClient();
  const jobs = useQuery({ queryKey: ['rb', 'exports', novelId], queryFn: () => rb.listExports(novelId), enabled: !!novelId && tab === 'render', retry: false, refetchInterval: 4000 });
  const novelExport = useMutation({
    mutationFn: () => rb.novelExport(novelId, fmt),
    onSuccess: r => { downloadText(r.filename, r.content, r.format === 'json' ? 'application/json' : 'text/plain;charset=utf-8'); setMsg({ tone: 'ok', text: `已下载 ${r.filename}` }); },
    onError: err => setMsg({ tone: 'err', text: `导出失败：${rbError(err)}` }),
  });
  const create = useMutation({
    mutationFn: () => rb.createExport(novelId, rfmt),
    onSuccess: () => { setMsg({ tone: 'ok', text: '已加入导出队列（状态以列表为准）' }); qc.invalidateQueries({ queryKey: ['rb', 'exports', novelId] }); },
    onError: err => setMsg({ tone: 'err', text: `创建失败：${rbError(err)}` }),
  });
  if (!novelId) return <p className="rb-empty">先打开一部作品再导出。</p>;
  return <div data-rebuild="export">
    <Tabs label="导出类型" value={tab} onChange={v => { setTab(v); setMsg(null); }} items={[{ id: 'novel', label: '小说文本' }, { id: 'render', label: '成片 / 文档' }]} />
    {tab === 'novel' ? <div className="rb-field">
      <select className="rb-select" aria-label="小说导出格式" value={fmt} onChange={ev => setFmt(ev.target.value)}>{NOVEL_EXPORT_FORMATS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select>
      <button type="button" className="rb-btn rb-btn--primary" disabled={novelExport.isPending} onClick={() => novelExport.mutate()}>{novelExport.isPending ? '导出中…' : '导出并下载'}</button>
    </div> : <div style={{ display: 'grid', gap: 10 }}>
      <div className="rb-field">
        <select className="rb-select" aria-label="成片导出格式" value={rfmt} onChange={ev => setRfmt(ev.target.value)}>{RENDER_EXPORT_FORMATS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select>
        <button type="button" className="rb-btn rb-btn--primary" disabled={create.isPending} onClick={() => create.mutate()}>新建导出任务</button>
      </div>
      {jobs.isError ? <p className="rb-note" data-tone="err">导出列表读取失败：{rbError(jobs.error)}</p>
        : jobs.isLoading ? <p className="rb-empty">读取中…</p>
        : (jobs.data?.items.length ?? 0) === 0 ? <p className="rb-empty">还没有导出任务。</p>
        : <ul className="rb-list" aria-label="导出任务">{jobs.data!.items.map((j: ExportJob) => <li key={j.id} className="rb-row">
            <span className="rb-row__main">{j.format.toUpperCase()} · {j.progress_message || jobLabel[j.status] || j.status}</span>
            <StateTag tone={jobTone(j.status)}>{jobLabel[j.status] || j.status}</StateTag>
            {j.status === 'completed' || j.status === 'succeeded' ? <a className="rb-btn" href={rb.exportDownloadUrl(j.id)} download>下载</a> : null}
          </li>)}</ul>}
    </div>}
    {msg ? <p className="rb-note" data-tone={msg.tone === 'err' ? 'err' : undefined} role="status" style={{ marginTop: 10 }}>{msg.text}</p> : null}
  </div>;
}

export function ExportMenu({ novelId, initialTab }: { novelId: string; initialTab?: 'novel' | 'render' }) {
  return <Popover label="导出" testId="rb-export">{() => <WithQuery><ExportBody novelId={novelId} initialTab={initialTab} /></WithQuery>}</Popover>;
}
