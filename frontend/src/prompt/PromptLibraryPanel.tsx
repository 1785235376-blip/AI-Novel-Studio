/**
 * Prompt Library（R3-U3-C2）。
 *
 * 只对**已加载且已授权**的条目做搜索与筛选，并把这一点说清楚：后端的读取有上限，
 * 已加载条目数不等于整个项目的 Prompt 总数。
 */
import { useMemo, useState } from 'react';

import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { PromptEntry, PromptLibrary } from './promptTypes';
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-EN]

type Props = {
  library: PromptLibrary | null;
  loading: boolean;
  error: string | null;
  selectedFamilyId: string | null;
  onSelect: (familyId: string) => void;
  onRefresh: () => void;
  onNew: () => void;
};

const anomalyLabels: Record<string, string> = {
  DUPLICATE_REVISION: '同一修订号出现多份',
  REVISION_GAP: '修订号不连续',
  REVISION_UNAVAILABLE: '有修订已删除或不可读',
  BROKEN_PREDECESSOR: '上一版本引用断裂',
  CROSS_FAMILY_LINK: '跨家族引用',
};

export function PromptLibraryPanel(props: Props) {
  const z = useTz();
  const { library, loading, error, selectedFamilyId, onSelect, onRefresh, onNew } = props;
  const [query, setQuery] = useState('');
  const [purpose, setPurpose] = useState('ALL');
  const [review, setReview] = useState('ALL');

  const visible = useMemo(() => {
    if (!library) return [];
    const needle = query.trim().toLowerCase();
    return library.entries.filter(entry => {
      if (purpose !== 'ALL' && entry.purpose !== purpose) return false;
      if (review === 'DRAFT' && entry.reviewStatus !== 'DRAFT') return false;
      if (review === 'APPROVED' && entry.reviewStatus !== 'APPROVED') return false;
      if (!needle) return true;
      // Only search what we actually loaded, and never the masked body: a REDACTED or
      // unavailable body has no text to match, so it cannot leak through search.
      const haystack = [
        entry.familyId, entry.purpose, entry.reviewStatus,
        String(entry.fields.find(row => row.field === 'model_reference')?.value ?? ''),
        entry.body.state === 'COMPLETE' || entry.body.state === 'TRUNCATED' ? entry.body.value : '',
        ...entry.fields.filter(row => row.authored && typeof row.value === 'string')
          .map(row => String(row.value)),
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(needle);
    });
  }, [library, query, purpose, review]);

  const incomplete = !!library && (!library.readComplete || library.hasMore || library.truncated);

  return (
    <section className="prompt-library" aria-label={z('Prompt 列表')}>
      <div className="prompt-library-actions">
        <Button onClick={onNew}>{z('新建 Prompt')}</Button>
        <Button onClick={onRefresh} disabled={loading}>{z(loading ? '正在读取…' : '重新读取')}</Button>
      </div>

      <div className="prompt-filters">
        <label htmlFor="prompt-search">{z('搜索')}</label>
        <input id="prompt-search" type="search" value={query} placeholder={z('在当前已加载的 Prompt 中搜索')}
          onChange={event => setQuery(event.target.value)} />
        <label htmlFor="prompt-purpose">{z('用途')}</label>
        <select id="prompt-purpose" value={purpose} onChange={event => setPurpose(event.target.value)}>
          <option value="ALL">{z('全部')}</option>
          <option value="IMAGE">IMAGE</option>
          <option value="VIDEO">VIDEO</option>
          <option value="AUDIO">AUDIO</option>
          <option value="TEXT">TEXT</option>
        </select>
        <label htmlFor="prompt-review">{z('状态')}</label>
        <select id="prompt-review" value={review} onChange={event => setReview(event.target.value)}>
          <option value="ALL">{z('全部')}</option>
          <option value="DRAFT">{z('草稿')}</option>
          <option value="APPROVED">{z('已审核')}</option>
        </select>
      </div>

      {incomplete && (
        <StatusMessage tone="warning">
          {z(`服务端只读取了有上限的一部分结果：搜索与筛选**仅在已加载的条目中进行**，已加载的 ${library?.promptCount ?? 0} 条不代表整个项目的 Prompt 总数。`)}
        </StatusMessage>
      )}
      {library && library.conflictedCount > 0 && (
        <StatusMessage tone="warning">
          {z(`有 ${library.conflictedCount} 份修订在并发保存中落败，已保留内容但**不计入**正式修订链。`)}
        </StatusMessage>
      )}
      {error && <StatusMessage tone="error">{z(error)}</StatusMessage>}
      {loading && !library && <StatusMessage>{z('正在读取 Prompt 列表…')}</StatusMessage>}

      {library && library.entries.length === 0 && !loading && (
        <EmptyState title={z('还没有 Prompt')} detail={z('这里只会显示当前身份有权读取的 Prompt。可以新建一份手写草稿。')} />
      )}
      {library && library.entries.length > 0 && visible.length === 0 && (
        <EmptyState title={z('没有匹配的结果')} detail={z('当前筛选或搜索在已加载的条目里没有匹配项。')} />
      )}

      <ul className="prompt-list">
        {visible.map(entry => (
          <li key={entry.familyId}>
            <button type="button" className="prompt-list-item"
              aria-current={entry.familyId === selectedFamilyId}
              onClick={() => onSelect(entry.familyId)}>
              <span className="prompt-list-title">
                {entry.purpose} · {entry.familyId.slice(0, 8)} · {z(`修订 ${entry.revision}`)}
              </span>
              <span className="prompt-list-meta">
                <Badge tone={entry.approved ? 'success' : 'info'}>
                  {z(entry.reviewStatus === 'APPROVED' ? '已审核' : '草稿')}
                </Badge>
                {entry.redacted && <Badge tone="warning">{z('已脱敏')}</Badge>}
                {!entry.historyComplete && <Badge tone="warning">{z('历史不完整')}</Badge>}
                {entry.body.state !== 'COMPLETE' && <Badge tone="warning">{z(bodyStateLabel(entry.body.state))}</Badge>}
                {entry.anomalies.map(row => (
                  <Badge key={row.kind} tone="warning">{z(anomalyLabels[row.kind] ?? row.kind)}</Badge>
                ))}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function bodyStateLabel(state: string): string {
  switch (state) {
    case 'TRUNCATED': return '正文被截断（仅预览）';
    case 'REDACTED': return '正文已脱敏';
    case 'UNDECODABLE': return '正文无法解码';
    case 'DELETED': return '正文已删除';
    case 'UNAVAILABLE': return '正文不可读';
    default: return '完整正文';
  }
}
