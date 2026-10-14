import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import {
  PRODUCTION_WORKFLOW_BOUNDS, PRODUCTION_WORKFLOW_ERROR_CODES, PRODUCTION_WORKFLOW_INTENT_ID,
  type ProductionWorkflowClient, type ProductionWorkflowIntent, type ProductionWorkflowIntentDraft,
  type ProductionWorkflowIntentValueInput, type ProductionWorkflowProblem, type ProductionWorkflowProjection,
  type ProductionWorkflowSurfaceState,
} from './productionWorkflowTypes';

const READ_FAILURE = '制作工作流读取失败，请稍后重新核对。';
const SAVE_FAILURE = '创作意图保存结果未确认，当前输入仍保留。';
const CUSTOM_INCOMPLETE = '自定义创作意图需要 1–120 个字符的名称。';
export const PRODUCTION_WORKFLOW_CONFLICT_NOTICE = '服务端创作意图已更新，你的选择仍保留。请核对后重新提交。';
const CONFLICT_REREAD_NOTICE = '已重新读取服务端版本；本地选择尚未提交。';

export type ProductionWorkflowControllerProps = {
  /** Stable workspace/branch identity. A change discards every previously read value. */
  identity: string;
  /** The workflow view is on screen. No read ever runs for a closed view. */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  client: ProductionWorkflowClient;
  onDirtyChange?: (dirty: boolean) => void;
  onUnavailable?: () => void;
};

function problemOf(reason: unknown, fallback: string): ProductionWorkflowProblem {
  // Only the transport's own bounded, user-facing ApiError text is rendered; an
  // unexpected local failure is never echoed verbatim.
  return reason instanceof ApiError
    ? { code: reason.problem.code, message: apiErrorView(reason, fallback).message }
    : { code: PRODUCTION_WORKFLOW_ERROR_CODES.readFailed, message: fallback };
}
const editableValues = (intent: ProductionWorkflowIntent): ProductionWorkflowIntentValueInput[] =>
  intent.values.map(({ intent_id, label, selected }) => ({ intent_id, label, selected }));
const sameValues = (left: ProductionWorkflowIntentValueInput[], right: ProductionWorkflowIntentValueInput[]) =>
  left.length === right.length && left.every((item, index) => item.intent_id === right[index].intent_id
    && item.label === right[index].label && item.selected === right[index].selected);
const blankCustom = (values: ProductionWorkflowIntentValueInput[], customId?: string) =>
  !!customId && values.some(item => item.selected && item.intent_id === customId && !item.label.trim());

/**
 * One read and one local, CAS-guarded intent replacement. The skin receives state and
 * actions; no JSX owns authority and no server value is invented locally.
 */
export function useProductionWorkflow(props: ProductionWorkflowControllerProps) {
  const [projection, setProjection] = useState<ProductionWorkflowProjection>();
  const [state, setState] = useState<ProductionWorkflowSurfaceState>('IDLE');
  const [problem, setProblem] = useState<ProductionWorkflowProblem>();
  const [notice, setNotice] = useState('');
  const [draft, setDraft] = useState<ProductionWorkflowIntentDraft>();
  const [conflict, setConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const alive = useRef(true), epoch = useRef(0), pending = useRef(false), revoked = useRef(false), savingRef = useRef(false);
  const abort = useRef<AbortController>(), identity = useRef(props.identity), latest = useRef(props);
  const projectionRef = useRef<ProductionWorkflowProjection>(), draftRef = useRef<ProductionWorkflowIntentDraft>();
  projectionRef.current = projection; draftRef.current = draft; latest.current = props; identity.current = props.identity;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const admit = useCallback(() => alive.current && !revoked.current && latest.current.active
    && !latest.current.denied && latest.current.isCurrent(), []);
  const customId = projection?.creative_intent.values.find(item => item.custom)?.intent_id;
  const custom = useRef(customId); custom.current = customId;

  const reload = useCallback(async (silent = false) => {
    const captured = latest.current, requestIdentity = captured.identity;
    if (!admit() || pending.current || (!silent && captured.busy)) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    if (!silent) {
      const request = ++epoch.current;
      pending.current = true; setProblem(undefined); setState('LOADING');
      try {
        const value = await captured.read(() => captured.client.read(controller.signal));
        if (request === epoch.current && admit()) { setProjection(value); setState('READY'); setConflict(false); setNotice(''); }
      } catch (reason) {
        if (request === epoch.current && admit() && !controller.signal.aborted) {
          setProblem(problemOf(reason, READ_FAILURE));
          if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
            revoked.current = true; setProjection(undefined); setDraft(undefined); setConflict(false); setNotice('');
            setState('DENIED'); latest.current.onDirtyChange?.(false); captured.onUnavailable?.();
          } else setState(reason instanceof ApiError && [404, 409].includes(reason.status) ? 'UNAVAILABLE' : 'ERROR');
        }
      } finally { if (request === epoch.current) pending.current = false; }
      return;
    }
    // A silent re-read keeps the visible draft and the previous projection on screen.
    const request = ++epoch.current;
    try {
      const value = await captured.read(() => captured.client.read(controller.signal));
      if (request === epoch.current && identity.current === requestIdentity && admit()) {
        setProjection(value);
        setDraft(previous => previous ? { ...previous, expected_version: value.creative_intent.version } : previous);
        setState('READY');
      }
    } catch { /* The original message stays; a failed re-read never clears the draft. */ }
  }, [admit]);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); pending.current = false; savingRef.current = false;
    revoked.current = props.denied; setProjection(undefined); setProblem(undefined); setNotice('');
    setConflict(false); setDraft(undefined); setSaving(false); setState(props.denied ? 'DENIED' : 'IDLE');
  }, [props.identity, props.denied]);
  useEffect(() => { if (props.active && !props.denied) void reload(); }, [props.active, props.identity, props.denied, reload]);

  const values = draft?.values ?? (projection ? editableValues(projection.creative_intent) : []);
  const editable = !props.denied && !revoked.current && projection?.creative_intent.editable === true;
  const dirty = !!draft && !!projection && !sameValues(draft.values, editableValues(projection.creative_intent));
  const customPending = blankCustom(values, customId);
  const canSubmit = editable && dirty && !customPending && !saving && !props.busy && !conflict;

  const draftValues = useCallback((): ProductionWorkflowIntentValueInput[] =>
    draftRef.current?.values ?? (projectionRef.current ? editableValues(projectionRef.current.creative_intent) : []), []);

  const edit = useCallback((next: ProductionWorkflowIntentValueInput[]) => {
    const source = projectionRef.current;
    if (!source) return;
    setDraft({ expected_version: draftRef.current?.expected_version ?? source.creative_intent.version, values: next });
    setConflict(false); setNotice(''); setProblem(undefined);
    latest.current.onDirtyChange?.(true);
  }, []);

  const toggleIntent = useCallback((intentId: string) => {
    const source = projectionRef.current;
    if (!admit() || latest.current.busy || !source || source.creative_intent.editable !== true
      || typeof intentId !== 'string' || !PRODUCTION_WORKFLOW_INTENT_ID.test(intentId)) return;
    edit(draftValues().map(item => item.intent_id === intentId ? { ...item, selected: !item.selected } : item));
  }, [admit, draftValues, edit]);

  const setCustomLabel = useCallback((value: string) => {
    const source = projectionRef.current;
    if (!admit() || latest.current.busy || !source || source.creative_intent.editable !== true || typeof value !== 'string') return;
    const id = custom.current;
    if (!id) return;
    const label = value.replace(/[\u0000-\u001f\u007f]/g, '').slice(0, PRODUCTION_WORKFLOW_BOUNDS.label);
    edit(draftValues().map(item => item.intent_id === id ? { ...item, label } : item));
  }, [admit, draftValues, edit]);

  const skip = useCallback(() => {
    if (!alive.current) return;
    setDraft(undefined); setConflict(false); setNotice(''); setProblem(undefined);
    latest.current.onDirtyChange?.(false);
  }, []);

  /** The explicit re-confirmation after a conflict: the local selection is kept. */
  const acknowledgeConflict = useCallback(() => {
    if (!alive.current || revoked.current || latest.current.denied || !latest.current.isCurrent()) return;
    setConflict(false); setNotice('已核对服务端最新版本；本地选择仍保留，可重新提交。');
  }, []);

  const submit = useCallback(async () => {
    const captured = latest.current, pendingDraft = draftRef.current;
    if (!pendingDraft || savingRef.current || revoked.current || captured.denied || captured.busy || !captured.active || !captured.isCurrent()) return;
    if (blankCustom(pendingDraft.values, custom.current)) {
      setProblem({ code: PRODUCTION_WORKFLOW_ERROR_CODES.localInvalid, message: CUSTOM_INCOMPLETE });
      return;
    }
    const request = epoch.current;
    savingRef.current = true; setSaving(true); setProblem(undefined); setConflict(false); setNotice('');
    try {
      const value: ProductionWorkflowIntent = await captured.mutate(() => captured.client.updateIntent(pendingDraft));
      if (alive.current && request === epoch.current && !revoked.current && captured.isCurrent()) {
        // The response is the owner's own new value; it is adopted, never predicted.
        setProjection(previous => previous && { ...previous, creative_intent: value });
        setDraft(undefined); setState('READY'); setNotice(`创作意图已保存 · v${value.version}。`);
        latest.current.onDirtyChange?.(false);
      }
    } catch (reason) {
      if (alive.current && !revoked.current && captured.isCurrent()) {
        setProblem(problemOf(reason, SAVE_FAILURE));
        if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
          revoked.current = true; setProjection(undefined); setDraft(undefined); setState('DENIED');
          latest.current.onDirtyChange?.(false); captured.onUnavailable?.();
        } else if (reason instanceof ApiError && (reason.status === 409 || reason.problem.code === PRODUCTION_WORKFLOW_ERROR_CODES.conflict)) {
          // The local input is kept; only the expected version is re-read.
          setConflict(true); setNotice(CONFLICT_REREAD_NOTICE);
          void reload(true);
        }
      }
    } finally { savingRef.current = false; if (alive.current) setSaving(false); }
  }, [reload]);

  return {
    state, problem, notice, projection, draft, values, conflict, saving, editable, dirty, customId, customPending, canSubmit,
    canRead: !props.denied && !revoked.current && props.active && !props.busy && state !== 'LOADING',
    reload, toggleIntent, setCustomLabel, skip, acknowledgeConflict, submit,
  };
}
export type ProductionWorkflowController = ReturnType<typeof useProductionWorkflow>;
