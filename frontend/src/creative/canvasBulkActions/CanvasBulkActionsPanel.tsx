import { useLayoutEffect, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../../ui/primitives';
import type { CanvasDefinition } from '../studioCanvasViewClient';
import { planCanvasBulkAction, type CanvasBulkActionInput } from './planCanvasBulkAction';

export type CanvasBulkActionsPanelProps = {
  input: CanvasBulkActionInput; ownerToken: object; current: boolean; busy: boolean; canApply: boolean;
  isCurrent: () => boolean; onApply: (definition: CanvasDefinition) => boolean | void | Promise<boolean | void>;
};
type Consent = { binding: string | null; owner: object; current: boolean; busy: boolean; canApply: boolean;
  retired: boolean; used: boolean; confirmed: Set<string> };
const labels = { REMOVE_CARDS: '移除所选引用卡片', ALIGN_LEFT: '所选卡片左对齐', ALIGN_TOP: '所选卡片顶端对齐' };
const stateLabels = { CURRENT_METADATA: '当前元数据可用', STALE: '元数据已过期', UNAVAILABLE: '来源不可见或不可用（原 pin 未提供）', UNVERIFIED: '当前元数据未核验（草稿 pin 未由原读取确认）' };
function current(props: CanvasBulkActionsPanelProps): boolean {
  try { return props.current && props.isCurrent(); } catch { return false; }
}
function plan(props: CanvasBulkActionsPanelProps) {
  if (!current(props)) return planCanvasBulkAction({ current: false } as CanvasBulkActionInput);
  const result = planCanvasBulkAction(props.input);
  return current(props) ? result : planCanvasBulkAction({ current: false } as CanvasBulkActionInput);
}

/** Original owner draft edit only. No transport, Save, dispatch, queue, or model execution. */
export function CanvasBulkActionsPanel(props: CanvasBulkActionsPanelProps) {
  const live = useRef(props); live.current = props;
  const alive = useRef(false), renderLease = useRef<object>(), lease = {};
  const activeApply = useRef<object>();
  const [, redraw] = useState(0), [notice, setNotice] = useState<{ consent: Consent; text: string }>();
  const preview = plan(props);
  const consent = useRef<Consent>();
  const previous = consent.current;
  if (!previous || previous.retired || previous.binding !== preview.binding || previous.owner !== props.ownerToken
    || previous.current !== props.current || previous.busy !== props.busy || previous.canApply !== props.canApply) {
    if (previous) previous.retired = true;
    consent.current = { binding: preview.binding, owner: props.ownerToken, current: props.current, busy: props.busy,
      canApply: props.canApply, retired: false, used: false, confirmed: new Set() };
  }
  const captured = consent.current!;
  useLayoutEffect(() => {
    alive.current = true; renderLease.current = lease;
    return () => { renderLease.current = undefined; alive.current = false; };
  });
  function retire() {
    captured.retired = true; captured.confirmed.clear();
    if (alive.current) redraw(value => value + 1);
  }
  function checked() {
    if (!alive.current || renderLease.current !== lease || consent.current !== captured || captured.retired) return;
    const latest = live.current;
    // Replan against live input, including in-place mutations, before accepting any retained UI intent.
    if (!current(latest)) { retire(); return; }
    const fresh = plan(latest);
    if (!latest.canApply || latest.busy || latest.ownerToken !== captured.owner || fresh.state !== 'ready'
      || fresh.binding !== captured.binding || latest.current !== captured.current) { retire(); return; }
    if (!captured.used && !activeApply.current) return fresh;
  }
  async function apply() {
    const fresh = checked();
    if (!fresh?.definition || !fresh.items.every(item => captured.confirmed.has(item.cardId))) return;
    // Latch before invoking even a synchronous parent edit; repeated clicks cannot submit twice.
    captured.used = true;
    const ticket = {}; activeApply.current = ticket; setNotice(undefined); redraw(value => value + 1);
    function stillBound() {
      if (!alive.current || activeApply.current !== ticket || consent.current !== captured || captured.retired) return false;
      const latest = live.current;
      if (!current(latest) || !latest.canApply || latest.busy || latest.ownerToken !== captured.owner || plan(latest).binding !== captured.binding) { retire(); return false; }
      return true;
    }
    try {
      const result = await live.current.onApply(fresh.definition);
      if (!stillBound()) return;
      setNotice({ consent: captured, text: result === false ? '原画布未接受本次草稿变更；请重新核对当前画布。' : '已交回原画布草稿编辑；尚未保存，请通过原 Save 持久化。' });
    } catch {
      if (stillBound()) setNotice({ consent: captured, text: '本次草稿编辑未确认；请核对原画布，没有自动重试或保存。' });
    } finally {
      if (activeApply.current === ticket) { activeApply.current = undefined; if (alive.current) redraw(value => value + 1); }
    }
  }
  const disabled = preview.state !== 'ready' || !props.current || !props.canApply || props.busy || captured.used || !!activeApply.current;
  return <Panel title="所选卡片操作影响预览" aria-label="画布多选操作影响预览">
    <StatusMessage tone={preview.state === 'ready' ? 'info' : 'warning'}>{preview.message}</StatusMessage>
    {preview.operation && <p>{labels[preview.operation]} · {preview.items.length} 张待核对卡片（最多 24 张）</p>}
    {preview.notes.map(note => <p key={note}>{note}</p>)}
    {preview.state === 'ready' && <>
      <fieldset disabled={disabled}>
        <legend>逐项确认本次影响</legend>
        <ol>{preview.items.map(item => <li key={item.cardId} style={{ overflowWrap: 'anywhere' }}>
          <p>卡片 {item.cardId} · {stateLabels[item.referenceState]}{item.filename ? ` · ${item.filename}` : ''}</p>
          <p>原位置 ({item.before.position.x}, {item.before.position.y})；分组 {item.beforeGroupId ?? '无'} → {item.after
            ? `位置 (${item.after.position.x}, ${item.after.position.y})；分组 ${item.afterGroupId ?? '无'}${item.changed ? '' : '（位置保持）'}`
            : '移除此画布引用；解除其分组成员关系'}</p>
          <p>{item.before.asset ? `原资产 pin ${item.before.asset.asset_id} · ${item.before.asset.kind} · v${item.before.asset.version} · digest ${item.before.asset.digest}` : '原资产 pin 不可见，未猜测或补全'}</p>
          <label><input type="checkbox" aria-label={`确认卡片 ${item.cardId} 的本次影响`} disabled={disabled}
            checked={captured.confirmed.has(item.cardId)} onChange={event => {
              const fresh = checked(); if (!fresh?.items.some(value => value.cardId === item.cardId)) return;
              if (event.target.checked) captured.confirmed.add(item.cardId); else captured.confirmed.delete(item.cardId);
              setNotice(undefined); redraw(value => value + 1);
            }} />确认卡片 {item.cardId} 的本次影响</label>
        </li>)}</ol>
      </fieldset>
      <Button disabled={disabled || !preview.items.every(item => captured.confirmed.has(item.cardId))}
        loading={!!activeApply.current} onClick={() => void apply()}>应用到当前画布草稿（仍需 Save）</Button>
      {(!props.canApply || props.busy) && <StatusMessage tone="warning">当前画布不可编辑或正在处理；原确认已失效，请恢复可编辑状态后逐项重新确认。</StatusMessage>}
    </>}
    {notice?.consent === captured && !captured.retired && <p role="status">{notice.text}</p>}
  </Panel>;
}
