import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { CreativeField, DirectorFields } from './CreativeCanvas';
import { DirectorTargetPanel } from './DirectorTargetPanel';
import type { CreativeClient, DirectorModelRoute } from './client';
import { checkedDirectorReviewSubmission, type DirectorModelClient, type DirectorPendingReceipt, type DirectorPreviewReceipt, type DirectorReviewSubmission } from './directorModelClient';
import type { DirectorAdoptionReceipt, DirectorStatusReceipt } from './directorObservationClient';
import { readVerifiedModelDraft } from './directorModelDraftHandoff';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import type { CreativeDocument } from './types';

type Props = {
  model: DirectorModelClient; creative: Pick<CreativeClient, 'export'>;
  proposal: { id: string; version: number; title: string };
  source: PlanningSnapshot; sourceMode?: 'STORYBOARD' | 'SCREENPLAY'; routes: DirectorModelRoute[];
  canMutate: boolean; disabled: boolean;
  onDocument: (document: CreativeDocument, pin: PlanningSnapshot) => void;
  onPending: (pending: boolean) => void; onDenied: () => void;
};

/** View state only. All execution, persistence and review stay with original owners. */
export function IndependentDirectorModelReview(props: Props) {
  const identity = JSON.stringify([props.proposal.id, props.proposal.version, props.source, props.sourceMode, props.canMutate]);
  const origin = useRef({ model: props.model, creative: props.creative, identity, generation: 0 });
  if (origin.current.model !== props.model || origin.current.creative !== props.creative || origin.current.identity !== identity)
    origin.current = { model: props.model, creative: props.creative, identity, generation: origin.current.generation + 1 };
  if (!props.canMutate) return <StatusMessage tone="warning">模型审核权限已变化，请重新打开原任务。</StatusMessage>;
  return <ModelReview key={origin.current.generation} {...props} />;
}

function ModelReview(props: Props) {
  const [preview, setPreview] = useState<DirectorPreviewReceipt>();
  const [status, setStatus] = useState<DirectorStatusReceipt>();
  const [pending, setPending] = useState<DirectorPendingReceipt>();
  const [draft, setDraft] = useState<DirectorReviewSubmission>();
  const [adopted, setAdopted] = useState<DirectorAdoptionReceipt>();
  const [submitted, setSubmitted] = useState<DirectorReviewSubmission>();
  const [routeId, setRouteId] = useState(''), [inputChecked, setInputChecked] = useState(false), [reviewChecked, setReviewChecked] = useState(false);
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState('');
  const [revoked, setRevoked] = useState(false);
  const [readConflict, setReadConflict] = useState(false), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const alive = useRef(true), locked = useRef(false), admission = useRef<symbol>();
  const latest = useRef(props); latest.current = props;
  const renderTicket = Symbol(); useLayoutEffect(() => { admission.current = renderTicket; });
  useEffect(() => { alive.current = true; return () => { alive.current = false; admission.current = undefined; }; }, []);
  const locallyPending = busy || uncertain || !!draft && !adopted;
  useEffect(() => { props.onPending(locallyPending); }, [locallyPending, props.onPending]);
  useEffect(() => () => latest.current.onPending(false), []);
  const current = () => { if (!alive.current || !latest.current.canMutate) throw new Error('原模型审核上下文已退休。'); };
  const admitted = () => alive.current && !revoked && admission.current === renderTicket && !locked.current && !props.disabled;
  const route = props.routes.find(row => row.route_id === routeId);
  function edit(change: () => void) { if (!admitted() || uncertain || adopted) return; admission.current = undefined; change(); setReviewChecked(false); }
  async function run(write: boolean, work: () => Promise<void>) {
    if (!admitted() || write && (uncertain || readConflict || !!adopted)) return;
    locked.current = true; setBusy(true); setError('');
    try { await work(); }
    catch (reason) {
      if (!alive.current) return;
      setError(reason instanceof Error ? reason.message : '原任务操作失败，请核对状态。');
      if (write) setUncertain(true);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { admission.current = undefined; setRevoked(true); setUncertain(false); setPreview(undefined); setStatus(undefined); setPending(undefined); setDraft(undefined); setSubmitted(undefined); setAdopted(undefined); props.onDenied(); }
    } finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  function installPending(value: DirectorPendingReceipt) {
    setPending(value); setDraft({ expected_version: value.expected_version, reviewed_output_digest: value.output_digest,
      title: props.proposal.title, director_notes: structuredClone(value.director_notes),
      ...(value.visual_target === null ? {} : { visual_target: structuredClone(value.visual_target) }) });
    setReviewChecked(false);
  }
  async function reopen(replaceDraft = false) {
    const value = await props.model.readStatus(props.proposal.id); current(); setStatus(value);
    if (submitted) return; // Exact uncertain review is reconciled separately; never replace local text.
    if (draft && !replaceDraft) {
      setReadConflict(value.phase !== 'PENDING_REVIEW' || value.version !== pending?.expected_version);
      setDiscardConfirmed(false);
      return;
    }
    if (value.phase === 'PREVIEW') { const p = await props.model.readPreview(props.proposal.id, props.source); current(); setPreview(p); setInputChecked(false); }
    if (value.phase === 'PENDING_REVIEW' && (!draft || replaceDraft)) { const p = await props.model.readPending(props.proposal.id, props.source); current(); installPending(p); }
    if (value.phase === 'ADOPTED_DRAFT') { const a = await props.model.readAdoptedDraft(props.proposal.id); current(); setAdopted(a); }
    if (replaceDraft && value.phase !== 'PENDING_REVIEW') { setDraft(undefined); setPending(undefined); }
    setReadConflict(false); setDiscardConfirmed(false);
    setUncertain(false);
  }
  if (revoked) return <StatusMessage tone="warning">原模型审核已拒绝访问。请重新验证身份后打开。</StatusMessage>;
  return <section className="creative-model-controls" aria-label={props.sourceMode === 'SCREENPLAY' ? '独立剧本模型导演审核' : '独立分镜模型导演审核'}>
    <h3>模型分析与人工审核</h3><p>仅使用已验证、零费用的本地文字路由。生成建议保留来源、理由与不确定性；不会自动执行媒体或保存画布。</p>
    <p>原分镜 {props.source.id} · v{props.source.version}</p>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {uncertain && <StatusMessage tone="warning">操作回执不确定。保留当前内容，不会自动重试；请读取原任务或核对刚才的审核提交。</StatusMessage>}
    {readConflict && !submitted && <StatusMessage tone="warning">原任务状态已变化，本地审核仍保留。
      <label><input type="checkbox" checked={discardConfirmed} disabled={busy || props.disabled} onChange={event => { if (admitted()) setDiscardConfirmed(event.target.checked); }} />确认放弃本地审核修改并读取当前原任务</label>
      <Button disabled={busy || props.disabled || !discardConfirmed} onClick={() => void run(false, async () => { if (discardConfirmed) await reopen(true); })}>按确认重新读取原任务</Button>
    </StatusMessage>}
    <Button disabled={busy || props.disabled} onClick={() => void run(false, reopen)}>读取原模型任务状态</Button>
    {!preview && !status && !uncertain && <>
      <CreativeField label="独立导演本地路由"><select value={routeId} disabled={busy || props.disabled} onChange={event => edit(() => setRouteId(event.target.value))}>
        <option value="">明确选择本地路由</option>{props.routes.filter(row => !row.synthetic).map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.provider_id} / {row.model_id}</option>)}
      </select></CreativeField>
      <Button disabled={busy || props.disabled || !route?.available || route.synthetic} onClick={() => void run(true, async () => {
        if (!route?.available || route.synthetic) return;
        const value = await props.model.preview(props.proposal.id, props.source, { expected_version: props.proposal.version, route_id: route.route_id });
        current(); setPreview(value); setInputChecked(false);
      })}>{props.sourceMode === 'SCREENPLAY' ? '预览独立剧本模型输入' : '预览独立分镜模型输入'}</Button>
    </>}
    {preview && (!status || status.phase === 'PREVIEW') && <>
      <Badge tone="info">预览尚未调用模型</Badge><p>{preview.provider_id} / {preview.model_id} · 最高费用 0 USD</p>
      <details><summary>核对完整输入与参数</summary><pre>{preview.prompt}</pre><pre>{JSON.stringify(preview.parameters, null, 2)}</pre></details>
      <label><input type="checkbox" checked={inputChecked} disabled={busy || uncertain || props.disabled} onChange={event => { if (admitted()) setInputChecked(event.target.checked); }} />已核对输入，允许调用一次本地模型</label>
      <Button disabled={busy || uncertain || props.disabled || !inputChecked} onClick={() => void run(true, async () => {
        if (!inputChecked) return; const value = await props.model.dispatch(props.proposal.id, props.source, preview); current(); setStatus(value); setInputChecked(false);
      })}>调用一次独立导演模型</Button>
    </>}
    {status && <><Badge>{status.phase}</Badge><p>任务 {status.job_id || '尚未建立'} · 结算 {status.settlement_state}</p>
      {status.cancellation_requested && <StatusMessage tone="warning">已请求本地取消；不保证上游停止或费用已确认。</StatusMessage>}
      {['ADMITTED', 'RUNNING'].includes(status.phase) && <Button disabled={busy || uncertain || props.disabled} onClick={() => void run(true, async () => { const value = await props.model.cancel(props.proposal.id, status); current(); setStatus(value); })}>请求取消原模型任务</Button>}
      {status.phase === 'COMPLETED' && !pending && <Button disabled={busy || uncertain || props.disabled} onClick={() => void run(true, async () => { const value = await props.model.prepareReview(props.proposal.id, props.source, status); current(); installPending(value); })}>准备原模型结果供人工审核</Button>}
    </>}
    {draft && pending && !adopted && <fieldset disabled={busy || uncertain || readConflict || props.disabled}>
      <legend>模型候选人工审核</legend>
      <CreativeField label="模型导演草稿标题"><input value={draft.title} maxLength={240} onChange={event => edit(() => setDraft({ ...draft, title: event.target.value }))} /></CreativeField>
      <DirectorTargetPanel prefix="模型审核 " value={draft.visual_target} onChange={value => edit(() => setDraft({ ...draft, visual_target: value ?? null }))} />
      {draft.director_notes.map((note, index) => <details key={note.id}><summary>模型调度 #{note.number}</summary><DirectorFields prefix={`模型 ${index + 1} `} value={note} onChange={value => edit(() => setDraft({ ...draft, director_notes: draft.director_notes.map(row => row.id === value.id ? value : row) }))} /></details>)}
      <label><input type="checkbox" checked={reviewChecked} onChange={event => { if (admitted()) setReviewChecked(event.target.checked); }} />已核对来源、理由和假设，创建独立导演草稿</label>
      <Button disabled={!reviewChecked || !draft.title.trim()} onClick={() => void run(true, async () => {
        if (!reviewChecked) return; const body = checkedDirectorReviewSubmission(draft); setSubmitted(body);
        const value = await props.model.review(props.proposal.id, body, pending); current(); setAdopted(value); setSubmitted(undefined); setReviewChecked(false);
      })}>采用模型审核结果</Button>
    </fieldset>}
    {submitted && pending && uncertain && <Button disabled={busy || props.disabled} onClick={() => void run(false, async () => {
      const value = await props.model.reconcileReview(props.proposal.id, submitted, pending); current(); setAdopted(value); setSubmitted(undefined); setUncertain(false);
    })}>只读核对刚才的审核提交</Button>}
    {adopted && <><StatusMessage tone="success">已采用为独立导演 DRAFT，画布尚未保存。</StatusMessage><Button disabled={busy || props.disabled} onClick={() => void run(false, async () => {
      const value = await readVerifiedModelDraft(props.model, props.creative, adopted, current); current(); props.onDocument(value.document, value.pin);
    })}>核对并打开模型导演草稿</Button></>}
  </section>;
}
