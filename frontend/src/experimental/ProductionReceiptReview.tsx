import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { WorkspaceNavigation } from './uxClient';
import { uniqueChapterTarget, originalTaskTarget, receiptPins, receiptOutputs } from './productionReceiptReviewHelpers';

/** Navigation never adopts a source or replays a task. Require explicit leave consent. */
export function ReceiptNavigation({ target, label, onNavigate, disabled = false, receiptIdentity = '' }: { target?: WorkspaceNavigation; label: string; onNavigate?: (target: WorkspaceNavigation) => void; disabled?: boolean; receiptIdentity?: string }) {
  const [leaving, setLeaving] = useState(false);
  const live = useRef({ active: true, key: '', callback: onNavigate, epoch: 0, consent: false });
  const key = JSON.stringify([target, disabled, receiptIdentity]);
  if (live.current.key !== key || live.current.callback !== onNavigate) live.current = { active: true, key, callback: onNavigate, epoch: live.current.epoch + 1, consent: false };
  const epoch = live.current.epoch;
  useEffect(() => { live.current.active = true; return () => { live.current.active = false; live.current.consent = false; }; }, []);
  const valid = () => live.current.active && live.current.epoch === epoch && !disabled && !!target && !!onNavigate;
  return <><Button disabled={disabled || !target || !onNavigate} onClick={() => { if (valid()) { live.current.consent = true; setLeaving(true); } }}>{label}</Button>
    {leaving && live.current.consent && <section aria-label={`确认${label}`}><StatusMessage tone="warning">离开此面板会丢弃未保存的来源声明和临时预检。将按原记录 ID 定位。章节入口显示当前正文，清单版本仅作对照，不是历史正文回放。不会生成、重试或批准。</StatusMessage>
      <Button onClick={() => { live.current.consent = false; setLeaving(false); }}>留在此处</Button>
      <Button disabled={disabled} onClick={() => { if (!valid() || !live.current.consent) return; live.current.consent = false; setLeaving(false); onNavigate!(target!); }}>确认离开并{label}</Button>
    </section>}
  </>;
}

export function ProductionReceiptReview({ manifestId, manifestVersion, receiptIdentity, taskId, taskVersion, pins: rawPins, outputs: rawOutputs, onNavigate, busy }: {
  manifestId: string; manifestVersion: number; receiptIdentity: string; taskId: string; taskVersion: number; pins: unknown; outputs: unknown;
  onNavigate?: (target: WorkspaceNavigation) => void; busy: boolean;
}) {
  const [page, setPage] = useState(0);
  const parsedPins = receiptPins(rawPins), parsedOutputs = receiptOutputs(rawOutputs);
  const pins = parsedPins || [], outputs = parsedOutputs || [];
  const identity = JSON.stringify([receiptIdentity, manifestId, manifestVersion, taskId, taskVersion, pins, outputs]);
  const count = Math.max(1, Math.ceil(pins.length / 20)), current = Math.min(page, count - 1);
  return <section aria-label="清单来源与恢复核对" className="experimental-section">
    <h3>原始回执与人工恢复</h3><p>清单 {manifestId} · v{manifestVersion}</p><p>捕获任务 {taskId} · v{taskVersion}。这是记录时的版本；当前状态与候选审核需在原媒体服务重新读取。</p>
    <ReceiptNavigation target={originalTaskTarget(taskId)} label="打开确切原媒体任务" onNavigate={onNavigate} disabled={busy} receiptIdentity={identity} />
    <StatusMessage>清单保留输入版本和产物摘要，不是当前可复用缓存的证明。没有逐阶段缓存命中或完整审批、实际费用快照；未知不能当作已通过、免费或已批准。</StatusMessage>
    <StatusMessage tone="warning">此清单没有直接选择性重建入口，尚不能据此执行。需在原修改影响面板选择当前来源与具体成果，重新预检；入口未启用或不可用时保持未就绪。</StatusMessage>
    {!parsedPins && <StatusMessage tone="warning">来源回执不完整或超出核对上限，不能据此定位或判断可复用。</StatusMessage>}
    <h4>记录的输入来源 · {parsedPins ? `${pins.length} 项` : '数量未知'}</h4>
    {parsedPins && !pins.length && <p>未记录章节或资产输入；不代表没有其它依赖。</p>}
    {pins.slice(current * 20, current * 20 + 20).map((pin, index) => <article className="experimental-record" key={`${current}:${index}`}>
      <p>{pin.kind} · {pin.state === 'UNAVAILABLE' ? '不可用或无权访问' : pin.id || '标识缺失'} · 记录 v{pin.state === 'UNAVAILABLE' ? '已隐藏' : pin.version ?? '未知'}</p><p>记录摘要：{pin.state === 'UNAVAILABLE' ? '已隐藏' : pin.digest || '未提供'}</p>
      {uniqueChapterTarget(pin, pins) && <ReceiptNavigation target={uniqueChapterTarget(pin, pins)} label={`查看当前来源章节 ${pin.id}`} onNavigate={onNavigate} disabled={busy} receiptIdentity={identity} />}
      {pin.kind === 'CHAPTER' && !uniqueChapterTarget(pin, pins) && <p>来源标识、版本或摘要不足，或存在重复引用；定位未就绪。</p>}
      {pin.kind !== 'CHAPTER' && <p>在原任务来源契约中核对资产引用；此处没有精确历史资产打开入口。</p>}
    </article>)}
    {count > 1 && <div className="experimental-actions"><Button disabled={current === 0 || busy} onClick={() => setPage(current - 1)}>上一页来源</Button><span>第 {current + 1} / {count} 页</span><Button disabled={current === count - 1 || busy} onClick={() => setPage(current + 1)}>下一页来源</Button></div>}
    {!parsedOutputs && <StatusMessage tone="warning">候选回执不完整或超出核对上限，当前审核状态未知。</StatusMessage>}
    <p>原候选 {parsedOutputs ? `${outputs.length} 项` : '数量未知'}；记录候选 ID 和摘要不代表已批准。原任务入口保留来源契约与当前审核状态。</p>
    {outputs.slice(0, 20).map((output, index) => <p key={index}>候选 {output.candidate_index + 1} · {output.proposal_id} · {output.digest}</p>)}
    {outputs.length > 20 && <p>这里只展示前 20 个候选，请在原任务核对其余记录。</p>}
  </section>;
}
