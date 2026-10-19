import { useRef } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { GraphLocalSubgraphParentController } from './useGraphLocalSubgraphParent';
import type { StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';

export function GraphLocalSubgraphPanel({ controller: c, definition, base, disabled }: {
  controller: GraphLocalSubgraphParentController; definition: StudioGraphDefinition; base?: StudioGraphRecord; disabled: boolean;
}) {
  const input = useRef<HTMLTextAreaElement>(null), composing = useRef(false), plan = c.preview;
  const call = definition.schema_version === 6 ? definition.nodes.find(node => node.definition_id === 'local_subgraph') : undefined;
  const state = call && base?.reference_states.find(row => row.node_id === call.id)?.state;
  return <details aria-label="受限本地子调用" open={definition.schema_version === 6}><summary>受限本地子调用 · 首片</summary>
    <p>固定三节点父链：父文本 → 一次本地子调用 → 原人工审核。只支持当前 schema 1 纯本地子图和唯一 TEXT/DRAFT 接口；没有模型、媒体、云端或自动执行。</p>
    {call && <section aria-label="当前子调用 pin">
      {state && state !== 'CURRENT' ? <StatusMessage tone="warning">当前 pin 已失效或不可用，来源细节与派生结果应重新读取核对；不会自动改绑新版本。请从新建空图明确准备另一份父草稿。</StatusMessage>
        : <><p>子图 {call.parameters.graph_id} · v{call.parameters.expected_version}；输入 {call.parameters.input_node_id}.text → 输出 {call.parameters.output_node_id}.draft。</p>
          <label>固定定义摘要<input readOnly value={call.parameters.definition_digest || ''} /></label>
          <label>固定执行摘要<input readOnly value={call.parameters.execution_digest || ''} /></label></>}
      <p>本首片保持父节点、连接和 pin 不变，可编辑父文本、标题及布局。运行始终预检整条父链；子图 Save 会使旧 pin 失效。总节点上限 24、子图上限 16、深度 1、协作式总 5 秒子调用预算，缓存关闭。</p>
    </section>}
    <Button disabled={disabled || !c.readable || c.pending || !c.available} onClick={() => void c.load()}>明确读取受限子调用与已保存图目录</Button>
    {!c.blank && <p>先通过原“新建空图”处理当前未保存输入，再选择子图生成受限父草稿；不会替换当前图或升级其他格式。</p>}
    <label>已保存 schema 1 子图<select aria-label="已保存 schema 1 子图" value={c.choice} disabled={disabled || !c.blank || c.pending} onChange={event => c.choose(event.target.value)}>
      <option value="">明确选择子图</option>{c.rows.map(row => <option key={row.id} value={row.id}>{row.definition.title} · v{row.version}</option>)}
    </select></label>
    <Button disabled={disabled || !c.blank || c.pending || !c.choice} onClick={() => void c.verify()}>读取当前版本并核对接口闭包</Button>
    <label>受限父级作者文本<textarea ref={input} maxLength={8000} value={c.text} disabled={disabled || !c.blank || c.pending}
      onChange={event => c.edit(event.target.value)} onCompositionStart={() => { composing.current = true; c.confirm(false); }}
      onCompositionEnd={event => { composing.current = false; c.edit(event.currentTarget.value); }} /></label>
    {c.pending && <StatusMessage tone="info">正在读取当前授权来源；尚未生成、保存或执行。</StatusMessage>}
    {c.error && <StatusMessage tone="warning">{c.error}</StatusMessage>}
    {plan && <section aria-label="受限父草稿预览"><p>{plan.source.definition.title} · {plan.source.id} · v{plan.source.version}</p>
      <label>核对定义摘要<input readOnly value={plan.source.definition_digest} /></label>
      <label>核对执行摘要<input readOnly value={plan.source.execution_digest} /></label>
      <p>输入 {plan.input}.text (TEXT) → 输出 {plan.output}.draft (DRAFT)。整个闭包 {plan.childNodes}/16 节点，固定父链 3 节点，合计 {plan.totalNodes}/24；拒绝隐藏、禁用、嵌套、模型和媒体依赖。</p>
      <label><input type="checkbox" checked={c.confirmed} disabled={disabled || c.pending || !c.text.trim()}
        onChange={event => c.confirm(event.target.checked)} />我已核对当前 pin、接口与容量，仅生成父草稿，之后明确保存</label>
      <Button disabled={disabled || c.pending || !c.confirmed || !c.text.trim()} onClick={() => {
        if (!composing.current && input.current?.value === c.text) c.create();
      }}>明确生成受限父草稿</Button>
    </section>}
  </details>;
}
