import { useLayoutEffect, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../../ui/primitives';
import type { CanvasVideoTrimTaskBinding } from '../canvasVideoTrimTask';
import type { ProductionJob } from '../studioProductionClient';
import { canDeriveFailedCanvasVideoDraft, deriveFailedCanvasVideoDraft, type FailedCanvasVideoDraft } from './failedCanvasVideoRecovery';

export type CanvasVideoFailedRecoveryPanelProps = {
  job: ProductionJob; task: CanvasVideoTrimTaskBinding; owner: object; current: boolean; busy: boolean; canMutate: boolean;
  isCurrent: () => boolean; newRequestId: () => string;
  onDerive: (draft: FailedCanvasVideoDraft) => void | Promise<void>; onRead: () => void | Promise<void>;
};
const snapshot = (value: unknown) => { try { return JSON.stringify(value); } catch { return undefined; } };
type Round = { values: unknown[]; retired: boolean; readRetired: boolean; consent: boolean; used: boolean; readUsed: boolean; pending: boolean; error: string };
const roundFor = (values: unknown[]): Round => ({ values, retired: false, readRetired: false, consent: false, used: false, readUsed: false, pending: false, error: '' });

/** Consent belongs to one observed original receipt and owner. This panel owns no client or queue. */
export function CanvasVideoFailedRecoveryPanel(props: CanvasVideoFailedRecoveryPanelProps) {
  const live = useRef(props); live.current = props;
  const alive = useRef(false), committed = useRef<object>();
  const [, render] = useState(0);
  const values = [props.job, snapshot(props.job), props.task, snapshot(props.task), props.owner, snapshot(props.owner),
    props.current, props.busy, props.canMutate, props.isCurrent, props.task.isCurrent, props.newRequestId, props.onDerive, props.onRead];
  const round = useRef(roundFor(values));
  if (values.some((value, index) => !Object.is(value, round.current.values[index]))) {
    round.current.retired = true; round.current.consent = false;
    round.current = roundFor(values);
  }
  const session = round.current;
  const refresh = () => render(value => value + 1);
  function owns() {
    return alive.current && committed.current === session && round.current === session;
  }
  function retire() { session.retired = true; session.consent = false; }
  function originalCurrent(mutation: boolean) {
    if (!owns() || session.readRetired || mutation && session.retired) return false;
    const p = live.current;
    // current=false must short circuit before either old current getter is read.
    if (!p.current || p.busy || mutation && !p.canMutate
      || p.job !== values[0] || snapshot(p.job) !== values[1]
      || p.task !== values[2] || snapshot(p.task) !== values[3]
      || p.owner !== values[4] || snapshot(p.owner) !== values[5]
      || p.current !== values[6] || p.busy !== values[7] || p.canMutate !== values[8]
      || p.isCurrent !== values[9] || p.task.isCurrent !== values[10]
      || p.newRequestId !== values[11] || p.onDerive !== values[12] || p.onRead !== values[13]) {
      retire(); session.readRetired = true; return false;
    }
    try {
      if (!p.isCurrent()) { retire(); session.readRetired = true; return false; }
      if (mutation && !p.task.isCurrent()) { retire(); return false; }
    } catch { retire(); session.readRetired = true; return false; }
    return true;
  }
  useLayoutEffect(() => {
    alive.current = true; committed.current = session;
    return () => { if (committed.current === session) committed.current = undefined; };
  });
  useLayoutEffect(() => () => { alive.current = false; }, []);

  if (!props.current) { retire(); session.readRetired = true; return null; }
  if (values[1] === undefined || values[3] === undefined || values[5] === undefined) { retire(); session.readRetired = true; }
  let eligible = false;
  try {
    if (!props.isCurrent()) { retire(); session.readRetired = true; }
    else if (!props.task.isCurrent()) retire();
    else eligible = canDeriveFailedCanvasVideoDraft(props.job, props.task);
  } catch { retire(); session.readRetired = true; }
  const blocked = !eligible || session.retired || props.busy || !props.canMutate || session.used || session.pending;
  async function derive() {
    if (blocked || !originalCurrent(true) || !session.consent || session.used || session.pending) return;
    session.used = true; session.pending = true; session.error = ''; refresh();
    try {
      // Only this explicit, once-consumed click may ask the owner for a fresh identity.
      const requestId = props.newRequestId();
      if (!originalCurrent(true)) return;
      const draft = deriveFailedCanvasVideoDraft(props.job, props.task, requestId);
      if (!originalCurrent(true)) return;
      await props.onDerive(draft);
    } catch (error) {
      if (originalCurrent(true)) session.error = error instanceof Error ? error.message : '新草稿未能接收，请重新读取原记录。';
    } finally {
      session.pending = false;
      if (owns() && !session.retired) refresh();
    }
  }
  async function read() {
    if (session.readUsed || session.pending || !originalCurrent(false)) return;
    session.readUsed = true; retire(); refresh();
    try { await props.onRead(); } catch (error) {
      if (originalCurrent(false)) session.error = error instanceof Error ? error.message : '原记录读取失败，请重新核对当前项目。';
    }
    if (owns()) refresh();
  }
  const command = eligible ? props.job.canvas_video : undefined;
  const binding = command?.canvas_return;
  return <Panel title="从失败视频任务派生新草稿" aria-label="失败视频任务派生草稿">
    <p>原 Job <code>{props.job.id}</code> · {props.job.status} · 原请求 <code>{props.job.request_id}</code></p>
    {command && <>
      <p>原视频 <code>{command.source_snapshots[0].id}</code> · v{command.source_snapshots[0].version} · 截取 {command.parameters.in_ms}–{command.parameters.out_ms} 毫秒</p>
      <p>源音轨：{command.parameters.include_audio === true ? '明确包含' : command.parameters.include_audio === false ? '明确不包含' : '原请求未指定'}</p>
      <p>原画布 <code>{binding?.canvas_id}</code> · v{binding?.canvas_version} · 卡片 <code>{binding?.card_id}</code> · {binding?.incarnation}</p>
    </>}
    <StatusMessage>派生会保留原视频范围、音轨选择和原位置版本绑定，只准备新草稿。请在原入口明确应用并保存新时间线，再分别确认预览、排队、执行、审核和回填。</StatusMessage>
    {(!eligible || session.retired) && <StatusMessage tone="warning">当前记录不能派生，或原确认已退役；请读取原记录核对。UNKNOWN 仅支持读取。</StatusMessage>}
    {!props.canMutate && <StatusMessage tone="warning">当前没有修改权限，仍可读取原记录。</StatusMessage>}
    <label><input type="checkbox" checked={session.consent && !session.retired} disabled={blocked} onChange={event => {
      if (blocked || !originalCurrent(true)) return;
      session.consent = event.target.checked; refresh();
    }} />我已核对原失败记录、视频范围、音轨选择和原画布位置，准备一个新草稿</label>
    <div className="creative-actions">
      <Button disabled={blocked || !session.consent} loading={session.pending} onClick={() => void derive()}>派生新的预览草稿</Button>
      <Button disabled={props.busy || session.pending || session.readUsed || session.readRetired} onClick={() => void read()}>读取原任务记录</Button>
    </div>
    {session.used && !session.pending && !session.error && !session.retired && <StatusMessage>本次派生确认已使用，请在新草稿中继续明确预览。</StatusMessage>}
    {session.error && <StatusMessage tone="error">{session.error}</StatusMessage>}
  </Panel>;
}
