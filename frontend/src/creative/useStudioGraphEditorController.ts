import { buildGraphStarter, type GraphStarterKind } from './graphStarter';
import type { ReviewedDirectorCanvasHandoff } from './directorCanvasHandoff';
import { planningSourceFork, planningSourceReferences } from './graphPlanningFork';
import type { OpenStoryboardEditor } from './storyboardEditorHandoff';
import { checkedStudioGraphDraft } from './studioGraphClient';
import { graphSelectionCopy, type GraphSelectionCopy } from './graphSelectionCopy';
import { autoLayout } from '../canvasops/canvasOps';
import { clampGraphPosition } from './graphCanvasGeometry';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { StoryboardReceipt } from './studioStoryboardContract';
import { checkedPlanningSnapshot, productionGraphDefinitions, type PlanningSnapshot, type PlanningDocument } from './studioProductionGraphContract';
import { checkedImageReferenceMetadata } from './studioImageRuntimeContract';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView, type Asset } from '../api';
import type { ProductionProvider, StudioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import type { StudioAsset, StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphPosition, StudioGraphRecord } from './studioGraphTypes';
import { GRAPH_VIDEO_OPERATIONS, GRAPH_IMAGE_OPERATIONS, GRAPH_MEDIA_OPERATIONS, type GraphImageOperation, type GraphMediaOperation } from './studioGraphTypes';
import { blankGraph, connectionIssue, graphCatalogForSchema, graphId, imageGraphDefinitions, videoGraphDefinitions, retainsSavedAssetBindings } from './graphDraft';
import { useStudioGraphTimelineEditor } from './useStudioGraphTimelineEditor';
import { graphDraftBaselineMatches, graphDraftRecoverable, readStudioGraphLocalDraft, studioGraphDraftKey,
  type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';

type PositionedNodeRequest = { position: StudioGraphPosition; scope: object; restoreFocus: () => void };

export type StudioGraphEditorSelection = { graphId?: string; runId?: string };
export type StudioGraphEditorProps = {
  active: boolean; denied: boolean; identity: string; client: StudioClient; canMutate: boolean; canReview: boolean;
  directorSource?: GraphDirectorSource;
  onOpenModels?: () => void;
  onOpenStoryboard?: OpenStoryboardEditor;
  providerSource?: Pick<StudioProductionClient, 'providers'>;
  busy: boolean; externalDirty: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  requestedGraphId?: string; requestedRunId?: string;
  /** Supplied only after the original overview and actor identity are verified. */
  draftOwner?: StudioGraphDraftOwner;
  onSelectionChange?: (selection: StudioGraphEditorSelection) => void;
  /** Synchronous parent activity fence, before React has rendered busy=true. */
  isBusy?: () => boolean;
};
const same = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const candidateKey = (value?: StudioGraphRecord) => value && JSON.stringify([value.id, value.version, value.definition_digest, value.execution_digest]);

/** Original graph editing authority and async guards, independent of its visual skin. */
export function useStudioGraphEditorController({ active, denied, identity, client, providerSource, canMutate, busy, externalDirty, isCurrent, read, mutate, requestedGraphId, onSelectionChange, isBusy, draftOwner }: StudioGraphEditorProps) {
  const [catalog, setCatalog] = useState<StudioGraphCatalog>(), [records, setRecords] = useState<StudioGraphRecord[]>([]), [base, setBase] = useState<StudioGraphRecord>();
  const [draft, setDraft] = useState<StudioGraphDefinition>(blankGraph), [selected, setSelectedState] = useState<string[]>([]);
  const [copyPreview, setCopyPreview] = useState<{ identity: string; client: StudioClient; graph: string | undefined; epoch: number; source: string; catalog: StudioGraphCatalog; result: GraphSelectionCopy }>();
  // Session-local source snapshot owned by this controller, never persisted or transported.
  const [copySource, setCopySource] = useState<{ identity: string; client: StudioClient; record: StudioGraphRecord; selected: string[]; sourceEpoch: number }>();
  const [crossPreview, setCrossPreview] = useState<{ source: NonNullable<typeof copySource>; target: StudioGraphRecord; epoch: number; previewEpoch: number; draft: string; catalog: StudioGraphCatalog; result: GraphSelectionCopy }>();
  const copySourceEpoch = useRef(0), crossCopyEpoch = useRef(0);
  const [independentConsent, setIndependentConsent] = useState('');
  const planningForkConsumed = useRef<object>();
  const [independentOrigin, setIndependentOrigin] = useState<{ identity: string; client: StudioClient; id: string; title: string; version: number; references: StudioGraphRecord['reference_states'] }>();
  const [past, setPast] = useState<StudioGraphDefinition[]>([]), [future, setFuture] = useState<StudioGraphDefinition[]>([]);
  const [loading, setLoading] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [blocked, setBlocked] = useState(false);
  const [candidate, setCandidate] = useState<StudioGraphRecord>(), [replaceConsent, setReplaceConsent] = useState<string>(), [checking, setChecking] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<() => void>(), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [localRecovery, setLocalRecovery] = useState<StudioGraphLocalDraft>(), [recoveryBusy, setRecoveryBusy] = useState(false);
  const [draftStorageKey, setDraftStorageKey] = useState<string>(), [draftStorageNotice, setDraftStorageNotice] = useState('');
  const [draftSavedAt, setDraftSavedAt] = useState<string>();
  const [recoveryError, setRecoveryError] = useState('');
  const recoveryEpoch = useRef(0);
  const persistedDraftRaw = useRef<string | null>(null);
  const ownerKey = draftOwner ? studioGraphDraftKey(draftOwner) : undefined;
  const firstDraftOwner = useRef<string>();
  if (ownerKey && !firstDraftOwner.current) firstDraftOwner.current = ownerKey;
  const draftOwnerCurrent = !!ownerKey && ownerKey === firstDraftOwner.current;
  const [kind, setKind] = useState<StudioGraphDefinitionId>('text_input'), [sourcePort, setSourcePortState] = useState(''), [targetPort, setTargetPortState] = useState('');
  const [mediaSchemaConsent, setMediaSchemaConsent] = useState(false);
  const [videoSchemaConsent, setVideoSchemaConsent] = useState('');
  const [pendingVideoCatalog, setPendingVideoCatalog] = useState<StudioGraphCatalog>();
  const schemaCatalogs = useRef(new Map<number, StudioGraphCatalog>());
  const [shotParent, setShotParent] = useState(''), [shotChoice, setShotChoice] = useState(''), [shotReceipt, setShotReceipt] = useState<StoryboardReceipt>(), [shotLoading, setShotLoading] = useState(false); const shotEpoch = useRef(0);
  const [imageSchemaConsent, setImageSchemaConsent] = useState('');
  const [executionDirty, setExecutionDirty] = useState(false);
  const [assets, setAssets] = useState<StudioAsset[]>([]), [assetChoice, setAssetChoice] = useState(''), [assetLoading, setAssetLoading] = useState(false), [preview, setPreview] = useState<StudioAsset>();
  const [previewState, setPreviewState] = useState<'READING' | 'CURRENT' | 'STALE' | 'UNAVAILABLE'>(), [previewRequest, setPreviewRequest] = useState(0);
  const [planningDocuments, setPlanningDocuments] = useState<PlanningDocument[]>([]), [planningChoice, setPlanningChoice] = useState(''), [planningLoading, setPlanningLoading] = useState(false);
  const planningEpoch = useRef(0);
  const alive = useRef(true), selectedEpoch = useRef(0), catalogEpoch = useRef(0), assetEpoch = useRef(0), saving = useRef(false);
  const candidateEpoch = useRef(0), candidateRequest = useRef<AbortController>();
  const draftRef = useRef(draft); draftRef.current = draft;
  const baseRef = useRef(base); baseRef.current = base;
  const createRequest = useRef(graphId('graph'));
  const current = useCallback(() => alive.current && isCurrent(), [isCurrent]);
  const locked = () => busy || recoveryBusy || saving.current || !!isBusy?.();
  const editable = !!catalog && canMutate && !denied && !busy && !recoveryBusy && !externalDirty && !executionDirty && !blocked && base?.can_edit !== false && current();
  // A fresh token denotes an actual authority transition, including A → B → A.
  // Unrelated selection/status renders preserve it; callbacks also recheck live locks.
  const connectionAuthority = [identity, client, ownerKey, base, draft, catalog, active, denied, canMutate,
    busy, recoveryBusy, externalDirty, executionDirty, blocked, editable, current()];
  const connectionFence = useRef({ values: connectionAuthority, token: {} });
  if (connectionAuthority.some((value, index) => !Object.is(value, connectionFence.current.values[index]))) {
    connectionFence.current = { values: connectionAuthority, token: {} };
  }
  const connectionScope = connectionFence.current.token;
  const connectionLive = useRef({ current, locked });
  connectionLive.current = { current, locked };
  function connectionSelectionCurrent(scope: object): boolean {
    return scope === connectionFence.current.token && scope === connectionScope && active && editable
      && connectionLive.current.current() && !connectionLive.current.locked()
      && draftRef.current === draft && baseRef.current === base && !!catalog;
  }
  function selectConnectionPort(port: { nodeId: string; portId: string; direction: 'input' | 'output' }, scope: object) {
    if (!connectionSelectionCurrent(scope)) return;
    const node = draft.nodes.find(value => value.id === port.nodeId);
    const descriptor = node && graphCatalogForSchema(catalog!.definitions, draft.schema_version).find(value => value.id === node.definition_id);
    if (!(port.direction === 'output' ? descriptor?.outputs : descriptor?.inputs)?.some(value => value.id === port.portId)) return;
    (port.direction === 'output' ? setSourcePort : setTargetPort)(JSON.stringify([port.nodeId, port.portId]));
  }
  function stageConnection(source: { nodeId: string; portId: string; direction: 'input' | 'output' },
    target: { nodeId: string; portId: string; direction: 'input' | 'output' }, scope: object): boolean {
    if (!connectionSelectionCurrent(scope) || !catalog || source.direction !== 'output' || target.direction !== 'input') return false;
    const edge = { id: 'pending-connection', source_node_id: source.nodeId, source_port: source.portId,
      target_node_id: target.nodeId, target_port: target.portId };
    if (connectionIssue(draft, catalog.definitions, edge)) return false;
    setSourcePort(JSON.stringify([source.nodeId, source.portId]));
    setTargetPort(JSON.stringify([target.nodeId, target.portId]));
    return true;
  }
  const recoveryFence = useRef({ ownerKey, busy, externalDirty, executionDirty, canMutate });
  recoveryFence.current = { ownerKey, busy, externalDirty, executionDirty, canMutate };
  const node = draft.nodes.find(row => row.id === selected[0]);
  const providerPicker = useGraphProviderPicker({ source: providerSource, client, identity, active, denied,
    scope: JSON.stringify([base?.id, selectedEpoch.current, selected, node?.definition_id, node?.parameters.operation_id]),
    node, editable, current, locked, read,
    bind: row => { const target = draftRef.current.nodes.find(value => value.id === selected[0]);
      if (!target || target.parameters.operation_id !== row.operation_id) return;
      change({ ...draftRef.current, nodes: draftRef.current.nodes.map(value => value.id === target.id
        ? { ...value, parameters: { ...value.parameters, provider_id: row.provider_id, model_id: row.model_id, allow_cloud: false } } : value) }); },
  });
  const reviewedSelectionEpoch = useRef(0);
  const setSelected = (value: string[]) => { reviewedSelectionEpoch.current++; providerPicker.reset(); setSelectedState(value); };
  const setSourcePort = (value: string) => { reviewedSelectionEpoch.current++; setSourcePortState(value); };
  const setTargetPort = (value: string) => { reviewedSelectionEpoch.current++; setTargetPortState(value); };
  const timelineEditor = useStudioGraphTimelineEditor({ client: client.graphs, node, editable, identity, isCurrent: current, isBusy: locked, read,
    update: parameters => { const selectedNode = draftRef.current.nodes.find(row => row.id === selected[0]); if (selectedNode?.definition_id !== 'timeline_export') return;
      change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === selectedNode.id ? { ...row, parameters } : row) }); } });
  // A point is session intent, not a node command. Source choices remain editable;
  // each Add closure separately fences the exact current source-selection render.
  const [insertionGeneration, setInsertionGeneration] = useState(0);
  const insertionValues = [connectionScope, timelineEditor.formDirty, insertionGeneration];
  const insertionFence = useRef({ values: insertionValues, token: {} });
  if (insertionValues.some((value, index) => !Object.is(value, insertionFence.current.values[index]))) {
    insertionFence.current = { values: insertionValues, token: {} };
  }
  const insertionScope = insertionFence.current.token;
  const [insertion, setInsertion] = useState<PositionedNodeRequest>();
  const insertionRef = useRef<PositionedNodeRequest>();
  // Keep expired intent visible and disabled until explicitly dismissed/replaced;
  // never silently turn a positioned Add into the ordinary grid fallback.
  const positionedInsertion = insertion;
  const insertionExpired = !!insertion && (insertion.scope !== insertionScope || insertionRef.current !== insertion);
  function invalidatePositionedInsertion() {
    if (!insertionRef.current) return;
    insertionFence.current = { values: insertionFence.current.values, token: {} };
    setInsertionGeneration(value => value + 1);
  }
  const sourceValues = [kind, assets, assetChoice, planningDocuments, planningChoice, shotParent, shotReceipt, shotChoice,
    timelineEditor.choice, timelineEditor.chosen, assetLoading, planningLoading, shotLoading, timelineEditor.loading];
  const insertionSourceFence = useRef({ values: sourceValues, token: {} });
  if (sourceValues.some((value, index) => !Object.is(value, insertionSourceFence.current.values[index]))) {
    insertionSourceFence.current = { values: sourceValues, token: {} };
  }
  const insertionSourceToken = insertionSourceFence.current.token;
  function insertionCurrent(scope: object) {
    return scope === insertionScope && scope === insertionFence.current.token && active && editable
      && connectionLive.current.current() && !connectionLive.current.locked() && !timelineEditor.formDirty
      && draftRef.current === draft && baseRef.current === base;
  }
  function requestPositionedInsertion(position: StudioGraphPosition, scope: object, restoreFocus: () => void): boolean {
    if (!insertionCurrent(scope) || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return false;
    const request = { position: { x: clampGraphPosition(position.x), y: clampGraphPosition(position.y) }, scope, restoreFocus };
    insertionRef.current = request; setInsertion(request); return true;
  }
  function cancelPositionedInsertion(request: PositionedNodeRequest) {
    if (insertionRef.current !== request) return;
    insertionRef.current = undefined; setInsertion(undefined);
    if (connectionLive.current.current() && !connectionLive.current.locked()) request.restoreFocus();
  }
  // Separate from positioned insertion: reviewed plans never consume a stale canvas
  // point or connect to the selected ancestor. Every selection transition retires intent.
  const reviewedSelection = reviewedSelectionEpoch.current, reviewedNavigation = selectedEpoch.current;
  const reviewedValues = [insertionScope, reviewedSelection, reviewedNavigation, selected, sourcePort, targetPort];
  const reviewedFence = useRef({ values: reviewedValues, token: {} });
  if (reviewedValues.some((value, index) => !Object.is(value, reviewedFence.current.values[index]))) {
    reviewedFence.current = { values: reviewedValues, token: {} };
  }
  const reviewedScope = reviewedFence.current.token;
  // A read may toggle busy, but must not survive a different owner/target/edit
  // lifetime (including A → B → A). No server authorization is inferred here.
  const reviewedVerificationValues = [identity, client, ownerKey, base, draft, catalog, active, denied, canMutate,
    externalDirty, executionDirty, blocked, reviewedSelection, reviewedNavigation, selected, sourcePort, targetPort, timelineEditor.formDirty];
  const reviewedVerificationFence = useRef({ values: reviewedVerificationValues, token: {} });
  if (reviewedVerificationValues.some((value, index) => !Object.is(value, reviewedVerificationFence.current.values[index]))) {
    reviewedVerificationFence.current = { values: reviewedVerificationValues, token: {} };
  }
  const verificationScope = reviewedVerificationFence.current.token;
  const isVerificationCurrent = () => verificationScope === reviewedVerificationFence.current.token
    && reviewedNavigation === selectedEpoch.current && reviewedSelection === reviewedSelectionEpoch.current && draftRef.current === draft && baseRef.current === base
    && connectionLive.current.current();
  const reviewedDirectorHandoff: ReviewedDirectorCanvasHandoff = {
    scope: reviewedScope,
    verificationScope, isVerificationCurrent,
    available: insertionCurrent(insertionScope) && !insertion && !!catalog
      && graphCatalogForSchema(catalog.definitions, draft.schema_version).some(row => row.id === 'director_plan'),
    insert: (snapshot, scope) => {
      if (!isVerificationCurrent() || scope !== reviewedScope || scope !== reviewedFence.current.token || !insertionCurrent(insertionScope) || insertionRef.current) return false;
      let pin: PlanningSnapshot;
      try { pin = checkedPlanningSnapshot(snapshot); } catch { return false; }
      const before = draftRef.current;
      insertNode('director_plan', undefined, pin);
      return draftRef.current !== before;
    },
  };
  const dirty = !same(draft, base?.definition || blankGraph()) || timelineEditor.formDirty;
  const independentKey = JSON.stringify([identity, base?.id, base?.version, draft]);
  const independentConfirmed = independentConsent !== '' && independentConsent === independentKey;
  const historyFull = !!base?.capacity && base.capacity.history_used >= base.capacity.history_limit
    && draft.schema_version === base.definition.schema_version;
  const visibleIndependentOrigin = active && !denied && current() && independentOrigin?.identity === identity && independentOrigin.client === client ? independentOrigin : undefined;
  const confirmIndependentGraph = (checked: boolean) => { if (editable && current() && !locked()) setIndependentConsent(checked ? independentKey : ''); };
  function prepareIndependentGraph() {
    if (!active || !editable || !base || !independentConfirmed || !current() || locked() || checking || timelineEditor.formDirty || executionDirty || externalDirty) return;
    try { checkedStudioGraphDraft(draftRef.current); } catch (reason) { setError(apiErrorView(reason, '当前完整草稿未通过原图校验，尚未准备新图。').message); return; }
    const source = baseRef.current;
    if (!source || source !== base || independentConsent !== JSON.stringify([identity, source.id, source.version, draftRef.current])) return;
    stageIndependentGraph(structuredClone(draftRef.current), source,
      '已准备独立新图草稿，尚未写入。完整作者内容与原版本绑定保持；请明确保存，届时由原服务重新核对来源与容量。原图及历史未修改。');
  }
  function stageIndependentGraph(value: StudioGraphDefinition, source: StudioGraphRecord, message: string) {
    providerPicker.reset(); timelineEditor.clearForm(); selectedEpoch.current++; invalidateCandidate();
    setIndependentOrigin({ identity, client, id: source.id, title: source.definition.title, version: source.version, references: structuredClone(source.reference_states) });
    setIndependentConsent(''); setBase(undefined); setDraft(value); setSelected([]); setPast([]); setFuture([]); setBlocked(false);
    setSourcePort(''); setTargetPort(''); setPendingNavigation(undefined); createRequest.current = graphId('graph'); reportSelection.current?.({});
    setError(''); setNotice(message);
  }
  const planningForkReferences = (() => { try { return node ? planningSourceReferences(draft, node.id) : []; } catch { return []; } })();
  function preparePlanningGraphFork(document: PlanningDocument, scope: object, nodeIds?: readonly string[]): boolean {
    if (scope !== verificationScope || planningForkConsumed.current === scope || !isVerificationCurrent()
      || !connectionSelectionCurrent(connectionScope) || !base || !node || checking || timelineEditor.formDirty
      || base.reference_states.find(value => value.node_id === node.id)?.state !== 'STALE') return false;
    try {
      const value = planningSourceFork(draftRef.current, node.id, document, nodeIds);
      planningForkConsumed.current = scope;
      stageIndependentGraph(value, base, '已准备使用所选更新来源的独立草稿，尚未保存。原图、历史及其他引用保持不变；请核对依赖后明确保存。');
      return true;
    } catch (reason) { setError(apiErrorView(reason, '无法准备更新来源草稿，原图保持不变。').message); return false; }
  }

  const replaceConfirmed = !!candidate && replaceConsent === candidateKey(candidate);
  const videoSchemaConfirmed = videoSchemaConsent !== '' && videoSchemaConsent === JSON.stringify(draft);
  const confirmVideoSchema = (value: boolean) => { if (editable && current() && !locked()) setVideoSchemaConsent(value ? JSON.stringify(draftRef.current) : ''); };
  const imageSchemaConfirmed = imageSchemaConsent !== '' && imageSchemaConsent === JSON.stringify(draft);
  const confirmImageSchema = (value: boolean) => { if (editable && current() && !locked()) setImageSchemaConsent(value ? JSON.stringify(draftRef.current) : ''); };
  const setReplaceConfirmed = (value: boolean) => { setReplaceConsent(value && current() && !locked() && !externalDirty && !checking ? candidateKey(candidate) : undefined); };
  const invalidateCandidate = useCallback(() => { candidateEpoch.current++; candidateRequest.current?.abort(); setCandidate(undefined); setReplaceConsent(undefined); setChecking(false); }, []);
  const protectedNodes = base?.definition.nodes.filter(node => ['asset_reference', 'director_plan', 'storyboard_plan'].includes(node.definition_id)).map(node => node.id) || [];

  const restoreRequest = useRef<string>();
  const reportSelection = useRef(onSelectionChange); reportSelection.current = onSelectionChange;
  const reportRunSelection = useCallback((runId?: string) => {
    if (current()) reportSelection.current?.({ graphId: baseRef.current?.id, runId });
  }, [current]);
  const accept = useCallback((record: StudioGraphRecord, restored = false) => {
    timelineEditor.resetForm(); setIndependentConsent(''); setIndependentOrigin(undefined);
    setMediaSchemaConsent(false);
    setImageSchemaConsent('');
    selectedEpoch.current++; invalidateCandidate(); setBase(record); setDraft(structuredClone(record.definition)); setPast([]); setFuture([]); setSelected([]); setBlocked(false); setSourcePort(''); setTargetPort('');
    setRecords(rows => [...rows.filter(row => row.id !== record.id), record]); createRequest.current = graphId('graph');
    if (!restored) reportSelection.current?.({ graphId: record.id });
  }, [invalidateCandidate]);
  const discard = useCallback(() => { if (!current() || busy || saving.current || isBusy?.() || executionDirty) return; setIndependentConsent(''); setIndependentOrigin(undefined); providerPicker.reset(); timelineEditor.clearForm(); selectedEpoch.current++; invalidateCandidate(); setDraft(structuredClone(baseRef.current?.definition || blankGraph())); setPast([]); setFuture([]); setBlocked(false); setPendingNavigation(undefined); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); }, [current, busy, isBusy, invalidateCandidate, executionDirty, timelineEditor.clearForm]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; candidateEpoch.current++; candidateRequest.current?.abort(); }; }, []);
  useEffect(() => { shotEpoch.current++; setShotReceipt(undefined); setShotChoice(''); setShotParent(''); setVideoSchemaConsent(''); planningEpoch.current++; setPlanningDocuments([]); setPlanningChoice(''); setPlanningLoading(false); setImageSchemaConsent(''); }, [identity, denied, canMutate, externalDirty, executionDirty]);
  useEffect(() => {
    if (denied) { setIndependentConsent(''); setIndependentOrigin(undefined); recoveryEpoch.current++; setLocalRecovery(undefined); setRecoveryBusy(false); setRecoveryError(''); timelineEditor.resetForm(); selectedEpoch.current++; catalogEpoch.current++; assetEpoch.current++; invalidateCandidate(); setCatalog(undefined); setRecords([]); setBase(undefined); setDraft(blankGraph()); setPast([]); setFuture([]); setSelected([]); setAssets([]); setPreview(undefined); setPreviewState(undefined); setPendingNavigation(undefined); setMediaSchemaConsent(false); setExecutionDirty(false); setError(''); setNotice(''); }
  }, [denied, invalidateCandidate]);

  const load = useCallback(async () => {
    if (!current()) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    try {
      const [schema, values] = await read(() => Promise.all([client.graphs.catalog(), client.graphs.list()]));
      if (current() && epoch === catalogEpoch.current) { [1, 2, 3].forEach(version => schemaCatalogs.current.set(version, schema)); setCatalog(schema); setRecords(values.items); }
    } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '创作图目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }, [client, current, read]);
  useEffect(() => { if (active && !denied && !catalog) void load(); }, [active, denied, catalog, load]);
  async function loadImageCatalog() {
    if (!current() || locked() || externalDirty || executionDirty || !client.graphs.imageCatalog) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    const getCatalog = client.graphs.imageCatalog;
    try { const value = await read(() => getCatalog());
      if (current() && epoch === catalogEpoch.current) { schemaCatalogs.current.set(4, value); setCatalog(value); setNotice('已读取图片节点目录；当前图格式、输入与运行保持，尚未升级或执行。'); }
    } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '图片节点目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }

  async function loadProductionCatalog() {
    if (!current() || locked() || externalDirty || executionDirty || !client.graphs.productionCatalog) return;
    const epoch = ++catalogEpoch.current; setLoading(true); setError('');
    try { const value = await read(() => client.graphs.productionCatalog!()); if (current() && epoch === catalogEpoch.current) { schemaCatalogs.current.set(4, value); setCatalog(value); setNotice('已读取视觉制作节点目录；没有升级图格式、绑定文档或执行模型。'); } }
    catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '视觉制作节点目录读取失败。').message); }
    finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }
  async function loadPlanningDocuments() {
    if (!current() || locked() || externalDirty || executionDirty || !client.graphs.planningDocuments) return;
    const epoch = ++planningEpoch.current; setPlanningLoading(true); setError('');
    try { const value = await read(() => client.graphs.planningDocuments!()); if (current() && epoch === planningEpoch.current) { setPlanningDocuments(value.documents); setPlanningChoice(''); } }
    catch (value) { if (current() && epoch === planningEpoch.current) setError(apiErrorView(value, '导演与分镜文档引用读取失败。').message); }
    finally { if (current() && epoch === planningEpoch.current) setPlanningLoading(false); }
  }
  const choosePlanningDocument = (value: string) => { if (editable && current() && !locked()) setPlanningChoice(value); };
  async function graphCatalogForRecord(value: StudioGraphRecord, signal?: AbortSignal) {
    if (value.definition.schema_version === 5) { if (!client.graphs.videoCatalog) throw new Error('视频图目录当前不可用。'); return client.graphs.videoCatalog(signal); }
    if (value.definition.schema_version !== 4) return schemaCatalogs.current.get(value.definition.schema_version) || client.graphs.catalog(signal);
    const production = value.definition.nodes.some(node => productionGraphDefinitions.includes(node.definition_id as typeof productionGraphDefinitions[number]));
    const get = production ? client.graphs.productionCatalog : client.graphs.imageCatalog; if (!get) throw new Error('当前节点目录不可用，请重新打开工作区。');
    return get(signal);
  }
  async function loadVideoCatalog() {
    if (!current() || locked() || externalDirty || executionDirty || !client.graphs.videoCatalog) return; const epoch = ++catalogEpoch.current; setLoading(true);
    try { const value = await read(() => client.graphs.videoCatalog!()); if (current() && epoch === catalogEpoch.current) { schemaCatalogs.current.set(5, value); if (draftRef.current.schema_version === 5) setCatalog(value); else setPendingVideoCatalog(value); setNotice('已读取视频图节点目录；旧图未升级，未执行媒体。'); } } catch (value) { if (current() && epoch === catalogEpoch.current) setError(apiErrorView(value, '视频图目录读取失败。').message); } finally { if (current() && epoch === catalogEpoch.current) setLoading(false); }
  }
  function upgradeVideoSchema() { const selectedCatalog = pendingVideoCatalog || schemaCatalogs.current.get(5); if (!editable || !current() || locked() || !videoSchemaConfirmed || !selectedCatalog?.capabilities.video_graph || draft.schema_version === 5) return; if (draft.nodes.some(node => !videoGraphDefinitions.includes(node.definition_id as typeof videoGraphDefinitions[number]))) { setError('当前图含视频图不支持的节点。请保留原图，明确新建空图；不会自动删除节点。'); return; } change({ ...draftRef.current, schema_version: 5 }); setCatalog(selectedCatalog); setPendingVideoCatalog(undefined); setVideoSchemaConsent(''); setKind('storyboard_plan'); }
  function chooseShotParent(value: string) { if (!editable || !current() || locked()) return; shotEpoch.current++; setShotParent(value); setShotChoice(''); setShotReceipt(undefined); }
  async function loadShotReceipt() {
    if (!editable || !current() || locked() || !client.graphs.videoStoryboard) return; const parent = draftRef.current.nodes.find(node => node.id === shotParent && node.definition_id === 'storyboard_plan'), pin = parent?.parameters.document_snapshot; if (!pin) return; const epoch = ++shotEpoch.current, captured = JSON.stringify(pin); setShotLoading(true);
    try { const receipt = await read(() => client.graphs.videoStoryboard!(pin.id)); if (current() && epoch === shotEpoch.current && captured === JSON.stringify(draftRef.current.nodes.find(node => node.id === shotParent)?.parameters.document_snapshot)) { if (captured !== JSON.stringify(receipt.document_snapshot)) throw new Error('分镜文档版本已经变化，请核对原绑定。'); setShotReceipt(receipt); setShotChoice(''); } } catch (value) { if (current() && epoch === shotEpoch.current) setError(apiErrorView(value, '分镜镜头读取失败。').message); } finally { if (current() && epoch === shotEpoch.current) setShotLoading(false); }
  }
  function chooseShot(value: string) { if (editable && current() && !locked()) setShotChoice(value); }
  const change = useCallback((next: StudioGraphDefinition, record = true) => {
    if (!editable || !current() || saving.current || isBusy?.()) return;
    if (!retainsSavedAssetBindings(baseRef.current?.definition.nodes || [], next.nodes)) { setError('已保存资产引用暂不能移除或重新绑定；可移动或禁用节点。原资产不会被删除。'); return; }
    if (same(draftRef.current, next)) return;
    if (record) { const previous = structuredClone(draftRef.current); setPast(rows => [...rows.slice(-49), previous]); setFuture([]); }
    crossCopyEpoch.current++; draftRef.current = next; setDraft(next); setError(''); setNotice(''); invalidateCandidate();
  }, [editable, current, isBusy, invalidateCandidate]);
  function applyStarterGraph(kind: GraphStarterKind, text: string, scope: object): boolean {
    if (scope !== verificationScope || !isVerificationCurrent() || !insertionCurrent(insertionScope)
      || insertionRef.current || !catalog || draftRef.current.nodes.length || draftRef.current.edges.length) return false;
    try {
      const next = buildGraphStarter(draftRef.current, catalog, kind, text);
      change(next); if (draftRef.current !== next) return false;
      setSelected([next.nodes[0].id]); setNotice('起步方案已加入本地空图，可一次撤销。仍需明确保存、配置和运行；未调用模型。'); return true;
    } catch (value) { setError(value instanceof Error ? value.message : '起步方案未应用。'); return false; }
  }
  const currentCopy = active && copyPreview && copyPreview.identity === identity && copyPreview.client === client && copyPreview.graph === base?.id
    && copyPreview.epoch === selectedEpoch.current && copyPreview.catalog === catalog && copyPreview.source === JSON.stringify(draft) && editable ? copyPreview.result : undefined;
  useEffect(() => { setCopyPreview(undefined); }, [identity, client, base?.id, denied, canMutate, externalDirty, executionDirty, active, draft, catalog]);
  function previewSelectionCopy() {
    if (!active || !editable || !current() || locked() || timelineEditor.formDirty || !catalog) return;
    setCopyPreview(undefined);
    try { const result = graphSelectionCopy(draftRef.current, selected, { ...catalog, definitions: graphCatalogForSchema(catalog.definitions, draftRef.current.schema_version) });
      setCopyPreview({ identity, client, graph: baseRef.current?.id, epoch: selectedEpoch.current, source: JSON.stringify(draftRef.current), catalog, result }); setError('');
    } catch (value) { setError(value instanceof Error ? value.message : '复制预览失败。'); }
  }
  function pasteSelectionCopy() {
    if (!currentCopy || !editable || !current() || locked() || timelineEditor.formDirty || copyPreview?.source !== JSON.stringify(draftRef.current)) return;
    change(currentCopy.definition); setSelected(currentCopy.selected); setCopyPreview(undefined);
  }
  const copyScopeMatches = !copySource || !base || base.project_id === copySource.record.project_id && same(base.scope, copySource.record.scope);
  const sourceCopy = active && current() && !denied && canMutate && base?.can_edit !== false && copyScopeMatches && copySource?.identity === identity && copySource.client === client && copySource.sourceEpoch === copySourceEpoch.current ? copySource : undefined;
  const currentCrossCopy = sourceCopy && crossPreview?.source === sourceCopy && crossPreview.target === base
    && crossPreview.epoch === selectedEpoch.current && crossPreview.previewEpoch === crossCopyEpoch.current && crossPreview.catalog === catalog
    && crossPreview.draft === JSON.stringify(draft) && editable ? crossPreview.result : undefined;
  useLayoutEffect(() => { copySourceEpoch.current++; crossCopyEpoch.current++; setCopySource(undefined); setCrossPreview(undefined); }, [identity, client, denied, canMutate, active]);
  useLayoutEffect(() => { if (base?.can_edit === false || !copyScopeMatches) { copySourceEpoch.current++; setCopySource(undefined); } }, [base?.can_edit, copyScopeMatches]);
  useLayoutEffect(() => { crossCopyEpoch.current++; setCrossPreview(undefined); }, [draft, base, catalog, externalDirty, executionDirty, copySource]);
  function captureSelectionForGraph() {
    if (!active || !editable || !current() || locked() || dirty || !base || base !== baseRef.current || !same(draftRef.current, base.definition) || !selected.length || !catalog) return;
    if (base.reference_states.some(row => selected.includes(row.node_id) && row.state !== 'CURRENT')) {
      setError('所选节点来源已变化或不可用，请先核对原绑定。'); return;
    }
    if (selected.some(id => !draftRef.current.nodes.some(node => node.id === id))) return;
    crossCopyEpoch.current++; setCopySource({ identity, client, record: structuredClone(base), selected: [...selected], sourceEpoch: ++copySourceEpoch.current }); setCrossPreview(undefined); setError('');
  }
  function previewCrossGraphCopy() {
    if (!sourceCopy || sourceCopy.sourceEpoch !== copySourceEpoch.current || !base || base.id === sourceCopy.record.id || !editable || !current() || locked() || timelineEditor.formDirty || !catalog) return;
    crossCopyEpoch.current++; setCrossPreview(undefined);
    if (base.project_id !== sourceCopy.record.project_id || !same(base.scope, sourceCopy.record.scope)) { copySourceEpoch.current++; setCopySource(undefined); setError('复制来源与目标必须属于同一项目和身份范围。'); return; }
    try {
      const result = graphSelectionCopy(sourceCopy.record.definition, sourceCopy.selected, catalog, draftRef.current);
      setCrossPreview({ source: sourceCopy, target: base, epoch: selectedEpoch.current, previewEpoch: crossCopyEpoch.current, draft: JSON.stringify(draftRef.current), catalog, result }); setError('');
    } catch (value) { setError(value instanceof Error ? value.message : '跨图复制预览失败。'); }
  }
  function pasteCrossGraphCopy() {
    if (!currentCrossCopy || !editable || !current() || locked() || timelineEditor.formDirty || crossPreview?.source.sourceEpoch !== copySourceEpoch.current || crossPreview?.previewEpoch !== crossCopyEpoch.current || crossPreview?.epoch !== selectedEpoch.current || crossPreview?.target !== baseRef.current || crossPreview?.draft !== JSON.stringify(draftRef.current)) return;
    change(currentCrossCopy.definition); setSelected(currentCrossCopy.selected); setCrossPreview(undefined);
  }
  function applyAutoLayout() {
    if (!editable || !current() || locked()) return;
    // Derive from the live draft, never a retained preview or saved version.
    // Original change() owns history, binding guards and the eventual CAS save.
    change(autoLayout(draftRef.current, { definitions: catalog?.definitions }));
  }
  function navigate(work: () => void) {
    if (!current() || locked() || externalDirty || executionDirty) return;
    if (dirty || blocked) { setDiscardConfirmed(false); setPendingNavigation(() => work); return; }
    work();
  }
  async function open(id: string) {
    if (!current() || locked() || externalDirty || executionDirty) return;
    providerPicker.reset(); const epoch = ++selectedEpoch.current; setError('');
    try { const result = await mutate(async () => {
      const value = await client.graphs.get(id);
      const imageCatalog = await graphCatalogForRecord(value);
      return { value, imageCatalog };
    }); if (current() && epoch === selectedEpoch.current) { if (result.imageCatalog) { catalogEpoch.current++; setCatalog(result.imageCatalog); } accept(result.value); } }
    catch (value) { if (current() && epoch === selectedEpoch.current) setError(apiErrorView(value, '创作图读取失败，当前草稿未替换。').message); }
  }
  function newGraph() { if (!current() || locked() || externalDirty || executionDirty) return; setIndependentConsent(''); setIndependentOrigin(undefined); setCatalog(schemaCatalogs.current.get(1)); timelineEditor.clearForm(); selectedEpoch.current++; invalidateCandidate(); setBase(undefined); setDraft(blankGraph()); setSelected([]); setPast([]); setFuture([]); setBlocked(false); setSourcePort(''); setTargetPort(''); createRequest.current = graphId('graph'); reportSelection.current?.({}); }
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
    if (historyFull && !retry) { setError('当前服务端记录的历史配额已满。完整草稿仍保留，可明确准备独立新图后保存；原图历史不会删除。'); return; }
    saving.current = true; setError(''); const originContext = visibleIndependentOrigin; const epoch = selectedEpoch.current, value = structuredClone(draftRef.current), original = base, request = createRequest.current;
    try {
      const saved = await mutate(() => original ? client.graphs.save(original.id, { expected_version: original.version, definition: value }) : client.graphs.create({ request_id: request, expected_version: 0, definition: value }));
      if (current() && epoch === selectedEpoch.current) { accept(saved); if (originContext) setIndependentOrigin(originContext); setNotice(originContext ? `独立新图已保存 · v${saved.version}。原图 ${originContext.id} 保持不变；没有创建运行。` : `创作图已保存 · v${saved.version}。没有自动创建运行。`); }
    } catch (value) {
      if (current() && epoch === selectedEpoch.current) { const quota = value instanceof ApiError && value.status === 422 && value.problem.code === 'EXPERIMENTAL_INVALID'
        ? ({ CREATIVE_GRAPH_HISTORY_CAPACITY: '原图历史数量或记录字节容量已满。草稿仍保留，可明确准备独立新图；原图历史不会删除。',
          CREATIVE_GRAPH_SCOPE_CAPACITY: '当前范围的图与运行总容量已满。草稿仍保留；新图也受同一范围容量限制，不会自动重试。',
          CREATIVE_GRAPH_COLLECTION_CAPACITY: '当前范围的图或运行数量已满。草稿仍保留；不能保证新图可保存，不会自动重试。' } as Record<string, string>)[value.problem.message] : undefined;
        setError(quota || apiErrorView(value, '创作图未确认保存，输入已保留。').message); if (!(value instanceof ApiError) || value.status === 0 || value.status === 409 || value.status >= 500 || value.problem.code === 'STUDIO_RESPONSE_INVALID') setBlocked(true); }
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
  function addNode(request?: PositionedNodeRequest) { insertNode(kind, request); }
  function insertNode(kind: StudioGraphDefinitionId, request?: PositionedNodeRequest, reviewedPin?: PlanningSnapshot) {
    if (reviewedPin && (!insertionCurrent(insertionScope) || !catalog
      || !graphCatalogForSchema(catalog.definitions, draft.schema_version).some(row => row.id === kind))) return;
    if (request && (request !== insertionRef.current || !insertionCurrent(request.scope)
      || insertionSourceToken !== insertionSourceFence.current.token
      || assetLoading || planningLoading || shotLoading || timelineEditor.loading
      || kind === 'text_generate' && draft.schema_version === 1
      || !catalog || !graphCatalogForSchema(catalog.definitions, draft.schema_version).some(row => row.id === kind))) return;

    const planning = reviewedPin || planningDocuments.find(row => row.id === planningChoice && row.mode === (kind === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD'));
    const spec = catalog?.definitions.find(row => row.id === kind), asset = assets.find(row => row.id === assetChoice);
    const media = kind === 'media_generate' || kind === 'media_review' || kind === 'timeline_export';
    const image = draft.schema_version === 4, video = draft.schema_version === 5, shot = shotReceipt?.shots.find(row => row.shot_id === shotChoice);
    const shotParentNode = draft.nodes.find(node => node.id === shotParent && node.definition_id === 'storyboard_plan');
    const shotFresh = !!shotReceipt && JSON.stringify(shotReceipt.document_snapshot) === JSON.stringify(shotParentNode?.parameters.document_snapshot);
    const schemaRequired = media || kind === 'asset_reference' && catalog?.capabilities.media_execution;
    const limit = draft.schema_version >= 3 ? catalog?.media_limits?.nodes || 24 : catalog!.limits.nodes;
    if (!editable || !spec || draft.nodes.length >= limit || schemaRequired && draft.schema_version !== 3 && !image && !video
      || video && !videoGraphDefinitions.includes(kind as typeof videoGraphDefinitions[number]) || image && !imageGraphDefinitions.some(value => value === kind)
      || ['media_generate', 'timeline_export'].includes(kind) && draft.nodes.filter(row => ['media_generate', 'timeline_export'].includes(row.definition_id)).length >= 4
      || ['image_generate', 'image_upscale'].includes(kind) && draft.nodes.filter(row => ['image_generate', 'image_upscale'].includes(row.definition_id)).length >= 4
      || kind === 'storyboard_shot' && (!shot || !shotFresh) || ['video_generate', 'timeline_export'].includes(kind) && video && draft.nodes.filter(row => ['video_generate', 'timeline_export'].includes(row.definition_id)).length >= 4 || ['director_plan', 'storyboard_plan'].includes(kind) && !planning || kind === 'asset_reference' && !asset || kind === 'timeline_export' && !timelineEditor.chosen) return;
    if (image && kind === 'asset_reference' && asset?.kind !== 'image') { setError('图片图只接受图片素材引用。'); return; }
    const node = { id: graphId(), definition_id: kind, definition_version: 1 as const, enabled: true, position: request ? { ...request.position } : { x: 24 + draft.nodes.length % 4 * 280, y: 24 + Math.floor(draft.nodes.length / 4) * 180 },
      parameters: kind === 'asset_reference' ? { asset_id: asset!.id, version: asset!.version, digest: asset!.sha256, kind: asset!.kind as 'image' | 'video' | 'audio' }
        : kind === 'media_generate' ? { operation_id: 'm5.image.t2i' as const, provider_id: '', model_id: '', prompt: '', parameters: {}, allow_cloud: false, license_note: '' }
        : kind === 'storyboard_shot' ? { shot_id: shot!.shot_id, shot_version: shot!.shot_version, shot_digest: shot!.shot_digest }
        : kind === 'video_generate' ? { operation_id: 'm7.video.t2v' as const, provider_id: '', model_id: '', prompt: '', parameters: {}, allow_cloud: false, license_note: '', bind_shot: true as const }
        : ['director_plan', 'storyboard_plan'].includes(kind) ? { document_snapshot: { id: planning!.id, version: planning!.version, digest: planning!.digest } }
        : kind === 'storyboard_prompt' ? { shot_id: '' }
        : kind === 'image_upscale' ? { operation_id: 'm5.image.upscale' as const, provider_id: '', model_id: '', parameters: {}, allow_cloud: false, license_note: '' }
        : kind === 'image_generate' ? { operation_id: 'm5.image.t2i' as const, provider_id: '', model_id: '', parameters: {}, allow_cloud: false, license_note: '' }
        : kind === 'timeline_export' ? { timeline_snapshot: { id: timelineEditor.chosen!.id, version: timelineEditor.chosen!.version, digest: timelineEditor.chosen!.timeline_digest },
          edit_operations: [], source_bindings: [], export_profile: { preset: 'REVIEW_MP4' as const } }
        : structuredClone(spec.default_parameters || {}) };
    const next = { ...draft, schema_version: kind === 'text_generate' && draft.schema_version === 1 ? 2 as const : draft.schema_version, nodes: [...draft.nodes, node] };
    change(next);
    if ((request || reviewedPin) && draftRef.current !== next) return;
    if (request) { insertionRef.current = undefined; setInsertion(undefined); }
    setSelected([node.id]);
    if (request) request.restoreFocus();
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
    if (!editable || !current() || locked()) return;
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || !['media_generate', 'image_generate', 'image_upscale', 'video_generate'].includes(target.definition_id)) return;
    if (['image_generate', 'image_upscale'].includes(target.definition_id) && key === 'prompt') return;
    if (target.definition_id === 'image_upscale' && (key === 'operation_id' || key === 'allow_cloud')) return;
    if (key === 'operation_id' && !(target.definition_id === 'video_generate' ? GRAPH_VIDEO_OPERATIONS.some(operation => operation === value) : target.definition_id === 'image_generate' ? GRAPH_IMAGE_OPERATIONS.some(operation => operation === value) : GRAPH_MEDIA_OPERATIONS.some(operation => operation === value))
      || (key === 'allow_cloud' ? typeof value !== 'boolean' : typeof value !== 'string')) return;
    if (target.parameters[key] === value) return;
    const manualBinding = key === 'provider_id' || key === 'model_id';
    if (manualBinding && ['image_generate', 'video_generate', 'image_upscale'].includes(target.definition_id) && !providerPicker.manualBindingCurrent()) return;
    if (key === 'operation_id' || manualBinding) providerPicker.reset();
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, [key]: value, ...(manualBinding || key === 'operation_id' && ['image_generate', 'video_generate'].includes(target.definition_id) ? { allow_cloud: false } : {}) } } : row) });
  }
  function updateMediaParameter(key: string, value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]), allowed = target?.parameters.operation_id && graphMediaParameterNames(target.parameters.operation_id, ['image_generate', 'image_upscale'].includes(target.definition_id));
    if (!target || !['media_generate', 'image_generate', 'image_upscale', 'video_generate'].includes(target.definition_id) || !allowed?.includes(key)) return;
    const next = { ...target.parameters.parameters };
    if (value === '') delete next[key];
    else if (['negative_prompt', 'voice_id', 'size', 'quality'].includes(key)) next[key] = value;
    else { const parsed = Number(value); if (!Number.isFinite(parsed) || !['speech_rate', 'denoising_strength'].includes(key) && !Number.isSafeInteger(parsed)) return; next[key] = parsed; }
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, parameters: next } } : row) });
  }
  function clearUnsupportedMediaParameters() {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || !['media_generate', 'image_generate', 'image_upscale', 'video_generate'].includes(target.definition_id) || !target.parameters.operation_id) return;
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
    const original = target.parameters.bindings?.find(binding => binding.port === port);
    const bindings = (target.parameters.bindings || []).filter(binding => binding.port !== port);
    if (value !== '') {
      const weight = Number(value); if (!Number.isFinite(weight) || weight <= 0 || weight > 1) return;
      bindings.push({ ...original, port: port as NonNullable<typeof target.parameters.bindings>[number]['port'], weight });
    }
    bindings.sort((left, right) => left.port.localeCompare(right.port));
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { bindings } } : row) });
  }
  function updateReferenceMetadata(port: string, key: 'purpose' | 'source_note', value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (target?.definition_id !== 'image_reference') return;
    const bindings = target.parameters.bindings?.map(binding => { if (binding.port !== port) return binding; const next = { ...binding }; if (value === '') delete next[key]; else Object.assign(next, checkedImageReferenceMetadata({ [key]: value }, true)); return next; });
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { bindings } } : row) });
  }
  function updateProductionField(key: 'style' | 'atmosphere' | 'color_palette' | 'shot_id' | 'reference_purpose', value: string) {
    const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (key === 'reference_purpose') { if (target?.definition_id !== 'video_generate' || value !== '' && !['style', 'action', 'camera'].includes(value)) return; const parameters = { ...target.parameters }; if (value === '') delete parameters.reference_purpose; else parameters.reference_purpose = value as 'style' | 'action' | 'camera'; change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters } : row) }); return; }
    if (!target || (key === 'shot_id' ? target.definition_id !== 'storyboard_prompt' || value.length > 240 : target.definition_id !== 'image_style' || value.length > (key === 'style' ? 2000 : 1000))) return;
    change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters: { ...row.parameters, [key]: value } } : row) });
  }
  function updateShotBinding(value: boolean) { const target = draftRef.current.nodes.find(row => row.id === selected[0]); if (!target || target.definition_id !== 'video_generate' || !editable || !current() || locked() || value && !draftRef.current.edges.some(edge => edge.target_node_id === target.id && edge.target_port === 'shot')) return;
    const parameters = { ...target.parameters }; if (value) parameters.bind_shot = true; else delete parameters.bind_shot; change({ ...draftRef.current, nodes: draftRef.current.nodes.map(row => row.id === target.id ? { ...row, parameters } : row) }); }
  function connect() {
    if (!editable || !sourcePort || !targetPort || draft.edges.length >= catalog!.limits.edges) return;
    const [source_node_id, source_port] = JSON.parse(sourcePort), [target_node_id, target_port] = JSON.parse(targetPort);
    const edge = { id: graphId('edge'), source_node_id, source_port, target_node_id, target_port }, problem = connectionIssue(draft, catalog!.definitions, edge);
    if (problem) { setError(problem); return; }
    change({ ...draft, edges: [...draft.edges, edge] }); setSourcePort(''); setTargetPort('');
  }
  function travel(redo: boolean) {
    if (!editable || locked() || !current()) return;
    providerPicker.reset();
    const from = redo ? future : past, value = redo ? from[0] : from.at(-1); if (!value) return;
    if (!retainsSavedAssetBindings(base?.definition.nodes || [], value.nodes)) { setError('撤销不能移除已经保存的资产绑定。'); return; }
    if (redo) { setPast(rows => [...rows.slice(-49), structuredClone(draft)]); setFuture(rows => rows.slice(1)); }
    else { setFuture(rows => [structuredClone(draft), ...rows].slice(0, 50)); setPast(rows => rows.slice(0, -1)); }
    crossCopyEpoch.current++; invalidateCandidate(); draftRef.current = structuredClone(value); setDraft(draftRef.current); setSourcePort(''); setTargetPort('');
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
      const imageCatalog = await graphCatalogForRecord(value, abort.signal);
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

  // Recover only after the existing authorized overview and graph catalog have loaded.
  // The namespace carries actor, scope AND the original owner's incarnation; no token.
  useEffect(() => {
    if (!active || denied || !catalog || !current() || !draftOwnerCurrent || !ownerKey || !draftOwner || draftStorageKey === ownerKey) return;
    try {
      const raw = localStorage.getItem(ownerKey);
      setLocalRecovery(raw ? readStudioGraphLocalDraft(raw, draftOwner) : undefined);
      persistedDraftRaw.current = raw;
      setDraftStorageNotice('');
    } catch {
      setDraftStorageNotice('本机图草稿无法读取或校验，原缓存保持；当前输入仍保留在本页。');
    }
    setDraftStorageKey(ownerKey);
  }, [active, denied, catalog, current, draftOwnerCurrent, ownerKey, draftStorageKey]);

  const draftRecoverable = graphDraftRecoverable(draft);
  useEffect(() => {
    if (!active || denied || !catalog || !current() || !draftOwnerCurrent || !ownerKey || !draftOwner
      || draftStorageKey !== ownerKey || localRecovery || recoveryBusy || draftStorageNotice) return;
    try {
      if (localStorage.getItem(ownerKey) !== persistedDraftRaw.current) {
        setDraftStorageNotice('其他页面已更新本机图草稿，原缓存保持；当前输入只保留在本页。'); return;
      }
      if (!dirty && !blocked) { localStorage.removeItem(ownerKey); persistedDraftRaw.current = null; setDraftSavedAt(undefined); return; }
      if (!draftRecoverable || timelineEditor.formDirty || executionDirty) return;
      const snapshot: StudioGraphLocalDraft = { schema_version: 1, owner: draftOwner, saved_at: new Date().toISOString(),
        request_id: createRequest.current, base: base ? { id: base.id, version: base.version,
          definition_digest: base.definition_digest, execution_digest: base.execution_digest } : null,
        definition: draft, uncertain: blocked };
      const raw = JSON.stringify(snapshot); localStorage.setItem(ownerKey, raw); persistedDraftRaw.current = raw;
      setDraftSavedAt(snapshot.saved_at);
    } catch {
      setDraftStorageNotice('本机图草稿未能保存，请保留此页面；服务端保存仍需明确操作。');
    }
  }, [active, denied, catalog, current, draftOwnerCurrent, ownerKey, draftStorageKey, localRecovery, recoveryBusy,
    draftStorageNotice, dirty, blocked, draftRecoverable, draft, base, timelineEditor.formDirty, executionDirty]);

  const canRecoverDraft = !!localRecovery && draftOwnerCurrent && canMutate && current() && !denied && !locked()
    && !externalDirty && !executionDirty && !dirty && !blocked && !timelineEditor.formDirty
    && (!base || base.id === localRecovery.base?.id) && (!requestedGraphId || requestedGraphId === localRecovery.base?.id)
    && draft.schema_version <= 2;
  async function recoverLocalDraft() {
    if (!canRecoverDraft || !localRecovery || !draftOwner || !ownerKey) return;
    const snapshot = localRecovery, key = ownerKey, epoch = ++recoveryEpoch.current, selection = selectedEpoch.current;
    const original = JSON.stringify(draftRef.current); setRecoveryBusy(true); setRecoveryError('');
    try {
      const record = await read(async () => {
        // Recheck even an unsaved graph: the public project ID may have been recreated.
        const overview = await client.overview();
        if (overview.project.id !== draftOwner.projectId || overview.project.incarnation !== draftOwner.incarnation)
          throw new Error('项目代次已经改变；旧草稿未恢复到当前项目。');
        if (!overview.capabilities.can_mutate) throw new Error('当前身份没有图编辑权限；本机草稿保持。');
        if (!snapshot.base) return undefined;
        const value = await client.graphs.get(snapshot.base.id);
        if (!graphDraftBaselineMatches(snapshot, value)) throw new Error('图服务端版本或摘要已改变；本机草稿保持，请先核对下方作者输入与当前服务端版本。');
        return value;
      });
      const fence = recoveryFence.current;
      if (!current() || epoch !== recoveryEpoch.current || selection !== selectedEpoch.current || fence.ownerKey !== key
        || fence.busy || fence.externalDirty || fence.executionDirty || !fence.canMutate || isBusy?.()
        || original !== JSON.stringify(draftRef.current)) return;
      if (localStorage.getItem(key) !== persistedDraftRaw.current) throw new Error('其他页面已更新本机图草稿，未替换当前输入；请重新打开后核对。');
      timelineEditor.resetForm(); setIndependentConsent(''); setIndependentOrigin(undefined); invalidateCandidate(); selectedEpoch.current++; setBase(record);
      draftRef.current = structuredClone(snapshot.definition); setDraft(draftRef.current); setSelected([]); setPast([]); setFuture([]);
      createRequest.current = snapshot.request_id; setBlocked(snapshot.uncertain); setSourcePort(''); setTargetPort('');
      setLocalRecovery(undefined); setRecoveryError(''); reportSelection.current?.({ graphId: record?.id });
      setNotice('已恢复本机文本图草稿。尚未保存到服务端，也未创建或执行运行。');
    } catch (value) {
      if (current() && epoch === recoveryEpoch.current) setRecoveryError(value instanceof ApiError
        ? apiErrorView(value, '当前图无法重新授权读取，本机草稿保持。').message : value instanceof Error ? value.message : '本机草稿未恢复。');
    } finally { if (current() && epoch === recoveryEpoch.current) setRecoveryBusy(false); }
  }
  function discardLocalRecovery() {
    if (!current() || locked() || !ownerKey || !draftOwnerCurrent) return;
    try {
      if (localStorage.getItem(ownerKey) !== persistedDraftRaw.current) { setDraftStorageNotice('其他页面已更新本机图草稿，未删除未经核对的新缓存。'); return; }
      localStorage.removeItem(ownerKey); persistedDraftRaw.current = null; setLocalRecovery(undefined); setRecoveryError(''); setDraftStorageNotice('');
    }
    catch { setDraftStorageNotice('本机图草稿未能删除，原缓存保持。'); }
  }

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
    localRecovery: current() && !denied ? localRecovery : undefined, recoveryBusy, recoveryError,
    draftStorageNotice, draftSavedAt, draftOwnerCurrent, draftRecoverable, canRecoverDraft, recoverLocalDraft, discardLocalRecovery,
    providerPicker, sourceCopy, currentCrossCopy, captureSelectionForGraph, previewCrossGraphCopy, pasteCrossGraphCopy, clearGraphCopy: () => { copySourceEpoch.current++; crossCopyEpoch.current++; setCopySource(undefined); setCrossPreview(undefined); }, currentCopy, previewSelectionCopy, pasteSelectionCopy, cancelSelectionCopy: () => setCopyPreview(undefined),
    catalog: catalog ? { ...catalog, ...(pendingVideoCatalog ? { capabilities: { ...catalog.capabilities, video_graph: true as const, video_graph_schema_version: 5 as const, video_graph_evidence: 'LOCAL_REQUIRED' as const, storyboard_video_approval_required: true as const, automatic_video_dispatch: false as const } } : {}), definitions: graphCatalogForSchema(catalog.definitions, draft.schema_version) } : undefined,
    independentConfirmed, confirmIndependentGraph, prepareIndependentGraph, independentOrigin: visibleIndependentOrigin, historyFull,
    starterScope: verificationScope, applyStarterGraph,
    planningForkScope: verificationScope, isPlanningForkCurrent: isVerificationCurrent, preparePlanningGraphFork, planningForkReferences,
    records, base, draft, selected, past, future, loading, error, notice, blocked,
    candidate, replaceConfirmed, checking, pendingNavigation, discardConfirmed, kind, sourcePort, targetPort,
    assets, assetChoice, assetLoading, preview, previewState, refreshPreview, downloadPreviewAsset, current, dirty, editable, protectedNodes, node,
    loadVideoCatalog, videoSchemaConfirmed, confirmVideoSchema, upgradeVideoSchema, shotParent, chooseShotParent, shotReceipt, shotChoice, chooseShot, shotLoading, loadShotReceipt,
    planningDocuments: current() ? planningDocuments : [], planningChoice: current() ? planningChoice : '', planningLoading, choosePlanningDocument, loadPlanningDocuments, loadProductionCatalog, updateProductionField, updateShotBinding, updateReferenceMetadata,
    discard, load, loadImageCatalog, change, applyAutoLayout, navigate, open, newGraph, save, checkServer, loadAssets, addNode, connect, travel, confirmNavigation, adoptCandidate,
    setReplaceConfirmed, setCandidate, setDiscardConfirmed, setPendingNavigation, setKind, setAssetChoice,
    reviewedDirectorHandoff, insertionScope, positionedInsertion, insertionExpired, invalidatePositionedInsertion, requestPositionedInsertion, cancelPositionedInsertion,
    connectionScope, stageConnection, selectConnectionPort, setSourcePort, setTargetPort, setSelected, reportRunSelection, mediaSchemaConsent, setMediaSchemaConsent, upgradeMediaSchema, executionDirty, setExecutionDirty,
    imageSchemaConfirmed, confirmImageSchema, upgradeImageSchema, updateImagePrompt, updateImageReference,
    updateMediaField, updateMediaParameter, clearUnsupportedMediaParameters, clearMediaTrimInputs, timelineEditor,
  };
}
export type StudioGraphEditorController = ReturnType<typeof useStudioGraphEditorController>;
export const GRAPH_MEDIA_PARAMETER_LABELS: Record<string, string> = { width: '宽度', height: '高度', steps: '采样步数', seed: '种子', negative_prompt: '负向提示词', size: '图片规格', quality: '图片质量',
  scale: '超分倍率（2 或 4）', denoising_strength: '重绘强度（大于 0 至 1）',
  duration_seconds: '时长（秒）', frame_rate: '帧率', voice_id: '语音标识', speech_rate: '语速', in_ms: '来源起点（毫秒）', out_ms: '来源终点（毫秒）' };
export function graphMediaParameterNames(operation: GraphMediaOperation | GraphImageOperation | 'm5.image.upscale', image = false): string[] {
  if (operation === 'm5.image.upscale') return image ? ['scale'] : [];
  const imageParameters = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'];
  if (image && ['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].includes(operation)) return ['steps', 'seed', 'negative_prompt', 'denoising_strength'];
  return ({ 'm5.image.t2i': imageParameters, 'm5.image.i2i': imageParameters, 'm5.image.reference': imageParameters, 'm5.image.inpaint': imageParameters,
    'm7.video.t2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'], 'm7.video.i2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
    'm7.video.v2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'], 'm8.audio.speech': ['voice_id', 'speech_rate'],
    'm8.audio.music': ['duration_seconds', 'seed'], 'm8.audio.effects': ['duration_seconds', 'seed'], 'm8.audio.trim': ['in_ms', 'out_ms'] } as Record<GraphMediaOperation | GraphImageOperation, string[]>)[operation];
}

/** Read-only configuration picker. The graph persists IDs, never this UI's route digest. */
function useGraphProviderPicker(props: {
  source?: Pick<StudioProductionClient, 'providers'>; client: StudioClient; identity: string; scope: string;
  active: boolean; denied: boolean; node?: StudioGraphDefinition['nodes'][number]; editable: boolean;
  current: () => boolean; locked: () => boolean; read: StudioGraphEditorProps['read']; bind: (row: ProductionProvider) => void;
}) {
  const latest = useRef(props); latest.current = props;
  const epoch = useRef(0), request = useRef<AbortController>(), alive = useRef(true);
  const [, setPickerRevision] = useState(0);
  const [catalog, setCatalog] = useState<{ source: typeof props.source; client: StudioClient; identity: string; scope: string; rows: ProductionProvider[] }>();
  const catalogRef = useRef(catalog); catalogRef.current = catalog;
  const [route, setRoute] = useState<'local' | 'cloud'>('local'), [choice, setChoice] = useState('');
  const routeRef = useRef(route); routeRef.current = route;
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const reset = useCallback(() => { epoch.current++; setPickerRevision(epoch.current); request.current?.abort(); request.current = undefined;
    catalogRef.current = undefined; setCatalog(undefined); setChoice(''); setLoading(false); setError(''); routeRef.current = 'local'; setRoute('local'); }, []);
  useLayoutEffect(() => { reset(); }, [props.source, props.client, props.identity, props.scope, props.active, props.denied, reset]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; request.current?.abort(); }; }, []);
  const supported = (value: typeof props) => !!value.node && ['image_generate', 'video_generate', 'image_upscale'].includes(value.node.definition_id);
  const readable = () => { const value = latest.current; return alive.current && value.active && !value.denied && value.current() && !value.locked() && !!value.source && supported(value); };
  const sameScope = (value: Pick<typeof props, 'source' | 'client' | 'identity' | 'scope'>) => { const now = latest.current; return value.source === now.source && value.client === now.client && value.identity === now.identity && value.scope === now.scope; };
  const visible = catalog && sameScope(catalog) && props.active && !props.denied && props.current() ? catalog : undefined;
  const rows = visible?.rows.filter(row => row.operation_id === props.node?.parameters.operation_id && row.local === (route === 'local') && (props.node?.definition_id !== 'image_upscale' || row.local)) || [];
  async function load() {
    if (!readable() || request.current || loading || !sameScope(props) || capturedEpoch !== epoch.current) return;
    const captured = latest.current, id = ++epoch.current, controller = new AbortController();
    request.current = controller; catalogRef.current = undefined; setCatalog(undefined); setChoice(''); setError(''); setLoading(true);
    const valid = () => alive.current && !controller.signal.aborted && id === epoch.current && sameScope(captured) && latest.current.active && !latest.current.denied && latest.current.current();
    try {
      const values = await captured.read(() => captured.source!.providers(controller.signal));
      if (!valid()) return;
      // Even identical duplicates are ambiguous: this unchanged graph schema stores only the tuple.
      const counts = new Map<string, number>(), tuple = (row: ProductionProvider) => JSON.stringify([row.operation_id, row.provider_id, row.model_id]);
      values.forEach(row => counts.set(tuple(row), (counts.get(tuple(row)) || 0) + 1));
      const unique = values.filter(row => counts.get(tuple(row)) === 1);
      const next = { source: captured.source, client: captured.client, identity: captured.identity, scope: captured.scope, rows: unique };
      catalogRef.current = next; setCatalog(next);
      if (unique.length !== values.length) setError('重复或含糊的服务配置已隐藏；原节点标识保持，请核对原服务配置。');
    } catch (reason) { if (valid()) setError(apiErrorView(reason, '服务配置读取失败，原节点标识保持。').message); }
    finally { if (valid()) { request.current = undefined; setLoading(false); } }
  }
  const capturedEpoch = epoch.current;
  function chooseRoute(value: string) {
    if (!sameScope(props) || capturedEpoch !== epoch.current || !readable() || !latest.current.editable || request.current || loading || !['local', 'cloud'].includes(value)
      || latest.current.node?.definition_id === 'image_upscale' && value !== 'local') return;
    if (value === routeRef.current) return;
    epoch.current++; routeRef.current = value as 'local' | 'cloud'; setRoute(value as 'local' | 'cloud'); setChoice('');
  }
  function choose(key: string) {
    if (!sameScope(props) || capturedEpoch !== epoch.current || !readable() || !latest.current.editable || route !== routeRef.current || loading || request.current) return;
    const accepted = catalogRef.current;
    if (!accepted || !sameScope(accepted)) return;
    const row = accepted.rows.find(value => mediaProviderKey(value) === key && value.operation_id === latest.current.node?.parameters.operation_id
      && value.local === (route === 'local') && (latest.current.node?.definition_id !== 'image_upscale' || value.local));
    if (!row) return;
    latest.current.bind(row); setChoice(key);
  }
  // Manual IDs may be authored without a catalog, but never through a retired
  // node/owner callback or a stale editability decision. Reuse the picker epoch.
  const manualBindingCurrent = () => sameScope(props) && capturedEpoch === epoch.current && alive.current
    && latest.current.active && !latest.current.denied && latest.current.current() && !latest.current.locked()
    && latest.current.editable && supported(latest.current);
  const stored = props.node?.parameters;
  const matchedRow = visible?.rows.find(row => row.operation_id === stored?.operation_id && row.provider_id === stored.provider_id && row.model_id === stored.model_id);
  const matched = !!matchedRow;
  const bindingRoute = matchedRow ? matchedRow.local ? 'local' : 'cloud' : 'unknown';
  return { rows, route, choice: rows.some(row => mediaProviderKey(row) === choice && row.provider_id === stored?.provider_id && row.model_id === stored?.model_id) ? choice : '',
    loading, error, loaded: !!visible, matched, bindingRoute, manualBindingCurrent, canRead: readable(), canEdit: readable() && props.editable && !loading, load, choose, chooseRoute, reset };
}
