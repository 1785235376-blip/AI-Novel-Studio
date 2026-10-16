import { useMemo, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';
import type { AuthoredWorkflow } from './declarativeAgentsClient';
import { previewCheckpointEdit, type GraphEditPreview } from './workflowGraphEditing';

type Props = { definition: AuthoredWorkflow; editorRevision: number; contextKey: string; disabled: boolean; onApply: (value: AuthoredWorkflow, revision: number) => void };
let sequence = 0;
export function WorkflowGraphEditPreview(props: Props) {
  const key = useMemo(() => ++sequence, [props.definition, props.editorRevision, props.contextKey, props.disabled]);
  return <PreviewBody key={key} {...props} />;
}
function PreviewBody({ definition, editorRevision, disabled, onApply }: Props) {
  const [mode, setMode] = useState<'insert' | 'remove'>('insert'), [selection, setSelection] = useState('');
  const [preview, setPreview] = useState<GraphEditPreview>(), [error, setError] = useState('');
  const consumed = useRef(false);
  const clear = () => { setPreview(undefined); setError(''); consumed.current = false; };
  const prepare = () => {
    if (disabled || !selection) return; clear();
    try {
      const edge = definition.edges[Number(selection)];
      setPreview(previewCheckpointEdit(definition, mode === 'insert' ? { kind: 'insert', source: edge?.source, target: edge?.target } : { kind: 'remove', id: selection }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : '当前结构无法预览；草稿保持原样。'); }
  };
  return <section className="experimental-record" aria-label="检查点连接助手">
    <h4>检查点连接助手</h4>
    <p>检查点是自动经过的标记，不是人工审核。这里只预览结构改动，尚未经过服务端验证；填入后仍须使用原验证与保存操作，不会启动运行。</p>
    {disabled && <StatusMessage>当前目录或定义尚未就绪，或另一个操作正在进行；结构助手暂不可用。</StatusMessage>}
    <Field label="检查点结构操作"><select disabled={disabled} value={mode} onChange={event => { setMode(event.target.value as typeof mode); setSelection(''); clear(); }}><option value="insert">在已有连接中插入检查点</option><option value="remove">移除单入单出检查点并衔接</option></select></Field>
    <Field label={mode === 'insert' ? '待插入检查点的连接' : '待移除的自动检查点'}><select disabled={disabled} value={selection} onChange={event => { setSelection(event.target.value); clear(); }}><option value="">请选择</option>{mode === 'insert' ? definition.edges.map((edge, index) => <option key={index} value={String(index)}>{edge.source} → {edge.target}</option>) : definition.nodes.filter(node => node.type === 'checkpoint').map(node => <option key={node.id} value={node.id}>{node.id} · {node.name}</option>)}</select></Field>
    <Button disabled={disabled || !selection} onClick={prepare}>预览检查点结构改动</Button>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {preview && <section aria-label="未验证的检查点结构预览">
      <p>{preview.kind === 'insert' ? '新增' : '移除'}自动检查点 {preview.nodeId}。原表单尚未改变；以下只说明依赖连接，不保证其他分支的执行先后次序。</p>
      <p>移除连接：{preview.removed.map(edge => `${edge.source} → ${edge.target}`).join('；')}</p>
      <p>新增连接：{preview.added.map(edge => `${edge.source} → ${edge.target}`).join('；')}</p>
      <Button disabled={disabled} onClick={clear}>取消结构预览</Button>
      <Button disabled={disabled} onClick={() => { if (disabled || consumed.current) return; consumed.current = true; onApply(preview.definition, editorRevision); setPreview(undefined); }}>将结构预览填入当前草稿</Button>
    </section>}
  </section>;
}
