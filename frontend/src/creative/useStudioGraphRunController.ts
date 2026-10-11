import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphAction, StudioGraphPreflight, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';
import { graphId } from './graphDraft';
import type { GraphModelAction, GraphModelActionEvidence } from './useStudioGraphModelExecutionController';
import type { GraphMediaAction, GraphMediaActionEvidence } from './useStudioGraphMediaExecution';

export type StudioGraphRunPanelProps = {
  client: StudioGraphClient; graph?: StudioGraphRecord; targetNodeIds: string[]; dirty: boolean; busy: boolean;
  canMutate: boolean; canReview: boolean; modelExecutionEnabled?: boolean; mediaExecutionEnabled?: boolean;
  requestedRunId?: string; onRunSelectionChange?: (runId?: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
};
type ReadKind = 'INSPECT' | 'LIST' | 'OPEN' | 'RESTORE' | 'MODEL_READ';
type OperationKind = ReadKind | 'CREATE' | 'ACTION' | 'MODEL' | 'MEDIA';
type Operation = { id: number; kind: OperationKind; client: StudioGraphClient; owner: string; controller: AbortController };
const targets = (ids: string[]) => JSON.stringify([...ids].sort());
const terminalRun = (run?: StudioGraphRun) => !!run && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(run.status);
const uncertainFailure = (value: unknown) => !(value instanceof ApiError) || value.status === 0 || value.status >= 500
  || value.status === 409 || value.problem.code === 'STUDIO_RESPONSE_INVALID';
const reviewIdentity = (run?: StudioGraphRun) => run?.review
  ? JSON.stringify([run.id, run.version, run.review.node_id, run.review.output_digest]) : undefined;
const invalidRun = () => new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '运行回执与当前图或记录不一致，请重新读取。' });

/** Local UI exclusion only. Every command still belongs to the original checked client. */
export function useStudioGraphRunController(props: StudioGraphRunPanelProps) {
  const [preflight, setPreflight] = useState<StudioGraphPreflight>(), [preflightConsent, setPreflightConsent] = useState<string>();
  const [outputConsent, setOutputConsent] = useState<string>(), [runs, setRuns] = useState<StudioGraphRun[]>([]);
  const [selected, setSelected] = useState<StudioGraphRun>(), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [pendingKind, setPendingKind] = useState<OperationKind>(), [uncertain, setUncertain] = useState(false), [note, setNote] = useState('');
  const [creationUncertain, setCreationUncertain] = useState(false);
  const alive = useRef(true), revoked = useRef(false), sequence = useRef(0), pending = useRef<Operation>();
  const latest = useRef(props); latest.current = props;
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const preflightRef = useRef(preflight); preflightRef.current = preflight;
  const preflightConsentRef = useRef(preflightConsent); preflightConsentRef.current = preflightConsent;
  const outputConsentRef = useRef(outputConsent); outputConsentRef.current = outputConsent;
  const uncertainRef = useRef(uncertain); uncertainRef.current = uncertain;
  const noteRef = useRef(note); noteRef.current = note;
  const creation = useRef<{ identity: string; request: string; uncertain: boolean }>();
  const restoredRun = useRef<string>(), preflightEpoch = useRef(0);
  const owner = JSON.stringify([props.graph?.id, props.graph?.version]), targetsKey = targets(props.targetNodeIds);
  const ownerRef = useRef(owner); ownerRef.current = owner;
  const visibleOwner = useRef({ client: props.client, owner });
  const current = useCallback(() => alive.current && !revoked.current && latest.current.client === visibleOwner.current.client
    && ownerRef.current === visibleOwner.current.owner && latest.current.isCurrent(), []);
  const preflightKey = (value?: StudioGraphPreflight) => {
    const source = latest.current.graph;
    return value && source && value.graph_id === source.id && value.expected_version === source.version
      && targets(value.target_node_ids) === targets(latest.current.targetNodeIds) && !latest.current.dirty
      ? JSON.stringify([source.id, source.version, targets(value.target_node_ids), value.preflight_digest]) : undefined;
  };
  function begin(kind: OperationKind): Operation | undefined {
    if (!current() || pending.current) return;
    const operation = { id: ++sequence.current, kind, client: latest.current.client, owner: ownerRef.current, controller: new AbortController() };
    pending.current = operation; setPendingKind(kind); return operation;
  }
  const live = (operation: Operation) => current() && pending.current?.id === operation.id
    && latest.current.client === operation.client && ownerRef.current === operation.owner && !operation.controller.signal.aborted;
  function finish(operation: Operation) {
    if (pending.current?.id !== operation.id) return;
    pending.current = undefined; if (alive.current) setPendingKind(undefined);
  }
  function cancelRead(operation: Operation) { operation.controller.abort(); finish(operation); }
  function resetReview() { outputConsentRef.current = undefined; setOutputConsent(undefined); }
  function markUncertain(value: boolean) { uncertainRef.current = value; setUncertain(value); }
  function clearPrivateState() {
    preflightRef.current = undefined; selectedRef.current = undefined; preflightConsentRef.current = undefined;
    setPreflight(undefined); setPreflightConsent(undefined); setSelected(undefined); setRuns([]); resetReview();
    noteRef.current = ''; setNote(''); creation.current = undefined; setCreationUncertain(false);
  }
  function unavailable(deny = false) {
    if (!alive.current || !latest.current.isCurrent()) return;
    if (deny) revoked.current = true;
    const operation = pending.current; if (operation) cancelRead(operation);
    clearPrivateState(); markUncertain(true); latest.current.onRunSelectionChange?.(undefined);
    setNotice('权限或入口已变更，已清除先前预览和结果。请重新核对当前能力与运行记录。');
  }
  function failure(value: unknown, operation: Operation, fallback = '运行操作未完成，请核对当前记录。') {
    if (!live(operation)) return;
    setError(apiErrorView(value, fallback).message);
    if (value instanceof ApiError && [401, 403].includes(value.status)) unavailable(true);
  }
  function acceptRun(value: StudioGraphRun, expectedId?: string, expectedGraphVersion?: number) {
    if (value.graph_id !== latest.current.graph?.id || expectedId && value.id !== expectedId
      || expectedGraphVersion !== undefined && value.graph_version !== expectedGraphVersion) throw invalidRun();
    selectedRef.current = value; setSelected(value); setRuns(rows => [...rows.filter(row => row.id !== value.id), value]); resetReview();
  }
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; sequence.current++; pending.current?.controller.abort(); pending.current = undefined; };
  }, []);
  useEffect(() => {
    const operation = pending.current; if (operation) cancelRead(operation);
    visibleOwner.current = { client: props.client, owner };
    revoked.current = false; restoredRun.current = undefined; clearPrivateState(); markUncertain(false); setError(''); setNotice('');
  }, [props.client, owner]);
  useEffect(() => {
    preflightEpoch.current++; preflightRef.current = undefined; preflightConsentRef.current = undefined;
    setPreflight(undefined); setPreflightConsent(undefined);
    if (!creation.current?.uncertain && pending.current?.kind !== 'CREATE') creation.current = undefined;
    if (pending.current?.kind === 'INSPECT') cancelRead(pending.current);
  }, [targetsKey, props.dirty]);
  useEffect(() => { resetReview(); }, [props.canReview, props.dirty]);
  useEffect(() => { if (selected && current()) latest.current.onRunSelectionChange?.(selected.id); }, [selected?.id, props.onRunSelectionChange, current]);

  // Navigation recovery remains an abortable owner GET, never a run action.
  useEffect(() => {
    const source = latest.current;
    if (!source.graph || !source.requestedRunId || selectedRef.current?.id === source.requestedRunId
      || restoredRun.current === source.requestedRunId || source.busy || pending.current || !current()) return;
    const operation = begin('RESTORE'); if (!operation) return;
    const requested = source.requestedRunId; restoredRun.current = requested;
    let settled = false; setError(''); resetReview();
    void source.read(() => source.client.getRun(requested, operation.controller.signal)).then(value => {
      if (!live(operation)) return;
      acceptRun(value, requested); settled = true; markUncertain(false);
      setNotice('已读取上次运行。未恢复执行；预览、确认和审核需要重新核对。');
    }).catch(value => {
      if (!live(operation)) return;
      settled = true; failure(value, operation, '上次运行当前不可读，请重新选择。未自动创建或重试任务。'); markUncertain(true);
    }).finally(() => finish(operation));
    return () => {
      if (!settled && restoredRun.current === requested) restoredRun.current = undefined;
      cancelRead(operation);
    };
  }, [props.requestedRunId, owner, props.client, props.read, props.isCurrent, props.busy]);

  async function inspect() {
    const source = latest.current;
    if (!source.graph || source.busy || source.dirty || !current()) return;
    const operation = begin('INSPECT'); if (!operation) return;
    const targetKey = targets(source.targetNodeIds), expectedEpoch = preflightEpoch.current;
    setError(''); preflightConsentRef.current = undefined; setPreflightConsent(undefined); preflightRef.current = undefined; setPreflight(undefined);
    try {
      const value = await source.read(() => source.client.preflight(source.graph!.id,
        { expected_version: source.graph!.version, target_node_ids: [...source.targetNodeIds] }, operation.controller.signal));
      if (live(operation) && expectedEpoch === preflightEpoch.current && !latest.current.dirty
        && targetKey === targets(latest.current.targetNodeIds)) { preflightRef.current = value; setPreflight(value); }
    } catch (value) { failure(value, operation); } finally { finish(operation); }
  }
  async function listRuns() {
    const source = latest.current; if (!source.graph || source.busy || !current()) return;
    const operation = begin('LIST'); if (!operation) return; setError('');
    try { const value = await source.read(() => source.client.runs(source.graph!.id, operation.controller.signal)); if (live(operation)) setRuns(value.items); }
    catch (value) { failure(value, operation); } finally { finish(operation); }
  }
  async function openRun(id: string) {
    const source = latest.current; if (!source.graph || source.busy || !current()) return;
    const operation = begin('OPEN'); if (!operation) return;
    selectedRef.current = undefined; setSelected(undefined); resetReview(); markUncertain(false); setError('');
    try { const value = await source.read(() => source.client.getRun(id, operation.controller.signal)); if (live(operation)) acceptRun(value, id); }
    catch (value) { failure(value, operation); } finally { finish(operation); }
  }
  function reviewPreflight(checked: boolean) {
    const source = latest.current, key = preflightKey(preflightRef.current);
    const value = checked && current() && !pending.current && !source.busy && source.canMutate && preflightRef.current?.executable ? key : undefined;
    preflightConsentRef.current = value; setPreflightConsent(value);
  }
  function reviewOutput(checked: boolean) {
    const source = latest.current, run = selectedRef.current;
    const value = checked && current() && !pending.current && !source.busy && !source.dirty && source.canReview
      && run?.status === 'WAITING_APPROVAL' && !run.stale && !uncertainRef.current ? reviewIdentity(run) : undefined;
    outputConsentRef.current = value; setOutputConsent(value);
  }
  async function createRun() {
    const source = latest.current, flight = preflightRef.current, key = preflightKey(flight);
    if (!source.graph || !flight?.executable || !key || preflightConsentRef.current !== key || source.busy || source.dirty || !source.canMutate || !current()) return;
    const identity = JSON.stringify([source.graph.id, source.graph.version, flight.preflight_digest, flight.target_node_ids]);
    if (creation.current?.uncertain && creation.current.identity !== identity) {
      setError('先核对上次创建回执；仅相同图版本、预检与目标可明确复用原请求，不能更换范围盲目重建。'); return;
    }
    const operation = begin('CREATE'); if (!operation) return;
    if (creation.current?.identity !== identity) creation.current = { identity, request: graphId('run'), uncertain: false };
    const request = creation.current.request; setError('');
    try {
      const value = await source.mutate(() => source.client.createRun(source.graph!.id, { expected_graph_version: source.graph!.version,
        reviewed_preflight_digest: flight.preflight_digest, target_node_ids: [...flight.target_node_ids], request_id: request }));
      if (live(operation)) {
        acceptRun(value, undefined, source.graph.version); markUncertain(false); preflightConsentRef.current = undefined; setPreflightConsent(undefined);
        creation.current = undefined; setCreationUncertain(false); setNotice('运行记录已建立。尚未自动执行节点。');
      }
    } catch (value) {
      if (live(operation)) {
        if (creation.current?.request === request) creation.current.uncertain = uncertainFailure(value);
        setCreationUncertain(uncertainFailure(value)); if (uncertainFailure(value)) markUncertain(true);
        failure(value, operation); if (current()) setNotice('创建回执需要核对。相同范围的明确重试保留原请求标识；不会自动重试。');
      }
    } finally { finish(operation); }
  }
  function canAction(kind: StudioGraphAction) {
    const source = latest.current, run = selectedRef.current;
    if (!run || !current() || pending.current || source.busy || source.dirty || terminalRun(run)) return false;
    if (kind === 'approve' || kind === 'reject') return source.canReview && run.status === 'WAITING_APPROVAL'
      && !run.stale && !uncertainRef.current && !!run.review && outputConsentRef.current === reviewIdentity(run);
    if (!source.canMutate) return false;
    if (kind === 'cancel') return true;
    if (uncertainRef.current || run.stale) return false;
    const modelInFlight = !!run.model_runtime?.execution && ['ADMITTED', 'UNKNOWN'].includes(run.model_runtime.status)
      || !!run.media_runtime && Object.values(run.node_states).some(node => node.status === 'WORKING');
    return kind === 'execute' ? !modelInFlight && run.status === 'QUEUED' : kind === 'pause'
      ? !modelInFlight && ['QUEUED', 'RUNNING', 'WAITING_APPROVAL'].includes(run.status) : !modelInFlight && run.status === 'PAUSED';
  }
  async function action(kind: StudioGraphAction) {
    if (!canAction(kind)) return;
    const source = latest.current, run = selectedRef.current!, reviewing = kind === 'approve' || kind === 'reject', actionNote = noteRef.current;
    const operation = begin('ACTION'); if (!operation) return; setError(''); resetReview();
    try {
      const value = await source.mutate(() => source.client.action(run.id, kind, { expected_version: run.version,
        ...(reviewing ? { node_id: run.review!.node_id, reviewed_output_digest: run.review!.output_digest } : {}), note: actionNote }));
      if (live(operation)) {
        acceptRun(value, run.id); markUncertain(false); setNotice(value.asset_output
          ? '原工作流运行记录已更新；私有文字资产状态见下方回执，正文未被写入。' : '原工作流运行记录已更新；正文和资产未被写入。');
      }
    } catch (value) { if (live(operation)) { if (uncertainFailure(value)) markUncertain(true); failure(value, operation); } }
    finally { finish(operation); }
  }
  const modelUnavailable = useCallback(() => unavailable(), []);
  async function mediaAction(kind: GraphMediaAction, evidence?: GraphMediaActionEvidence): Promise<boolean> {
    const source = latest.current, run = selectedRef.current;
    if (!run?.media_runtime || source.busy || source.dirty || !current()) return false;
    if (kind === 'get') {
      const operation = begin('OPEN'); if (!operation) return false;
      try {
        const value = await source.read(() => source.client.getRun(run.id, operation.controller.signal));
        if (live(operation)) { acceptRun(value, run.id); markUncertain(false); return true; }
      } catch (value) { failure(value, operation); } finally { finish(operation); }
      return false;
    }
    if (kind === 'cancel') { if (!canAction('cancel')) return false; await action('cancel'); return selectedRef.current?.status === 'CANCELLED'; }
    if (kind === 'reject') {
      if (!evidence || !source.canReview || run.status !== 'WAITING_APPROVAL' || run.stale || uncertainRef.current
        || run.current_node_id !== evidence.node_id || !evidence.reviewed_output_digest) return false;
      const operation = begin('MEDIA'); if (!operation) return false;
      try {
        const value = await source.mutate(() => source.client.action(run.id, 'reject', { expected_version: run.version,
          node_id: evidence.node_id, reviewed_output_digest: evidence.reviewed_output_digest!, note: noteRef.current }));
        if (live(operation)) { acceptRun(value, run.id); markUncertain(false); return true; }
      } catch (value) { if (live(operation)) { if (uncertainFailure(value)) markUncertain(true); failure(value, operation); } }
      finally { finish(operation); }
      return false;
    }
    if (!evidence || run.stale || terminalRun(run) || run.status === 'PAUSED'
      || (kind === 'review' ? !source.canReview : !source.canMutate)
      || uncertainRef.current && !['refresh', 'reconcile'].includes(kind)) return false;
    const { previewMedia, dispatchMedia, executeMedia, refreshMedia, reconcileMedia, reviewMedia } = source.client;
    if (!previewMedia || !dispatchMedia || !executeMedia || !refreshMedia || !reconcileMedia || !reviewMedia) {
      setError('当前入口缺少完整媒体操作客户端，请使用完整 Studio 工作区重新核对。'); return false;
    }
    const operation = begin('MEDIA'); if (!operation) return false; setError(''); resetReview();
    const body = { expected_version: run.version, ...evidence };
    try {
      const value = await source.mutate(() => {
        switch (kind) {
          case 'preview': return previewMedia(run.id, body);
          case 'dispatch': return dispatchMedia(run.id, { ...body, reviewed_preview_digest: evidence.reviewed_preview_digest! });
          case 'execute': return executeMedia(run.id, { ...body, expected_job_version: evidence.expected_job_version!, expected_request_digest: evidence.expected_request_digest! });
          case 'refresh': return refreshMedia(run.id, body);
          case 'reconcile': return reconcileMedia(run.id, { ...body, expected_job_version: evidence.expected_job_version!, expected_request_digest: evidence.expected_request_digest! });
          case 'review': return reviewMedia(run.id, { ...body, expected_job_version: evidence.expected_job_version!, expected_request_digest: evidence.expected_request_digest!, reviewed_output_digest: evidence.reviewed_output_digest! });
          default: throw invalidRun();
        }
      });
      if (live(operation)) { acceptRun(value, run.id); markUncertain(false); setNotice('图媒体运行回执已更新，请在媒体面板核对原任务与审核结果。'); return true; }
    } catch (value) {
      if (live(operation)) {
        if (uncertainFailure(value)) markUncertain(true);
        failure(value, operation); if (current() && value instanceof ApiError && value.status === 404) unavailable();
      }
    } finally { finish(operation); }
    return false;
  }
  async function modelAction(kind: GraphModelAction, evidence: GraphModelActionEvidence = {}): Promise<boolean> {
    const source = latest.current, run = selectedRef.current, model = run?.model_runtime;
    if (!source.modelExecutionEnabled || !run || !model || source.busy || source.dirty || !source.canMutate || !current()
      || run.stale || terminalRun(run) || run.status === 'PAUSED') return false;
    if (kind === 'preview' && (uncertainRef.current || !['AWAITING_PREVIEW', 'PREVIEWED'].includes(model.status)
      || model.execution || !evidence.route_id || typeof evidence.allow_synthetic !== 'boolean')) return false;
    if (kind === 'dispatch' && (uncertainRef.current || model.status !== 'PREVIEWED' || model.execution
      || !model.preview?.execution_available || evidence.reviewed_preview_digest !== model.preview.preview_digest)) return false;
    if (kind === 'refresh' && !model.execution) return false;
    const operation = begin('MODEL'); if (!operation) return false; setError(''); resetReview();
    try {
      const value = await source.mutate(() => kind === 'preview'
        ? source.client.previewModel(run.id, { expected_version: run.version, route_id: evidence.route_id!, allow_synthetic: evidence.allow_synthetic! })
        : kind === 'dispatch' ? source.client.dispatchModel(run.id, { expected_version: run.version, reviewed_preview_digest: evidence.reviewed_preview_digest!,
          ...(evidence.archive_result ? { archive_result: true as const } : {}) }) : source.client.refreshModel(run.id, { expected_version: run.version }));
      if (live(operation)) {
        acceptRun(value, run.id); markUncertain(false);
        setNotice(kind === 'preview' ? '模型输入已准备，尚未调用。' : kind === 'dispatch'
          ? '一次模型任务已提交。请手动核对回执，结果仍需人工审核。' : '模型回执已核对。未自动重放或应用到正文。'); return true;
      }
    } catch (value) {
      if (live(operation)) {
        if (uncertainFailure(value)) markUncertain(true);
        failure(value, operation); if (current() && value instanceof ApiError && value.status === 404) unavailable();
      }
    } finally { finish(operation); }
    return false;
  }
  // Child capability/advisory reads share the run panel's local exclusion slot.
  // They do not grant execution or lock themselves out when their own GET starts.
  async function readModel<T>(work: () => Promise<T>): Promise<T> {
    const source = latest.current;
    if (source.busy || source.dirty || !current()) throw new ApiError({ status: 409, code: 'STUDIO_MODEL_READ_BUSY', message: '当前操作结束后再核对模型信息。' });
    const operation = begin('MODEL_READ');
    if (!operation) throw new ApiError({ status: 409, code: 'STUDIO_MODEL_READ_BUSY', message: '当前运行操作结束后再核对模型信息。' });
    try { return await source.read(work); }
    catch (value) {
      if (live(operation) && value instanceof ApiError && [401, 403].includes(value.status)) { failure(value, operation); }
      throw value;
    } finally { finish(operation); }
  }
  function changeNote(value: string) { if (current() && !pending.current && !latest.current.busy && !latest.current.dirty) { noteRef.current = value.slice(0, 1000); setNote(noteRef.current); } }
  const locked = props.busy || props.dirty || !!pendingKind || !current();
  const key = preflightKey(preflight), outputKey = reviewIdentity(selected);
  const reviewed = !!key && key === preflightConsent, outputReviewed = !!outputKey && outputKey === outputConsent;
  const visible = current();
  return { preflight: visible ? preflight : undefined, reviewed: visible && reviewed, outputReviewed: visible && outputReviewed,
    runs: visible ? runs : [], selected: visible ? selected : undefined, error, notice, note: visible ? note : '', uncertain, creationUncertain, locked,
    modelLocked: props.busy || props.dirty || !current() || !!pendingKind && pendingKind !== 'MODEL_READ',
    canReadRuns: !!props.graph && !props.busy && !pendingKind && current(),
    loading: ['INSPECT', 'LIST', 'OPEN', 'RESTORE'].includes(pendingKind ?? ''), pendingKind,
    terminal: terminalRun(selected), current, inspect, listRuns, openRun, createRun, action, canAction,
    reviewPreflight, reviewOutput, changeNote, modelAction, mediaAction, modelUnavailable, readModel };
}
export type StudioGraphRunController = ReturnType<typeof useStudioGraphRunController>;
