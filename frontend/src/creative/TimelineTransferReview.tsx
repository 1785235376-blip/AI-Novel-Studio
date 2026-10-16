import { useState } from 'react';
import { Button } from '../ui/primitives';
import type { TimelineTransferPreview } from './studioTimelineTransferTypes';
import { transferClipTarget, transferLossText } from './timelineTransferReview';

export function TimelineTransferReview({ preview, disabled, onLocate }: { preview: TimelineTransferPreview; disabled: boolean;
  onLocate?: (preview: TimelineTransferPreview, path: string) => void }) {
  const [page, setPage] = useState(0);
  const offset = Math.min(page, Math.max(0, Math.ceil(preview.loss_report.length / 20) - 1)) * 20;
  return <section aria-label="交换兼容性逐项检查">
    {preview.format === 'OTIO' && <p>OTIO 原生子集保留轨道、片段、间隙、源范围、时间位置和受支持的变速。Studio 扩展保留的效果不等于外部软件能执行；外部修改后扩展可能无法恢复。</p>}
    <p>这里只定位当前导出快照对应的原编辑片段，不修改、修复或执行交换。导入路径属于外部文件，不能按相同序号定位当前草稿。</p>
    <ol start={offset + 1}>{preview.loss_report.slice(offset, offset + 20).map((loss, index) => {
      const target = transferClipTarget(preview, loss.path);
      return <li key={offset + index}><p>{transferLossText[loss.code] ?? '原转换器报告此限制；保留原代码供核对，不推断兼容性。'} · {loss.severity}</p>
        <p><code>{loss.path}</code> · <code>{loss.code}</code></p>
        {target ? <><p>轨道 {target.track.order + 1} · 片段 <code>{target.clip.id}</code> · 素材 <code>{target.clip.source_snapshot.id}</code> · v{target.clip.source_snapshot.version}</p>
          <details><summary>精确来源与时间</summary><p>摘要 <code>{target.clip.source_snapshot.digest}</code></p><p>放入 {target.clip.start_ms} ms · 源范围 [{target.clip.in_ms}, {target.clip.out_ms}) ms · 速度 {target.clip.speed_num ?? 1}/{target.clip.speed_den ?? 1}</p>
            <p>时间以原整数毫秒和有理数速度显示，不舍入到帧。素材引用只作文本，不读取媒体。</p>
            {preview.media_bindings.filter(binding => (['id', 'kind', 'asset_kind', 'version', 'digest'] as const).every(key => binding.source_snapshot[key] === target.clip.source_snapshot[key])).map(binding => <p key={binding.reference}><code>{binding.reference}</code></p>)}
          </details><Button disabled={disabled || !onLocate} onClick={() => onLocate?.(preview, loss.path)}>定位原片段 {target.clip.id}</Button></>
          : <p>此项没有可证明的原编辑片段定位；请按原路径核对。</p>}
      </li>;
    })}</ol>
    {preview.loss_report.length > 20 && <div><Button disabled={!offset} onClick={() => setPage(Math.max(0, page - 1))}>上一页限制</Button>
      <span>{offset + 1}–{Math.min(offset + 20, preview.loss_report.length)} / {preview.loss_report.length}</span>
      <Button disabled={offset + 20 >= preview.loss_report.length} onClick={() => setPage(page + 1)}>下一页限制</Button></div>}
  </section>;
}
