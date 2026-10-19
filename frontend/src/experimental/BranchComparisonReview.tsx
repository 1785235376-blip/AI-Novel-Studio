import { useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { Details } from './shared';
import { branchBlockExcerpt, branchSegment, branchSegmentLabels, type BranchComparison, type BranchReference } from './branchComparisonReviewHelpers';

function Receipt({ label, value }: { label: string; value: BranchReference }) {
  return <article className="experimental-record"><strong>{label}</strong>
    <p>章节 {value.id || 'UNKNOWN'} · v{value.version} · 分支 {value.branch_id === null ? '主线' : value.branch_id || 'UNKNOWN'}</p>
    <p>正文摘要：{value.document_digest || 'UNKNOWN'}</p>
    {value.is_archived && <Badge tone="warning">已归档</Badge>}
  </article>;
}
function Excerpt({ label, value }: { label: string; value: unknown }) {
  const excerpt = branchBlockExcerpt(value);
  return <div><strong>{label}</strong><p>{excerpt.text}</p>{excerpt.limited && <StatusMessage tone="warning">摘要已截断，请展开完整富文本块核对。</StatusMessage>}</div>;
}

export function BranchComparisonReview({ comparison, choices }: { comparison: BranchComparison; choices: Record<string, 'ORIGINAL' | 'FORK'> }) {
  const [page, setPage] = useState(0), [changesOnly, setChangesOnly] = useState(true);
  const rows = comparison.segments.map((value, index) => ({ value, index, segment: branchSegment(value) }))
    .filter(row => !changesOnly || row.segment.kind !== 'UNCHANGED');
  const pages = Math.max(1, Math.ceil(rows.length / 20)), current = Math.min(page, pages - 1);
  return <section aria-label="三方差异人工阅读">
    <Receipt label="当前分支（待采用内容）" value={comparison.source} />
    <Receipt label="当前来源（拟写入目标）" value={comparison.target} />
    <p>比较摘要：{comparison.preview_digest || 'UNKNOWN'}</p>
    <p>仅显示这次读取的版本；未证明它们仍为最新。纯文本摘要不展示格式、锁定标记或嵌入对象；完整富文本差异仍为核对依据。分叉基线版本未由此比较接口单独提供。</p>
    <StatusMessage>{comparison.can_apply ? '原比较结果：无待解决冲突，仍需原提案和人工确认流程。' : `原比较结果：待解决冲突 ${comparison.conflicts.length}，尚不可提交。`}</StatusMessage>
    <label className="experimental-check"><input type="checkbox" checked={changesOnly} onChange={event => { setChangesOnly(event.target.checked); setPage(0); }} />只看有改动的块</label>
    <p aria-live="polite">共 {rows.length} 段 · 第 {current + 1} / {pages} 页</p>
    {!rows.length && <p>当前筛选没有差异块；文档根属性冲突仍需在原人工选择中检查。</p>}
    {rows.slice(current * 20, current * 20 + 20).map(({ value, index, segment }) => <article className="experimental-record" key={index} aria-label={`比较段 ${index + 1}`}>
      <strong>比较段 {index + 1}</strong><Badge>{typeof segment.kind === 'string' && Object.hasOwn(branchSegmentLabels, segment.kind) ? branchSegmentLabels[segment.kind] : '未知差异类型'}</Badge>
      {Number.isSafeInteger(segment.start) && Number.isSafeInteger(segment.end) && <p>基线块范围 [{String(segment.start)}, {String(segment.end)})（从 0 开始；不是字符位置）</p>}
      {segment.kind === 'UNCHANGED' ? <Excerpt label="共同正文" value={segment.nodes} /> : <><Excerpt label="分叉基线" value={segment.base} /><Excerpt label="当前来源" value={segment.ORIGINAL} /><Excerpt label="当前分支" value={segment.FORK} /></>}
      {segment.kind === 'CONFLICT' && <p>当前人工选择：{choices[String(index)] === 'ORIGINAL' ? '保留当前来源' : choices[String(index)] === 'FORK' ? '采用当前分支' : '尚未选择'}（仅针对本次比较）</p>}
      <Details label={`比较段 ${index + 1} 完整富文本块`} value={value} />
    </article>)}
    <div className="experimental-actions"><Button disabled={current === 0} onClick={() => setPage(current - 1)}>差异上一页</Button><Button disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>差异下一页</Button></div>
  </section>;
}
