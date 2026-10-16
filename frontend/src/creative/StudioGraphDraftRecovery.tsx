import { useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import type { StudioGraphEditorController } from './useStudioGraphEditorController';

/** Shared canvas chrome only; restoration stays in the original editor controller. */
export function StudioGraphDraftRecovery({ controller }: { controller: StudioGraphEditorController }) {
  const { localRecovery: recovery, draftStorageNotice, draftSavedAt, draftOwnerCurrent, draftRecoverable,
    recoveryError, recoveryBusy, canRecoverDraft, recoverLocalDraft, discardLocalRecovery } = controller;
  // Consent belongs to the displayed snapshot. An effect-based reset can race
  // a real click when the initial cache read finishes under a busy renderer.
  const [confirmedRecovery, setConfirmedRecovery] = useState<typeof recovery>();
  const confirmed = !!recovery && confirmedRecovery === recovery;
  if (!draftOwnerCurrent) return <StatusMessage tone="warning">作者身份或项目代次尚未确认，图草稿只保留在本页。</StatusMessage>;
  return <section aria-label="本机图草稿恢复">
    {draftStorageNotice && <StatusMessage tone="warning">{draftStorageNotice}</StatusMessage>}
    {!draftRecoverable && <StatusMessage tone="warning">本机自动恢复当前仅支持不含外部引用的文本图 v1 / v2。当前图输入只保留在本页；请明确保存到服务端。</StatusMessage>}
    {!recovery && draftRecoverable && !draftStorageNotice && <StatusMessage>{draftSavedAt
      ? `文本图草稿已保留在本机 · ${new Date(draftSavedAt).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai' })}。服务端版本、审核与运行仍需明确操作。`
      : '文本图后续修改可自动保留在本机；服务端保存仍需明确操作。'}</StatusMessage>}
    {recovery && <Panel title="发现本机文本图草稿">
      <p>{recovery.definition.title} · {recovery.definition.nodes.length} 节点 / {recovery.definition.edges.length} 连接 · {recovery.base ? `基于 v${recovery.base.version}` : '尚未保存到服务端'}</p>
      <p>恢复前会重新核对身份、项目代次与服务端版本。请先保存或放弃当前输入，再恢复同一图的草稿。</p>
      {recoveryError && <StatusMessage tone="warning">{recoveryError}</StatusMessage>}
      <Button disabled={!canRecoverDraft || recoveryBusy} loading={recoveryBusy} onClick={() => void recoverLocalDraft()}>核对并恢复本机图草稿</Button>
      <details><summary>查看待恢复的作者输入</summary>{recovery.definition.nodes.flatMap(node =>
        (['text', 'result', 'note', 'instruction'] as const).flatMap(field => typeof node.parameters[field] === 'string'
          ? <label key={`${node.id}:${field}`}>本机草稿 {node.id} · {field}<textarea readOnly value={String(node.parameters[field])} /></label> : []))}</details>
      <label><input type="checkbox" checked={confirmed} disabled={recoveryBusy} onChange={event => setConfirmedRecovery(event.target.checked ? recovery : undefined)} />确认放弃此本机恢复草稿</label>
      <Button disabled={!confirmed || recoveryBusy} onClick={discardLocalRecovery}>放弃本机图恢复草稿</Button>
    </Panel>}
  </section>;
}
