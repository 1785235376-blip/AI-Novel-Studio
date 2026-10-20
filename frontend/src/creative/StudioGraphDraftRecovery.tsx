import { GraphConditionFields } from './GraphConditionFields';
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
  const [notePage, setNotePage] = useState<{ snapshot: typeof recovery; page: number }>();
  const notes = recovery?.definition.presentation?.notes ?? [];
  const page = notePage?.snapshot === recovery ? Math.min(notePage?.page ?? 0, Math.max(0, Math.ceil(notes.length / 20) - 1)) : 0;
  const offset = page * 20;
  const confirmed = !!recovery && confirmedRecovery === recovery;
  if (!draftOwnerCurrent) return <StatusMessage tone="warning">作者身份或项目代次尚未确认，图草稿只保留在本页。</StatusMessage>;
  return <section aria-label="本机图草稿恢复">
    {draftStorageNotice && <StatusMessage tone="warning">{draftStorageNotice}</StatusMessage>}
    {!draftRecoverable && <StatusMessage tone="warning">本机草稿保留支持无外部引用的文本图 v1 / v2 与受限条件图 v7；条件图恢复还须明确核对当前门禁。当前格式的输入只保留在本页，请明确保存到服务端。</StatusMessage>}
    {!recovery && draftRecoverable && !draftStorageNotice && <StatusMessage>{draftSavedAt
      ? `文本图草稿已保留在本机 · ${new Date(draftSavedAt).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai' })}。服务端版本、审核与运行仍需明确操作。`
      : '文本图后续修改可自动保留在本机；服务端保存仍需明确操作。'}</StatusMessage>}
    {recovery && <Panel title="发现本机文本图草稿">
      <p>{recovery.definition.title} · {recovery.definition.nodes.length} 节点 / {recovery.definition.edges.length} 连接 · {recovery.base ? `基于 v${recovery.base.version}` : '尚未保存到服务端'}</p>
      <p>恢复前会重新核对身份、项目代次与服务端版本。请先保存或放弃当前输入，再恢复同一图的草稿。</p>
      {recoveryError && <StatusMessage tone="warning">{recoveryError}</StatusMessage>}
      <Button disabled={!canRecoverDraft || recoveryBusy} loading={recoveryBusy} onClick={() => void recoverLocalDraft()}>核对并恢复本机图草稿</Button>
      <details><summary>查看待恢复的作者输入</summary>
        <p>以下仅为本机缓存的作者输入，未与当前服务端内容逐项比对。查看与翻页不会恢复、保存或运行图。</p>
        {typeof recovery.definition.presentation?.comment === 'string' && <label>本机草稿 · 图注释<textarea readOnly value={recovery.definition.presentation.comment} /></label>}
        <p>本机草稿 · {notes.length} 张空间便笺</p>
        {notes.length > 0 && <section aria-label="本机草稿空间便笺">
          <p role="status">显示 {offset + 1}–{Math.min(offset + 20, notes.length)} / {notes.length} 张便笺；每页最多 20 张，文本完整保留。</p>
          {notes.slice(offset, offset + 20).map(note => <label key={note.id}>本机草稿便笺 {note.id}<textarea readOnly value={note.text} /></label>)}
          {notes.length > 20 && <div>
            <Button type="button" disabled={!offset} onClick={() => setNotePage({ snapshot: recovery, page: page - 1 })}>上一页缓存便笺</Button>
            <Button type="button" disabled={offset + 20 >= notes.length} onClick={() => setNotePage({ snapshot: recovery, page: page + 1 })}>下一页缓存便笺</Button>
          </div>}
        </section>}
        {recovery.definition.schema_version === 7 && <p>受限条件图 v7：恢复只恢复作者草稿。门禁默认关闭；不会恢复运行、审核授权或启用缓存。</p>}
        {recovery.definition.nodes.filter(node => node.definition_id === 'local_condition' && node.parameters.predicate).map(node => <section key={node.id} aria-label={`本机草稿 ${node.id} · 条件`}><GraphConditionFields value={node.parameters.predicate!} disabled onChange={() => {}} /></section>)}
        {recovery.definition.nodes.flatMap(node =>
        (['text', 'result', 'note', 'instruction'] as const).flatMap(field => typeof node.parameters[field] === 'string'
          ? <label key={`${node.id}:${field}`}>本机草稿 {node.id} · {field}<textarea readOnly value={String(node.parameters[field])} /></label> : []))}</details>
      <label><input type="checkbox" checked={confirmed} disabled={recoveryBusy} onChange={event => setConfirmedRecovery(event.target.checked ? recovery : undefined)} />确认放弃此本机恢复草稿</label>
      <Button disabled={!confirmed || recoveryBusy} onClick={discardLocalRecovery}>放弃本机图恢复草稿</Button>
    </Panel>}
  </section>;
}
