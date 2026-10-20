import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { AssetComparisonDownload } from './assetComparisonPreview';
import { Button, StatusMessage } from '../ui/primitives';
import { ASSET_BROWSER_NOTICES, ASSET_BROWSER_UNVERIFIED,
  type AssetBrowserAsset, type AssetBrowserCompareResult } from './assetBrowserTypes';

const ZOOM_STEPS = [1, 1.5, 2, 3] as const;

/** 一个媒体槽：图片可缩放，音视频必须**用户主动开始**，同一时刻只有一个在播。 */
export type AssetMediaSlot = 'LEFT' | 'RIGHT';

/**
 * 音视频预览**互斥**：谁开始播放，谁就成为唯一活动槽；父层因此在同一个事件里
 * 停止另一个槽。切换版本 / 素材同样会让旧槽失活并停止播放。
 */
function MediaSurface({
  asset, slot, zoom, activeSlot, onStartPlayback, onStopPlayback, onZoom, download,
}: {
  asset: AssetBrowserAsset;
  slot: AssetMediaSlot;
  zoom: number;
  activeSlot: AssetMediaSlot | null;
  onStartPlayback: (slot: AssetMediaSlot) => void;
  onStopPlayback: (slot: AssetMediaSlot) => void;
  onZoom: (value: number) => void;
  download?: AssetComparisonDownload;
}) {
  const kind = asset.media_kind;
  const [url, setUrl] = useState('');
  const [state, setState] = useState<'IDLE' | 'LOADING' | 'READY' | 'FAILED'>('IDLE');
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const objectUrl = useRef('');
  const epoch = useRef(0), pending = useRef(false), alive = useRef(false);
  const snapshot = JSON.stringify([asset.id, asset.version, asset.digest, asset.size, asset.media_type, asset.kind, asset.media_kind, asset.branch_id, asset.deleted]);

  // Before paint: no old bytes or playback survive a version / scope / reader change.
  useLayoutEffect(() => {
    epoch.current++; pending.current = false; alive.current = true;
    setUrl(''); setState('IDLE');
    return () => {
      epoch.current++; pending.current = false; alive.current = false;
      const node = media.current;
      if (node) { try { node.pause(); node.currentTime = 0; } catch { /* not loaded */ } }
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = '';
    };
  }, [snapshot, download]);
  useEffect(() => {
    if (activeSlot === slot) return;
    const node = media.current;
    if (node) { try { node.pause(); node.currentTime = 0; } catch { /* not loaded */ } }
  }, [activeSlot, slot]);

  async function load() {
    if (!download || pending.current || !alive.current) return;
    pending.current = true;
    const request = epoch.current;
    const current = () => alive.current && epoch.current === request;
    setState('LOADING');
    // A failed re-read must not leave old media looking like a verified result.
    if (media.current) { try { media.current.pause(); media.current.currentTime = 0; } catch { /* not loaded */ } }
    onStopPlayback(slot);
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = ''; setUrl('');
    try {
      const blob = await download(asset, current);
      if (!current()) return;
      objectUrl.current = URL.createObjectURL(blob);
      setUrl(objectUrl.current); setState('READY');
    } catch {
      if (current()) setState('FAILED');
    } finally {
      if (current()) pending.current = false;
    }
  }

  function mediaFailed(failedUrl: string) {
    // Ignore a decoder event from an element that has already been replaced.
    if (!alive.current || !failedUrl || objectUrl.current !== failedUrl) return;
    if (media.current) { try { media.current.pause(); media.current.currentTime = 0; } catch { /* not loaded */ } }
    onStopPlayback(slot);
    URL.revokeObjectURL(objectUrl.current); objectUrl.current = '';
    setUrl(''); setState('FAILED');
  }

  if (kind === null) {
    return <p className="asset-browser__note">
      此素材没有被归入图片 / 视频 / 音频，无法预览（{ASSET_BROWSER_NOTICES.unverified}）。
    </p>;
  }
  const canDownload = typeof download === 'function';

  return <div className="asset-browser__media" data-kind={kind} data-slot={slot} data-active={activeSlot === slot}>
    {kind === 'image' && <>
      <Button type="button" variant="ghost" disabled={!canDownload || state === 'LOADING'} onClick={() => void load()}>
        {url ? '重新读取图片' : '读取图片预览'}
      </Button>
      {url && <img src={url} alt={`${asset.filename} 预览`} onError={() => mediaFailed(url)} style={{ transform: `scale(${zoom})` }}/>}
      <div className="asset-browser__actions" role="group" aria-label="图片缩放">
        {ZOOM_STEPS.map(step => <Button key={step} type="button" variant="ghost" aria-pressed={zoom === step}
          onClick={() => onZoom(step)}>{step}×</Button>)}
      </div>
    </>}
    {kind === 'audio' && <>
      <Button type="button" variant="ghost" disabled={!canDownload || state === 'LOADING'} onClick={() => void load()}>
        {url ? '重新读取音频' : '读取音频预览（需你主动开始）'}
      </Button>
      {url && <audio ref={media} src={url} controls preload="none" onError={() => mediaFailed(url)} aria-label={`${asset.filename} 音频预览`}
        onPlay={() => onStartPlayback(slot)} onPause={() => { if (activeSlot === slot) onStopPlayback(slot); }}/>}
    </>}
    {kind === 'video' && <>
      <Button type="button" variant="ghost" disabled={!canDownload || state === 'LOADING'} onClick={() => void load()}>
        {url ? '重新读取视频' : '读取视频预览（需你主动开始）'}
      </Button>
      {url && <video ref={media} src={url} controls preload="none" onError={() => mediaFailed(url)} aria-label={`${asset.filename} 视频预览`}
        onPlay={() => onStartPlayback(slot)} onPause={() => { if (activeSlot === slot) onStopPlayback(slot); }}/>}
    </>}
    {(kind === 'audio' || kind === 'video') && activeSlot === slot
      && <Button type="button" variant="ghost" onClick={() => onStopPlayback(slot)}>停止播放（切换到别处会先停止）</Button>}
    {state === 'FAILED' && <StatusMessage tone="error">{ASSET_BROWSER_NOTICES.previewFailed}</StatusMessage>}
  </div>;
}

/**
 * 版本对比：图片缩放 + 上一个 / 下一个版本 + 显式的逐字段差异。
 *
 * - 音视频预览**互斥且由用户主动开始**：同一时刻只有一个槽在播放；切到另一个版本
 *   或另一条素材会先停止旧播放。
 * - 对比结论只来自 `compareVersions()`：相同 / 不同 / 无法核实三种情况分别列出；
 *   无法核实绝不写成"相同"。
 * - 旧的版本列表来自 owner 已披露的来源投影（调用方传入），这里**不**发明版本历史。
 */
export function AssetComparePanel({
  current, other, candidates, otherId, comparison, download, onPick, onZoom, onStartPlayback, onStopPlayback,
  activeSlot, zoom,
}: {
  current: AssetBrowserAsset;
  other?: AssetBrowserAsset;
  candidates: readonly { id: string; version: number | null; digest: string; label: string }[];
  otherId: string | null;
  comparison?: AssetBrowserCompareResult;
  download?: AssetComparisonDownload;
  onPick: (assetId: string) => void;
  onZoom: (value: number) => void;
  onStartPlayback: (slot: AssetMediaSlot) => void;
  onStopPlayback: (slot: AssetMediaSlot) => void;
  activeSlot: AssetMediaSlot | null;
  zoom: number;
}) {
  const index = candidates.findIndex(candidate => candidate.id === otherId);
  const previous = index > 0 ? candidates[index - 1] : undefined;
  const next = index >= 0 && index < candidates.length - 1 ? candidates[index + 1] : undefined;
  return <section className="asset-browser__compare" aria-label="版本对比">
    <header>
      <h3>版本对比</h3>
      <p className="asset-browser__note">
        对比只显示老 / 新版本的差异。选择另一个版本不会更新任何镜头、节点或时间线；
        只有你在各自模块里明确选择，绑定才会变化。
      </p>
    </header>
    <div className="asset-browser__compare-picks">
      <Button type="button" variant="ghost" disabled={!previous}
        onClick={() => previous && onPick(previous.id)}>
        {previous ? `上一个版本 v${previous.version ?? ASSET_BROWSER_UNVERIFIED}` : '上一个版本（未披露）'}
      </Button>
      <Button type="button" variant="ghost" disabled={!next}
        onClick={() => next && onPick(next.id)}>
        {next ? `下一个版本 v${next.version ?? ASSET_BROWSER_UNVERIFIED}` : '下一个版本（未披露）'}
      </Button>
    </div>
    <div className="asset-browser__compare-grid">
      <div className="asset-browser__compare-side" role="group" aria-label="当前版本预览">
        <h4>当前 v{current.version ?? ASSET_BROWSER_UNVERIFIED}</h4>
        <MediaSurface asset={current} slot="LEFT" zoom={zoom} activeSlot={activeSlot}
          onStartPlayback={onStartPlayback} onStopPlayback={onStopPlayback} onZoom={onZoom} download={download}/>
      </div>
      <div className="asset-browser__compare-side" role="group" aria-label="对比版本预览">
        <h4>对比版本</h4>
        {candidates.length === 0
          ? <p className="asset-browser__note">原 owner 未披露任何可对比版本；无法对比。</p>
          : <>
            <label className="asset-browser__field">
              <span>选择对比版本</span>
              <select aria-label="选择对比版本" value={otherId ?? ''} onChange={event => onPick(event.target.value)}>
                <option value="">请选择</option>
                {candidates.map(candidate => <option key={candidate.id} value={candidate.id}>
                  {candidate.label} · {candidate.version === null ? `v${ASSET_BROWSER_UNVERIFIED}` : `v${candidate.version}`}
                </option>)}
              </select>
            </label>
            {other && other.id === otherId && <>
              <p className="asset-browser__note">{other.filename} · v{other.version ?? ASSET_BROWSER_UNVERIFIED}</p>
              <MediaSurface asset={other} slot="RIGHT" zoom={zoom} activeSlot={activeSlot}
                onStartPlayback={onStartPlayback} onStopPlayback={onStopPlayback} onZoom={onZoom} download={download}/>
            </>}
            {otherId && !other && <p className="asset-browser__note">对比版本尚未核实，预览未读取。</p>}
            {comparison && <p className="asset-browser__note">
              对比目标 {comparison.right_id} · {comparison.same_asset ? '同一资产的不同版本' : '不同资产（内容以 SHA-256 核对）'}
            </p>}
          </>}
      </div>
    </div>
    {comparison
      ? <table className="asset-browser__delta">
        <caption>逐字段差异（{comparison.changed.length} 项不同 · {comparison.unverifiable.length} 项无法核实）</caption>
        <thead><tr><th scope="col">字段</th><th scope="col">当前</th><th scope="col">对比</th><th scope="col">结论</th></tr></thead>
        <tbody>{comparison.entries.map(entry => <tr key={entry.field} data-verdict={entry.verdict}>
          <th scope="row">{entry.label}</th>
          <td>{entry.left ?? ASSET_BROWSER_UNVERIFIED}</td>
          <td>{entry.right ?? ASSET_BROWSER_UNVERIFIED}</td>
          <td>{entry.verdict === 'SAME' ? '相同' : entry.verdict === 'DIFFERENT' ? '不同' : '无法核实'}</td>
        </tr>)}</tbody>
      </table>
      : <p className="asset-browser__note">选择一个对比版本后才会显示逐字段差异。</p>}
    {comparison && !comparison.differs && comparison.unverifiable.length > 0 && <StatusMessage tone="warning">
      没有任何字段被核实为不同，但有 {comparison.unverifiable.length} 个字段原 owner 未披露；
      这不等于"完全相同"。
    </StatusMessage>}
    {comparison?.content_differs === true && <StatusMessage tone="warning">
      两边的 SHA-256 不同：内容确实不同。是否跟随新版本由你决定。
    </StatusMessage>}
  </section>;
}
