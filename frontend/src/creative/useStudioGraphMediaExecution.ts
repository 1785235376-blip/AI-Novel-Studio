import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphMediaNodeRuntime, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

export type GraphMediaAction = 'get' | 'preview' | 'dispatch' | 'execute' | 'refresh' | 'reconcile' | 'review' | 'reject' | 'cancel';
export type GraphMediaActionEvidence = { node_id: string; reviewed_preview_digest?: string; expected_job_version?: number;
  expected_request_digest?: string; reviewed_output_digest?: string };
export type StudioGraphMediaExecutionProps = {
  client: StudioGraphClient; graph?: StudioGraphRecord; run?: StudioGraphRun; locked: boolean; canMutate: boolean; canReview: boolean;
  uncertain: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>;
  perform: (action: GraphMediaAction, evidence?: GraphMediaActionEvidence) => Promise<boolean>;
  onUnavailable: () => void; onDirtyChange?: (dirty: boolean) => void;
};
type Candidate = { url: string; kind: 'image' | 'video' | 'audio'; binding: string };
type Request = { id: number; client: StudioGraphClient; runId: string; controller: AbortController };
const terminal = (run?: StudioGraphRun) => !!run && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(run.status);
const candidateKey = (run?: StudioGraphRun, node?: StudioGraphMediaNodeRuntime) => {
  const job = node?.execution?.job, asset = job?.output_candidate;
  return run && job && asset ? JSON.stringify([run.id, run.version, node!.node_id, job.id, job.version, job.request_digest, asset.id, asset.version, asset.digest]) : '';
};
const uncertainFailure = (value: unknown) => !(value instanceof ApiError) || value.status === 0 || value.status >= 500
  || [408, 409, 425, 429].includes(value.status) || value.problem.code === 'STUDIO_RESPONSE_INVALID';

/** This controller owns consent and private Blob lifetime; the parent retains the original run mutation owner. */
export function useStudioGraphMediaExecution(props: StudioGraphMediaExecutionProps) {
  const [selectedId, setSelectedId] = useState(''), [previewConsent, setPreviewConsent] = useState(''), [reviewConsent, setReviewConsent] = useState('');
  const [candidate, setCandidate] = useState<Candidate>(), [pendingKind, setPendingKind] = useState<string>(), [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false), [denied, setDenied] = useState(false);
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), revoked = useRef(false), epoch = useRef(0), pending = useRef<Request>();
  const visibleOwner = useRef({ client: props.client, runId: props.run?.id });
  const selectedRef = useRef(selectedId), previewConsentRef = useRef(previewConsent), reviewConsentRef = useRef(reviewConsent);
  const candidateRef = useRef<Candidate>(), sent = useRef(new Set<string>()), uncertainRef = useRef(uncertain);
  selectedRef.current = selectedId; previewConsentRef.current = previewConsent; reviewConsentRef.current = reviewConsent; uncertainRef.current = uncertain;
  const current = () => alive.current && !revoked.current && latest.current.client === visibleOwner.current.client
    && latest.current.run?.id === visibleOwner.current.runId && latest.current.isCurrent();
  function clearConsent() { previewConsentRef.current = ''; reviewConsentRef.current = ''; setPreviewConsent(''); setReviewConsent(''); }
  function clearCandidate() { if (candidateRef.current) URL.revokeObjectURL(candidateRef.current.url); candidateRef.current = undefined; setCandidate(undefined); reviewConsentRef.current = ''; setReviewConsent(''); }
  function markUncertain(value: boolean) { uncertainRef.current = value; setUncertain(value); }
  function unavailable() {
    revoked.current = true; epoch.current++; pending.current?.controller.abort(); pending.current = undefined;
    clearCandidate(); clearConsent(); setDenied(true); setPendingKind(undefined); latest.current.onUnavailable();
  }
  function snapshot() {
    const source = latest.current, graph = source.graph, run = source.run, nodes = run?.media_runtime?.nodes || [];
    const node = nodes.find(item => item.node_id === selectedRef.current) || nodes.find(item => item.node_id === run?.current_node_id) || nodes[0];
    const execution = node?.execution, job = execution?.job, preview = node?.preview, reviewRecovery = execution?.review_recovery;
    const reviewNodeId = graph && run && graph.id === run.graph_id && graph.version === run.graph_version
      ? graph.definition.edges.find(edge => edge.source_node_id === node?.node_id && edge.source_port === 'candidate'
        && edge.target_port === 'candidate' && graph.definition.nodes.some(item => item.id === edge.target_node_id && item.definition_id === 'media_review'))?.target_node_id : undefined;
    const locked = source.locked || !!pending.current || denied || !current();
    const commandsAvailable = [source.client.previewMedia, source.client.dispatchMedia, source.client.executeMedia,
      source.client.refreshMedia, source.client.reconcileMedia, source.client.reviewMedia].every(method => typeof method === 'function');
    const disabled = locked || !commandsAvailable || !source.canMutate || !run || run.stale || terminal(run) || run.status === 'PAUSED';
    const reviewDisabled = locked || !commandsAvailable || !source.canReview || !run || run.stale || terminal(run) || run.status === 'PAUSED';
    const unknown = source.uncertain || uncertainRef.current || execution?.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY';
    const previewKey = run && node && preview && !execution ? JSON.stringify([run.id, run.version, node.node_id, preview.preview_digest,
      preview.production_preview.request_digest, preview.production_preview.provider?.route_digest, preview.production_preview.execution_recipe.recipe_digest]) : '';
    const binding = candidateKey(run, node), visibleCandidate = candidateRef.current?.binding === binding ? candidateRef.current : undefined;
    const actionKey = (action: GraphMediaAction) => !run || !node ? '' : action === 'dispatch'
      ? JSON.stringify([run.id, node.node_id, action, preview?.preview_digest])
      : job ? JSON.stringify([run.id, node.node_id, action, job.id, job.version, job.request_digest])
      : reviewRecovery ? JSON.stringify([run.id, node.node_id, action, execution?.job_id, reviewRecovery.job_version, reviewRecovery.request_digest])
      : JSON.stringify([run.id, run.version, node.node_id, action]);
    const onceOnly = (action: GraphMediaAction) => ['dispatch', 'execute', 'review', 'reject', 'cancel'].includes(action);
    const allowed = (action: GraphMediaAction) => !onceOnly(action) || !sent.current.has(actionKey(action));
    const reviewCurrent = !!reviewNodeId && run?.current_node_id === reviewNodeId && run.node_states[reviewNodeId]?.status === 'WAITING_APPROVAL';
    const canRecoverReview = !locked && commandsAvailable && source.canMutate && !!run && !!execution?.job_id
      && execution.status === 'REVIEWING' && execution.review_state === 'REVIEW_RESERVED' && !!reviewRecovery;
    return { run, nodes, node, execution, job, preview, reviewRecovery, reviewNodeId, reviewCurrent, locked, disabled, reviewDisabled, unknown, previewKey, binding, visibleCandidate, actionKey, onceOnly,
      canRead: !locked && !!run,
      canPreview: !disabled && !unknown && !!source.client.previewMedia && !!node && !execution && ['AWAITING_PREVIEW', 'PREVIEWED'].includes(node.status) && allowed('preview'),
      canConfirm: !disabled && !unknown && !!previewKey && preview?.production_preview.execution_available === true,
      canDispatch: !disabled && !unknown && !!source.client.dispatchMedia && !!previewKey && previewConsentRef.current === previewKey && allowed('dispatch'),
      canExecute: !disabled && !unknown && !!source.client.executeMedia && job?.status === 'QUEUED' && !execution?.send_reserved && run?.current_node_id === node?.node_id && run?.status === 'RUNNING' && allowed('execute'),
      canRefresh: !disabled && !!source.client.refreshMedia && !!execution && (execution.job_id === null || !!job && !['FAILED', 'CANCELLED'].includes(job.status)) && allowed('refresh'),
      canReconcile: canRecoverReview && !!source.client.reconcileMedia && allowed('reconcile') || !disabled && !!source.client.reconcileMedia && !!job && (execution?.owner === 'timeline' ? ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status)
        : execution?.owner === 'video' ? ['RUNNING', 'SEND_RESERVED', 'UNKNOWN', 'RESULT_READY', 'REVIEWING'].includes(job.status)
        : job.needs_reconciliation === true || ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status)) && allowed('reconcile'),
      canCancel: !disabled && !!job && (execution?.owner === 'timeline' ? ['QUEUED', 'RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status)
        : !['APPROVED', 'FAILED', 'CANCELLED', 'REVIEWING'].includes(job.status)) && allowed('cancel'),
      canCandidate: !locked && !!job?.output_candidate && !!source.client.mediaCandidate,
      canReview: !reviewDisabled && !!source.client.reviewMedia && reviewCurrent && !!visibleCandidate && !!binding && reviewConsentRef.current === binding
        && (['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING'].includes(job?.status || '') || job?.status === 'APPROVED' && execution?.review_state === 'REVIEW_RESERVED') && allowed('review'),
      canReject: !reviewDisabled && reviewCurrent && !!visibleCandidate && !!binding && reviewConsentRef.current === binding
        && ['AWAITING_REVIEW', 'SUCCEEDED'].includes(job?.status || '') && allowed('reject'),
    };
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; pending.current?.controller.abort(); pending.current = undefined;
    if (candidateRef.current) URL.revokeObjectURL(candidateRef.current.url); candidateRef.current = undefined; latest.current.onDirtyChange?.(false); }; }, []);
  useLayoutEffect(() => {
    epoch.current++; pending.current?.controller.abort(); pending.current = undefined; visibleOwner.current = { client: props.client, runId: props.run?.id };
    revoked.current = false; sent.current.clear(); selectedRef.current = ''; setSelectedId(''); clearCandidate(); clearConsent(); markUncertain(false); setDenied(false); setPendingKind(undefined); setError('');
  }, [props.client, props.run?.id]);
  const state = snapshot(), binding = state.binding;
  useLayoutEffect(() => { clearConsent(); clearCandidate(); }, [props.run?.version, selectedId, props.canReview, props.canMutate, binding]);
  useEffect(() => { if (!props.isCurrent()) { epoch.current++; pending.current?.controller.abort(); pending.current = undefined; clearCandidate(); clearConsent(); setPendingKind(undefined); } }, [props.isCurrent, props.locked]);
  const dirty = current() && (!!previewConsent || !!reviewConsent || uncertain || props.uncertain
    || state.execution?.receipt_state === 'UNKNOWN_NO_AUTOMATIC_REPLAY' || !!pendingKind);
  useLayoutEffect(() => { props.onDirtyChange?.(dirty); }, [dirty, props.onDirtyChange]);
  function chooseNode(value: string) {
    const state = snapshot(); if (state.locked || !state.nodes.some(node => node.node_id === value)) return;
    selectedRef.current = value; setSelectedId(value); clearConsent(); clearCandidate(); setError('');
  }
  function confirmPreview(value: boolean) { const state = snapshot(); const key = value && state.canConfirm ? state.previewKey : ''; previewConsentRef.current = key; setPreviewConsent(key); }
  function confirmReview(value: boolean) { const state = snapshot(); const key = value && !state.reviewDisabled && state.reviewCurrent && state.visibleCandidate ? state.binding : ''; reviewConsentRef.current = key; setReviewConsent(key); }
  function valid(request: Request) { return current() && pending.current?.id === request.id && epoch.current === request.id && request.client === latest.current.client
    && request.runId === latest.current.run?.id && !request.controller.signal.aborted; }
  function finish(request: Request) { if (pending.current?.id === request.id) { pending.current = undefined; if (alive.current) setPendingKind(undefined); } }
  async function action(kind: GraphMediaAction) {
    const source = latest.current, state = snapshot();
    const allowed = kind === 'get' ? state.canRead : ({ preview: state.canPreview, dispatch: state.canDispatch, execute: state.canExecute,
      refresh: state.canRefresh, reconcile: state.canReconcile, review: state.canReview, reject: state.canReject, cancel: state.canCancel })[kind];
    if (!allowed || !state.run || kind !== 'get' && !state.node) return;
    const request: Request = { id: ++epoch.current, client: source.client, runId: state.run.id, controller: new AbortController() };
    const evidence = kind === 'get' ? undefined : { node_id: kind === 'review' || kind === 'reject' ? state.reviewNodeId! : state.node!.node_id,
      ...(kind === 'dispatch' ? { reviewed_preview_digest: state.preview!.preview_digest } : {}),
      ...(!['preview', 'dispatch'].includes(kind) && state.job ? { expected_job_version: state.job.version, expected_request_digest: state.job.request_digest } : {}),
      ...(kind === 'reconcile' && !state.job && state.reviewRecovery ? { expected_job_version: state.reviewRecovery.job_version,
        expected_request_digest: state.reviewRecovery.request_digest } : {}),
      ...(kind === 'review' || kind === 'reject' ? { reviewed_output_digest: state.job!.output_candidate!.digest } : {}) };
    if (state.onceOnly(kind)) sent.current.add(state.actionKey(kind));
    pending.current = request; setPendingKind(kind); setError(''); clearConsent();
    try {
      const accepted = await source.perform(kind, evidence);
      if (!valid(request)) return;
      if (accepted) { if (kind === 'get') markUncertain(false); }
      else { markUncertain(true); setError('操作回执尚未确认，请读取原运行核对；不会自动重复发送。'); }
    } catch (value) {
      if (!valid(request)) return;
      setError(apiErrorView(value, '图媒体操作需要重新核对，未自动重试。').message);
      if (kind !== 'get' && uncertainFailure(value)) markUncertain(true);
      if (value instanceof ApiError && [401, 403, 404].includes(value.status)) unavailable();
    } finally { finish(request); }
  }
  async function loadCandidate() {
    const source = latest.current, state = snapshot(); if (!state.canCandidate || !state.run || !state.node || !state.job?.output_candidate) return;
    const request: Request = { id: ++epoch.current, client: source.client, runId: state.run.id, controller: new AbortController() }, expected = state.binding;
    const asset = state.job.output_candidate; pending.current = request; setPendingKind('candidate'); clearCandidate(); setError('');
    try {
      const blob = await source.read(() => source.client.mediaCandidate!(state.run!.id, state.node!.node_id));
      if (!valid(request) || snapshot().binding !== expected) return;
      if (!blob.size || blob.size > 25 * 1024 * 1024 || !blob.type.startsWith(`${asset.kind}/`)) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '候选大小或媒体类型不匹配。' });
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()))).map(value => value.toString(16).padStart(2, '0')).join('');
      if (!valid(request) || snapshot().binding !== expected) return;
      if (hash !== asset.digest) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '候选内容与已记录摘要不匹配，不能审核。' });
      const value = { url: URL.createObjectURL(blob), kind: asset.kind, binding: expected }; candidateRef.current = value; setCandidate(value);
    } catch (value) {
      if (!valid(request)) return; setError(apiErrorView(value, '候选读取失败，请重新核对原运行。').message);
      if (value instanceof ApiError && [401, 403, 404].includes(value.status)) unavailable();
    } finally { finish(request); }
  }
  const visible = current();
  return { ...state, run: visible ? state.run : undefined, nodes: visible ? state.nodes : [], node: visible ? state.node : undefined,
    preview: visible ? state.preview : null, execution: visible ? state.execution : null, job: visible ? state.job : undefined,
    candidate: visible && candidate?.binding === state.binding ? candidate : undefined, pendingKind, error, uncertain: visible && (uncertain || props.uncertain), dirty,
    selectedId: state.node?.node_id || '', previewReviewed: !!state.previewKey && previewConsent === state.previewKey,
    outputReviewed: !!state.binding && reviewConsent === state.binding, chooseNode, confirmPreview, confirmReview, action, loadCandidate };
}
export type StudioGraphMediaExecutionController = ReturnType<typeof useStudioGraphMediaExecution>;
