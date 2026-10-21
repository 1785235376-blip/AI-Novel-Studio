import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { buildMediaCanvasHistoryComparison } from './mediaCanvasHistoryCompare';
import { MediaCanvasHistoryCompare } from './MediaCanvasHistoryComparePanel';
import type { CanvasViewClient, CanvasViewHistory, CanvasViewRecord } from './studioCanvasViewClient';

type Receipt = { token: object; history: CanvasViewHistory };
type Approval = { receipt: Receipt; version: number; binding: string; selection: object; retired: boolean };
export function MediaCanvasHistoryPanel(props: { base: CanvasViewRecord; client: CanvasViewClient; owner: object; incarnation?: string; canMutate: boolean; externalDirty: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(f: () => Promise<T>) => Promise<T>; mutate: <T>(f: () => Promise<T>) => Promise<T>; onAdopt: (row: CanvasViewRecord) => void; onUncertain: () => void }) {
  const [receipt, setReceipt] = useState<Receipt>(), [version, setVersion] = useState(0), [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), running = useRef(false), live = useRef(props), receiptRef = useRef(receipt), approval = useRef<Approval>();
  const selection = useRef<object>({}), activeRestore = useRef<object>(); live.current = props; receiptRef.current = receipt;
  const values = [props.owner, props.client, props.client.history, props.client.restore, props.base.id, props.base.version, props.base.definition_digest,
    JSON.stringify(props.base.scope), props.incarnation, props.canMutate, props.externalDirty];
  const fence = useRef({ values, token: {}, retired: false });
  if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) {
    if (approval.current) approval.current.retired = true;
    fence.current = { values, token: {}, retired: false };
  }
  const generation = fence.current, token = generation.token;
  function current() {
    if (generation.retired) return false;
    const now = live.current;
    try {
      if (!alive.current || fence.current !== generation || !now.isCurrent() || now.externalDirty
        || now.owner !== generation.values[0] || now.client !== generation.values[1]
        || now.client.history !== generation.values[2] || now.client.restore !== generation.values[3]
        || now.base.id !== generation.values[4] || now.base.version !== generation.values[5] || now.base.definition_digest !== generation.values[6]
        || JSON.stringify(now.base.scope) !== generation.values[7] || now.incarnation !== generation.values[8] || now.canMutate !== generation.values[9]) generation.retired = true;
    } catch { generation.retired = true; }
    if (generation.retired && approval.current) approval.current.retired = true;
    return !generation.retired;
  }
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; if (approval.current) approval.current.retired = true; }; }, []);
  const visible = receipt?.token === token ? receipt : undefined, target = visible?.history.items.find(row => row.version === version);
  function comparison(proof: Receipt, targetVersion: number) {
    return buildMediaCanvasHistoryComparison({ base: live.current.base, history: proof.history, targetVersion, incarnation: live.current.incarnation, current: current() });
  }
  const diff = visible && target ? comparison(visible, target.version) : undefined;
  function validApproval(value: Approval) {
    if (value.retired) return false;
    const observed = comparison(value.receipt, value.version);
    if (!current() || selection.current !== value.selection || observed.state !== 'ready' || observed.binding !== value.binding) value.retired = true;
    return !value.retired;
  }
  const approved = approval.current, confirmed = consent && !!approved && approved.receipt === visible && approved.version === version && validApproval(approved);
  const busy = pending || props.busy || !!props.isBusy?.();
  const canRestore = current() && props.canMutate && !busy && !uncertain && !!props.incarnation && visible?.history.incarnation === props.incarnation
    && target?.can_restore === true && diff?.state === 'ready' && !!diff.binding;
  function retireSelection() { if (approval.current) approval.current.retired = true; approval.current = undefined; selection.current = {}; setConsent(false); }
  async function load() {
    if (!current() || running.current || props.busy || props.isBusy?.()) return;
    running.current = true; setPending(true); setError(''); setReceipt(undefined); receiptRef.current = undefined; retireSelection(); setVersion(0);
    try {
      const value = await props.read(() => { if (!current()) throw new Error('旧画布读取已退役。'); return props.client.history(props.base.id); });
      if (!current()) return;
      if (value.project_id !== props.base.project_id || JSON.stringify(value.scope) !== JSON.stringify(props.base.scope) || value.id !== props.base.id
        || value.current_version !== props.base.version || value.current_definition_digest !== props.base.definition_digest
        || props.incarnation && value.incarnation !== props.incarnation) throw new Error('画布版本、范围或项目轮次已改变，请重新读取当前画布。');
      setReceipt({ token, history: structuredClone(value) });
    } catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : '历史读取失败。'); }
    finally { running.current = false; if (alive.current) setPending(false); }
  }
  async function restore() {
    const proof = visible, chosen = target, accepted = approval.current;
    if (!current() || !canRestore || running.current || !proof || receiptRef.current !== proof || !chosen || !confirmed || !accepted || !validApproval(accepted)) return;
    const captured = structuredClone(proof.history), capturedIncarnation = proof.history.incarnation, chosenVersion = chosen.version;
    const operation = {}; activeRestore.current = operation; running.current = true; setPending(true); approval.current = undefined;
    receiptRef.current = undefined; setReceipt(undefined); setConsent(false); let sent = false;
    try {
      const row = await props.mutate(() => {
        if (activeRestore.current !== operation || !validApproval(accepted) || !live.current.canMutate
          || live.current.incarnation !== capturedIncarnation || captured.items.find(item => item.version === chosenVersion)?.can_restore !== true) {
          throw new Error('版本差异或原范围已改变，本次恢复确认退役；没有发送恢复请求。');
        }
        sent = true; return props.client.restore(captured, chosenVersion);
      });
      if (current() && live.current.incarnation === capturedIncarnation) props.onAdopt(row);
      else if (alive.current) { setUncertain(true); props.onUncertain(); setError('恢复期间原范围或轮次改变，结果待核对；不能自动重试。'); }
    } catch (reason) {
      if (alive.current) {
        if (sent) { setUncertain(true); props.onUncertain(); }
        setError((sent ? '恢复结果待核对，请重新读取当前画布。' : '恢复未发送，请重新读取历史并核对差异。') + (reason instanceof Error ? reason.message : ''));
      }
    } finally { if (activeRestore.current === operation) activeRestore.current = undefined; running.current = false; if (alive.current) setPending(false); }
  }
  return <details><summary>画布版本历史与恢复</summary><section aria-label="持久画布版本历史">
    <p>读取原画布 row 的版本历史。恢复会创建新当前版本，保留原历史与素材 pin；不会回滚或重新生成素材，也不会自动绑定最新素材。</p>
    <Button disabled={busy || props.externalDirty} onClick={() => void load()}>读取画布版本历史</Button>
    {visible && <><p>当前 v{visible.history.current_version} · 历史 {visible.history.items.length} 项。</p>
      <label>待恢复画布版本<select aria-label="待恢复画布版本" value={version || ''} disabled={busy} onChange={event => { if (current()) { retireSelection(); setVersion(Number(event.target.value)); } }}>
        <option value="">明确选择历史版本</option>{visible.history.items.map(row => <option key={row.version} value={row.version} disabled={!row.can_restore}>v{row.version} · {row.definition.cards.length} 卡片 · {row.can_restore ? '可核对恢复' : row.version === visible.history.current_version ? '当前版本' : '来源过期或不可用'}</option>)}
      </select></label>
      {target && <><MediaCanvasHistoryCompare base={props.base} history={visible.history} targetVersion={target.version} incarnation={props.incarnation} current={current()} isCurrent={current} />
        <p>将 v{target.version} 的布局和原资产引用保存为 v{visible.history.current_version + 1}；恢复后原有重放、候选、预览和回填意图需重新核对。</p>
        <label><input type="checkbox" disabled={!canRestore} checked={confirmed} onChange={event => {
          if (!current() || visible !== receiptRef.current || !canRestore) return;
          if (!event.target.checked) { retireSelection(); return; }
          const observed = comparison(visible, target.version);
          if (observed.state !== 'ready' || !observed.binding) return;
          approval.current = { receipt: visible, version: target.version, binding: observed.binding, selection: selection.current, retired: false }; setConsent(true);
        }} />确认创建新的当前版本并退役旧预览</label>
        <Button disabled={!canRestore || !confirmed} onClick={() => void restore()}>恢复此画布版本为新版本</Button></>}
    </>}
    {!props.incarnation && <p>当前页面未提供项目轮次；历史可供查看，须等原项目上下文重新核对，不能猜测恢复轮次。</p>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section></details>;
}
