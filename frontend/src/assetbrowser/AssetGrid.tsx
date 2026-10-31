import { useEffect, useRef, useState } from 'react';
import { File, Image as ImageIcon, Music2, Video } from 'lucide-react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { ASSET_BROWSER_MEDIA_KIND_LABELS, ASSET_BROWSER_NOTICES, ASSET_BROWSER_REVIEW_LABELS,
  type AssetBrowserRow, type AssetBrowserViewMode } from './assetBrowserTypes';

const iconFor = (mediaType: string) => mediaType.startsWith('image/') ? <ImageIcon aria-hidden="true"/>
  : mediaType.startsWith('video/') ? <Video aria-hidden="true"/>
    : mediaType.startsWith('audio/') ? <Music2 aria-hidden="true"/> : <File aria-hidden="true"/>;

const formatBytes = (size: number | null) => {
  if (size === null) return ASSET_BROWSER_NOTICES.unverified;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
};

/**
 * 缩略图：只在**真的需要**时按既有下载接口读取一次（`IntersectionObserver`
 * 决定"需要"），并且只对图片类型读取。绝不预取整库、绝不扫描磁盘。
 */
function useOnDemandThumbnail(
  row: AssetBrowserRow, download?: (assetId: string) => Promise<Blob>, enabled = true,
) {
  const [visible, setVisible] = useState(false);
  const [url, setUrl] = useState('');
  const [failed, setFailed] = useState(false);
  const holder = useRef<HTMLDivElement>(null);
  const wanted = enabled && !!download && row.media_type.startsWith('image/');

  useEffect(() => {
    if (!wanted) return;
    const node = holder.current;
    if (!node || typeof IntersectionObserver === 'undefined') { setVisible(true); return; }
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) setVisible(true);
    }, { rootMargin: '160px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [wanted, row.id]);

  useEffect(() => {
    if (!wanted || !visible || !download) return;
    let active = true;
    let objectUrl = '';
    setUrl(''); setFailed(false);
    void download(row.id).then(blob => {
      if (!active) return;
      try { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
      catch { setFailed(true); }
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [wanted, visible, download, row.id, row.digest]);

  return { holder, url, failed, wanted };
}

function referenceText(row: AssetBrowserRow): string {
  if (row.reference_counts === null) return `引用 ${ASSET_BROWSER_NOTICES.unverified}`;
  return row.reference_counts.total
    ? `被引用 ${row.reference_counts.total} 处${row.reference_counts.not_current ? ` · ${row.reference_counts.not_current} 处需核对` : ''}`
    : '未被引用（已核实）';
}

/**
 * 网格 / 列表共用**同一个**行渲染与**同一个**选择模型；`mode` 只决定容器类名和
 * 是否显示缩略图（列表同样可以显示）。切换模式不会改变选中项。
 */
export function AssetGrid({
  rows, mode, selectedId, busy, download, onSelect,
}: {
  rows: readonly AssetBrowserRow[];
  mode: AssetBrowserViewMode;
  selectedId: string | null;
  busy: boolean;
  download?: (assetId: string) => Promise<Blob>;
  onSelect: (assetId: string) => void;
}) {
  return <div className="asset-browser__grid-wrap">
    <ul className={`asset-browser__grid asset-browser__grid--${mode.toLocaleLowerCase()}`}
      aria-label="素材列表" data-mode={mode}>
      {rows.map(row => <AssetCard key={row.id} row={row} mode={mode} selected={selectedId === row.id}
        busy={busy} download={download} onSelect={() => onSelect(row.id)}/>)}
    </ul>
    {!rows.length && <StatusMessage>{ASSET_BROWSER_NOTICES.noMatch}</StatusMessage>}
  </div>;
}

function AssetCard({
  row, mode, selected, busy, download, onSelect,
}: {
  row: AssetBrowserRow;
  mode: AssetBrowserViewMode;
  selected: boolean;
  busy: boolean;
  download?: (assetId: string) => Promise<Blob>;
  onSelect: () => void;
}) {
  const { holder, url, failed, wanted } = useOnDemandThumbnail(row, download, mode === 'GRID');
  return <li className={`asset-browser__card${selected ? ' is-selected' : ''}`}>
    <button type="button" className="asset-browser__card-select" aria-pressed={selected}
      aria-label={`选择素材 ${row.filename}`} disabled={busy} onClick={onSelect}>
      {mode === 'GRID' && <div ref={holder} className="asset-browser__thumb" aria-busy={wanted && !url && !failed}>
        {url && <img src={url} alt={`${row.filename} 缩略图`} loading="lazy" onError={() => { /* 失败的缩略图不影响选择 */ }}/>}
        {!url && !failed && <span className="asset-browser__thumb-fallback" aria-hidden="true">{iconFor(row.media_type)}</span>}
        {failed && <span className="asset-browser__thumb-fallback" role="status">缩略图未读取</span>}
      </div>}
      <header>
        <strong title={row.filename}>{row.filename}</strong>
        <span className="asset-browser__meta">
          {row.media_kind ? ASSET_BROWSER_MEDIA_KIND_LABELS[row.media_kind] : row.kind} · {row.media_type}
        </span>
      </header>
      <dl className="asset-browser__facts">
        <div><dt>版本</dt><dd>{row.version === null ? ASSET_BROWSER_NOTICES.unverified : `v${row.version}`}</dd></div>
        <div><dt>大小</dt><dd>{formatBytes(row.size)}</dd></div>
        <div><dt>审核</dt><dd>{ASSET_BROWSER_REVIEW_LABELS[row.review_state]}</dd></div>
        <div><dt>引用</dt><dd>{referenceText(row)}</dd></div>
      </dl>
      <div className="asset-browser__badges">
        {row.tags.map(tag => <Badge key={tag} tone="neutral">{tag}</Badge>)}
        {row.stale === true && <Badge tone="warning">来源已过期</Badge>}
        {row.integrity !== null && row.integrity !== 'VERIFIED'
          && <Badge tone="warning">{row.integrity === 'DELETED' ? '已删除' : '内容不可读'}</Badge>}
        {row.reference_counts === null && <Badge tone="neutral">引用{ASSET_BROWSER_NOTICES.unverified}</Badge>}
      </div>
    </button>
  </li>;
}
