import { Badge, Button, StatusMessage } from '../ui/primitives';
import { defaultAuthorRequestScope, type AuthorRequestScope, type AuthorSourceManifest } from './authorContextClient';

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
