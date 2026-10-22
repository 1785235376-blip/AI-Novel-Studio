// [HERMIA-FE-20261022 REBUILD-3] 小说资料研究侧栏：/novels/{nid}/research（列/增/删）+ knowledge-base/review。
// 右侧抽屉，不挤占正文全宽；外部抓取关闭时如实说明。
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Drawer, StateTag, WithQuery } from './primitives';
import { rb, rbError } from './rebuildApi';

const TYPES = [['NOTE', '笔记'], ['BOOK', '书籍'], ['ARTICLE', '文章'], ['WEBSITE', '网页'], ['ARCHIVE', '档案'], ['INTERVIEW', '访谈'], ['OTHER', '其他']] as const;
const typeLabel = (t: string) => TYPES.find(x => x[0] === t)?.[1] || t;

export function ResearchBody({ novelId }: { novelId: string }) {
  const qc = useQueryClient();
  const key = ['rb', 'research', novelId];
  const list = useQuery({ queryKey: key, queryFn: () => rb.research(novelId), enabled: !!novelId, retry: false });
  const [title, setTitle] = useState(''); const [type, setType] = useState('NOTE'); const [url, setUrl] = useState(''); const [notes, setNotes] = useState('');
  const [filter, setFilter] = useState('');
  const [note, setNote] = useState<{ tone: 'ok' | 'err' | 'warn'; text: string } | null>(null);
  const add = useMutation({ mutationFn: () => rb.addResearch(novelId, { title: title.trim(), source_type: type, url: url.trim(), notes }), onSuccess: () => { setTitle(''); setUrl(''); setNotes(''); setNote({ tone: 'ok', text: '已添加' }); qc.invalidateQueries({ queryKey: key }); }, onError: e => setNote({ tone: 'err', text: `添加失败：${rbError(e)}` }) });
  const del = useMutation({ mutationFn: (id: string) => rb.deleteResearch(novelId, id), onSuccess: () => qc.invalidateQueries({ queryKey: key }), onError: e => setNote({ tone: 'err', text: `删除失败：${rbError(e)}` }) });
  const kb = useMutation({ mutationFn: () => rb.knowledgeReview(novelId), onSuccess: r => setNote({ tone: 'ok', text: `已生成知识库审阅${r?.id ? `（${r.id.slice(0, 8)}）` : ''}，到「设定」里逐条确认` }), onError: e => setNote({ tone: 'warn', text: `知识库：${rbError(e)}` }) });
  if (!novelId) return <p className="rb-empty">先打开一部作品。</p>;
  const items = (list.data?.items || []).filter(r => !filter || `${r.title} ${r.notes || ''} ${r.url || ''}`.toLowerCase().includes(filter.toLowerCase()));
  return <div data-rebuild="research" style={{ display: 'grid', gap: 12 }}>
    <form className="rb-panel" style={{ margin: 0 }} onSubmit={e => { e.preventDefault(); if (title.trim()) add.mutate(); }}>
      <div className="rb-field"><input className="rb-input" style={{ flex: 1 }} aria-label="资料标题" placeholder="资料标题" maxLength={240} value={title} onChange={e => setTitle(e.target.value)} />
        <select className="rb-select" aria-label="资料类型" value={type} onChange={e => setType(e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      <input className="rb-input" aria-label="来源链接" placeholder="来源链接（可选，不会自动抓取）" value={url} onChange={e => setUrl(e.target.value)} />
      <textarea className="rb-input" style={{ height: 64, padding: 8 }} aria-label="资料笔记" placeholder="摘录或笔记" value={notes} onChange={e => setNotes(e.target.value)} />
      <div className="rb-field"><button type="submit" className="rb-btn rb-btn--primary" disabled={!title.trim() || add.isPending}>添加资料</button>
        <button type="button" className="rb-btn" disabled={kb.isPending} onClick={() => kb.mutate()}>从正文生成知识库审阅</button></div>
    </form>
    {note ? <p className="rb-note" data-tone={note.tone === 'err' ? 'err' : undefined} role="status">{note.text}</p> : null}
    <div className="rb-field"><input className="rb-input" style={{ flex: 1 }} aria-label="筛选资料" placeholder="筛选资料" value={filter} onChange={e => setFilter(e.target.value)} />
      {list.data ? <StateTag tone="muted">{list.data.total} 条</StateTag> : null}
      {list.data && list.data.external_fetch === false ? <StateTag tone="muted">不联网抓取</StateTag> : null}</div>
    {list.isError ? <p className="rb-note" data-tone="err">资料读取失败：{rbError(list.error)}</p>
      : list.isLoading ? <p className="rb-empty">读取中…</p>
      : items.length === 0 ? <p className="rb-empty">{filter ? '没有匹配的资料。' : '还没有资料。写作中查到的史料、地名、人物原型都可以记在这里。'}</p>
      : <ul className="rb-list" aria-label="资料列表">{items.map(r => <li key={r.id} className="rb-row" style={{ alignItems: 'flex-start', flexDirection: 'column' }}>
          <div className="rb-field" style={{ width: '100%' }}><strong className="rb-row__main">{r.title}</strong><StateTag tone="muted">{typeLabel(r.source_type)}</StateTag>
            <button type="button" className="rb-btn" aria-label={`删除 ${r.title}`} onClick={() => del.mutate(r.id)}>删除</button></div>
          {r.notes ? <span className="rb-sub">{r.notes.slice(0, 140)}</span> : null}
          {r.url ? <span className="rb-sub" style={{ wordBreak: 'break-all' }}>{r.url}</span> : null}
        </li>)}</ul>}
  </div>;
}

export function ResearchDrawer({ novelId, onClose }: { novelId: string; onClose: () => void }) {
  return <Drawer title="资料" onClose={onClose}><WithQuery><ResearchBody novelId={novelId} /></WithQuery></Drawer>;
}
