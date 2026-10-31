import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { uniqueGraphProviders } from './graphProviderChoices';
import { graphSelectedVideoBinding, selectedVideoBindingNodes, type SelectedVideoBindingPreview } from './graphSelectedVideoBinding';
import type { StudioGraphCatalog, StudioGraphDefinition } from './studioGraphTypes';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';

type Props = {
  definition: StudioGraphDefinition; selected: string[]; catalog?: StudioGraphCatalog;
  source?: Pick<StudioProductionClient, 'providers'>; scope: object; generation: number;
  editable: boolean; current: () => boolean; locked: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  apply: (definition: StudioGraphDefinition) => boolean;
};
type Preview = { result: SelectedVideoBindingPreview; generation: number; authority: object;
  source: string; provider: string; next: string };

/** Authoring only; never delegates consent to the single-node picker. */
export function useGraphSelectedVideoBinding(props: Props) {
  const latest = useRef(props); latest.current = props;
  const reader = props.source?.providers;
  const values = [props.scope, props.source, reader, props.generation];
  const lifetime = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, lifetime.current.values[index]))) lifetime.current = { values, token: {} };
  const token = lifetime.current.token;
  const authorityValues = [token, props.editable, props.locked()];
  const authority = useRef({ values: authorityValues, token: {} });
  if (authorityValues.some((value, index) => !Object.is(value, authority.current.values[index]))) authority.current = { values: authorityValues, token: {} };
  const authorityToken = authority.current.token;
  const alive = useRef(true), actionEpoch = useRef(0), readEpoch = useRef(0), request = useRef<AbortController>();
  const [, setRevision] = useState(0);
  const [catalog, setCatalog] = useState<{ token: object; rows: ProductionProvider[] }>();
  const catalogRef = useRef(catalog); catalogRef.current = catalog;
  const [choice, setChoice] = useState(''), choiceRef = useRef('');
  const [preview, setPreview] = useState<Preview>(), previewRef = useRef<Preview>();
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const reset = useCallback(() => {
    actionEpoch.current++; setRevision(actionEpoch.current); readEpoch.current++; request.current?.abort(); request.current = undefined;
    catalogRef.current = undefined; setCatalog(undefined); choiceRef.current = ''; setChoice('');
    previewRef.current = undefined; setPreview(undefined); setLoading(false); setError('');
  }, []);
  useLayoutEffect(reset, [token, reset]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; readEpoch.current++; request.current?.abort(); }; }, []);
  const inScope = () => alive.current && token === lifetime.current.token && reader === latest.current.source?.providers && latest.current.current();
  let selectionError = '';
  try { selectedVideoBindingNodes(props.definition, props.selected); }
  catch (reason) { selectionError = reason instanceof Error ? reason.message : '请选择视频生成节点。'; }
  const usable = () => inScope() && latest.current.editable && !latest.current.locked();
  const canRead = usable() && !selectionError && !!props.source && !!props.catalog?.capabilities.video_graph;
  const visibleCatalog = inScope() && catalog?.token === token ? catalog : undefined;
  const operation = props.definition.nodes.find(node => node.id === props.selected[0])?.parameters.operation_id;
  const rows = visibleCatalog?.rows.filter(row => row.local === true && row.readiness === 'CONFIGURED_NOT_VERIFIED' && row.operation_id === operation) ?? [];
  const acceptedProvider = () => catalogRef.current?.token === token
    ? catalogRef.current.rows.find(row => mediaProviderKey(row) === choiceRef.current && row.local === true
      && row.readiness === 'CONFIGURED_NOT_VERIFIED' && row.operation_id === operation) : undefined;
  const capturedEpoch = actionEpoch.current;
  const interactionCurrent = () => capturedEpoch === actionEpoch.current && inScope() && authorityToken === authority.current.token;
  async function load() {
    if (!interactionCurrent() || !canRead || !usable() || request.current) return;
    actionEpoch.current++; const id = ++readEpoch.current, controller = new AbortController(), captured = latest.current;
    request.current = controller; catalogRef.current = undefined; setCatalog(undefined);
    choiceRef.current = ''; setChoice(''); previewRef.current = undefined; setPreview(undefined); setLoading(true); setError('');
    // The read envelope may toggle busy; owner/selection/draft/permission transitions still retire it.
    const valid = () => inScope() && id === readEpoch.current && !controller.signal.aborted;
    try {
      const values = await captured.read(() => captured.source!.providers(controller.signal));
      if (!valid()) return;
      const unique = uniqueGraphProviders(values), accepted = { token, rows: structuredClone(unique) };
      catalogRef.current = accepted; setCatalog(accepted);
      if (unique.length !== values.length) setError('重复或含糊的服务配置已隐藏；请核对原服务配置。');
    } catch (reason) { if (valid()) setError(reason instanceof Error ? reason.message : '本地服务配置读取失败。'); }
    finally { if (valid()) { request.current = undefined; setLoading(false); } }
  }
  function choose(key: string) {
    if (!interactionCurrent() || !usable() || request.current || !visibleCatalog) return;
    if (key && !rows.some(row => mediaProviderKey(row) === key)) return;
    if (key === choiceRef.current) return;
    actionEpoch.current++; choiceRef.current = key; setChoice(key); previewRef.current = undefined; setPreview(undefined); setError('');
  }
  function prepare() {
    if (!interactionCurrent() || !usable() || request.current || !props.catalog) return;
    const provider = acceptedProvider(); if (!provider) return;
    try {
      const result = graphSelectedVideoBinding(props.definition, props.selected, props.catalog, provider);
      const value = { result, generation: ++actionEpoch.current, authority: authorityToken,
        source: JSON.stringify(props.definition), provider: JSON.stringify(provider), next: JSON.stringify(result.definition) };
      previewRef.current = value; setPreview(value); setError('');
    } catch (reason) { previewRef.current = undefined; setPreview(undefined); setError(reason instanceof Error ? reason.message : '批量绑定预览失败。'); }
  }
  function apply() {
    const value = previewRef.current, provider = acceptedProvider();
    if (!interactionCurrent() || !usable() || request.current || !value || value !== preview || !provider || !props.catalog
      || value.generation !== actionEpoch.current || value.authority !== authority.current.token
      || value.source !== JSON.stringify(props.definition) || value.provider !== JSON.stringify(provider)) return false;
    try {
      const result = graphSelectedVideoBinding(props.definition, props.selected, props.catalog, provider);
      if (JSON.stringify(result.definition) !== value.next) return false;
      // Consume synchronously, before change(), including duplicate callbacks in one event.
      actionEpoch.current++; previewRef.current = undefined; setPreview(undefined);
      if (!latest.current.apply(result.definition)) { setError('当前草稿已改变，绑定未应用；请重新预览。'); return false; }
      setError(''); return true;
    } catch (reason) { previewRef.current = undefined; setPreview(undefined); setError(reason instanceof Error ? reason.message : '绑定未应用。'); return false; }
  }
  const visiblePreview = usable() && preview && preview === previewRef.current && preview.generation === actionEpoch.current
    && preview.authority === authority.current.token ? preview.result : undefined;
  function cancel() {
    if (!interactionCurrent()) return;
    actionEpoch.current++; setRevision(actionEpoch.current); previewRef.current = undefined; setPreview(undefined);
  }
  return { rows, choice: visibleCatalog ? choice : '', loading: inScope() && loading, error: inScope() ? error : '',
    selectionError, canRead, canChoose: canRead && !!visibleCatalog && !request.current,
    preview: visiblePreview, load, choose, prepare, apply, cancel };
}
