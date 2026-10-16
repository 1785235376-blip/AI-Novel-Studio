import { TimelineTransferReview } from './TimelineTransferReview';
import type { TimelineTransferPreview } from './studioTimelineTransferTypes';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioAsset } from './studioClient';
import type { StudioTimelineTransferController } from './useStudioTimelineTransfer';
import type { TimelineTransferDirection, TimelineTransferFormat } from './studioTimelineTransferTypes';

/** Replaceable presentation; transfer ownership and private drafts stay in the controller. */
export function StudioTimelineTransferPanel({ controller: c, assets, onLocate }: { controller: StudioTimelineTransferController; assets: StudioAsset[]; onLocate?: (preview: TimelineTransferPreview, path: string) => void }) {
  if (!c.available || !c.owns) return null;
  return <section aria-label="时间线和字幕交换"><h3>时间线与字幕交换</h3>
    <p>操作绑定当前保存版本。OTIO 导入需要逐项绑定正式素材；SRT/VTT 导入替换字幕。先保存草稿，再预览和确认转换。</p>
    {!c.canOperate && !c.pending && !c.unknown && <StatusMessage tone="info">请先读取或保存时间线，并核对当前素材版本。未保存的编辑不能参与交换。</StatusMessage>}
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage tone="info">{c.notice}</StatusMessage>}
    <fieldset disabled={!c.canOperate}><legend>交换设置</legend>
      <label>方向<select value={c.direction} onChange={event => c.change({ direction: event.currentTarget.value as TimelineTransferDirection, content: '', mappings: [] })}>
        <option value="EXPORT">导出当前保存版本</option><option value="IMPORT">导入到当前时间线</option></select></label>
      <label>格式<select value={c.format} onChange={event => c.change({ format: event.currentTarget.value as TimelineTransferFormat, mappings: [] })}>
        <option value="OTIO">OTIO 时间线</option><option value="SRT">SRT 字幕</option><option value="VTT">WebVTT 字幕</option></select></label>
      {c.direction === 'IMPORT' && <><label>选择本地 {c.format} 文件<input type="file" accept={`.${c.format.toLowerCase()}`}
        onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; void c.selectFile(file); }} /></label>
        <p>请选择 UTF-8 文件，最多 {c.format === 'OTIO' ? '2 MiB' : '192000 字节'}。读取后仍需核对内容与转换预览。</p>
        <label>文件内容<textarea rows={8} maxLength={c.format === 'OTIO' ? 2 * 1024 * 1024 : 192000}
        value={c.content} onChange={event => c.change({ content: event.currentTarget.value, mappings: [] })} /></label>
        <p>内容只在当前会话的交换草稿中保留，不会自动修改原文件。当前目标画布尺寸与帧率用于导入；未变的 Studio 元数据与不同画布会拒绝转换。</p>
        {c.format === 'OTIO' && <><Button onClick={c.discoverReferences}>识别文件中的媒体引用</Button>
          <p>引用文字只用于明确映射，不会自动打开、下载或扫描外部媒体。</p>
          {c.mappings.map((mapping, index) => <label key={mapping.reference}>引用 {index + 1} <code>{mapping.reference}</code>
            <select value={mapping.assetId} onChange={event => c.change({ mappings: c.mappings.map((row, i) => i === index ? { ...row, assetId: event.currentTarget.value } : row) })}>
              <option value="">选择已有正式素材</option>{assets.filter(asset => !asset.deleted_at && ['image', 'video', 'audio'].includes(asset.kind)).map(asset =>
                <option key={asset.id} value={asset.id}>{asset.filename} · {asset.kind} · v{asset.version}</option>)}</select></label>)}</>}
      </>}
    </fieldset>
    {c.pending === 'FILE' && <StatusMessage tone="info">正在读取所选文件到本轮交换草稿。</StatusMessage>}
    <Button loading={c.pending === 'PREVIEW'} disabled={!c.canOperate || c.direction === 'IMPORT' && (!c.content.trim() || c.format === 'OTIO' && (!c.mappings.length || c.mappings.some(row => !row.assetId)))} onClick={() => void c.previewTransfer()}>读取转换预览</Button>
    {c.preview && <section aria-label="转换预览"><h4>待确认预览</h4>
      <p>{c.preview.timeline.tracks.length} 条轨道 · {c.preview.timeline.tracks.reduce((sum, track) => sum + track.clips.length, 0)} 个片段 · {c.preview.timeline.captions.length} 条字幕 · {(c.preview.timeline.duration_ms / 1000).toFixed(3)} 秒</p>
      <details><summary>片段、素材与字幕</summary>{c.preview.timeline.tracks.map(track => <div key={track.id}>
        <p>{track.kind === 'VIDEO' ? '视频' : '音频'}轨道 {track.order + 1} · {track.role ?? '原用途'} · {track.locked ? '锁定' : '可编辑'} · {track.muted ? '隐藏或静音' : '参与渲染'} · {track.gain_db} dB</p><ul>{track.clips.map(clip => <li key={clip.id}>
          <p>{assets.find(asset => asset.id === clip.source_snapshot.id)?.filename ?? '素材不可用'} · v{clip.source_snapshot.version} · 放入 {clip.start_ms} ms · 入点 {clip.in_ms} — 出点 {clip.out_ms} ms</p>
          <p>速度 {clip.speed_num ?? 1}/{clip.speed_den ?? 1} · 淡入 {clip.fade_in_ms ?? 0} ms · 淡出 {clip.fade_out_ms ?? 0} ms · {clip.muted ? '隐藏或静音' : '参与渲染'} · 片段音量 {clip.gain_db ?? 0} dB</p>
          {track.kind === 'VIDEO' && <p>位置 {clip.x}, {clip.y} · 尺寸 {clip.width} × {clip.height} · 不透明度 {clip.opacity ?? 1} · {clip.include_audio ? '加入视频原声' : '未加入视频原声'}{clip.crop && <> · 源裁剪 {clip.crop.x}, {clip.crop.y}, {clip.crop.width} × {clip.crop.height}</>}</p>}
          {clip.transition_out && <p>交叉溶解：片段 <code>{clip.id}</code> → <code>{clip.transition_out.to_clip_id}</code> · 重叠窗口 {clip.transition_out.duration_ms} ms。
            {c.format === 'OTIO' && <>该关系保留在 Studio 元数据中，外部剪辑软件的原生轨道不能保真还原；请核对对应损失。</>}</p>}
        </li>)}</ul></div>)}
        <ul>{c.preview.timeline.captions.map((cue, index) => <li key={index}>{cue.start_ms} — {cue.end_ms} ms · {cue.text}</li>)}</ul></details>
      <details><summary>版本和转换摘要</summary><p>原 v{c.preview.timeline_snapshot.version} · <code>{c.preview.timeline_snapshot.digest}</code></p>
        <p>转换 <code>{c.preview.timeline_digest}</code> · 预览 <code>{c.preview.preview_digest}</code></p></details>
      {c.preview.loss_report.length > 0 && <><Badge tone="warning">{c.preview.loss_report.length} 个损失或互通限制</Badge>
        <TimelineTransferReview key={c.preview.preview_digest} preview={c.preview} disabled={!c.canOperate || !!c.pending || !!c.unknown} onLocate={onLocate} />
        <label><input type="checkbox" disabled={!c.canOperate} checked={c.acknowledged} onChange={event => c.setAcknowledged(event.currentTarget.checked)} />已读取全部损失和互通限制，接受本次转换</label></>}
      <label><input type="checkbox" disabled={!c.canOperate} checked={c.confirmed} onChange={event => c.setConfirmed(event.currentTarget.checked)} />已核对原版本、素材、片段与字幕，确认本次{c.direction === 'IMPORT' ? '导入并保存新版本' : '读取交换附件'}</label>
      <Button variant="primary" loading={c.pending === 'IMPORT' || c.pending === 'ATTACHMENT'} disabled={!c.canOperate || !c.confirmed || c.preview.requires_loss_acknowledgment && !c.acknowledged}
        onClick={() => void (c.direction === 'IMPORT' ? c.importTransfer() : c.attachmentTransfer())}>{c.direction === 'IMPORT' ? '明确导入到原时间线' : '读取并核对附件'}</Button>
    </section>}
    {c.unknown && <StatusMessage tone="warning">本次导入状态为 UNKNOWN。原请求 <code>{c.unknown.requestId}</code> 保留，编辑和再次导入暂时锁定；只有匹配原保存回执才采用结果。</StatusMessage>}
    {c.unknown && <Button loading={c.pending === 'CHECK'} disabled={!!c.pending} onClick={() => void c.checkOriginal()}>读取本次请求的原时间线回执</Button>}
    {c.attachment && <p><a href={c.attachment.url} download={c.attachment.filename}>保存 {c.attachment.filename}</a> · {c.attachment.bytes} 字节 · SHA256 <code>{c.attachment.digest}</code></p>}
    <Button disabled={!!c.pending || !!c.unknown} onClick={c.clear}>清除本轮交换草稿和附件</Button>
    <p>Resolve / Premiere 互通与完整产品验收仍待执行；这些操作不渲染媒体、不调用模型。</p>
  </section>;
}
