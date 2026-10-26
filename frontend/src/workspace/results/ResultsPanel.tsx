/**
 * [HERMIA-FE-20261025 U4-M8c] Result card at the ORIGINAL work location: standing (candidate / reviewed / adopted),
 * source + version, and explicit review / adopt with a two-step confirm. No auto-review, no auto-adopt, no Canon writes.
 * Mount: nothing is read on mount — the user presses 「读取结果」. Raw ids/codes only in data-* attributes.
 */
import {useRef, useState} from 'react';
import type {ProductionJob} from '../../creative/studioProductionClient';
import {actionAvailability, projectResult, type ResultView} from './resultModel';
import {BLOCK_TEXT, createAdoptFlow, type AdoptDeps, type AdoptTarget, type Prepared} from './adoptFlow';
import {resolveExecutionTruth} from '../history/executionTruth';

type Msg = {tone: 'info' | 'warning' | 'error' | 'success'; text: string} | null;
import {useDz} from '../defaultui/drawerEn';
export function ResultsPanel(props: {deps: AdoptDeps; target: AdoptTarget; online?: boolean}) {
  const z = useDz(); // [UWPORT-P2] en drawer text
  const flow = useRef(createAdoptFlow(props.deps)).current;
  const [job, setJob] = useState<ProductionJob | null>(null), [view, setView] = useState<ResultView | null>(null);
  const [prepared, setPrepared] = useState<Extract<Prepared, {ok: true}> | null>(null), [busy, setBusy] = useState(false), [msg, setMsg] = useState<Msg>(null);
  const [confirmReview, setConfirmReview] = useState(false);

  async function read() {
    setBusy(true); setMsg(null); setPrepared(null); setConfirmReview(false);
    const epoch = props.deps.lease.epoch;
    const truth = await resolveExecutionTruth(async () => {
      const j = await props.deps.production.get(props.target.job.owner, props.target.job.id);
      if (props.deps.lease.isCurrent() && props.deps.lease.epoch === epoch) {
        let canvas = null; try { canvas = await props.deps.canvasViews.get(props.target.canvasId); } catch { canvas = null; }
        if (props.deps.lease.isCurrent() && props.deps.lease.epoch === epoch) { setJob(j); setView(projectResult(j, canvas, props.target.cardId)); }
      }
      return j;
    }, props.deps.lease, {online: props.online ?? true});
    if (truth.state === 'RETIRED') { setBusy(false); return; }
    if (truth.state === 'UNKNOWN') setMsg({tone: 'warning', text: truth.next});
    setBusy(false);
  }
  async function startAdopt() {
    setBusy(true); setMsg(null);
    const p = await flow.prepare({...props.target, job: job ?? props.target.job});
    if (p.ok) setPrepared(p); else setMsg({tone: 'error', text: BLOCK_TEXT[p.reason]});
    setBusy(false);
  }
  async function confirmAdopt() {
    if (!prepared) return; setBusy(true);
    const r = await flow.commit({...props.target, job: job ?? props.target.job}, prepared);
    setPrepared(null);
    if (r.state === 'adopted') { setMsg({tone: 'success', text: z('已采用到作品原位置。旧版本仍保留在作品历史里。')}); if (job) setView(projectResult(job, r.record, props.target.cardId)); }
    else if (r.state === 'blocked') setMsg({tone: 'error', text: BLOCK_TEXT[r.reason]});
    else setMsg({tone: 'warning', text: r.next});
    setBusy(false);
  }
  async function doReview() {
    if (!job) return; setBusy(true); setConfirmReview(false);
    const r = await flow.review(job);
    if (r.state === 'reviewed') { setJob(r.job); setView(projectResult(r.job, null, props.target.cardId)); setMsg({tone: 'success', text: z('已审核为正式素材。它还没有被采用到作品，需要你另行确认。')}); }
    else if (r.state === 'blocked') setMsg({tone: 'error', text: BLOCK_TEXT[r.reason]});
    else setMsg({tone: 'warning', text: r.next});
    setBusy(false);
  }
  const acts = view ? actionAvailability(view, {canMutate: props.deps.canMutate(), compareTargetIsAsset: false}) : null;
  return (
    <section className="u4-results" aria-label={z('生成结果')} data-testid="u4-results" data-standing={view?.standing ?? 'none'} data-error-code={view?.errorCode ?? undefined}>
      <header><h3>{z('生成结果')}</h3></header>
      {!view && <p>{z('还没有读取结果。读取不会触发生成。')}</p>}
      {view && <div data-testid="u4-result-view">
        <strong data-testid="u4-standing-label">{z(view.label)}</strong>
        <p>{z(view.detail)}</p>
        <p data-testid="u4-source">{z('来源：')}{z(view.sourceLabel)}{view.assetVersion != null ? z(` · 正式素材第 ${view.assetVersion} 版`) : ''}</p>
      </div>}
      <div role="group" aria-label={z('结果操作')}>
        <button type="button" onClick={read} disabled={busy} data-testid="u4-read">{z(view ? '重新读取原任务' : '读取结果')}</button>
        {acts && (['review', 'adopt', 'compare', 'canon'] as const).map(a => {
          const label = z({review: '审核为正式素材…', adopt: '采用到作品…', compare: '对照', canon: '写入设定'}[a]);
          const onClick = a === 'review' ? () => setConfirmReview(true) : a === 'adopt' ? startAdopt : undefined;
          return <button key={a} type="button" disabled={busy || !acts[a].ok} aria-describedby={acts[a].ok ? undefined : `u4-why-${a}`} onClick={onClick} data-testid={`u4-${a}`}>
            {label}{!acts[a].ok && <span id={`u4-why-${a}`} className="u4-why">{z('（')}{z(acts[a].reason ?? '')}{z('）')}</span>}</button>;
        })}
      </div>
      {confirmReview && <div role="alertdialog" aria-label={z('确认审核')} data-testid="u4-review-confirm">
        <p>{z('确认把这份候选审核为正式素材？审核不会把它放进作品，也不会写入设定。')}</p>
        <button type="button" onClick={doReview} disabled={busy} data-testid="u4-review-yes">{z('确认审核')}</button>
        <button type="button" onClick={() => setConfirmReview(false)}>{z('取消')}</button></div>}
      {prepared && <div role="alertdialog" aria-label={z('确认采用')} data-testid="u4-adopt-confirm">
        <p>{z(`将作品原位置换成已审核素材第 ${prepared.guard.assetVersion} 版。作品会生成新版本，旧版本保留可恢复。不会重新生成。`)}</p>
        <button type="button" onClick={confirmAdopt} disabled={busy} data-testid="u4-adopt-yes">{z('确认采用')}</button>
        <button type="button" onClick={() => setPrepared(null)}>{z('取消')}</button></div>}
      {msg && <div role={msg.tone === 'error' ? 'alert' : 'status'} data-testid="u4-msg" data-tone={msg.tone}>{msg.text}</div>}
    </section>);
}
