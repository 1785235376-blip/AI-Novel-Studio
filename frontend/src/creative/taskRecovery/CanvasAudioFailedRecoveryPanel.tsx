import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../../ui/primitives';
import { checkedCanvasAudioTaskEnvelope } from '../canvasAudioTaskEnvelope';
import type { CanvasAudioTrimTaskBinding } from '../canvasAudioTrimTask';
import type { ProductionJob } from '../studioProductionClient';
import { deriveFailedCanvasAudioCommand, type DerivedCanvasAudioCommand } from './failedCanvasAudioRecovery';

export type CanvasAudioFailedRecoveryPanelProps = {
  job: ProductionJob; task: CanvasAudioTrimTaskBinding; owner: object; current: boolean; busy: boolean; canMutate: boolean;
  isCurrent: () => boolean; newRequestId: () => string;
  onDerive: (command: DerivedCanvasAudioCommand) => void | Promise<void>; onRead: () => void | Promise<void>;
};
const snapshot = (value: unknown) => { try { return JSON.stringify(value); } catch { return undefined; } };

/** Explicit consent over the original failed receipt; owns neither client nor queue. */
export function CanvasAudioFailedRecoveryPanel(props: CanvasAudioFailedRecoveryPanelProps) {
  const live = useRef(props); live.current = props;
  const alive = useRef(false), committed = useRef<object>(), lease = {};
  const [, render] = useState(0);
  const values = [props.job, snapshot(props.job), props.task, snapshot(props.task), props.owner, snapshot(props.owner),
    props.current, props.busy, props.canMutate, props.isCurrent, props.task.isCurrent, props.newRequestId, props.onDerive, props.onRead];
  const round = useRef({ values, retired: false, consent: false, used: false, readUsed: false, pending: false, error: '' });
  if (values.some((v, i) => !Object.is(v, round.current.values[i]))) {
    round.current.retired = true;
    round.current = { values, retired: false, consent: false, used: false, readUsed: false, pending: false, error: '' };
  }
  const session = round.current;
  function current() {
    if (!alive.current || committed.current !== lease || round.current !== session || session.retired) return false;
    const p = live.current;
    if (!p.current || !p.isCurrent() || !p.task.isCurrent()
      || snapshot(p.job) !== values[1] || snapshot(p.task) !== values[3] || snapshot(p.owner) !== values[5]) {
      session.retired = true; session.consent = false; return false;
    }
    return true;
  }
  useLayoutEffect(() => {
    alive.current = true; committed.current = lease;
    return () => { if (committed.current === lease) committed.current = undefined; };
  });
  useLayoutEffect(() => () => { alive.current = false; }, []);
  // Hide a retired owner's receipt in the very first render, before effects.
  if (!props.current) { session.retired = true; return null; }
  let available = false, reason = '';
  try {
    if (!props.isCurrent() || !props.task.isCurrent()) session.retired = true;
    deriveFailedCanvasAudioCommand(props.job, props.task, props.job.request_id === 'recovery-check' ? 'recovery-check-2' : 'recovery-check');
    available = !session.retired;
  } catch (error) { reason = error instanceof Error ? error.message : '原失败任务不可派生。'; }
  const blocked = !available || props.busy || !props.canMutate || session.used || session.pending;
  const refresh = () => render(v => v + 1);
  async function derive() {
    if (!current() || blocked || live.current.busy || !live.current.canMutate || !session.consent || session.used) return;
    session.used = true; session.pending = true; session.error = ''; refresh();
    try {
      const request = props.newRequestId();
      if (!current()) return;
      const command = deriveFailedCanvasAudioCommand(props.job, props.task, request);
      if (!current()) return;
      await props.onDerive(command);
    } catch (error) {
      if (round.current === session && alive.current && !session.retired)
        session.error = error instanceof Error ? error.message : '新草稿未能交付，请重新读取原任务后核对。';
    } finally {
      session.pending = false;
      if (round.current === session && alive.current && !session.retired) refresh();
    }
  }
  async function read() {
    if (!alive.current || committed.current !== lease || round.current !== session || session.readUsed || props.busy || session.pending) return;
    if (!props.current || !props.isCurrent() || snapshot(props.job) !== values[1]
      || snapshot(props.task) !== values[3] || snapshot(props.owner) !== values[5]) {
      session.retired = true; session.readUsed = true; session.consent = false; return;
    }
    session.readUsed = true; session.retired = true; session.consent = false; refresh();
    try { await props.onRead(); } catch (error) {
      if (alive.current && round.current === session && props.isCurrent())
        session.error = error instanceof Error ? error.message : '原任务读取失败，请重新核对当前项目。';
    }
    if (alive.current && round.current === session) refresh();
  }
  const binding = props.task.returnBinding;
  const parameters = checkedCanvasAudioTaskEnvelope(props.job.command?.parameters, true);
  return <section aria-label="失败音频任务派生草稿">
    <h3>从失败音频任务派生新草稿</h3>
    <p>原任务 {props.job.id} · {props.job.status} · 原请求 {props.job.request_id}</p>
    <p>仅保留原来源音频、截取范围、增益和淡入淡出，以及画布 {binding?.canvas_id ?? '未绑定'} / 卡片 {binding?.card_id ?? '未绑定'} 的版本化位置。生成新的请求标识并保留失败来源。</p>
    {parameters && <p>原参数：{JSON.stringify(parameters)}</p>}
    {available && <p>来源 {props.task.source.id} · v{props.task.source.version} · 画布 v{binding?.canvas_version} · {binding?.incarnation}</p>}
    <StatusMessage>派生只打开待预览草稿。预览、入队、执行、审核和回流仍须分别明确确认；费用未估算。</StatusMessage>
    {!available && <StatusMessage tone="warning">{reason || '原任务核对已退役，请重新读取。'} 当前仅允许读取原记录。</StatusMessage>}
    {!props.canMutate && <StatusMessage tone="warning">当前没有修改权限，仅可读取原记录。</StatusMessage>}
    <label><input type="checkbox" checked={session.consent && !session.retired} disabled={blocked} onChange={event => {
      if (!current() || blocked) return;
      session.consent = event.target.checked; refresh();
    }} />我已核对原失败任务、来源、参数与画布位置，派生一个新草稿</label>
    <Button disabled={blocked || !session.consent} loading={session.pending} onClick={() => void derive()}>派生新任务草稿</Button>
    <Button disabled={props.busy || session.pending || session.readUsed} onClick={() => void read()}>读取原任务记录</Button>
    {session.used && !session.pending && !session.error && <StatusMessage>本次派生操作已使用，请在新草稿中继续明确预览。</StatusMessage>}
    {session.error && <StatusMessage tone="error">{session.error}</StatusMessage>}
  </section>;
}
