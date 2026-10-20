/** Search and select only the revision records already supplied by the existing owner. */
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
  const [query, setQuery] = useState('');
  const searchId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return [...versions].sort((a, b) => b.revision - a.revision).filter(row =>
      !needle || [`修订 ${row.revision}`, row.changeNote, row.changeReason]
        .filter(Boolean).join(' ').toLocaleLowerCase().includes(needle));
  }, [versions, query]);

  return <section aria-label="版本记录检索">
    <div className="prompt-filters">
      <label htmlFor={searchId}>搜索版本记录</label>
      <input ref={searchRef} id={searchId} type="search" maxLength={512} value={query}
        placeholder="按修订号、修改说明或原因搜索"
        onChange={event => setQuery(event.target.value)} />
    </div>
    {query && <Button variant="ghost" onClick={() => { setQuery(''); searchRef.current?.focus(); }}>清除版本搜索</Button>}
    <p aria-live="polite">已加载 {versions.length} 条版本记录，当前显示 {visible.length} 条。仅检索当前已加载记录。</p>
    {versions.length === 0 ? <EmptyState title="没有已加载的版本记录" detail="当前响应未包含版本记录，请重新读取家族详情。" />
      : visible.length === 0 && <EmptyState title="已加载记录中没有匹配的版本" detail="请调整搜索条件或清除搜索。筛选不会删除或修改版本记录。" />}
    <ol className="prompt-version-list" aria-label="Prompt 版本记录">
      {visible.map(row => <li key={row.assetId}>
        <span>修订 {row.revision}</span>
        {row.assetId === headAssetId && <Badge tone="info">当前</Badge>}
        {!row.available && <Badge tone="warning">已删除 / 不可读</Badge>}
        {row.redacted && <Badge tone="warning">已脱敏</Badge>}
        {row.changeNote && <span className="prompt-version-note">{row.changeNote}</span>}
        {row.changeReason && <span className="prompt-version-note">修改原因：{row.changeReason}</span>}
        {professional && <code>{row.assetId.slice(0, 8)}</code>}
        {versions.length > 1 && <div className="prompt-version-actions">
          <Button variant="ghost" aria-label={`将修订 ${row.revision} 选作旧版`}
            aria-pressed={fromId === row.assetId} onClick={() => onSelectFrom(row.assetId)}>{fromId === row.assetId ? '已选旧版' : '选作旧版'}</Button>
          <Button variant="ghost" aria-label={`将修订 ${row.revision} 选作新版`}
            aria-pressed={toId === row.assetId} onClick={() => onSelectTo(row.assetId)}>{toId === row.assetId ? '已选新版' : '选作新版'}</Button>
        </div>}
      </li>)}
    </ol>
    {versions.length > 1 && <p className="prompt-diff-limit">选择版本只更新下方的比较选项；点击“比较正文”后才会读取正文。</p>}
  </section>;
}
