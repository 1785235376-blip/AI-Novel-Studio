import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, apiErrorView, api, type Asset, type CollaborationContext, type ModelCenterModel } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { AppShell, type ScopeLabels, type StudioModule } from '../ui/AppShell';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { AssetLibraryPanel, type AssetLibraryAdapter } from '../novel/AssetLibraryPanel';
import { AssetInspector } from '../novel/AssetInspector';
import type { LineageAsset } from '../experimental/ProductionLineagePanel';
import { StudioAssetDeclarationForm } from './StudioAssetDeclarationForm';
import { studioClient, studioTransport, type StudioAsset, type StudioOverview, type StudioPreferences, type StudioStorage } from './studioClient';
import { rememberLocalStudioSelection, rememberLocalWorkspaceSelection, type LocalStudioModule } from '../workspaceSelection';
import { useStudioGraphEditor } from './useStudioGraphEditor';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import { StudioWorkspaceOperationPanel } from './StudioWorkspaceOperationPanel';
import { readLocalStudioInterfaceMode, readLocalStudioResume, rememberLocalStudioInterfaceMode, rememberLocalStudioResume, type StudioInterfaceMode, type StudioWorkspaceLocation, type StudioWorkspaceStage, type StudioWorkspaceView } from './studioWorkspaceResume';
import { useStudioWorkspacePreferences } from './useStudioWorkspacePreferences';
import { StudioWorkspacePreferencesForm } from './StudioWorkspacePreferencesForm';
import { studioProductionClient, type ProductionJob } from './studioProductionClient';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { StudioManualMaskPanel } from './StudioManualMaskPanel';
import { createProductionWorkflowClient } from '../production/productionWorkflowClient';
import { ProductionDashboard } from '../production/ProductionDashboard';
import { ProductionInspectorPanel } from '../production/ProductionInspectorPanel';
import { useProductionWorkflow } from '../production/useProductionWorkflow';
import type { ProductionWorkflowAssetKind, ProductionWorkflowModuleId } from '../production/productionWorkflowTypes';
// UX-PRODUCT batch 1: the unified task center (UX-02) and the studio entry /
// intent / interface-mode surface (UX-01). Both are additive mounted content in
// their own folders; neither introduces a second project, task or preference owner.
import { TaskCenterPanel } from '../taskcenter/TaskCenter';
import { StudioStartPanel } from '../onboarding/StudioStartPanel';
import { InterfaceModeSwitch } from '../onboarding/InterfaceModeSwitch';
import { createStudioEntryClient } from '../onboarding/studioEntryClient';
import { useStudioEntry } from '../onboarding/useStudioEntry';
import './independentStudio.css';

export const isManualStudioModule = (module: StudioModule): module is LocalStudioModule => ['IMAGE', 'ASSETS', 'VIDEO', 'AUDIO'].includes(module);
let studioObserver = 0;
const signature = (projectId: string, context: CollaborationContext) => JSON.stringify([projectId, context.sessionToken, context.actor?.id, context.actor?.workspaceId, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
function lineageAsset(asset: Asset): LineageAsset {
  const row = asset.provenance as (NonNullable<Asset['provenance']> & { source_task_id?: string }) | undefined;
  return { id: asset.id, label: asset.filename, kind: asset.kind, version: asset.version!, digest: asset.sha256, deleted: !!asset.deleted_at,
    integrity: row?.integrity || 'CONTENT_UNAVAILABLE', origin: row?.origin || 'UNDECLARED', license: row?.license || { label: 'UNSPECIFIED', source: '', note: '' },
    operation: row?.operation || '', parents: row?.parents || [], sources: row?.sources || [], stale: row?.stale ?? true,
    source_task_id: typeof row?.source_task_id === 'string' && row.source_task_id ? row.source_task_id : undefined };
}
export type IndependentStudioProps = { projectId: string; context: CollaborationContext; scope: ScopeLabels; actor: string; module: LocalStudioModule;
  requestedAssetId?: string; onModuleChange: (module: StudioModule) => void; onProjectChoice: () => void; onVerified?: (projectId: string) => void; status?: ReactNode };

/** Independent module content; the original shell and asset owners remain authoritative. */
export function IndependentStudioWorkspace(props: IndependentStudioProps) {
  return <IndependentStudioSession key={signature(props.projectId, props.context)} {...props} />;
}
function IndependentStudioSession({ projectId, context, scope, actor, module, requestedAssetId, onModuleChange, onProjectChoice, onVerified, status }: IndependentStudioProps) {
  const query = useQueryClient();
  const capturedHost = useRef({ ...useLocalHostSession.getState() });
  const watchHost = !context.sessionToken && !context.scope && !context.actor;
  const origin = useRef(signature(projectId, context));
  const alive = useRef(true), revoked = useRef(false), authorityLost = useRef(false), busyRef = useRef(false);
  const [identityRetired, setIdentityRetired] = useState(false);
  const client = useMemo(() => studioClient(projectId, context), [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const productionClient = useMemo(() => studioProductionClient(projectId, context), [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const cutoutPermission = useRef(false);
  const cutoutLease = useRef<{ job: ProductionJob; control?: Promise<ProductionJob> }>();
  const [cacheKey] = useState(() => `independent-studio-${++studioObserver}`);
  const [overview, setOverview] = useState<StudioOverview>(), [rows, setRows] = useState<StudioAsset[]>([]);
  const [selected, setSelected] = useState<Asset>(), [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false), [busy, setBusy] = useState(false), [readingAsset, setReadingAsset] = useState(false), [storageLoading, setStorageLoading] = useState(false);
  const [pendingDeclaration, setPendingDeclaration] = useState<StudioAsset>(), [lineageDirty, setLineageDirty] = useState(false), [relationshipDirty, setRelationshipDirty] = useState(false), [formRevision, setFormRevision] = useState(0), [storage, setStorage] = useState<StudioStorage>();
  const [resume] = useState(() => !context.scope && !context.sessionToken && !context.actor
    ? readLocalStudioResume(projectId) : { state: 'EMPTY' as const });
  const [workspaceView, setWorkspaceView] = useState<StudioWorkspaceView>(resume.state === 'SAVED' ? resume.location.view : 'ASSETS');
  const [productionStage, setProductionStage] = useState<StudioWorkspaceStage>(resume.state === 'SAVED' ? resume.location.stage : 'M4');
  const [graphLocation, setGraphLocation] = useState<Pick<StudioWorkspaceLocation, 'graphId' | 'runId'>>(resume.state === 'SAVED'
    ? { graphId: resume.location.graphId, runId: resume.location.runId } : {});
  const graphView = workspaceView === 'GRAPH', productionView = workspaceView === 'PRODUCTION';
  // Presentation-only interface mode. Both modes share the same project, assets,
  // tasks, graph and drafts; switching never converts, copies or deletes data.
  const authoredLocally = !context.scope && !context.sessionToken && !context.actor;
  const [interfaceMode, setInterfaceMode] = useState<StudioInterfaceMode>(
    () => authoredLocally ? readLocalStudioInterfaceMode(projectId) : 'PROFESSIONAL');
  const changeInterfaceMode = useCallback((mode: StudioInterfaceMode) => {
    if (mode === 'NOVICE') {
      // A novice never lands on the node graph: move off it instead of leaving a
      // hidden view rendered.
      setWorkspaceView(current => current === 'GRAPH' ? 'TASKS' : current);
    }
    setInterfaceMode(mode);
    // Best-effort local hint; when no location is saved yet the next resume write
    // carries the mode, and this never fabricates a location to store it.
    rememberLocalStudioInterfaceMode(projectId, mode);
  }, [projectId]);
  const [pendingNavigation, setPendingNavigation] = useState<() => void>(), [discard, setDiscard] = useState(false);
  const selectionEpoch = useRef(0), overviewEpoch = useRef(0), storageEpoch = useRef(0), storageReading = useRef(false);
  const overviewReading = useRef<AbortController>(), storageRequest = useRef<AbortController>();
  const graphDirtyRef = useRef(false);
  const [mediaDirty, setMediaDirty] = useState(false), [timelineDirty, setTimelineDirty] = useState(false), [productionRevision, setProductionRevision] = useState(0);
  const [productionJob, setProductionJob] = useState<{ client: typeof productionClient; job: ProductionJob }>();
  const mediaDirtyRef = useRef(false), timelineDirtyRef = useRef(false), assetReadEpoch = useRef(0);
  const [maskDirty, setMaskDirty] = useState(false);
  const maskDirtyRef = useRef(false);
  const maskDraftChanged = useCallback((value: boolean) => { maskDirtyRef.current = value; setMaskDirty(value); }, []);
  const [workflowDirty, setWorkflowDirty] = useState(false), [workflowModule, setWorkflowModule] = useState<ProductionWorkflowModuleId>('director'), [workflowAssetKind, setWorkflowAssetKind] = useState<ProductionWorkflowAssetKind>('image');
  const workflowDirtyRef = useRef(false);
  const workflowDraftChanged = useCallback((value: boolean) => { workflowDirtyRef.current = value; setWorkflowDirty(value); }, []);
  const mediaDraftChanged = useCallback((value: boolean) => { mediaDirtyRef.current = value; setMediaDirty(value); }, []);
  const timelineDraftChanged = useCallback((value: boolean) => { timelineDirtyRef.current = value; setTimelineDirty(value); }, []);
  const verifiedCallback = useRef(onVerified); verifiedCallback.current = onVerified;
  const lastImport = useRef<{ body: string; key: string }>();
  const sameStudioIdentity = useCallback(() => {
    const state = useStudio.getState();
    return origin.current === signature(state.novelId, { sessionToken: state.sessionToken, actor: state.actor, scope: state.scope });
  }, []);
  const sameHostIdentity = useCallback(() => {
    const host = useLocalHostSession.getState(), captured = capturedHost.current;
    return !watchHost || host.token === captured.token && host.actorId === captured.actorId && host.epoch === captured.epoch;
  }, [watchHost]);
  const current = useCallback(() => {
    if (!sameStudioIdentity() || !sameHostIdentity()) authorityLost.current = true;
    return alive.current && !revoked.current && !authorityLost.current;
  }, [sameStudioIdentity, sameHostIdentity]);
  const deny = useCallback(() => { revoked.current = true; selectionEpoch.current++; overviewEpoch.current++; storageEpoch.current++; assetReadEpoch.current++; overviewReading.current?.abort(); storageRequest.current?.abort(); setDenied(true); setSelected(undefined); setRows([]); setOverview(undefined); setStorage(undefined); setProductionJob(undefined); setPendingDeclaration(undefined); setPendingNavigation(undefined); setDiscard(false); setLineageDirty(false); setRelationshipDirty(false); mediaDirtyRef.current = false; timelineDirtyRef.current = false; setMediaDirty(false); setTimelineDirty(false); }, []);
  const retireIdentity = useCallback(() => {
    authorityLost.current = true; setIdentityRetired(true);
    selectionEpoch.current++; overviewEpoch.current++; storageEpoch.current++; assetReadEpoch.current++;
    overviewReading.current?.abort(); storageRequest.current?.abort();
    setSelected(undefined); setRows([]); setOverview(undefined); setStorage(undefined); setProductionJob(undefined);
    setPendingDeclaration(undefined); setPendingNavigation(undefined); setDiscard(false); setError(''); setNotice(''); setLoading(false);
  }, []);
  useEffect(() => {
    // Observe every transition synchronously, including A -> B -> A inside one React batch.
    // Redraw immediately to hide adopted data; only local authored graph text remains read-only.
    const studioChanged = () => { if (!sameStudioIdentity()) retireIdentity(); };
    const hostChanged = () => { if (!sameHostIdentity()) { authorityLost.current = true; deny(); } };
    const unsubscribeStudio = useStudio.subscribe(studioChanged);
    const unsubscribeHost = useLocalHostSession.subscribe(hostChanged);
    studioChanged(); hostChanged();
    return () => { unsubscribeStudio(); unsubscribeHost(); };
  }, [sameStudioIdentity, sameHostIdentity, deny, retireIdentity]);
  const guarded = useCallback(async <T,>(operation: () => Promise<T>, signal?: AbortSignal): Promise<T> => {
    if (signal?.aborted) throw new DOMException('读取已取消。', 'AbortError');
    if (!current()) throw new Error('项目或会话已改变，请重新打开。');
    try {
      const result = await operation();
      if (signal?.aborted) throw new DOMException('读取已取消。', 'AbortError');
      if (!current()) throw new Error('项目或会话已改变，请重新打开。');
      return result;
    } catch (reason) {
      // A cancelled read no longer owns the visible selection. Active reads and
      // every mutation still revoke the workspace after authoritative denial.
      if (!signal?.aborted && current() && reason instanceof ApiError && [401, 403].includes(reason.status)) deny();
      throw reason;
    }
  }, [current, deny]);
  const writable = overview?.capabilities.can_mutate === true && !denied && !identityRetired;
  cutoutPermission.current = writable;
  const graphMutation = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
    if (busyRef.current || !current()) throw new Error('当前操作尚未结束，请先核对结果。');
    busyRef.current = true; setBusy(true);
    try { return await guarded(operation); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  }, [current, guarded]);
  // This exception belongs to the original workspace semaphore, not to a second
  // mutation owner: only the same executing cutout's read/CAS cancel may overlap.
  const sameCutout = (expected: ProductionJob, value: ProductionJob) => value.operation_id === 'm5.image.cutout' && value.owner === 'image'
    && value.id === expected.id && value.novel_id === expected.novel_id && value.branch_id === expected.branch_id
    && value.request_id === expected.request_id && value.request_digest === expected.request_digest && value.version >= expected.version;
  const cutoutExecution = {
    execute: (job: ProductionJob) => graphMutation(async () => {
      if (!writable || job.operation_id !== 'm5.image.cutout' || job.owner !== 'image' || job.status !== 'QUEUED') throw new Error('当前不能执行此本地任务。');
      const lease = { job } as NonNullable<typeof cutoutLease.current>; cutoutLease.current = lease;
      try { return await productionClient.execute(job); }
      finally {
        // A late execute cannot release other workspace mutations while its
        // exact cancellation/read still owns the semaphore.
        if (lease.control) await lease.control.catch(() => undefined);
        if (cutoutLease.current === lease) cutoutLease.current = undefined;
      }
    }),
    control: (kind: 'read' | 'cancel', expected: ProductionJob) => {
      const lease = cutoutLease.current;
      if (!lease || lease.control || !busyRef.current || !current() || !cutoutPermission.current || !sameCutout(lease.job, expected))
        return Promise.reject(new Error('当前没有可核对的本地抠图执行。'));
      const work = guarded(async () => {
        const original = await productionClient.get('image', lease.job.id);
        if (!current() || !cutoutPermission.current || cutoutLease.current !== lease || !sameCutout(expected, original)) throw new Error('原本地任务版本未确认，请重新读取。');
        if (kind === 'read' || !['QUEUED', 'RUNNING', 'UNKNOWN', 'AWAITING_REVIEW'].includes(original.status)) return original;
        const cancelled = await productionClient.cancel(original);
        if (!current() || !cutoutPermission.current || cutoutLease.current !== lease || !sameCutout(original, cancelled) || cancelled.version <= original.version
          || cancelled.status !== 'CANCELLED') throw new Error('取消回执未确认，请读取原任务核对。');
        return cancelled;
      });
      lease.control = work;
      void work.finally(() => { if (lease.control === work) lease.control = undefined; }).catch(() => undefined);
      return work;
    },
  };
  const adoptPreferences = useCallback((value: StudioPreferences) => { setOverview(previous => previous && { ...previous, preferences: value }); }, []);
  const graphDraftBlocked = useCallback(() => graphDirtyRef.current || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current, []);
  const operationPending = useCallback(() => busyRef.current, []);
  const preferenceController = useStudioWorkspacePreferences({ initial: overview?.preferences, denied: denied || identityRetired, canMutate: writable, busy, externalDirty: lineageDirty || relationshipDirty || mediaDirty || timelineDirty || maskDirty,
    client, isCurrent: current, read: guarded, mutate: graphMutation, onAdopt: adoptPreferences, isExternallyDirty: graphDraftBlocked });
  const preferenceDirty = preferenceController.dirty || preferenceController.blocked;
  const rememberGraphLocation = useCallback((selection: { graphId?: string; runId?: string }) => {
    if (current()) setGraphLocation(previous => previous.graphId === selection.graphId && previous.runId === selection.runId ? previous : selection);
  }, [current]);
  const graph = useStudioGraphEditor({ active: graphView && overview?.project.entry_kind === 'NEUTRAL_STUDIO', denied, identity: cacheKey, client, canMutate: writable, canReview: overview?.capabilities.can_review === true && !denied, busy, externalDirty: preferenceDirty || lineageDirty || relationshipDirty, isCurrent: current, read: guarded, mutate: graphMutation,
    requestedGraphId: graphLocation.graphId, requestedRunId: graphLocation.runId, onSelectionChange: rememberGraphLocation, isBusy: operationPending });
  graphDirtyRef.current = graph.dirty;
  // One additive read-only workflow projection over the same captured Studio transport.
  // It is mounted content only: no second owner, no execution and no shell change.
  const workflowClient = useMemo(() => createProductionWorkflowClient(projectId,
    studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined }), context.scope),
    [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const modelSource = useMemo(() => ({ load: () => api.modelCenterModels({ ...context, scope: context.scope ? { ...context.scope } : undefined })
    .then(value => { if (!value || !Array.isArray(value.items)) throw new Error('模型注册表不可用。'); return value.items; }) }),
    [context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const workflow = useProductionWorkflow({ identity: cacheKey,
    active: productionView && overview?.project.entry_kind === 'NEUTRAL_STUDIO' && !denied && !identityRetired,
    denied: denied || identityRetired, busy, isCurrent: current, read: guarded, mutate: graphMutation, client: workflowClient,
    onDirtyChange: workflowDraftChanged, onUnavailable: deny });
  // UX-01 entry controller over the same captured Studio transport. It lists the
  // original projects, creates through the original blank-project owner and reads
  // or replaces the saved intent; it executes no generation. It is active only
  // while the start surface is actually on screen, so a normal session issues no
  // extra request at all.
  const startVisible = authoredLocally && !denied && !identityRetired
    && overview?.project.entry_kind === 'NEUTRAL_STUDIO' && workspaceView === 'START'
    && !rows.length && !selected;
  const entryClient = useMemo(() => createStudioEntryClient(studioTransport({
    ...context, scope: context.scope ? { ...context.scope } : undefined }), projectId),
    [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const entry = useStudioEntry({ client: entryClient, identity: cacheKey, active: startVisible, projectId });
  const dirty = preferenceDirty || lineageDirty || relationshipDirty || graph.dirty || mediaDirty || timelineDirty || maskDirty || workflowDirty;
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const lineageDirtyRef = useRef(lineageDirty); lineageDirtyRef.current = lineageDirty;
  const relationshipDirtyRef = useRef(relationshipDirty); relationshipDirtyRef.current = relationshipDirty;
  const refresh = useCallback(async () => {
    if (busyRef.current || !current()) return;
    overviewReading.current?.abort(); const abort = new AbortController(); overviewReading.current = abort;
    const epoch = ++overviewEpoch.current;
    setLoading(true); setError('');
    try {
      const value = await guarded(() => client.overview(abort.signal));
      if (value.project.id !== projectId || value.project.entry_kind !== 'NEUTRAL_STUDIO') throw new Error('当前项目尚未启用独立工作区，请返回项目列表重新选择。');
      if (!value.capabilities || !value.preferences || !Number.isSafeInteger(value.preferences.version) || !Array.isArray(value.preferences.intents)) throw new Error('项目能力或偏好数据不可用，请重新读取。');
      if (current() && epoch === overviewEpoch.current && !abort.signal.aborted) { setOverview(value); verifiedCallback.current?.(projectId); }
    } catch (reason) { if (current() && epoch === overviewEpoch.current && !abort.signal.aborted) setError(apiErrorView(reason, '项目读取失败。').message); }
    finally { if (current() && epoch === overviewEpoch.current) setLoading(false); }
  }, [client, current, guarded, projectId]);
  useEffect(() => { alive.current = true; void refresh(); return () => { alive.current = false; overviewEpoch.current++; storageEpoch.current++; selectionEpoch.current++; overviewReading.current?.abort(); storageRequest.current?.abort(); }; }, [refresh]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty || busyRef.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    if (!overview || context.scope || context.sessionToken || context.actor || !current()) return;
    if (!rememberLocalWorkspaceSelection(projectId) || !rememberLocalStudioSelection(projectId, module, selected?.id)
      || !rememberLocalStudioResume(projectId, { module, view: workspaceView, stage: productionStage, interfaceMode, ...graphLocation })) setNotice('浏览器无法记住本次选择；已保存内容仍在服务端，可以从项目列表重新打开。');
  }, [overview, context.scope, context.sessionToken, context.actor, current, projectId, module, selected?.id, workspaceView, productionStage, interfaceMode, graphLocation]);
  const invalidateStorage = useCallback(() => { storageEpoch.current++; storageRequest.current?.abort(); storageReading.current = false; setStorageLoading(false); setStorage(undefined); }, []);
  const loadProductionAssets = useCallback(async () => {
    if (!current() || busyRef.current) return;
    const epoch = ++assetReadEpoch.current;
    try {
      const value = await graphMutation(() => client.assets());
      if (current() && epoch === assetReadEpoch.current) setRows(value.items);
    } catch (reason) { if (current() && epoch === assetReadEpoch.current) setNotice(apiErrorView(reason, '素材列表读取失败。').message); }
  }, [current, graphMutation, client]);
  const productionApproved = useCallback(async () => {
    invalidateStorage(); await loadProductionAssets();
    if (current()) void query.invalidateQueries({ queryKey: [cacheKey, projectId, 'assets'] });
  }, [invalidateStorage, loadProductionAssets, current, query, cacheKey, projectId]);
  useEffect(() => {
    if (productionView && overview && !denied) void loadProductionAssets();
  }, [productionView, overview?.project.id, denied, loadProductionAssets]);
  const refreshedAsset = useCallback((asset: StudioAsset) => {
    selectionEpoch.current += 1;
    setSelected(asset); setRows(previous => [...previous.filter(row => row.id !== asset.id), asset]); setLineageDirty(false); setRelationshipDirty(false);
    void query.invalidateQueries({ queryKey: [cacheKey, projectId, 'assets'] });
    invalidateStorage();
  }, [query, cacheKey, projectId, invalidateStorage]);
  const declared = useCallback((asset: StudioAsset) => client.lineage(asset.id, { expected_version: asset.version, origin: 'EXTERNAL_IMPORT', parent_asset_ids: [], chapter_ids: [], license: { label: 'UNSPECIFIED', source: '', note: '' }, operation: '外部文件导入' }), [client]);
  const adapter = useMemo<AssetLibraryAdapter>(() => ({
    cacheKey, canMutate: writable, mutationsBlocked: dirty || busy, canImport: overview?.capabilities.manual_import === true && overview.capabilities.media_validator_configured, isCurrent: current,
    list: async () => { const result = await guarded(() => client.assets()); setRows(result.items); return result.items; },
    upload: async body => {
      if (!writable || !overview?.capabilities.media_validator_configured || !['image', 'video', 'audio'].includes(body.kind)) throw new Error('请核对媒体校验工具，并选择支持的图片、音频或视频文件。');
      if (busyRef.current || dirtyRef.current) throw new Error('请先保存或放弃当前输入，再导入其他资产。');
      busyRef.current = true; setBusy(true); setNotice('');
      const identity = JSON.stringify([body.filename, body.kind, body.content_base64]);
      if (lastImport.current?.body !== identity) lastImport.current = { body: identity, key: crypto.randomUUID() };
      try {
        const imported = await guarded(() => client.importAsset({ filename: body.filename, kind: body.kind as 'image' | 'video' | 'audio', content_base64: body.content_base64, idempotency_key: lastImport.current!.key }));
        // Saving provenance is a second mutation. A failed declaration never repeats the import.
        try { const asset = await guarded(() => declared(imported)); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); return asset; }
        catch (reason) { if (!current()) throw reason; setPendingDeclaration(imported); setNotice('文件已保存，来源声明尚未保存。可仅重试声明，无需重新上传。'); return imported; }
      } finally { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }
    },
    download: asset => overview?.capabilities.manual_export === true ? guarded(() => client.download(asset.id)) : Promise.reject(new Error('当前无法导出资产。')),
    remove: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能删除资产。')); busyRef.current = true; setBusy(true); return guarded(() => client.remove(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }); },
    trash: async () => { const value = await guarded(() => client.assets(true)); const items = value.items.filter(asset => !!asset.deleted_at); return { items, total: items.length }; },
    restore: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能恢复资产。')); busyRef.current = true; setBusy(true); return guarded(() => client.restore(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }); },
  }), [cacheKey, writable, dirty, busy, overview?.capabilities.manual_import, overview?.capabilities.manual_export, overview?.capabilities.media_validator_configured, current, guarded, client, declared, invalidateStorage]);
  useEffect(() => {
    if (!overview || !requestedAssetId) return;
    let active = true; const epoch = ++selectionEpoch.current;
    void guarded(() => client.asset(requestedAssetId)).then(asset => { if (active && epoch === selectionEpoch.current) setSelected(asset); }).catch(reason => { if (active && epoch === selectionEpoch.current && current()) setNotice(apiErrorView(reason, '上次资产当前不可读，请重新选择。').message); });
    return () => { active = false; };
  }, [overview?.project.id, requestedAssetId, guarded, client, current]);
  const loadStorage = async () => {
    if (storageReading.current || !current()) return;
    const epoch = ++storageEpoch.current, abort = new AbortController(); storageRequest.current = abort;
    storageReading.current = true; setStorageLoading(true);
    try { const value = await guarded(() => client.storage(abort.signal)); if (current() && epoch === storageEpoch.current) setStorage(value); }
    catch (reason) { if (current() && epoch === storageEpoch.current && !abort.signal.aborted) setNotice(apiErrorView(reason, '存储统计读取失败。').message); }
    finally { if (epoch === storageEpoch.current) { storageReading.current = false; storageRequest.current = undefined; if (current()) setStorageLoading(false); } }
  };
  const refreshSelectedAsset = async (assetId: string) => {
    if (busyRef.current || !current()) return;
    const epoch = ++selectionEpoch.current;
    busyRef.current = true; setBusy(true); setReadingAsset(true);
    try { const asset = await guarded(() => client.asset(assetId)); if (epoch === selectionEpoch.current) refreshedAsset(asset); }
    catch (reason) { if (current()) setNotice(apiErrorView(reason, '资产读取失败。').message); }
    finally { busyRef.current = false; if (alive.current) { setBusy(false); setReadingAsset(false); } }
  };
  const navigate = (action: () => void) => {
    if (!current()) return;
    if (busyRef.current) { setNotice('当前操作尚未结束，请等待结果确认后再离开。'); return; }
    if (dirty || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current || workflowDirtyRef.current) { setDiscard(false); setPendingNavigation(() => action); return; }
    action();
  };
  const confirmNavigation = () => {
    if (!discard || !pendingNavigation || !current()) return;
    if (busyRef.current || preferenceController.pending) { setNotice('当前操作尚未结束，未放弃输入或离开。请先核对结果。'); return; }
    const action = pendingNavigation; setPendingNavigation(undefined); setDiscard(false);
    setLineageDirty(false); setRelationshipDirty(false); setFormRevision(value => value + 1); preferenceController.discard(); graph.discard();
    mediaDraftChanged(false); timelineDraftChanged(false); maskDraftChanged(false); workflow.skip(); setProductionRevision(value => value + 1); setProductionJob(undefined); action();
  };
  const sidebar = <div className="independent-studio-sidebar"><h2>独立创作</h2><p>图片、视频和声音共享项目资产。连接其它模块由你决定。</p><Button onClick={() => navigate(onProjectChoice)}>返回项目列表</Button>
    <StudioWorkspacePreferencesForm controller={preferenceController} locked={graph.dirty || mediaDirty || timelineDirty || maskDirty} />
    <details onToggle={event => { if (event.currentTarget.open && !storage && overview) void loadStorage(); }}><summary>项目存储</summary>{storageLoading && <StatusMessage>正在核对项目存储…</StatusMessage>}{storage ? <><p>有效资产 {storage.assets.count} 项 · {storage.assets.bytes} 字节</p><p>回收站 {storage.trash.count} 项 · {storage.trash.bytes} 字节</p>
      {storage.admission?.state === 'READY' && <p>当前可导入容量估算：{storage.admission.available_import_bytes} 字节；已扣除安全预留空间和项目配额。</p>}
      {storage.admission?.state === 'LOW_SPACE_OR_QUOTA' && <StatusMessage tone="warning">空间或项目配额不足，当前无法继续导入。已有资产仍可查看和导出。</StatusMessage>}
      {storage.admission?.state === 'UNAVAILABLE' && <StatusMessage tone="warning">当前无法确认存储容量，导入将由服务端安全校验。</StatusMessage>}
      {!storage.admission && <p>容量校验状态尚未提供，上传仍由服务端核对。</p>}
      <p>以上为查询时估算；实际上传会再次校验。回收站仍占用空间，不会自动清理。</p><p>模型目录仅引用；缓存单独管理；导出位置由下载时选择。</p><p>本入口不清理或移动任何外部模型文件。</p></> : <p>展开后读取服务端统计。</p>}<Button disabled={!overview || storageLoading} onClick={() => void loadStorage()}>刷新存储统计</Button></details>
  </div>;
  const maskEpoch = selectionEpoch.current;
  const main = <div className="independent-studio">
    {overview && !denied && <div className="studio-graph-actions" aria-label="独立工作区内容"><Button aria-pressed={workspaceView === 'START'} onClick={() => navigate(() => setWorkspaceView('START'))}>创作开始</Button><Button aria-pressed={workspaceView === 'TASKS'} onClick={() => navigate(() => setWorkspaceView('TASKS'))}>任务中心</Button><Button aria-pressed={workspaceView === 'ASSETS'} onClick={() => navigate(() => setWorkspaceView('ASSETS'))}>素材工作区</Button>{interfaceMode === 'PROFESSIONAL' && <Button aria-pressed={graphView} onClick={() => navigate(() => setWorkspaceView('GRAPH'))}>创作图</Button>}<Button aria-pressed={productionView} onClick={() => navigate(() => setWorkspaceView('PRODUCTION'))}>制作操作</Button><InterfaceModeSwitch mode={interfaceMode} onChange={changeInterfaceMode} /></div>}
    {workspaceView === 'TASKS' && !denied && <TaskCenterPanel projectId={projectId}
      transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })}
      scope={context.scope} identity={cacheKey} active={workspaceView === 'TASKS' && !denied && !identityRetired}
      denied={denied || identityRetired} busy={busy} isCurrent={current} read={guarded} mutate={graphMutation}
      onNavigate={target => { if (!current()) return; if (target.queue === 'TASKS') { navigate(() => setWorkspaceView('PRODUCTION')); setNotice(`已定位到原任务 ${target.task_id}（${target.authority}）：这里只发出定位回调，没有重新提交模型或渲染。`); } else { navigate(() => setWorkspaceView('ASSETS')); setNotice(`已定位到待审候选 ${target.item_id}（${target.domain}）：请在对应工作区按原版本复核。`); } }}
      onUnavailable={deny} />}
    {startVisible && <StudioStartPanel controller={entry} onOpenProject={id => {
      if (id === projectId) { navigate(() => setWorkspaceView(resume.state === 'SAVED' ? resume.location.view : 'ASSETS')); setNotice('已回到本项目保存的位置。'); return; }
      setNotice(`项目“${id}”已经存在；请从项目列表打开它，当前工作区不会自动切换，也不会为它新建任何内容。`);
    }} mode={interfaceMode} onModeChange={changeInterfaceMode} />}
    {workspaceView === 'ASSETS' && <Panel title="独立素材工作区"><p>无需小说、章节或模型，导入素材即可保存和导出。</p><p>上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。</p>{overview && <Badge tone="info">{!writable ? overview.capabilities.can_review === true ? '仅审核与读取' : '只读' : overview.capabilities.media_validator_configured ? '手工导入可用' : '媒体校验工具缺失'} · 不需要模型</Badge>}{overview && !overview.capabilities.media_validator_configured && <p>图片、视频和音频导入需要 FFmpeg / ffprobe 校验工具。当前可查看和导出已保存资产，未调用模型。</p>}</Panel>}
    {loading && <StatusMessage>正在核对项目与权限…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {denied ? <EmptyState title="当前会话无权访问此项目" detail="私人预览已关闭。重新核对身份与范围后再打开。" /> : !overview && !loading ? <Button onClick={() => void refresh()}>重新读取项目</Button> : null}
    {pendingNavigation && !denied && <section className="creative-navigation-confirm" role="alert"><p>{mediaDirty || timelineDirty ? '制作输入尚未保存，或请求结果仍待核对。离开只放弃本地输入，不会取消远端任务；重新打开后先读取原任务回执。' : graph.dirty ? '有未保存的创作图输入。可以继续编辑，或确认放弃后离开。' : preferenceController.blocked ? '偏好保存结果尚待核对。离开不代表请求失败，再次操作前仍需读取服务端版本。' : '有未保存的偏好、来源声明或资产关联。可以继续编辑，或确认放弃后离开。'}</p><label><input type="checkbox" disabled={busy || !!preferenceController.pending} checked={discard} onChange={event => setDiscard(event.target.checked)} />确认放弃未保存输入</label><Button disabled={!discard || busy || !!preferenceController.pending} onClick={confirmNavigation}>确认离开</Button><Button onClick={() => { setPendingNavigation(undefined); setDiscard(false); }}>继续编辑</Button></section>}
    {pendingDeclaration && !denied && workspaceView === 'ASSETS' && <Button disabled={!writable || busy || lineageDirty || relationshipDirty} onClick={() => { if (busyRef.current || lineageDirtyRef.current || relationshipDirtyRef.current) return; busyRef.current = true; setBusy(true); void guarded(() => declared(pendingDeclaration)).then(asset => { refreshedAsset(asset); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); }).catch(reason => { if (current()) setNotice(apiErrorView(reason, '来源声明仍未保存，文件已保留。').message); }).finally(() => { busyRef.current = false; if (alive.current) setBusy(false); }); }}>仅重试外部导入声明</Button>}
    {graphView && overview && !denied && graph.content}
    {productionView && overview && !denied && <ProductionDashboard controller={workflow} selectedModuleId={workflowModule}
      onSelectModule={setWorkflowModule} selectedKind={workflowAssetKind} onSelectKind={setWorkflowAssetKind} />}
    {productionView && overview && !denied && interfaceMode === 'PROFESSIONAL' && <StudioWorkspaceOperationPanel identity={cacheKey} denied={denied} busy={busy}
      isCurrent={current} read={guarded} loadContracts={client.productionContracts} requestedStage={productionStage}
      onStageChange={setProductionStage} onUnavailable={deny} onOpenSurface={view => navigate(() => setWorkspaceView(view))} />}
    {productionView && overview && !denied && interfaceMode === 'NOVICE' && <Panel title="制作操作（新手模式）">
      <p>新手模式只展开主要操作：素材执行、时间线与任务中心都在本页或“任务中心”里。制作操作契约、阶段与来源详情属于专业视图。</p>
      <p>两种模式使用同一份项目、素材、任务与草稿；切换不会转换、复制或删除任何数据。</p>
      <Button onClick={() => changeInterfaceMode('PROFESSIONAL')}>切换到专业模式查看契约与参数</Button>
    </Panel>}
    {productionView && overview && !denied && <>
      <Button disabled={busy} onClick={() => void loadProductionAssets()}>读取当前素材版本</Button>
      <StudioMediaExecutionPanel key={`media:${cacheKey}:${productionRevision}`} client={productionClient} assets={rows}
        canMutate={writable && !preferenceDirty && !lineageDirty && !relationshipDirty} canReview={overview.capabilities.can_review === true}
        busy={busy} isBusy={operationPending} isCurrent={current} read={guarded} mutate={graphMutation} cutoutExecution={cutoutExecution}
        onDirtyChange={mediaDraftChanged} onUnavailable={deny} externalJob={productionJob?.client === productionClient ? productionJob.job : undefined} onApproved={productionApproved} />
      <StudioTimelineEditor key={`timeline:${cacheKey}:${productionRevision}`} client={productionClient} assets={rows}
        canMutate={writable && !preferenceDirty && !lineageDirty && !relationshipDirty} busy={busy} isBusy={operationPending}
        isCurrent={current} read={guarded} mutate={graphMutation} onDirtyChange={timelineDraftChanged} onUnavailable={deny}
        onJob={job => { if (current()) setProductionJob({ client: productionClient, job }); }} />
    </>}
    {workspaceView === 'ASSETS' && overview && !denied && <AssetLibraryPanel novelId={projectId} adapter={adapter} selectedAssetId={selected?.id} onSelectAsset={asset => navigate(() => { selectionEpoch.current += 1; setSelected(asset); setLineageDirty(false); setRelationshipDirty(false); })} />}
    {module === 'IMAGE' && workspaceView === 'ASSETS' && overview && !denied && selected && <StudioManualMaskPanel
      key={`mask:${cacheKey}:${maskEpoch}:${selected.id}:${selected.version}:${selected.sha256}:${formRevision}`} asset={selected} client={client}
      canMutate={writable && !preferenceDirty && !lineageDirty && !relationshipDirty} busy={busy} isBusy={operationPending}
      isCurrent={current} isSourceCurrent={() => selectionEpoch.current === maskEpoch} watchHost={watchHost} read={guarded} mutate={graphMutation}
      onDirtyChange={maskDraftChanged} onUnavailable={deny} onSaved={result => {
        if (!current() || selectionEpoch.current !== maskEpoch) return;
        setRows(previous => [...previous.filter(row => row.id !== result.asset.id), result.asset]); invalidateStorage();
        void query.invalidateQueries({ queryKey: [cacheKey, projectId, 'assets'] });
      }} onOpenAsset={id => navigate(() => { void refreshSelectedAsset(id); })} onRefreshAssets={() => { void loadProductionAssets(); }} />}
  </div>;
  const extra = selected && <>{selected.provenance && <section className="independent-studio-lineage" aria-label="独立资产来源"><p>版本 v{selected.version} · {selected.provenance.origin} · {selected.provenance.integrity}</p><p>许可：{selected.provenance.license.label}（作者声明，未作法律验证）</p>{selected.provenance.stale && <StatusMessage tone="warning">来源已变化或不可用，请核对后再复用。</StatusMessage>}
    <StudioAssetDeclarationForm key={`${selected.id}:${selected.version}:${formRevision}`} row={lineageAsset(selected)} assets={rows.map(lineageAsset)} readOnly={!writable || busy || relationshipDirty || maskDirty} onDirtyChange={setLineageDirty} saved={() => {}} saveLineage={async body => { if (busyRef.current || !writable || relationshipDirtyRef.current || maskDirtyRef.current) throw new Error('请先保存或放弃关联输入，再保存来源声明。'); busyRef.current = true; setBusy(true); try { const value = await guarded(() => client.lineage(selected.id, body)); refreshedAsset(value); setNotice('来源声明已保存。'); return value; } finally { busyRef.current = false; if (alive.current) setBusy(false); } }} />
    <Button disabled={busy} onClick={() => navigate(() => { void refreshSelectedAsset(selected.id); })}>重新读取当前资产</Button>
  </section>}
    <AssetRelationshipsPanel key={`${selected.id}:${selected.version}:${formRevision}`} asset={selected} client={client} canMutate={writable} canReview={overview?.capabilities.can_review === true && !denied} blocked={lineageDirty || maskDirty} busy={busy} isCurrent={current} read={guarded} onDirtyChange={setRelationshipDirty} mutate={async operation => {
      if (busyRef.current || lineageDirtyRef.current || maskDirtyRef.current || !current()) throw new Error('请先保存或放弃来源输入，再修改关联。');
      busyRef.current = true; setBusy(true);
      try { const asset = await guarded(operation); refreshedAsset(asset); setNotice('关联已保存，原文件和引用内容未改变。'); return asset; }
      finally { busyRef.current = false; if (alive.current) setBusy(false); }
    }} />
  </>;
  const retiredNotice = <EmptyState title="身份已改变" detail="原范围的服务端信息已关闭。请重新核对身份与项目后打开工作区。" />;
  return <AppShell module={module} onModuleChange={next => navigate(() => onModuleChange(next))} scope={identityRetired ? { workspace: '待核对', project: '待核对', storyline: '待核对', branch: '待核对' } : { ...scope, project: overview?.project.title || scope.project }} projectNoun={overview?.project.entry_kind === 'NEUTRAL_STUDIO' ? '项目' : undefined} actor={identityRetired ? '身份待核对' : actor} sidebar={identityRetired ? retiredNotice : sidebar} main={identityRetired ? graphView ? graph.content : retiredNotice : main}
    inspector={identityRetired ? graphView ? graph.inspector : retiredNotice : denied ? <EmptyState title="权限失效" detail="重新核对身份与项目范围后再打开。" /> : graphView ? graph.inspector : productionView ? <><Panel title="制作操作"><p>当前阶段：{productionStage}</p><p>在主工作区核对输入、版本、来源和审核要求。实际任务的权限、状态与回执由原执行入口确认。</p></Panel><ProductionInspectorPanel controller={workflow} selectedModuleId={workflowModule} selectedKind={workflowAssetKind} onSelectKind={setWorkflowAssetKind} modelSource={modelSource}/></> : <AssetInspector asset={selected} novelId={projectId} downloadAsset={adapter.download} isCurrent={current} showReferences={false} extra={extra} />}
    status={<>{identityRetired ? '身份已改变' : denied ? '权限失效' : loading ? '正在核对' : error ? '读取失败' : busy ? readingAsset || preferenceController.pending === 'READ' ? '读取中' : '操作中' : dirty || pendingDeclaration ? '未保存或待核对' : '已保存'} · {productionView ? '制作操作' : graphView ? '创作图' : '独立素材'} · 模型调用记录见运行回执{!identityRetired && status}</>} />;
}
