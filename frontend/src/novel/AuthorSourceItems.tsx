import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { apiErrorView, type CollaborationContext } from '../api';
import { authorContextSources, authorRequestKey, defaultAuthorRequestScope, type AddedAuthorSource, type AddedSourceItem, type AuthorRequestBody, type AuthorRequestScope, type AuthorSourceManifest, type NativeSourceCatalog } from './authorContextClient';

/** Controls carry the actual source fingerprint, never client-authored context. */
export function AuthorSourceItems({ manifest, scope = defaultAuthorRequestScope, onChange, disabled }: {
  manifest: AuthorSourceManifest; scope?: AuthorRequestScope;
  onChange?: (value: AuthorRequestScope) => void; disabled: boolean;
}) {
  const change = (row: AuthorSourceManifest['items'][number], include: boolean) => {
    if (!onChange || disabled) return;
    const items = (scope.source_items || []).filter(item => item.key !== row.key);
    onChange({ ...scope, source_items: [...items, { key: row.key, source_digest: row.source_digest, include }] });
  };
  const kinds: Record<string, string> = { CHARACTER: '人物', LOCATION: '地点', FORESHADOWING: '伏笔', SECRET: '作者秘密' };
  return <section aria-label="实际请求逐项来源">
    <h4>实际请求逐项来源</h4>
    <p className="novel-help">这里仅列出当前权限和目标路线允许的、有稳定身份的原始资料。移除一项会同时移除来源独立性不明确的摘要、记忆、状态和风格 / 规划引用；正文及手写指令仍由上方范围单独控制。</p>
    {manifest.dependent_context_omitted && <StatusMessage>逐项排除已生效，可能依赖它的整包派生资料也已排除。不会通过摘要重新混入。</StatusMessage>}
    {manifest.unidentified_sources_require_bundle_removal && <StatusMessage>部分材料没有稳定来源身份，无法单独固定；可使用“包含自动上下文整包”关闭整个自动来源。</StatusMessage>}
    {!manifest.items.length && <p className="novel-help">本次请求没有可逐项控制的原始资料；可以使用正文范围、自动整包和已批准引用控制。</p>}
    <ul className="ai-context-preview__sources">{manifest.items.map(row => <li className="ai-context-preview__source" key={row.key}>
      <label className="author-request-controls__check"><input type="checkbox" checked={row.included} disabled={disabled || !onChange}
        aria-label={`包含${kinds[row.kind] || '来源'}：${row.label} · ${row.key.slice(0, 8)}`} onChange={event => change(row, event.target.checked)} />{kinds[row.kind] || '来源'}：{row.label}</label>
      <span>{row.version === null ? '原记录无数字版本，使用内容摘要' : `原记录 v${row.version}`} · {row.source_digest.slice(0, 12)}</span>
      {row.pinned ? <Badge>本次已固定{row.included ? '包含' : '排除'}的来源版本</Badge>
        : <Button disabled={disabled || !onChange} onClick={() => change(row, true)}>固定 {row.label} 当前版本</Button>}
    </li>)}</ul>
  </section>;
}

const sourceKinds = { CHAPTER: '章节', CANON: 'Canon 正式事实', STORY_GRAPH: 'StoryGraph 已批准记录', RESEARCH: 'Research 引文' };
const referenceKey = (row: AddedAuthorSource) => JSON.stringify([row.kind, row.id, row.citation?.paragraph]);

/** The parent request scope is the only selected-source state. Catalogue text
 * is a read-only preview; requests send pointers and the server resolves them. */
export function AuthorSourcePicker({ body, context, disabled, onChange, manifest }: {
  body: AuthorRequestBody; context: CollaborationContext; disabled: boolean;
  onChange: (value: AuthorRequestScope) => void; manifest?: AuthorSourceManifest;
}) {
  const scope = body.request_scope || defaultAuthorRequestScope;
  const refs = scope.added_sources || [];
  const [kind, setKind] = useState<AddedAuthorSource['kind']>('CHAPTER');
  const [query, setQuery] = useState(''), [result, setResult] = useState<NativeSourceCatalog>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>();
  const controller = useRef<AbortController>(), epoch = useRef(0);
  const identity = authorRequestKey({ ...body, request_scope: undefined }, context);
  const current = useRef(identity); current.current = identity;
  useEffect(() => {
    ++epoch.current; controller.current?.abort(); setResult(undefined); setError(undefined); setBusy(false);
    return () => { ++epoch.current; controller.current?.abort(); };
  }, [identity, kind, query]);
  const refresh = async () => {
    if (disabled || busy) return;
    const request = new AbortController(); controller.current?.abort(); controller.current = request;
    const ticket = ++epoch.current; setBusy(true); setError(undefined); setResult(undefined);
    try {
      const rows = await authorContextSources(body.novel_id, { kind, query, provider_id: body.provider_id }, context, request.signal);
      if (!request.signal.aborted && ticket === epoch.current && current.current === identity) setResult(rows);
    } catch (failure) { if (!request.signal.aborted && ticket === epoch.current) setError(failure); }
    finally { if (!request.signal.aborted && ticket === epoch.current) setBusy(false); }
  };
  const update = (values: AddedAuthorSource[]) => onChange({ ...scope, added_sources: values });
  const add = (row: AddedSourceItem) => {
    if (disabled || refs.length >= 16 || refs.some(ref => referenceKey(ref) === referenceKey(row))) return;
    update([...refs, { kind: row.kind, id: row.id, version: row.version, source_digest: row.source_digest,
      ...(row.citation ? { citation: row.citation } : {}), include: true, max_characters: 4000 }]);
  };
  return <section aria-label="添加原始上下文来源">
    <h4>添加并固定原始来源</h4>
    <p className="novel-help">明确选择原始记录或引文，固定版本与内容摘要；预检和最终发送均重新读取。Research 保持参考资料身份，不会成为 Canon。云端路线不显示 LOCAL_ONLY 来源。</p>
    <p className="novel-help">“不含正文”仅关闭隐式正文与自动上下文；这里手动添加的来源独立生效。取消包含会同时关闭可能依赖它的自动上下文和风格 / 规划引用；正文仍由正文范围控制。</p>
    <label>来源类型<select aria-label="添加来源类型" value={kind} disabled={disabled || busy} onChange={event => setKind(event.target.value as AddedAuthorSource['kind'])}>{Object.entries(sourceKinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label>查找原始来源<input aria-label="查找原始来源" value={query} maxLength={160} disabled={disabled || busy} onChange={event => setQuery(event.target.value)} /></label>
    <Button disabled={disabled || busy} loading={busy} onClick={() => void refresh()}>读取可添加来源</Button>
    {!!error && <StatusMessage tone="error">{apiErrorView(error, '来源不可用，请重新读取。').message}</StatusMessage>}
    {result && !result.branch_sources_available && <StatusMessage>当前分支没有原始章节读取能力，无法添加章节。其他来源仍按各自权限读取。</StatusMessage>}
    {result && !result.items.length && <EmptyState title="没有可添加来源" detail="请检查类型、查找条件、当前项目权限与目标模型路线。" />}
    {result?.truncated && <StatusMessage>仅显示前 30 项，请缩小查找条件。</StatusMessage>}
    <ul className="ai-context-preview__sources">{result?.items.map(row => <li className="ai-context-preview__source" key={row.key}>
      <strong>{row.label}</strong><span>{row.version == null ? '原记录无数字版本' : `v${row.version}`} · {row.source_digest.slice(0, 12)} · {row.privacy_level}</span>
      {row.citation && <span>引文段落 {row.citation.paragraph}{row.citation.page ? ` · 页 ${row.citation.page}` : ''} · {row.citation.quote_sha256.slice(0, 12)}</span>}
      <details><summary>预览 {row.label}</summary><pre>{row.preview}</pre><span>{row.characters} 字符{row.preview_truncated ? '，目录预览已截断' : ''}</span></details>
      <Button disabled={disabled || refs.length >= 16 || refs.some(ref => referenceKey(ref) === referenceKey(row))} onClick={() => add(row)}>添加并固定 {row.label}</Button>
    </li>)}</ul>
    <h4>本次手动来源（{refs.length} / 16）</h4>
    {!refs.length && <p className="novel-help">尚未手动添加来源。</p>}
    <ul className="ai-context-preview__sources">{refs.map((ref, index) => {
      const resolved = manifest?.added_items?.find(row => referenceKey(row) === referenceKey(ref));
      const label = resolved?.label || `${sourceKinds[ref.kind]} · ${ref.id}`;
      return <li className="ai-context-preview__source" key={referenceKey(ref)}>
        <label><input type="checkbox" aria-label={`包含手动来源 ${ref.id}`} checked={ref.include} disabled={disabled} onChange={event => update(refs.map((row, at) => at === index ? { ...row, include: event.target.checked } : row))} />{label}</label>
        <span>{ref.version == null ? '内容摘要固定' : `固定 v${ref.version}`} · {ref.source_digest.slice(0, 12)}</span>
        <label>最多字符<input type="number" min={256} max={8000} step={1} aria-label={`来源字符上限 ${ref.id}`} value={ref.max_characters} disabled={disabled} onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= 256 && value <= 8000) update(refs.map((row, at) => at === index ? { ...row, max_characters: value } : row)); }} /></label>
        {resolved?.truncated && <StatusMessage>本次准确请求按所选字符上限截断至 {resolved.characters} 字符。</StatusMessage>}
        <Button disabled={disabled} onClick={() => update(refs.filter((_, at) => at !== index))}>移除手动来源 {ref.id}</Button>
      </li>;
    })}</ul>
    {!!refs.length && <p className="novel-help">总包含量上限 32000 字符。来源改动、撤销或权限变化后必须重新选择与预检；移除固定项不会自动改写原始资料。</p>}
  </section>;
}
