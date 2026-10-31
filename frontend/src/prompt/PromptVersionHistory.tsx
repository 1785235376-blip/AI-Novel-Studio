/** Search and select only the revision records already supplied by the existing owner. */
import { useTz } from '../i18n'; // [HERMIA-FE-20261031 VERA-EN]
import { useId, useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState } from '../ui/primitives';
import type { PromptVersionRow } from './promptTypes';

export function PromptVersionHistory({ versions, headAssetId, professional, fromId, toId, onSelectFrom, onSelectTo }: {
  versions: readonly PromptVersionRow[];
  headAssetId: string;
  professional: boolean;
  fromId: string;
  toId: string;
  onSelectFrom: (assetId: string) => void;
  onSelectTo: (assetId: string) => void;
}) {
  const z = useTz(); // [HERMIA-FE-20261031 VERA-EN]
  const [query, setQuery] = useState('');
  const searchId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return [...versions].sort((a, b) => b.revision - a.revision).filter(row =>
      !needle || [`修订 ${row.revision}`, row.changeNote, row.changeReason]
        .filter(Boolean).join(' ').toLocaleLowerCase().includes(needle));
  }, [versions, query]);

  return <section aria-label={z('版本记录检索')}>
    <div className="prompt-filters">
      <label htmlFor={searchId}>{z('搜索版本记录')}</label>
      <input ref={searchRef} id={searchId} type="search" maxLength={512} value={query}
        placeholder={z('按修订号、修改说明或原因搜索')}
        onChange={event => setQuery(event.target.value)} />
    </div>
    {query && <Button variant="ghost" onClick={() => { setQuery(''); searchRef.current?.focus(); }}>{z('清除版本搜索')}</Button>}
    <p aria-live="polite">{z(`已加载 ${versions.length} 条版本记录，当前显示 ${visible.length} 条。仅检索当前已加载记录。`)}</p>
    {versions.length === 0 ? <EmptyState title={z('没有已加载的版本记录')} detail={z('当前响应未包含版本记录，请重新读取家族详情。')} />
      : visible.length === 0 && <EmptyState title={z('已加载记录中没有匹配的版本')} detail={z('请调整搜索条件或清除搜索。筛选不会删除或修改版本记录。')} />}
    <ol className="prompt-version-list" aria-label={z('Prompt 版本记录')}>
      {visible.map(row => <li key={row.assetId}>
        <span>{z(`修订 ${row.revision}`)}</span>
        {row.assetId === headAssetId && <Badge tone="info">{z('当前')}</Badge>}
        {!row.available && <Badge tone="warning">{z('已删除 / 不可读')}</Badge>}
        {row.redacted && <Badge tone="warning">{z('已脱敏')}</Badge>}
        {row.changeNote && <span className="prompt-version-note">{row.changeNote}</span>}
        {row.changeReason && <span className="prompt-version-note">{z('修改原因：')}{row.changeReason}</span>}
        {professional && <code>{row.assetId.slice(0, 8)}</code>}
        {versions.length > 1 && <div className="prompt-version-actions">
          <Button variant="ghost" aria-label={z(`将修订 ${row.revision} 选作旧版`)}
            aria-pressed={fromId === row.assetId} onClick={() => onSelectFrom(row.assetId)}>{z(fromId === row.assetId ? '已选旧版' : '选作旧版')}</Button>
          <Button variant="ghost" aria-label={z(`将修订 ${row.revision} 选作新版`)}
            aria-pressed={toId === row.assetId} onClick={() => onSelectTo(row.assetId)}>{z(toId === row.assetId ? '已选新版' : '选作新版')}</Button>
        </div>}
      </li>)}
    </ol>
    {versions.length > 1 && <p className="prompt-diff-limit">{z('选择版本只更新下方的比较选项；点击“比较正文”后才会读取正文。')}</p>}
  </section>;
}
