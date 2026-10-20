import { useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { EditionSegment, LanguageEdition } from './multilingualEditionsClient';

/** Navigate the original saved segment IDs, never inferred text offsets. */
export function TerminologyIssueNavigator({ edition, blocked, onOpen }: {
  edition: LanguageEdition; blocked: boolean; onOpen: (segmentId: string) => void;
}) {
  const [page, setPage] = useState(0);
  if (edition.stale || edition.content_withheld) return null;
  const segments = Array.isArray(edition.segments) ? edition.segments : [];
  const validIdentity = typeof edition.id === 'string' && !!edition.id.trim() && Number.isSafeInteger(edition.version) && edition.version > 0;
  const valid = (segment: EditionSegment) => !!segment
    && typeof segment.id === 'string' && !!segment.id.trim()
    && typeof segment.chapter_id === 'string' && !!segment.chapter_id.trim()
    && Number.isSafeInteger(segment.source_version) && segment.source_version > 0
    && Array.isArray(segment.path) && segment.path.length > 0 && segment.path.every(value => Number.isSafeInteger(value) && value >= 0)
    && typeof segment.source_text === 'string' && typeof segment.target_text === 'string'
    && Array.isArray(segment.issues) && segment.issues.every(issue => !!issue && typeof issue.code === 'string' && !!issue.code.trim()
      && ['rule_id', 'other_rule_id', 'term', 'expected', 'found'].every(key => { const value = issue[key as keyof typeof issue]; return value === undefined || typeof value === 'string'; })
      && (issue.rule_version === undefined || (Number.isSafeInteger(issue.rule_version) && issue.rule_version > 0)));
  if (!validIdentity || segments.some(segment => !valid(segment))) return <StatusMessage tone="warning">术语问题的原段落身份或来源版本不完整；请刷新当前语言版本后再定位。</StatusMessage>;
  const rows = segments.map((segment, index) => ({ segment, index })).filter(({ segment }) => segment.issues.length > 0);
  if (!rows.length) return null;
  const pages = Math.ceil(rows.length / 20);
  const currentPage = Math.min(page, pages - 1);
  return <section className="experimental-section" aria-label="已保存术语问题导航">
    <h4>按原段落处理术语问题</h4>
    <p>语言版本 v{edition.version} · 术语修订 {edition.term_revision ?? '未知'} · {rows.length} 个段落。仅依据已保存内容；未保存输入不参与检查。定位不会替换译文或批准规则。</p>
    <p>打开后在原双语编辑器人工修改，保存草稿、提交审核，再预检术语与版本。不会猜测重复词、组合字符或双向文字的位置。</p>
    {blocked && <StatusMessage>先完成当前操作，或保存／还原未保存译文，再定位其他段落。</StatusMessage>}
    {rows.slice(currentPage * 20, currentPage * 20 + 20).map(({ segment, index }) => <article className="experimental-record" key={`${segment.id}:${index}`}>
      <p>第 {index + 1} 段 · 原稿 v{segment.source_version} · 章节 {segment.chapter_id} · 路径 {segment.path.join('.')} · {segment.issues.length} 项问题</p>
      <Button disabled={blocked || segments.filter(row => row.id === segment.id).length !== 1} onClick={() => onOpen(segment.id)}>定位第 {index + 1} 段术语问题</Button>
    </article>)}
    {pages > 1 && <div className="experimental-actions"><Button disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>上一页问题段落</Button><span>第 {currentPage + 1} / {pages} 页</span><Button disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>下一页问题段落</Button></div>}
  </section>;
}
