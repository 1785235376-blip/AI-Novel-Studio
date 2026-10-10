import { useMemo, useState, type ReactNode } from 'react';
import { Box, Clapperboard, Film, Globe, Music, Users } from 'lucide-react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { CreativeAsset, CreativeDocument, CreativeInput, CreativeReferences, WorkspaceMode } from './types';
import { modeForDocument } from './types';
const categories = [{ id: 'World', label: '世界', icon: Globe }, { id: 'Character', label: '人物', icon: Users }, { id: 'Scene', label: '场景', icon: Clapperboard }, { id: 'Shot', label: '镜头', icon: Box }, { id: 'Audio', label: '音频', icon: Music }, { id: 'Video', label: '视频', icon: Film }] as const;
export type AssetSelection = { id: string; title: string; kind: string; detail: string };
export function AssetBrowser({ mode, documents, draft, references, assets, loading, error, selectedDocumentId, onDocument, onSelect, onRetry, novelSidebar, onExit }: { mode: WorkspaceMode; documents: CreativeDocument[]; draft?: CreativeInput; references?: CreativeReferences; assets?: CreativeAsset[]; loading: boolean; error: boolean; selectedDocumentId?: string; onDocument: (document: CreativeDocument) => void; onSelect: (asset: AssetSelection) => void; onRetry: () => void; novelSidebar: ReactNode; onExit: () => void }) {
  const [category, setCategory] = useState<typeof categories[number]['id']>('Scene'), [query, setQuery] = useState('');
  const rows = useMemo((): AssetSelection[] => {
    if (category === 'World') return [...(references?.locations || []).map(row => ({ id: row.id, title: row.name, kind: 'World', detail: '已登记地点' })), ...(references?.story_routes || []).map(row => ({ id: row.id, title: row.name, kind: 'World', detail: '已登记故事路线' }))];
    if (category === 'Character') return (references?.characters || []).map(row => ({ id: row.id, title: row.name, kind: 'Character', detail: '作品人物资料' }));
    if (category === 'Scene') return (draft?.scenes || []).map(row => ({ id: row.id, title: row.heading, kind: 'Scene', detail: [row.location, row.time].filter(Boolean).join(' · ') || `场景 ${row.sequence}` }));
    if (category === 'Shot') return (draft?.shots || []).map(row => ({ id: row.id, title: `镜头 ${row.number}`, kind: 'Shot', detail: `${row.shot_size} · ${row.duration_seconds}s` }));
    return (assets || []).filter(row => row.media_type?.startsWith(category.toLowerCase() + '/') || row.kind?.toLowerCase().includes(category.toLowerCase())).map(row => ({ id: row.id, title: row.filename, kind: category, detail: `${row.media_type} · ${row.size} bytes` }));
  }, [category, draft, references, assets]);
  const filtered = rows.filter(row => `${row.title} ${row.detail}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="creative-asset-browser" aria-label="资产浏览器"><header><span className="creative-eyebrow">Asset Browser</span><h2>创作资产</h2><Button variant="ghost" onClick={onExit}>返回经典工作区</Button></header>
    {mode === 'NOVEL' && <details className="creative-chapters" open><summary>章节与写作工具</summary>{novelSidebar}</details>}
    {mode !== 'NOVEL' && <section aria-label="创作文档"><h3>当前阶段文档</h3>{documents.filter(row => modeForDocument(row.mode) === mode).map(row => <button className="creative-asset-row" aria-pressed={selectedDocumentId === row.id} key={row.id} onClick={() => onDocument(row)}><strong>{row.title}</strong><small>v{row.version} · {row.scenes.length} 场景</small></button>)}{!documents.some(row => modeForDocument(row.mode) === mode) && <p>尚无已保存文档。在画布中创建第一份草稿。</p>}</section>}
    <div className="creative-asset-categories" aria-label="资产类别">{categories.map(({ id, label, icon: Icon }) => <button key={id} aria-pressed={category === id} onClick={() => setCategory(id)}><Icon aria-hidden="true" /><span>{label}<small>{id}</small></span></button>)}</div>
    <label className="creative-field"><span>筛选资产</span><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="名称或描述" /></label>
    {loading && <StatusMessage>正在读取作品资产…</StatusMessage>}{error && <StatusMessage tone="warning">部分资料未能读取。<Button onClick={onRetry}>重试资产</Button></StatusMessage>}
    <div className="creative-asset-list" aria-label={`${category} 资产`}>{filtered.map(row => <button key={row.id} className="creative-asset-row" onClick={() => onSelect(row)}><strong>{row.title}</strong><small>{row.detail}</small></button>)}{!filtered.length && !loading && <EmptyState title={query ? '没有匹配资产' : '此类别暂无可用资料'} detail={category === 'Scene' || category === 'Shot' ? '场景和镜头来自当前文档；可以直接在画布中添加。' : '仅显示服务端已登记且当前身份可读取的资料。'} />}</div>
  </div>;
}
