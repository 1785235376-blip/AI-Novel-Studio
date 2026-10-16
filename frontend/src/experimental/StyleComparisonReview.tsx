import { useLayoutEffect, useRef, useState } from 'react';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import type { StyleAnalysis } from './styleReviewClient';
import type { WorkspaceNavigation } from './uxClient';
import { measuredRatio, readStyleComparison } from './styleComparison';
const labels = { sentence_length_mean: '平均句长（非空白字符）', paragraph_length_mean: '平均段落长度（非空白字符）', dialogue_share_nonspace: '引号内对白占比', repeated_unit_share: '重复词单元占比' };
function ratioText(value: unknown) {
  const ratio = measuredRatio(value);
  return !ratio ? '测量不可用' : ratio.denominator === 0 ? '没有可测量单位（0 / 0）' : `${ratio.numerator} / ${ratio.denominator} = ${(ratio.numerator / ratio.denominator).toFixed(3)}`;
}
export function StyleComparisonReview({ row, onNavigate }: { row: StyleAnalysis; onNavigate?: (target: WorkspaceNavigation) => void }) {
  const [page, setPage] = useState(0), [leaving, setLeaving] = useState(false);
  const intent = useRef(false);
  useLayoutEffect(() => { intent.current = false; setLeaving(false); return () => { intent.current = false; }; }, [row.id, row.version, row.comparison, row.stale]);
  if (row.stale || row.comparison == null) return null;
  const target = readStyleComparison(row.comparison);
  if (!target) return <StatusMessage tone="warning">保存的比较证据格式不完整，不能定位目标。请刷新报告或重新分析。</StatusMessage>;
  const comparable = target.comparable && target.language === row.language && target.interpretation === 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT';
  const metricLabels = { ...labels, repeated_unit_share: target.language === 'zh' ? '重复汉字单元占比（非分词）' : '重复英文词单元占比' };
  const pages = Math.max(1, Math.ceil(target.paragraphs.length / 20)), currentPage = Math.min(page, pages - 1);
  return <section aria-label={`样本与目标比较 ${row.id}`}>
    <h4>已保存样本与目标原文核对</h4>
    <p>参考：档案 {row.style_id} v{row.style_version} · {row.language === 'zh' ? '中文汉字方法' : '英文词方法'}。目标：{target.chapter_id} v{target.expected_version} · {target.language === 'zh' ? '中文汉字方法' : '英文词方法'}。</p>
    <StatusMessage>这些比例只描述所选文本。篇幅、选区与标点会影响结果；不提供校准漂移阈值、风格匹配分数或文学质量判断。请结合下面的目标原文与上方来源样本逐项核对，再自行决定是否编辑已有风格档案或正文。</StatusMessage>
    {(row.metrics.sample_sufficiency === 'SHORT_SAMPLE' || target.metrics.sample_sufficiency === 'SHORT_SAMPLE') && <Badge tone="warning">短样本：至少一侧少于五个句子，不能据此概括整体文风</Badge>}
    {!comparable ? <StatusMessage tone="warning">语言或测量方法不一致，不作跨方法比例比较；原文仍可人工核对。</StatusMessage> : <dl className="experimental-meta">{Object.entries(metricLabels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>参考样本：{ratioText(row.metrics[key])}；目标全文：{ratioText(target.metrics[key])}</dd></div>)}</dl>}
    <p>参考样本的独立测量与原文位于上方“来源样本”。目标段落仅展示已保存的证据，打开正文交由原编辑器核对版本与未保存输入；此处不会选择文字、保存或改写。</p>
    {onNavigate && <Button onClick={() => { intent.current = true; setLeaving(true); }}>打开比较目标原章节 v{target.expected_version}</Button>}
    {leaving && onNavigate && <section aria-label="确认离开文风核对">
      <StatusMessage tone="warning">打开章节会离开此文风面板，未保存的风格档案输入和文风意见审核理由将丢失。若有未确认的保存请求，请先取消离开并核对结果。本操作不会保存这些输入。</StatusMessage>
      <p>目标：{target.chapter_id} v{target.expected_version}。这不是历史原文回放；编辑器会核对当前章节版本。</p>
      <Button onClick={() => { intent.current = false; setLeaving(false); }}>取消离开，保留文风输入</Button>
      <Button onClick={() => { if (!intent.current) return; intent.current = false; setLeaving(false); onNavigate({ kind: 'chapter', id: target.chapter_id, version: target.expected_version }); }}>确认放弃未保存文风输入并打开章节</Button>
    </section>}
    {!onNavigate && <StatusMessage>当前宿主未接入章节导航，仍可核对下面的已保存原文。</StatusMessage>}
    <details className="experimental-details"><summary>比较目标的逐段原文与测量</summary>
      {!target.paragraphs.length && <p>此目标没有已保存的非空段落证据。</p>}
      {target.paragraphs.slice(currentPage * 20, (currentPage + 1) * 20).map(paragraph => <section key={`${paragraph.paragraph}:${paragraph.start}`}>
        <p>目标 {target.chapter_id} v{target.expected_version} · 原始 Markdown 段落 {paragraph.paragraph} · Unicode 范围 {paragraph.start}–{paragraph.end}（结束位置不包含）</p>
        <Field label={`比较目标 ${row.id} 段落 ${paragraph.paragraph} 原文`}><textarea readOnly value={paragraph.quote} /></Field>
        <dl className="experimental-meta">{Object.entries(metricLabels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{ratioText(paragraph.metrics[key])}</dd></div>)}</dl>
      </section>)}
      {pages > 1 && <div className="experimental-actions"><Button disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>上一页目标段落</Button><span>第 {currentPage + 1} / {pages} 页（每页最多 20 段）</span><Button disabled={currentPage + 1 === pages} onClick={() => setPage(currentPage + 1)}>下一页目标段落</Button></div>}
      {target.paragraphs_truncated && <StatusMessage tone="warning">报告仅保存前 200 个目标段落；全文测量仍包括其余正文，未展示的段落不代表没有差异。</StatusMessage>}
    </details>
  </section>;
}
