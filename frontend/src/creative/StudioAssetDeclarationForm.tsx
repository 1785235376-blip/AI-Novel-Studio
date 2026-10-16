import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { AssetLineageForm, type LineageAsset, type LineageDeclaration } from '../experimental/ProductionLineagePanel';
import { Field, Form, useAction } from '../experimental/shared';

type Props = { row: LineageAsset; assets: LineageAsset[]; saved: () => void;
  saveLineage: (body: LineageDeclaration) => Promise<unknown>; readOnly?: boolean; onDirtyChange?: (dirty: boolean) => void };

/** Keep the original manual form; Studio result inputs are immutable job evidence. */
export function StudioAssetDeclarationForm(props: Props) {
  return props.row.source_task_id ? <GeneratedDeclaration {...props} /> : <AssetLineageForm {...props} />;
}

function GeneratedDeclaration({ row, saved, saveLineage, readOnly = false, onDirtyChange }: Props) {
  const [label, setLabel] = useState(row.license.label), [source, setSource] = useState(row.license.source || '');
  const [note, setNote] = useState(row.license.note || ''), [operation, setOperation] = useState(row.operation);
  const initial = useRef(JSON.stringify([label, source, note, operation]));
  const action = useAction(saved);
  useEffect(() => { onDirtyChange?.(JSON.stringify([label, source, note, operation]) !== initial.current); }, [label, source, note, operation, onDirtyChange]);
  const unavailable = readOnly || row.deleted || row.integrity !== 'VERIFIED'
    || !['GENERATED_RESULT', 'DERIVED_PROCESSING'].includes(row.origin)
    || row.parents.some(parent => !parent.id || ['DELETED', 'UNAVAILABLE'].includes(parent.state));
  return <Form onSubmit={() => {
    if (unavailable || action.busy || !label.trim()) return;
    const body: LineageDeclaration = { expected_version: row.version, origin: row.origin as LineageDeclaration['origin'],
      parent_asset_ids: row.parents.flatMap(parent => parent.id ? [parent.id] : []), chapter_ids: [],
      license: { label, source, note }, operation };
    void action.run(() => saveLineage(body), '作者许可与操作说明已保存。原生成来源保持不变。');
  }}>
    <h3>生成资产声明 · 基于 v{row.version}</h3>{action.feedback}
    <StatusMessage>许可为作者声明。生成任务、源资产和文档快照由原执行记录固定；修改声明不会批准来源或改变原生成结果。</StatusMessage>
    <p>原任务：{row.source_task_id} · 来源类型：{row.origin}</p>
    <details><summary>核对原始来源</summary>
      {row.parents.map((parent, index) => <p key={`asset:${parent.id || index}`}>资产 {parent.id || '不可用'} · {parent.state}{parent.version ? ` · v${parent.version}` : ''} · {parent.digest || '摘要不可用'}</p>)}
      {row.sources.map((document, index) => <p key={`document:${document.id || index}`}>文档 {document.id || '不可用'} · {document.state}{document.version ? ` · v${document.version}` : ''} · {document.digest || '摘要不可用'}</p>)}
      {!row.parents.length && !row.sources.length && <p>此原任务未绑定源资产或文档。</p>}
    </details>
    {unavailable && <StatusMessage tone="warning">当前声明只读，或资产／父资产不可用；请先读取当前版本核对。</StatusMessage>}
    <Field label="处理操作说明"><input disabled={unavailable || action.busy} value={operation} maxLength={160} onChange={event => setOperation(event.target.value)} /></Field>
    <Field label="许可声明"><input required disabled={unavailable || action.busy} value={label} maxLength={160} onChange={event => setLabel(event.target.value)} /></Field>
    <Field label="许可来源"><input disabled={unavailable || action.busy} value={source} maxLength={2000} onChange={event => setSource(event.target.value)} /></Field>
    <Field label="许可使用备注"><textarea disabled={unavailable || action.busy} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} /></Field>
    <Button type="submit" disabled={unavailable || action.busy || !label.trim()}>保存作者声明</Button>
  </Form>;
}
