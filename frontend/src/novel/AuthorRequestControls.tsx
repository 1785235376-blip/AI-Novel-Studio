import { useId } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { defaultAuthorRequestScope, type AuthorRequestScope } from './authorContextClient';
import './AuthorRequestPreview.css';

/** Individual identified sources use conservative dependent-bundle removal. */
export function AuthorRequestControls({ value = defaultAuthorRequestScope, onChange, source, styleProfileId, plotPlanId, disabled = false, operation }: {
  value?: AuthorRequestScope; onChange: (value: AuthorRequestScope) => void; source: string;
  styleProfileId?: string; plotPlanId?: string; disabled?: boolean; operation: string;
}) {
  const reduced = value.source_mode !== 'AUTO';
  const sourceLabelId = useId();
  return <section className="ai-context-preview author-request-controls" aria-label="本次请求材料范围">
    <header className="ai-context-preview__header"><h3>本次请求材料范围</h3></header>
    <label><span id={sourceLabelId}>正文范围</span><select aria-labelledby={sourceLabelId} value={value.source_mode} disabled={disabled} onChange={event => onChange({ ...value, source_mode: event.target.value as AuthorRequestScope['source_mode'] })}>
      <option value="AUTO">当前选区；未选中时使用末尾 2000 字符</option>
      <option value="SELECTION_ONLY" disabled={!source}>只用当前已保存选区</option>
      <option value="NONE" disabled={operation === 'rewrite'}>不包含正文</option>
    </select></label>
    <label className="author-request-controls__check"><input type="checkbox" checked={!reduced && value.include_automatic_context} disabled={disabled || reduced} onChange={event => onChange({ ...value, include_automatic_context: event.target.checked })} />包含自动上下文整包</label>
    <p className="novel-help">自动整包可能包含章节摘要、人物、记忆、策略与其他派生资料。预检后可固定或移除有稳定身份的单项；其来源独立性不明确的派生资料会一并排除。</p>
    {!!value.source_items?.length && <div><StatusMessage>本次有 {value.source_items.length} 项来源版本限制；过期或不可见的来源会阻止发送。清除后必须重新预检，不会自动生成。</StatusMessage><Button disabled={disabled} onClick={() => { const { source_items: _removed, ...rest } = value; onChange(rest); }}>清除逐项来源限制</Button></div>}
    {reduced && <StatusMessage>为保证排除的正文不从摘要或参考重新进入，将同时移除自动整包和风格 / 规划引用。只保留本次要求、手写风格与明确选中的正文。</StatusMessage>}
    <label className="author-request-controls__check"><input type="checkbox" checked={!reduced && !!styleProfileId && value.include_style_reference} disabled={disabled || reduced || !styleProfileId} onChange={event => onChange({ ...value, include_style_reference: event.target.checked })} />固定已批准风格引用{styleProfileId ? `：${styleProfileId}` : '（未选择）'}</label>
    <label className="author-request-controls__check"><input type="checkbox" checked={!reduced && !!plotPlanId && value.include_plan_reference} disabled={disabled || reduced || !plotPlanId} onChange={event => onChange({ ...value, include_plan_reference: event.target.checked })} />固定已批准规划引用{plotPlanId ? `：${plotPlanId}` : '（未选择）'}</label>
    <p className="novel-help">固定引用使用现有选择的 ID 和当前批准版本，不复制资料。移除任一引用时，对应引用及独立性不明确的自动派生资料会一并排除；其他明确选择的引用仍需当前批准，请重新预检。版本或审核状态变化会阻止旧请求发送。</p>
  </section>;
}
