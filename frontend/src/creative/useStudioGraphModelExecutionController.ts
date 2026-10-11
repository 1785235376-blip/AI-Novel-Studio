import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphModelCapabilities, StudioGraphRun } from './studioGraphTypes';

export type GraphModelAction = 'preview' | 'dispatch' | 'refresh';
export type GraphModelActionEvidence = { route_id?: string; allow_synthetic?: boolean; reviewed_preview_digest?: string; archive_result?: true };
export type StudioGraphModelExecutionPanelProps = {
  client: StudioGraphClient; run?: StudioGraphRun; locked: boolean; canMutate: boolean; uncertain: boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>;
  perform: (action: GraphModelAction, evidence?: GraphModelActionEvidence) => Promise<boolean>; onUnavailable: () => void;
};
type Request = { id: number; kind: 'LOAD' | 'ACTION'; client: StudioGraphClient; runId?: string; controller: AbortController };

/** Route selection and consent are local state; perform retains the original run owner. */
export function useStudioGraphModelExecutionController(props: StudioGraphModelExecutionPanelProps) {
  const [capabilities, setCapabilities] = useState<StudioGraphModelCapabilities>(), [routeId, setRouteId] = useState('');
  const [allowSynthetic, setAllowSynthetic] = useState(false), [consent, setConsent] = useState<string>();
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), epoch = useRef(0), pending = useRef<Request>();
  const latest = useRef(props); latest.current = props;
  const consentRef = useRef(consent); consentRef.current = consent;
  const capabilitiesRef = useRef(capabilities); capabilitiesRef.current = capabilities;
  const choice = useRef({ routeId, allowSynthetic }); choice.current = { routeId, allowSynthetic };
  const visibleOwner = useRef({ client: props.client, runId: props.run?.id });
  const current = useCallback(() => alive.current && latest.current.client === visibleOwner.current.client
    && latest.current.run?.id === visibleOwner.current.runId && latest.current.isCurrent(), []);
  const valid = (request: Request) => current() && pending.current?.id === request.id && epoch.current === request.id
    && latest.current.client === request.client && latest.current.run?.id === request.runId && !request.controller.signal.aborted;
  function clearConsent() { consentRef.current = undefined; setConsent(undefined); }
  function finish(request: Request) { if (pending.current?.id === request.id) { pending.current = undefined; if (alive.current) setLoading(false); } }
  function abortLoad() {
    const request = pending.current;
    if (request?.kind === 'LOAD') { request.controller.abort(); epoch.current++; finish(request); }
  }
  function clearCapabilities() {
    capabilitiesRef.current = undefined; setCapabilities(undefined); choice.current = { routeId: '', allowSynthetic: false };
    setRouteId(''); setAllowSynthetic(false); clearConsent();
  }
  function unavailable() { abortLoad(); clearCapabilities(); latest.current.onUnavailable(); }
  function snapshot() {
    const source = latest.current, model = source.run?.model_runtime;
    const preview = !source.run?.stale ? model?.preview : null, execution = model?.execution;
    const route = capabilitiesRef.current?.routes.find(item => item.route_id === choice.current.routeId);
    const terminal = !!source.run && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(source.run.status);
    const disabled = source.locked || !!pending.current || !source.canMutate || !!source.run?.stale || source.run?.status === 'PAUSED' || terminal || !current();
    const previewReady = !!model && ['AWAITING_PREVIEW', 'PREVIEWED'].includes(model.status) && !execution;
    const exactRoute = !!preview?.route && !!route && preview.route.route_id === route.route_id
      && preview.route.provider_id === route.provider_id && preview.route.model_id === route.model_id && preview.route.synthetic === route.synthetic;
    const confirmationKey = source.run && preview && route ? JSON.stringify([source.run.id, source.run.version, preview.preview_digest,
      route.route_id, route.provider_id, route.model_id, route.synthetic, choice.current.allowSynthetic]) : undefined;
    const canConfirm = model?.status === 'PREVIEWED' && !execution && !!preview?.execution_available && exactRoute && !!route?.available
      && (!route.synthetic || choice.current.allowSynthetic) && !disabled && !source.uncertain;
    return { model, preview, execution, route, terminal, disabled, previewReady, exactRoute, confirmationKey, canConfirm,
      canDispatch: canConfirm && !!confirmationKey && consentRef.current === confirmationKey,
      canPreview: previewReady && !disabled && !source.uncertain && !!route?.available && (!route.synthetic || choice.current.allowSynthetic),
      canRefresh: !!execution && !disabled };
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; pending.current?.controller.abort(); pending.current = undefined; }; }, []);
  useEffect(() => {
    abortLoad(); visibleOwner.current = { client: props.client, runId: props.run?.id }; clearCapabilities(); setError('');
  }, [props.client, props.run?.id]);
  useEffect(() => {
    clearConsent();
    if (props.locked || !props.isCurrent()) abortLoad();
  }, [props.run?.version, props.run?.model_runtime?.preview?.preview_digest, props.locked, props.canMutate, props.uncertain, props.isCurrent]);

  async function load() {
    const source = latest.current; if (pending.current || source.locked || !current()) return;
    const request: Request = { id: ++epoch.current, kind: 'LOAD', client: source.client, runId: source.run?.id, controller: new AbortController() };
    pending.current = request; setLoading(true); setError(''); clearCapabilities();
    try {
      const value = await source.read(() => source.client.modelCapabilities(request.controller.signal));
      if (valid(request) && !latest.current.locked) { capabilitiesRef.current = value; setCapabilities(value); }
    } catch (value) {
      if (valid(request)) {
        setError(apiErrorView(value, '模型能力读取失败。请核对当前项目权限。').message);
        if (value instanceof ApiError && [401, 403, 404].includes(value.status)) unavailable();
      }
    } finally { finish(request); }
  }
  function chooseRoute(value: string) {
    const state = snapshot();
    if (state.disabled || state.execution || latest.current.uncertain || value && !capabilitiesRef.current?.routes.some(route => route.route_id === value && route.available)) return;
    choice.current = { routeId: value, allowSynthetic: false }; setRouteId(value); setAllowSynthetic(false); clearConsent();
  }
  function chooseSynthetic(value: boolean) {
    const state = snapshot();
    if (state.disabled || state.execution || latest.current.uncertain || !state.route?.synthetic) return;
    choice.current.allowSynthetic = value; setAllowSynthetic(value); clearConsent();
  }
  function reviewPreview(value: boolean) {
    const state = snapshot(), key = value && state.canConfirm ? state.confirmationKey : undefined;
    consentRef.current = key; setConsent(key);
  }
  async function action(kind: GraphModelAction) {
    const source = latest.current, state = snapshot();
    if (!source.run || pending.current || !current() || state.disabled || kind === 'preview' && !state.canPreview
      || kind === 'dispatch' && !state.canDispatch || kind === 'refresh' && !state.canRefresh) return;
    const request: Request = { id: ++epoch.current, kind: 'ACTION', client: source.client, runId: source.run.id, controller: new AbortController() };
    const evidence = kind === 'preview' ? { route_id: state.route!.route_id, allow_synthetic: choice.current.allowSynthetic }
      : kind === 'dispatch' ? { reviewed_preview_digest: state.preview!.preview_digest,
        ...(capabilitiesRef.current?.result_storage ? { archive_result: true as const } : {}) } : undefined;
    pending.current = request; setLoading(true); setError(''); clearConsent();
    try { await source.perform(kind, evidence); }
    catch (value) {
      if (valid(request)) {
        setError(apiErrorView(value, '模型操作回执需要核对。请读取当前运行，不会自动重复调用。').message);
        if (value instanceof ApiError && [401, 403, 404].includes(value.status)) unavailable();
      }
    } finally { finish(request); }
  }
  const state = snapshot();
  const visible = current();
  return { ...state, capabilities: visible ? capabilities : undefined, routeId: visible ? routeId : '', allowSynthetic: visible && allowSynthetic,
    run: visible ? props.run : undefined,
    model: visible ? state.model : undefined, preview: visible ? state.preview : null,
    execution: visible ? state.execution : undefined, route: visible ? state.route : undefined, loading, error,
    reviewed: !!state.confirmationKey && consent === state.confirmationKey,
    canRead: !props.locked && !loading && current(), current, load, chooseRoute, chooseSynthetic, reviewPreview, action };
}
export type StudioGraphModelExecutionController = ReturnType<typeof useStudioGraphModelExecutionController>;
