import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView, type Asset } from '../api';
import type { StudioAsset, StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphRecord } from './studioGraphTypes';
import { GRAPH_IMAGE_OPERATIONS, GRAPH_MEDIA_OPERATIONS, type GraphImageOperation, type GraphMediaOperation } from './studioGraphTypes';
import { blankGraph, connectionIssue, graphCatalogForSchema, graphId, imageGraphDefinitions, retainsSavedAssetBindings } from './graphDraft';
import { useStudioGraphTimelineEditor } from './useStudioGraphTimelineEditor';

export type StudioGraphEditorSelection = { graphId?: string; runId?: string };
export type StudioGraphEditorProps = {
  active: boolean; denied: boolean; identity: string; client: StudioClient; canMutate: boolean; canReview: boolean;
  busy: boolean; externalDirty: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  requestedGraphId?: string; requestedRunId?: string;
  onSelectionChange?: (selection: StudioGraphEditorSelection) => void;
  /** Synchronous parent activity fence, before React has rendered busy=true. */
  isBusy?: () => boolean;
};
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const candidateKey = (value?: StudioGraphRecord) => value && JSON.stringify([value.id, value.version, value.definition_digest, value.execution_digest]);

/** Original graph editing authority and async guards, independent of its visual skin. */
export function useStudioGraphEditorController({ active, denied, identity, client, canMutate, busy, externalDirty, isCurrent, read, mutate, requestedGraphId, onSelectionChange, isBusy }: StudioGraphEditorProps) {
  const [catalog, setCatalog] = useState<StudioGraphCatalog>(), [records, setRecords] = useState<StudioGraphRecord[]>([]), [base, setBase] = useState<StudioGraphRecord>();
  const [draft, setDraft] = useState<StudioGraphDefinition>(blankGraph), [selected, setSelected] = useState<string[]>([]);
  const [past, setPast] = useState<StudioGraphDefinition[]>([]), [future, setFuture] = useState<StudioGraphDefinition[]>([]);
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [blocked, setBlocked] = useState(false);
  const [candidate, setCandidate] = useState<StudioGraphRecord>(), [replaceConsent, setReplaceConsent] = useState<string>(), [checking, setChecking] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<() => void>(), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [kind, setKind] = useState<StudioGraphDefinitionId>('text_input'), [sourcePort, setSourcePort] = useState(''), [targetPort, setTargetPort] = useState('');
  const [mediaSchemaConsent, setMediaSchemaConsent] = useState(false);
  const [imageSchemaConsent, setImageSchemaConsent] = useState('');
  const [executionDirty, setExecutionDirty] = useState(false);
  const [assets, setAssets] = useState<StudioAsset[]>([]), [assetChoice, setAssetChoice] = useState(''), [assetLoading, setAssetLoading] = useState(false), [preview, setPreview] = useState<StudioAsset>();
  const [previewState, setPreviewState] = useState<'READING' | 'CURRENT' | 'STALE' | 'UNAVAILABLE'>(), [previewRequest, setPreviewRequest] = useState(0);
  const alive = useRef(true), selectedEpoch = useRef(0), catalogEpoch = useRef(0), assetEpoch = useRef(0), saving = useRef(false);
  const candidateEpoch = useRef(0), candidateRequest = useRef<AbortController>();
  const draftRef = useRef(draft); draftRef.current = draft;
  const baseRef = useRef(base); baseRef.current = base;
  const createRequest = useRef(graphId('graph'));
  const current = useCallback(() => alive.current && isCurrent(), [isCurrent]);
  const locked = () => busy || saving.current || !!isBusy?.();
  const editable = !!catalog && canMutate && !denied && !busy && !externalDirty && !executionDirty && !blocked && base?.can_edit !== false && current();
  const node = draft.nodes.find(row => row.id === selected[0]);
  const timelineEditor = useStudioGraphTimelineEditor({ client: client.graphs, node, editable, identity, isCurrent: current, isBusy: locked, read,
    update: parameters => { const selectedNode = draftRef.current.nodes.find(row => row.id === selected[0]); if (selectedNode?.definition_id !== 'timeline_export') return;
      change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === selectedNode.id ? { ...row, parameters } : row) }); } });
  const dirty = !same(draft, base?.definition || blankGraph()) || timelineEditor.formDirty;
  const replaceConfirmed = !!candidate && replaceConsent === candidateKey(candidate);
  const imageSchemaConfirmed = imageSchemaConsent !== '' && imageSchemaConsent === JSON.stringify(draft);
  const confirmImageSchema = (value: boolean) => { if (editable && current() && !locked()) setImageSchemaConsent(value ? JSON.stringify(draftRef.current) : ''); };
  const setReplaceConfirmed = (value: boolean) => { setReplaceConsent(value && current() && !locked() && !externalDirty && !checking ? candidateKey(candidate) : undefined); };
  const invalidateCandidate = useCallback(() => { candidateEpoch.current++; candidateRequest.current?.abort(); setCandidate(undefined); setReplaceConsent(undefined); setChecking(false); }, []);
  const protectedNodes = base?.definition.nodes.filter(node => node.definition_id === 'asset_reference').map(node => node.id) || [];

  const restoreRequest = useRef<string>();
  const reportSelection = useRef(onSelectionChange); reportSelection.current = onSelectionChange;
  const reportRunSelection = useCallback((runId?: string) => {
    if (current()) reportSelection.current?.({ graphId: baseRef.current?.id, runId });
  }, [current]);
  const accept = useCallback((record: StudioGraphRecord, restored = false) => {
    timelineEditor.resetForm();
    setMediaSchemaConsent(false);
    setImageSchemaConsent('');
    selectedEpoch.current++; invalidateCandidate(); setBase(record); setDraft(structuredClone(record.definition)); setPast([]); setFuture([]); setSelected([]); setBlocked(false); setSourcePort(''); setTargetPort('');
    setRecords(rows => [...rows.filter(row => row.id !== record.id), record]); createRequest.current = graphId('graph');
    if (!restored) reportSelection.current?.({ graphId: record.id });
  }, [invalidateCandidate]);
  const discard = useCallback(() => { if (!current() || busy || saving.current || isBusy?.() || executionDirty) return; timelineEditor.clearForm(); selectedEpoch.current++; invalidateCandidate(); setDraft(structuredClone(baseRef.current?.definition || blankGraph())); setPast([]); setFuture([]); setBlocked(false); setPendingNavigation(undefined); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); }, [current, busy, isBusy, invalidateCandidate, executionDirty, timelineEditor.clearForm]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; candidateEpoch.current++; candidateRequest.current?.abort(); }; }, []);
  useEffect(() => { setImageSchemaConsent(''); }, [identity, denied, canMutate, externalDirty, executionDirty]);
  useEffect(() => {
    if (denied) { timelineEditor.resetForm(); selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; invalidateCandidate(); setCatalog(undefined); setRecords([]); setBase(undefined); setDraft(blankGraph()); setPast([]); setFuture([]); setSelected([]); setAssets([]); setPreview(undefined); setPreviewState(undefined); setPendingNavigation(undefined); setMediaSchemaConsent(false); setExecutionDirty(false); setError(''); setNotice(''); }
  }, [denied, invalidateCandidate]);

  const load = useCallback(async () => {
    if (!current()) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    try {
      const [schema, values] = await read(() => Promise.all([client.graphs.catalog(), client.graphs.list()]));
      if (current() && epoch === catalogEpoch.current) { setCatalog(schema); setRecords(values.items); }
    } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '创作图目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }, [client, current, read]);
  useEffect(() => { if (active && !denied && !catalog) void load(); }, [active, denied, catalog, load]);
  async function loadImageCatalog() {
    if (!current() || locked() || externalDirty || executionDirty || !client.graphs.imageCatalog) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    const getCatalog = client.graphs.imageCatalog;
    try { const value = await read(() => getCatalog());
      if (current() && epoch === catalogEpoch.current) { setCatalog(value); setNotice('已读取图片节点目录；当前图格式、输入与运行保持，尚未升级或执行。'); }
    } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '图片节点目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }

  const change = useCallback((next: StudioGraphDefinition, record = true) => {
    if (!editable || !current() || saving.current || isBusy?.()) return;
    if (!retainsSavedAssetBindings(baseRef.current?.definition.nodes || [], next.nodes)) { setError('已保存资产引用暂不能移除或重新绑定；可移动或禁用节点。原资产不会被删除。'); return; }
    if (same(draftRef.current, next)) return;
    if (record) { setPast(rows => [...rows.slice(-49), structuredClone(draftRef.current)]); setFuture([]); }
    draftRef.current = next; setDraft(next); setError(''); setNotice(''); invalidateCandidate();
  }, [editable, current, isBusy, invalidateCandidate]);
  function navigate(work: () => void) {
    if (!current() || locked() || externalDirty || executionDirty) return;
    if (dirty || blocked) { setDiscardConfirmed(false); setPendingNavigation(() => work); return; }
    work();
  }
  async function open(id: string) {
    if (!current() || locked() || externalDirty || executionDirty) return;
    const epoch = ++selectedEpoch.current; setError('');
    try { const result = await mutate(async () => {
      const value = await client.graphs.get(id);
      if (value.definition.schema_version === 4 && !client.graphs.imageCatalog) throw new Error('图片节点目录当前不可用，请重新打开工作区。');
      const imageCatalog = value.definition.schema_version === 4 ? await client.graphs.imageCatalog!() : undefined;
      return { value, imageCatalog };
    }); if (current() && epoch === selectedEpoch.current) { if (result.imageCatalog) { catalogEpoch.current++; setCatalog(result.imageCatalog); } accept(result.value); } }
    catch (value) { if (current() && epoch === selectedEpoch.current) setError(apiErrorView(value, '创作图读取失败，当前草稿未替换。').message); }
  }
  function newGraph() { if (!current() || locked() || externalDirty || executionDirty) return; timelineEditor.clearForm(); selectedEpoch.current++; invalidateCandidate(); setBase(undefined); setDraft(blankGraph()); setSelected([]); setPast([]); setFuture([]); setBlocked(false); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); reportSelection.current?.({}); }
  function confirmNavigation() {
    if (!discardConfirmed || !pendingNavigation || !current() || locked() || externalDirty || executionDirty) return;
    const work = pendingNavigation; setPendingNavigation(undefined); setDiscardConfirmed(false); work();
  }
  function adoptCandidate() {
    if (!candidate || !replaceConfirmed || !current() || locked() || externalDirty || executionDirty || checking) return;
    accept(candidate); setReplaceConfirmed(false); setError(''); setNotice('已采用核对的图服务端版本，没有创建或执行运行。');
  }
  async function save(retry = false) {
    if ((!editable && !(retry && blocked && !base && canMutate && !busy && !externalDirty)) || timelineEditor.formDirty || executionDirty || locked() || !current() || !draft.title.trim()) return;
    saving.current = true; setError(''); const epoch = selectedEpoch.current, value = structuredClone(draftRef.current), original = base, request = createRequest.current;
    try {
      const saved = await mutate(() => original ? client.graphs.save(original.id, { expected_version: original.version, definition: value }) : client.graphs.create({ request_id: request, expected_version: 0, definition: value }));
      if (current() && epoch === selectedEpoch.current) { accept(saved); setNotice(`创作图已保存 · v${saved.version}。没有自动创建运行。`); }
    } catch (value) {
      if (current() && epoch === selectedEpoch.current) { setError(apiErrorView(value, '创作图未确认保存，输入已保留。').message); if (!(value instanceof ApiError) || value.status === 0 || value.status === 409 || value.status >= 500 || value.problem.code === 'STUDIO_RESPONSE_INVALID') setBlocked(true); }
    } finally { saving.current = false; }
  }
  async function checkServer() {
    if (locked() || !current()) return;
    candidateRequest.current?.abort(); const abort = new AbortController(); candidateRequest.current = abort;
    const source = base, epoch = selectedEpoch.current, request = ++candidateEpoch.current; setError(''); setReplaceConsent(undefined); setCandidate(undefined); setChecking(true);
    const valid = () => current() && epoch === selectedEpoch.current && request === candidateEpoch.current && !abort.signal.aborted;
    try {
      if (!source) { await load(); if (valid()) setNotice('已读取保存目录。创建回执不确定时，可明确使用同一请求重试，不按标题猜测或自动重复创建。'); }
      else {
        const value = await read(() => client.graphs.get(source.id, abort.signal));
        if (value.version < source.version || value.version === source.version && (value.definition_digest !== source.definition_digest || value.execution_digest !== source.execution_digest)) throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '图服务端版本或摘要与已读取版本不一致，请重新核对。' });
        if (valid()) { setReplaceConsent(undefined); setCandidate(value); }
      }
    } catch (value) { if (valid()) setError(apiErrorView(value, '服务端版本核对失败。').message); }
    finally { if (request === candidateEpoch.current) { candidateRequest.current = undefined; if (current()) setChecking(false); } }
  }
  async function loadAssets() {
    if (assetLoading || !current()) return;
    const epoch = ++assetEpoch.current; setAssetLoading(true); setError('');
    try { const result = await read(() => client.assets()); if (current() && epoch === assetEpoch.current) { setAssets(result.items.filter(row => ['image', 'video', 'audio'].includes(row.kind) && !row.deleted_at)); setAssetChoice(''); } }
    catch (value) { if (current() && epoch === assetEpoch.current) setError(apiErrorView(value, '原资产目录读取失败。').message); }
    finally { if (current() && epoch === assetEpoch.current) setAssetLoading(false); }
  }
  function addNode() {
    const spec = catalog?.definitions.find(row => row.id === kind), asset = assets.find(row => row.id === assetChoice);
    const media = kind === 'media_generate' || kind === 'media_review' || kind === 'timeline_export';
    const image = draft.schema_version === 4;
    const schemaRequired = media || kind === 'asset_reference' && catalog?.capabilities.media_execution;
    const limit = draft.schema_version >= 3 ? catalog?.media_limits?.nodes || 24 : catalog!.limits.nodes;
    if (!editable || !spec || draft.nodes.length >= limit || schemaRequired && draft.schema_version !== 3 && !image
      || image && !imageGraphDefinitions.some(value => value === kind)
      || ['media_generate', 'timeline_export'].includes(kind) && draft.nodes.filter(row => ['media_generate', 'timeline_export'].includes(row.definition_id)).length >= 4
      || kind === 'image_generate' && draft.nodes.filter(row => row.definition_id === 'image_generate').length >= 4
      || kind === 'asset_reference' && !asset || kind === 'timeline_export' && !timelineEditor.chosen) return;
    if (image && kind === 'asset_reference' && asset?.kind !== 'image') { setError('图片图只接受图片素材引用。'); return; }
    const node = { id: graphId(), definition_id: kind, definition_version: 1 as const, enabled: true, position: { x: 24 + draft.nodes.length % 4 * 280, y: 24 + Math.floor(draft.nodes.length / 4) * 180 },
      parameters: kind === 'asset_reference' ? { asset_id: asset!.id, version: asset!.version, digest: asset!.sha256, kind: asset!.kind as 'image' | 'video' | 'audio' }
        : kind === 'media_generate' ? { operation_id: 'm5.image.t2i' as const, provider_id: '', model_id: '', prompt: '', parameters: {}, allow_cloud: false, license_note: '' }
        : kind === 'image_generate' ? { operation_id: 'm5.image.t2i' as const, provider_id: '', model_id: '', parameters: {}, allow_cloud: false, license_note: '' }
        : kind === 'timeline_export' ? { timeline_snapshot: { id: timelineEditor.chosen!.id, version: timelineEditor.chosen!.version, digest: timelineEditor.chosen!.timeline_digest },
          edit_operations: [], source_bindings: [], export_profile: { preset: 'REVIEW_MP4' as const } }
        : structuredClone(spec.default_parameters || {}) };
    change({ ...draft, schema_version: kind === 'text_generate' && draft.schema_version === 1 ? 2 : draft.schema_version, nodes: [...draft.nodes, node] }); setSelected([node.id]);
  }
  function upgradeMediaSchema() {
    if (!editable || !current() || locked() || !mediaSchemaConsent || !catalog?.capabilities.media_execution || draft.schema_version >= 3) return;
    change({ ...draft, schema_version: 3 }); setMediaSchemaConsent(false);
  }
  function upgradeImageSchema() {
    if (!editable || !current() || locked() || !imageSchemaConfirmed || !catalog?.capabilities.image_graph || draft.schema_version === 4) return;
    if (draft.nodes.some(node => !imageGraphDefinitions.some(kind => kind === node.definition_id)
      || node.definition_id === 'asset_reference' && node.parameters.kind !== 'image')) {
      setError('当前图含图片图 v4 不支持的节点或非图片来源。请保留原图，并明确新建空图使用图片节点；不会移除原节点。'); return;
    }
    change({ ...draftRef.current, schema_version: 4 }); setImageSchemaConsent(''); setKind('image_reference');
  }
  function updateMediaField(key: 'operation_id' | 'provider_id' | 'model_id' | 'prompt' | 'allow_cloud' | 'license_note', value: string | boolean) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || !['media_generate', 'image_generate'].includes(target.definition_id)) return;
    if (target.definition_id === 'image_generate' && key === 'prompt') return;
    if (key === 'operation_id' && !(target.definition_id === 'image_generate' ? GRAPH_IMAGE_OPERATIONS.some(operation => operation === value) : GRAPH_MEDIA_OPERATIONS.some(operation => operation === value))
      || (key === 'allow_cloud' ? typeof value !== 'boolean' : typeof value !== 'string')) return;
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, [key]: value } } : row) });
  }
  function updateMediaParameter(key: string, value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]), allowed = target?.parameters.operation_id && graphMediaParameterNames(target.parameters.operation_id, target.definition_id === 'image_generate');
    if (!target || !['media_generate', 'image_generate'].includes(target.definition_id) || !allowed?.includes(key)) return;
    const next = { ...target.parameters.parameters };
    if (value === '') delete next[key];
    else if (['negative_prompt', 'voice_id', 'size', 'quality'].includes(key)) next[key] = value;
    else { const parsed = Number(value); if (!Number.isFinite(parsed) || !['speech_rate', 'denoising_strength'].includes(key) && !Number.isSafeInteger(parsed)) return; next[key] = parsed; }
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, parameters: next } } : row) });
  }
  function clearUnsupportedMediaParameters() {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || !['media_generate', 'image_generate'].includes(target.definition_id) || !target.parameters.operation_id) return;
    const allowed = graphMediaParameterNames(target.parameters.operation_id, target.definition_id === 'image_generate'), next = Object.fromEntries(Object.entries(target.parameters.parameters || {}).filter(([key]) => allowed.includes(key)));
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, parameters: next } } : row) });
  }
  function clearMediaTrimInputs() {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || target.definition_id !== 'media_generate' || target.parameters.operation_id !== 'm8.audio.trim') return;
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, provider_id: null, model_id: null, prompt: '', allow_cloud: false } } : row) });
  }
  function updateImagePrompt(value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || target.definition_id !== 'image_prompt' || value.length > 8000) return;
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { prompt: value } } : row) });
  }
  function updateImageReference(port: string, value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || target.definition_id !== 'image_reference' || !/^source_[1-5]$/.test(port)) return;
    const bindings = (target.parameters.bindings || []).filter(binding => binding.port !== port);
    if (value !== '') {
      const weight = Number(value); if (!Number.isFinite(weight) || weight <= 0 || weight > 1) return;
      bindings.push({ port: port as NonNullable<typeof target.parameters.bindings>[number]['port'], weight });
    }
    bindings.sort((left, right) => left.port.localeCompare(right.port));
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { bindings } } : row) });
  }
  function connect() {
    if (!editable || !sourcePort || !targetPort || draft.edges.length >= catalog!.limits.edges) return;
    const [source_node_id, source_port] = JSON.parse(sourcePort), [target_node_id, target_port] = JSON.parse(targetPort);
    const edge = { id: graphId('edge'), source_node_id, source_port, target_node_id, target_port }, problem = connectionIssue(draft, catalog!.definitions, edge);
    if (problem) { setError(problem); return; }
    change({ ...draft, edges: [...draft.edges, edge] }); setSourcePort(''); setTargetPort('');
  }
  function travel(redo: boolean) {
    if (!editable || locked() || !current()) return;
    const from = redo ? future : past, value = redo ? from[0] : from.at(-1); if (!value) return;
    if (!retainsSavedAssetBindings(base?.definition.nodes || [], value.nodes)) { setError('撤销不能移除已经保存的资产绑定。'); return; }
    if (redo) { setPast(rows => [...rows.slice(-49), structuredClone(draft)]); setFuture(rows => rows.slice(1)); }
    else { setFuture(rows => [structuredClone(draft), ...rows].slice(0, 50)); setPast(rows => rows.slice(0, -1)); }
    invalidateCandidate(); draftRef.current = structuredClone(value); setDraft(draftRef.current); setSourcePort(''); setTargetPort('');
  }
  const downloadPreviewAsset = useCallback((asset: Asset) => read(() => client.download(asset.id)), [read, client]);
  const refreshPreview = () => { if (current() && !locked()) setPreviewRequest(value => value + 1); };
  useEffect(() => {
    let valid = true; setPreview(undefined); setPreviewState(undefined);
    if (!active || !node || node.definition_id !== 'asset_reference' || !node.parameters.asset_id || denied) return;
    setPreviewState('READING'); const abort = new AbortController();
    void read(() => client.asset(node.parameters.asset_id!, abort.signal)).then(value => {
      if (!valid || !current()) return;
      if (value.version !== node.parameters.version || value.sha256 !== node.parameters.digest || value.kind !== node.parameters.kind || value.deleted_at) {
        setPreviewState('STALE'); setNotice('引用资产的当前版本、摘要或类型与图中绑定不同。未替换绑定，也未将当前资产当作原版本预览。');
      } else { setPreview(value); setPreviewState('CURRENT'); }
    }).catch(value => { if (valid && current() && !abort.signal.aborted) { setPreviewState('UNAVAILABLE'); setNotice(apiErrorView(value, '引用资产当前不可预览。').message); } });
    return () => { valid = false; abort.abort(); };
  }, [active, denied, node?.id, node?.parameters.asset_id, node?.parameters.version, node?.parameters.digest, node?.parameters.kind, previewRequest, client, read, current]);

  // A recovery hint is only a read target. Never save, create, execute or guess by title.
  useEffect(() => {
    if (!active || denied || !requestedGraphId || !catalog || busy || externalDirty || executionDirty || dirty || blocked || !current()) return;
    const recoveryKey = JSON.stringify([identity, requestedGraphId]);
    if (restoreRequest.current === recoveryKey) return;
    restoreRequest.current = recoveryKey;
    if (base?.id === requestedGraphId) return;
    const epoch = ++selectedEpoch.current, originalDraft = structuredClone(draftRef.current);
    let valid = true, settled = false; const abort = new AbortController(); setError('');
    void read(async () => {
      const value = await client.graphs.get(requestedGraphId, abort.signal);
      if (value.definition.schema_version === 4 && !client.graphs.imageCatalog) throw new Error('图片节点目录当前不可用，请重新打开工作区。');
      const imageCatalog = value.definition.schema_version === 4 ? await client.graphs.imageCatalog!(abort.signal) : undefined;
      return { value, imageCatalog };
    }).then(({ value, imageCatalog }) => {
      if (valid && current() && epoch === selectedEpoch.current) {
        settled = true;
        if (same(draftRef.current, originalDraft) && !saving.current) { if (imageCatalog) { catalogEpoch.current++; setCatalog(imageCatalog); } accept(value, true); }
      }
    }).catch(value => {
      if (valid && !abort.signal.aborted && current() && epoch === selectedEpoch.current) {
        settled = true;
        setError(apiErrorView(value, '上次创作图当前不可读；当前草稿未替换。').message);
        setNotice('上次图未恢复。可从已保存目录明确选择，不会自动重建或执行。');
      }
    });
    return () => {
      valid = false; abort.abort();
      if (!settled && restoreRequest.current === recoveryKey) restoreRequest.current = undefined;
    };
  }, [active, denied, requestedGraphId, catalog, busy, externalDirty, executionDirty, dirty, blocked, current, identity, base?.id, read, client, accept]);

  // Retired owners expose only text changed locally, never saved identities, bindings or receipts.
  const retired = !current();
  const localTextFields = { text: '作者输入文本', result: '手工处理结果', note: '可选导演备注', instruction: '本地模型写作指令', prompt: '媒体提示词', license_note: '来源与授权说明' };
  const retainedText = retired ? draft.nodes.flatMap(node => {
    const saved = base?.definition.nodes.find(row => row.id === node.id);
    return Object.entries(localTextFields).flatMap(([key, label]) => {
      const value = node.parameters[key as keyof typeof localTextFields];
      return typeof value === 'string' && value !== saved?.parameters[key as keyof typeof localTextFields] ? [{ label, value }] : [];
    });
  }) : [];
  const retainedTitle = !base || draft.title !== base.definition.title ? draft.title : blankGraph().title;
  return {
    retired, retainedText, retainedTitle,
    catalog: catalog ? { ...catalog, definitions: graphCatalogForSchema(catalog.definitions, draft.schema_version) } : undefined,
    records, base, draft, selected, past, future, loading, error, notice, blocked,
    candidate, replaceConfirmed, checking, pendingNavigation, discardConfirmed, kind, sourcePort, targetPort,
    assets, assetChoice, assetLoading, preview, previewState, refreshPreview, downloadPreviewAsset, current, dirty, editable, protectedNodes, node,
    discard, load, loadImageCatalog, change, navigate, open, newGraph, save, checkServer, loadAssets, addNode, connect, travel, confirmNavigation, adoptCandidate,
    setReplaceConfirmed, setCandidate, setDiscardConfirmed, setPendingNavigation, setKind, setAssetChoice,
    setSourcePort, setTargetPort, setSelected, reportRunSelection, mediaSchemaConsent, setMediaSchemaConsent, upgradeMediaSchema, executionDirty, setExecutionDirty,
    imageSchemaConfirmed, confirmImageSchema, upgradeImageSchema, updateImagePrompt, updateImageReference,
    updateMediaField, updateMediaParameter, clearUnsupportedMediaParameters, clearMediaTrimInputs, timelineEditor,
  };
}
export type StudioGraphEditorController = ReturnType<typeof useStudioGraphEditorController>;
export const GRAPH_MEDIA_PARAMETER_LABELS: Record<string, string> = { width: '宽度', height: '高度', steps: '采样步数', seed: '种子', negative_prompt: '负向提示词', size: '图片规格', quality: '图片质量',
  denoising_strength: '重绘强度（大于 0 至 1）',
  duration_seconds: '时长（秒）', frame_rate: '帧率', voice_id: '语音标识', speech_rate: '语速', in_ms: '来源起点（毫秒）', out_ms: '来源终点（毫秒）' };
export function graphMediaParameterNames(operation: GraphMediaOperation | GraphImageOperation, image = false): string[] {
  const imageParameters = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'];
  if (image && ['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].includes(operation)) return ['steps', 'seed', 'negative_prompt', 'denoising_strength'];
  return ({ 'm5.image.t2i': imageParameters, 'm5.image.i2i': imageParameters, 'm5.image.reference': imageParameters, 'm5.image.inpaint': imageParameters,
    'm7.video.t2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'], 'm7.video.i2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
    'm7.video.v2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'], 'm8.audio.speech': ['voice_id', 'speech_rate'],
    'm8.audio.music': ['duration_seconds', 'seed'], 'm8.audio.effects': ['duration_seconds', 'seed'], 'm8.audio.trim': ['in_ms', 'out_ms'] } as Record<GraphMediaOperation | GraphImageOperation, string[]>)[operation];
}
