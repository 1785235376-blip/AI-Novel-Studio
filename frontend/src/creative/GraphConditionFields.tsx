import type { GraphConditionPredicate } from './studioGraphTypes';
/** A closed form for saved literals; no expression, script, environment or model input. */
export function GraphConditionFields({ value, disabled, onChange }: { value: GraphConditionPredicate; disabled: boolean; onChange: (next: GraphConditionPredicate) => void }) {
  return <fieldset disabled={disabled}><legend>本地条件</legend><p>条件读取这里保存的值。真分支与假分支中只有一条会运行，另一条正常跳过；缓存关闭。</p>
    <label>条件类型<select value={value.kind} onChange={event => { if (event.target.value === 'boolean') onChange({ kind: 'boolean', value: true }); else if (event.target.value === 'enum') onChange({ kind: 'enum', value: 'A', equals: 'A' }); }}><option value="boolean">布尔值</option><option value="enum">A/B 等值</option></select></label>
    {value.kind === 'boolean' ? <label>保存的布尔值<select value={String(value.value)} onChange={event => { if (['true', 'false'].includes(event.target.value)) onChange({ kind: 'boolean', value: event.target.value === 'true' }); }}><option value="true">真 → when_true</option><option value="false">假 → when_false</option></select></label> : <>
      <label>保存的 A/B 值<select value={value.value} onChange={event => { if (event.target.value === 'A' || event.target.value === 'B') onChange({ ...value, value: event.target.value }); }}><option>A</option><option>B</option></select></label>
      <label>比较目标<select value={value.equals} onChange={event => { if (event.target.value === 'A' || event.target.value === 'B') onChange({ ...value, equals: event.target.value }); }}><option>A</option><option>B</option></select></label></>}
    <p>分支结果必须通过原人工审核；保存草稿不创建运行。</p>
  </fieldset>;
}
