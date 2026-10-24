import { StudioProductionLeaveContext } from './studioProductionLeaveRisk';
import type { StudioProductionLeaveGuard, StudioProductionLeaveRisk } from './studioProductionLeaveRisk';
import { StudioComicPanel } from './StudioComicPanel';
import { StudioVideoReferencePanel } from './StudioVideoReferencePanel';
import { StudioProductionTasksPanel } from '../taskcenter/StudioProductionTasks';
import type { StudioProductionTask } from '../taskcenter/studioProductionTask';
import { prepareCanvasImageNodeResume, type CanvasImageNodeResume } from './canvasImageNodeResume';
import { CanvasImageNodeTargetPanel } from './CanvasImageNodeTargetPanel';
import { CanvasImageNodeJobObservationPanel } from './CanvasImageNodeJobObservationPanel';
import { CanvasImageNodeJobDiscardPanel } from './CanvasImageNodeJobDiscardPanel';
import { canonicalImageNode, canvasImageNodeInCommand } from './canvasImageNode';
import { StudioModelReferencePanel } from './StudioModelReferencePanel';
import { CreativeWorkspace } from './CreativeWorkspace';
import { checkedStoryboardCapabilities, prepareStoryboardEditor, type OpenStoryboardEditor, type PreparedStoryboardEditor } from './storyboardEditorHandoff';
import { StudioStoryboardAssetHandoff } from './StudioStoryboardAssetHandoff';
import type { TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, apiErrorView, api, type Asset, type CollaborationContext, type ModelCenterModel } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { AppShell, type ScopeLabels, type StudioModule } from '../ui/AppShell';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { PromptWorkspace } from '../prompt/PromptWorkspace';
import { AssetLibraryPanel, type AssetLibraryAdapter } from '../novel/AssetLibraryPanel';
// UX-PRODUCT batch 4: the model/storage centre (UX-07) and the in-project hint
// assistant (UX-08). Both are read-only and open on demand.
import { ModelCenterPanel } from '../modelcenter/ModelCenterPanel';
import { ProjectGuidePanel } from '../guide/ProjectGuidePanel';
// UX-PRODUCT batch 5 (UX-09): the unified export and handover centre. Read-only:
// it can only read export receipts and refuse a format it has no owner for.
import { DeliveryCenterPanel } from '../delivery/DeliveryCenterPanel';
import { AssetInspector } from '../novel/AssetInspector';
import type { LineageAsset } from '../experimental/ProductionLineagePanel';
import { StudioAssetDeclarationForm } from './StudioAssetDeclarationForm';
import { studioClient, studioTransport, type StudioAsset, type StudioOverview, type StudioComicWorkspace, type StudioPreferences, type StudioStorage } from './studioClient';
import { rememberLocalStudioSelection, rememberLocalWorkspaceSelection, type LocalStudioModule } from '../workspaceSelection';
import { creativeClient } from './client';
import { useStudioGraphEditor } from './useStudioGraphEditor';
import { studioGraphDraftOwner } from './studioGraphLocalDraft';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import type { AssetReferencePin } from './AssetReferenceInspection';
import { StudioWorkspaceOperationPanel } from './StudioWorkspaceOperationPanel';
import { readLocalStudioInterfaceMode, readLocalStudioResume, rememberLocalStudioInterfaceMode, rememberLocalStudioResume, type StudioInterfaceMode, type StudioWorkspaceLocation, type StudioWorkspaceStage, type StudioWorkspaceView } from './studioWorkspaceResume';
import { useStudioWorkspacePreferences } from './useStudioWorkspacePreferences';
import { StudioWorkspacePreferencesForm } from './StudioWorkspacePreferencesForm';
import { studioProductionClient, type ProductionJob, type StudioImageNodeJobDiscard, type StudioImageNodeJobObservation } from './studioProductionClient';
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
import { TaskOwnerResult } from '../taskcenter/TaskOwnerResult';
import type { TaskCenterNavigationTarget } from '../taskcenter/taskCenterTypes';
// UX-PRODUCT batch 2 (UX-03): the reuse-oriented asset browser. Additive content in
// the ASSETS view; it reads through the same captured transport and never copies an
// asset, executes a target module or physically deletes a file.
import { AssetBrowserPanel } from '../assetbrowser/AssetBrowserPanel';
import { StudioStartPanel } from '../onboarding/StudioStartPanel';
import { InterfaceModeSwitch } from '../onboarding/InterfaceModeSwitch';
import { createStudioEntryClient } from '../onboarding/studioEntryClient';
import { useStudioEntry } from '../onboarding/useStudioEntry';
import './independentStudio.css';

export const isManualStudioModule = (module: StudioModule): module is LocalStudioModule => ['IMAGE', 'ASSETS', 'VIDEO', 'AUDIO', 'EDIT'].includes(module);
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
  requestedAssetId?: string; onOpenBroker?: () => void; onModuleChange: (module: StudioModule) => void; onProjectChoice: () => void; onVerified?: (projectId: string) => void; status?: ReactNode };
type NodeResumeSource = CanvasImageNodeResume & { ticket: number; selectionEpoch: number; module: LocalStudioModule };
type DiscardTrace = { key: string; ownerKey: string; projectId: string; incarnation: string; jobId: string; requestId: string; requestDigest: string;
  version: number; target: string; state: 'UNKNOWN' | 'ACK_CONFIRMED' | 'STATE_CONFIRMED' };

/** Independent module content; the original shell and asset owners remain authoritative. */
export function IndependentStudioWorkspace(props: IndependentStudioProps) {
  // An explicit Host credential is captured by the transport, independently of
  // the store/Host authority signature. Replacing it retires the whole session.
  return <IndependentStudioSession key={JSON.stringify([signature(props.projectId, props.context), props.context.localHostToken])} {...props} />;
}
function IndependentStudioSession({ projectId, context, scope, actor, module, requestedAssetId, onOpenBroker, onModuleChange, onProjectChoice, onVerified, status }: IndependentStudioProps) {
  const query = useQueryClient();
  const [editorSession, setEditorSession] = useState<{ prepared: PreparedStoryboardEditor; ticket: number; module: 'IMAGE' | 'VIDEO' }>();
  const editorTicket = useRef(0), editorPreparing = useRef(false);
  const pendingEditor = useRef<(() => Promise<void>)>();
  const nodeResumeTicket = useRef(0), nodeResumeSourceTicket = useRef(0);
  const targetObservationEpoch = useRef(0), targetObservationContextEpoch = useRef(0);
  const pendingNodeResume = useRef<(() => Promise<void>)>();
  const nodeResumeReading = useRef<{ ticket: number; controller: AbortController }>();
  const nodeResumeSource = useRef<NodeResumeSource>();
  const retirePendingNodeResume = useCallback(() => {
    nodeResumeTicket.current++; pendingNodeResume.current = undefined; nodeResumeReading.current?.controller.abort();
  }, []);
  const editorLocation = useRef(module);
  if (editorLocation.current !== module) { editorLocation.current = module; editorTicket.current++; retirePendingNodeResume(); nodeResumeSource.current = undefined; targetObservationEpoch.current++; targetObservationContextEpoch.current++; if (editorSession) setEditorSession(undefined); }

  const capturedHost = useRef({ ...useLocalHostSession.getState() });
  const productionLeaveScope = useRef(`项目 ${projectId} · 分支 ${context.scope?.branchId ?? 'local'}${context.scope ? ` · 工作区 ${context.scope.workspaceId} · 协作项目 ${context.scope.projectId} · 故事线 ${context.scope.storylineId}` : ''} · 操作者 ${context.actor?.id || capturedHost.current.actorId || actor}`).current;
  const watchHost = !context.sessionToken && !context.scope && !context.actor;
  const origin = useRef(signature(projectId, context));
  const alive = useRef(true), revoked = useRef(false), authorityLost = useRef(false), busyRef = useRef(false);
  const [identityRetired, setIdentityRetired] = useState(false);
  // Retirement closes private controllers permanently. Only the existing Novel
  // navigation may leave for the original Host verification; it grants no authority.
  const navigationEpoch = useRef(0), studioRetired = useRef(false), novelExitCommitted = useRef(false), draftSeen = useRef(false), pendingWrites = useRef(0);
  const leaveRisk = useRef({ dirty: false, unknown: false, comicInFlight: false, requestIds: [] as string[], productionRequests: [] as string[] });
  const captureLeaveRisk = useRef<() => void>(() => {});
  const productionRiskReaders = useRef(new Set<() => StudioProductionLeaveRisk>());
  const leaveGuard = useMemo<StudioProductionLeaveGuard>(() => ({
    register: read => {
      productionRiskReaders.current.add(read);
      return () => { captureLeaveRisk.current(); productionRiskReaders.current.delete(read); };
    },
    capture: () => captureLeaveRisk.current(),
  }), []);
  const [, redrawLeaveGuard] = useState(0);
  const [acknowledgeUnknown, setAcknowledgeUnknown] = useState(false);
  const client = useMemo(() => studioClient(projectId, context), [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const directorSource = useMemo(() => creativeClient(projectId, context), [client]);
  const productionClient = useMemo(() => studioProductionClient(projectId, context), [projectId, context.sessionToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const productionClientRef = useRef(productionClient); productionClientRef.current = productionClient;
  const cutoutPermission = useRef(false);
  const cutoutLease = useRef<{ job: ProductionJob; control?: Promise<ProductionJob> }>();
  const [cacheKey] = useState(() => `independent-studio-${++studioObserver}`);
  const [overview, setOverview] = useState<StudioOverview>(), [rows, setRows] = useState<StudioAsset[]>([]);
  const [comicWorkspace, setComicWorkspace] = useState<StudioComicWorkspace>();
  const comicOnly = module === 'IMAGE' && !!comicWorkspace && !overview;
  const [selected, setSelected] = useState<Asset>(), [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false), [busy, setBusy] = useState(false), [readingAsset, setReadingAsset] = useState(false), [storageLoading, setStorageLoading] = useState(false);
  const [relationshipReviewEpoch, setRelationshipReviewEpoch] = useState<number>();
  const [pendingDeclaration, setPendingDeclaration] = useState<StudioAsset>(), [lineageDirty, setLineageDirty] = useState(false), [relationshipDirty, setRelationshipDirty] = useState(false), [formRevision, setFormRevision] = useState(0), [storage, setStorage] = useState<StudioStorage>();
  const [resume] = useState(() => !context.scope && !context.sessionToken && !context.actor
    ? readLocalStudioResume(projectId) : { state: 'EMPTY' as const });
  const [workspaceView, setWorkspaceView] = useState<StudioWorkspaceView>(resume.state === 'SAVED' ? resume.location.view : (module === 'EDIT' ? 'PRODUCTION' : 'ASSETS')); // [HERMIA-FE-20261022] EDIT cold → 制作操作/时间线
  const workspaceViewRef = useRef(workspaceView); workspaceViewRef.current = workspaceView;
  const targetObservationView = useRef(workspaceView);
  if (targetObservationView.current !== workspaceView) { targetObservationView.current = workspaceView; targetObservationContextEpoch.current++; }
  const targetObservationRenderEpoch = targetObservationContextEpoch.current;
  const defaultCanvasChosen=useRef(resume.state==='SAVED');
  useEffect(()=>{
    if(defaultCanvasChosen.current||!overview)return;
    defaultCanvasChosen.current=true;
    if(module==='IMAGE'&&overview.project.entry_kind==='NEUTRAL_STUDIO')setWorkspaceView(view=>view==='ASSETS'?'GRAPH':view);
  },[module,overview]);
  const [productionStage, setProductionStage] = useState<StudioWorkspaceStage>(resume.state === 'SAVED' ? resume.location.stage : 'M4');
  const [graphLocation, setGraphLocation] = useState<Pick<StudioWorkspaceLocation, 'graphId' | 'runId'>>(resume.state === 'SAVED'
    ? { graphId: resume.location.graphId, runId: resume.location.runId } : {});
  const [taskTarget, setTaskTarget] = useState<{ id: string; target: TaskCenterNavigationTarget }>();
  const taskTransport = useMemo(() => studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined }), [client]);
  // Stable across presentation changes; explicit local credentials also retire asset previews.
  const assetTransport = useMemo(() => studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined }), [client, context.localHostToken]);
  useEffect(() => { if (workspaceView !== 'TASKS') setTaskTarget(undefined); }, [workspaceView]);
  const [storyboardHandoff, setStoryboardHandoff] = useState<TimelineAssetHandoff & { selectionEpoch: number }>();
  const [storyboardDirty, setStoryboardDirty] = useState(false), storyboardDirtyRef = useRef(false);
  const [comicOpen, setComicOpen] = useState(false), [comicDirty, setComicDirty] = useState(false), [comicError, setComicError] = useState('');
  const comicDirtyRef = useRef(false), comicBusyRef = useRef(false);
  const comicDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; comicDirtyRef.current = value; setComicDirty(value); }, []);
  const comicBusyChanged = useCallback((value: boolean) => {
    comicBusyRef.current = value;
    if (alive.current) redrawLeaveGuard(epoch => epoch + 1);
  }, []);
  const storyboardOperation = useRef(false);
  const storyboardOwnsOperation = useCallback(() => storyboardOperation.current, []);
  const storyboardDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; storyboardDirtyRef.current = value; setStoryboardDirty(value); }, []);
  useEffect(() => { if (workspaceView !== 'PRODUCTION') { setStoryboardHandoff(undefined); storyboardDraftChanged(false); } }, [workspaceView, storyboardDraftChanged]);
  const [assetHandoff, setAssetHandoff] = useState<TimelineAssetHandoff>();
  const [mediaHandoff, setMediaHandoff] = useState<TimelineAssetHandoff & { target?: 'IMAGE' | 'VIDEO' }>();
  useEffect(() => { if (workspaceView !== 'PRODUCTION') setMediaHandoff(undefined); }, [workspaceView]);
  useEffect(() => { if (workspaceView !== 'PRODUCTION') setAssetHandoff(undefined); }, [workspaceView]);
  const [modelOpen, setModelOpen] = useState(false), [guideOpen, setGuideOpen] = useState(false), [deliveryOpen, setDeliveryOpen] = useState(false);
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
  const [pendingNavigation, setPendingNavigation] = useState<{ kind: 'CURRENT'; action: () => void; epoch: number; nodeResumeTicket?: number } | { kind: 'NOVEL'; epoch: number }>(), [discard, setDiscard] = useState(false);
  const selectionEpoch = useRef(0), overviewEpoch = useRef(0), storageEpoch = useRef(0), storageReading = useRef(false);
  // A request retires stale callbacks immediately, but the current relationship
  // form remains visibly disabled until that same-source read settles. The new
  // epoch then remounts it even when the returned asset version is unchanged.
  const relationshipRenderEpoch = useRef(selectionEpoch.current);
  if (!readingAsset) relationshipRenderEpoch.current = selectionEpoch.current;
  const overviewReading = useRef<AbortController>(), storageRequest = useRef<AbortController>();
  const graphDirtyRef = useRef(false);
  const [mediaDirty, setMediaDirty] = useState(false), [timelineDirty, setTimelineDirty] = useState(false), [productionRevision, setProductionRevision] = useState(0);
  const [productionJob, setProductionJob] = useState<{ client: typeof productionClient; job: ProductionJob; resume?: NodeResumeSource }>();
  const productionJobRef = useRef(productionJob); productionJobRef.current = productionJob;
  const nodeResumeActive = productionJob?.client === productionClient && !!productionJob.resume;
  const [targetObservation, setTargetObservation] = useState<{ ticket: number; source: { job: StudioProductionTask; key: string; isCurrent: () => boolean } }>();
  const [jobObservation, setJobObservation] = useState<{ ticket: number; source: { job: StudioProductionTask; key: string; isCurrent: () => boolean } }>();
  const [discardPreparation, setDiscardPreparation] = useState<{ ticket: number; source: { job: StudioProductionTask; key: string; isCurrent: () => boolean };
    claim: () => boolean; onConfirmed: (receipt: StudioImageNodeJobDiscard) => void }>();
  const discardClaims = useRef(new Set<string>()), discardTraces = useRef(new Map<string, DiscardTrace>()), discardWrites = useRef(0);
  const [discardTraceRows, setDiscardTraceRows] = useState<DiscardTrace[]>([]);
  const unknownDiscard = () => [...discardTraces.current.values()].some(row => row.state === 'UNKNOWN');
  const unknownLeaveRisk = () => leaveRisk.current.unknown || unknownDiscard();
  const publishDiscardTraces = () => { if (alive.current) setDiscardTraceRows([...discardTraces.current.values()]); };
  // Selection state retires independently of the per-session one-use mutation claims.
  const retireTargetObservation = useCallback(() => { targetObservationEpoch.current++; setTargetObservation(undefined); setJobObservation(undefined); setDiscardPreparation(undefined); }, []);
  const observedDiscardState = (snapshot: StudioImageNodeJobObservation) => {
    const job = snapshot.job;
    if (job.status !== 'CANCELLED' || job.attempt !== 0 || job.output_candidate !== null || job.receipt_digest !== null
      || job.approved_asset_version !== null || job.cancellation_mode !== 'LOCAL_RESULT_DISCARD') return;
    let changed = false;
    for (const row of discardTraces.current.values()) {
      if (row.state === 'UNKNOWN' && row.ownerKey === cacheKey && job.novel_id === row.projectId && snapshot.incarnation === row.incarnation
        && job.id === row.jobId && job.request_id === row.requestId && job.request_digest === row.requestDigest
        && job.version === row.version + 1 && canonicalImageNode(snapshot.target) === row.target) {
        row.state = 'STATE_CONFIRMED'; changed = true;
      }
    }
    if (changed) { publishDiscardTraces(); captureLeaveRisk.current(); }
  };
  const mediaDirtyRef = useRef(false), timelineDirtyRef = useRef(false), assetReadEpoch = useRef(0);
  const [maskDirty, setMaskDirty] = useState(false);
  const maskDirtyRef = useRef(false);
  const maskDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; maskDirtyRef.current = value; setMaskDirty(value); }, []);
  const [workflowDirty, setWorkflowDirty] = useState(false), [workflowModule, setWorkflowModule] = useState<ProductionWorkflowModuleId>('director'), [workflowAssetKind, setWorkflowAssetKind] = useState<ProductionWorkflowAssetKind>('image');
  const workflowDirtyRef = useRef(false);
  const workflowDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; workflowDirtyRef.current = value; setWorkflowDirty(value); }, []);
  const mediaDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; mediaDirtyRef.current = value; setMediaDirty(value); }, []);
  // The Prompt workspace holds a local draft (and possibly an in-flight submit). It joins the
  // host's existing leave-confirmation rather than adding its own beforeunload.
  const promptDirtyRef = useRef(false);
  const [promptDirty, setPromptDirty] = useState(false);
  const promptDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; promptDirtyRef.current = value; setPromptDirty(value); }, []);
  const timelineDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; timelineDirtyRef.current = value; setTimelineDirty(value); }, []);
  const verifiedCallback = useRef(onVerified); verifiedCallback.current = onVerified;
  const lastVideoReferenceSave = useRef<{body:string;key:string;unknown:boolean}>();
  const lastClaySave = useRef<{body:string;key:string;unknown:boolean}>();
  const lastImport = useRef<{ body: string; key: string; unknown: boolean }>();
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
  const deny = useCallback(() => { retirePendingNodeResume(); nodeResumeSource.current = undefined; retireTargetObservation(); captureLeaveRisk.current(); navigationEpoch.current++; setAcknowledgeUnknown(false); revoked.current = true; selectionEpoch.current++; overviewEpoch.current++; storageEpoch.current++; assetReadEpoch.current++; overviewReading.current?.abort(); storageRequest.current?.abort(); setDenied(true); setStoryboardHandoff(undefined); storyboardDirtyRef.current = false; setStoryboardDirty(false); setAssetHandoff(undefined); setMediaHandoff(undefined); setSelected(undefined); setRows([]); setOverview(undefined); setComicWorkspace(undefined); setStorage(undefined); setProductionJob(undefined); setPendingDeclaration(undefined); setPendingNavigation(undefined); setDiscard(false); setLineageDirty(false); setRelationshipDirty(false); mediaDirtyRef.current = false; timelineDirtyRef.current = false; setMediaDirty(false); setTimelineDirty(false); }, [retirePendingNodeResume, retireTargetObservation]);
  const retireIdentity = useCallback(() => {
    retirePendingNodeResume(); nodeResumeSource.current = undefined; retireTargetObservation();
    captureLeaveRisk.current(); navigationEpoch.current++; setAcknowledgeUnknown(false); studioRetired.current = true; authorityLost.current = true; setIdentityRetired(true); setAssetHandoff(undefined); setMediaHandoff(undefined);
    selectionEpoch.current++; overviewEpoch.current++; storageEpoch.current++; assetReadEpoch.current++;
    overviewReading.current?.abort(); storageRequest.current?.abort();
    setSelected(undefined); setRows([]); setOverview(undefined); setComicWorkspace(undefined); setStorage(undefined); setProductionJob(undefined);
    setPendingDeclaration(undefined); setPendingNavigation(undefined); setDiscard(false); setError(''); setNotice(''); setLoading(false);
  }, [retirePendingNodeResume, retireTargetObservation]);
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
      // An aborted operation no longer owns the visible selection. Current
      // reads and mutations still revoke the workspace after authoritative denial.
      if (!signal?.aborted && current() && reason instanceof ApiError && [401, 403].includes(reason.status)) deny();
      throw reason;
    }
  }, [current, deny]);
  const guardedWrite = useCallback(async <T,>(operation: () => Promise<T>, signal?: AbortSignal): Promise<T> => {
    if (!current()) throw new Error('项目或会话已改变，请重新打开。');
    pendingWrites.current++;
    try { return await guarded(operation, signal); }
    finally {
      pendingWrites.current--;
      if (alive.current) redrawLeaveGuard(epoch => epoch + 1);
    }
  }, [current, guarded]);
  const guardedDiscardWrite = useCallback(async <T,>(operation: () => Promise<T>, signal?: AbortSignal): Promise<T> => {
    discardWrites.current++;
    try { return await guardedWrite(operation, signal); }
    finally { discardWrites.current--; }
  }, [guardedWrite]);
  useEffect(() => {
    if (!comicOpen || comicWorkspace || !overview || module !== 'IMAGE' || !current()) return;
    const abort = new AbortController(); setComicError(''); comicBusyChanged(true);
    void client.comicWorkspace(abort.signal).then(value => {
      if (!abort.signal.aborted && current()) setComicWorkspace(value);
    }).catch(reason => {
      if (!abort.signal.aborted && current()) setComicError(apiErrorView(reason, '漫画权限读取失败，请关闭后重新打开。').message);
    }).finally(() => { if (!abort.signal.aborted && current()) comicBusyChanged(false); });
    return () => { abort.abort(); comicBusyChanged(false); };
  }, [comicOpen, comicWorkspace, overview, module, client, current, comicBusyChanged]);
  const writable = overview?.capabilities.can_mutate === true && !denied && !identityRetired;
  const discardPermission = useRef({ value: writable, generation: 0 });
  if (discardPermission.current.value !== writable) discardPermission.current = { value: writable, generation: discardPermission.current.generation + 1 };
  const discardPermissionGeneration = discardPermission.current.generation;
  cutoutPermission.current = writable;
  const graphMutation = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
    if (busyRef.current || !current()) throw new Error('当前操作尚未结束，请先核对结果。');
    busyRef.current = true; setBusy(true);
    try { return await guarded(operation); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  }, [current, guarded]);
  const storyboardPerform = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
    if (busyRef.current || !current()) throw new Error('当前操作尚未结束，请先核对结果。');
    storyboardOperation.current = true;
    try { return await graphMutation(operation); } finally { storyboardOperation.current = false; }
  }, [graphMutation, current]);
  // This exception belongs to the original workspace semaphore, not to a second
  // mutation owner: only the same executing cutout's read/CAS cancel may overlap.
  const sameCutout = (expected: ProductionJob, value: ProductionJob) => ['m5.image.cutout', 'm5.image.composite'].includes(value.operation_id) && value.operation_id === expected.operation_id && value.owner === 'image'
    && value.id === expected.id && value.novel_id === expected.novel_id && value.branch_id === expected.branch_id
    && value.request_id === expected.request_id && value.request_digest === expected.request_digest && value.version >= expected.version;
  const cutoutExecution = {
    execute: (job: ProductionJob) => graphMutation(async () => {
      if (!writable || !['m5.image.cutout', 'm5.image.composite'].includes(job.operation_id) || job.owner !== 'image' || job.status !== 'QUEUED') throw new Error('当前不能执行此本地任务。');
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
  const graphDraftBlocked = useCallback(() => storyboardDirtyRef.current || graphDirtyRef.current || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current, []);
  const operationPending = useCallback(() => busyRef.current, []);
  const preferenceController = useStudioWorkspacePreferences({ initial: overview?.preferences, denied: denied || identityRetired, canMutate: writable, busy, externalDirty: storyboardDirty || lineageDirty || relationshipDirty || mediaDirty || timelineDirty || maskDirty,
    client, isCurrent: current, read: guarded, mutate: graphMutation, onAdopt: adoptPreferences, isExternallyDirty: graphDraftBlocked });
  const preferenceDirty = preferenceController.dirty || preferenceController.blocked;
  const rememberGraphLocation = useCallback((selection: { graphId?: string; runId?: string }) => {
    if (current()) setGraphLocation(previous => previous.graphId === selection.graphId && previous.runId === selection.runId ? previous : selection);
  }, [current]);
  const graph = useStudioGraphEditor({ active: !editorSession && graphView && overview?.project.entry_kind === 'NEUTRAL_STUDIO', denied, identity: cacheKey, client, directorSource, onOpenStoryboard: (request, isOriginCurrent) => openStoryboard(request, isOriginCurrent), onOpenModels: () => navigate(() => onModuleChange('CONTROL')), onOpenBroker: onOpenBroker ? () => navigate(onOpenBroker) : undefined, providerSource: productionClient, canMutate: writable, canReview: overview?.capabilities.can_review === true && !denied, busy, externalDirty: preferenceDirty || lineageDirty || relationshipDirty, isCurrent: current, read: guarded, mutate: graphMutation,
    productionTaskSource:productionClient,productionTaskLeaveGuard:leaveGuard,onCanvasTaskApproved:()=>productionApproved(),onCanvasTaskUnavailable:()=>deny(),
    draftOwner: studioGraphDraftOwner(projectId, overview?.project.incarnation, context, capturedHost.current),
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
    active: productionView && !storyboardHandoff && overview?.project.entry_kind === 'NEUTRAL_STUDIO' && !denied && !identityRetired,
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
  const dirty = comicDirty || storyboardDirty || preferenceDirty || lineageDirty || relationshipDirty || graph.dirty || mediaDirty || timelineDirty || maskDirty || workflowDirty;
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const lineageDirtyRef = useRef(lineageDirty); lineageDirtyRef.current = lineageDirty;
  const relationshipDirtyRef = useRef(relationshipDirty); relationshipDirtyRef.current = relationshipDirty;
  const lineageDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; lineageDirtyRef.current = value; setLineageDirty(value); }, []);
  const relationshipDraftChanged = useCallback((value: boolean) => { if (value) draftSeen.current = true; relationshipDirtyRef.current = value; setRelationshipDirty(value); }, []);
  if (dirty || promptDirty) draftSeen.current = true;
  captureLeaveRisk.current = () => {
    const risk = leaveRisk.current;
    risk.dirty ||= draftSeen.current || dirtyRef.current || comicDirtyRef.current || storyboardDirtyRef.current
      || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current || workflowDirtyRef.current || promptDirtyRef.current;
    risk.unknown ||= pendingWrites.current > discardWrites.current || (busyRef.current && draftSeen.current) || preferenceController.blocked || graph.directorPending
      || !!lastImport.current?.unknown || !!lastVideoReferenceSave.current?.unknown || !!lastClaySave.current?.unknown;
    // Read original controller refs before denial, hiding or cleanup clears them.
    // Scope is captured here explicitly; origin/cacheKey contain credentials.
    for (const read of productionRiskReaders.current) {
      const snapshot = read(); risk.unknown ||= snapshot.unknown;
      if (snapshot.unknown) for (const request of snapshot.requests) {
        risk.requestIds = [...new Set([...risk.requestIds, request.requestId])];
        const identity = `${request.owner} · ${request.operationId} · ${productionLeaveScope}`;
        risk.productionRequests = [...new Set([...risk.productionRequests, `${request.requestId} · ${identity}`])];
      }
    }
    // This child only reports a boolean and reports false again during unmount.
    // A cleanup is not a settlement receipt for an operation already in flight.
    risk.comicInFlight ||= comicBusyRef.current;
    if (risk.unknown) risk.requestIds = [...new Set([...risk.requestIds,
      lastImport.current?.key, lastVideoReferenceSave.current?.key, lastClaySave.current?.key,
      cutoutLease.current?.job.request_id, productionJob?.job.request_id].filter((id): id is string => !!id))];
  };
  useEffect(() => {
    if (current() && !dirty && !promptDirty && !pendingWrites.current) draftSeen.current = false;
  }, [dirty, promptDirty, current]);
  const navigationBusy = (retiredExit = false) => busyRef.current || pendingWrites.current > 0 || comicBusyRef.current
    || storyboardOperation.current || editorPreparing.current || !!cutoutLease.current
    || (retiredExit ? leaveRisk.current.comicInFlight : !!preferenceController.pending);
  const refresh = useCallback(async () => {
    if (busyRef.current || !current()) return;
    overviewReading.current?.abort(); const abort = new AbortController(); overviewReading.current = abort;
    const epoch = ++overviewEpoch.current;
    setLoading(true); setError('');
    try {
      const result = await guarded(async () => {
        try { return { overview: await client.overview(abort.signal) }; }
        catch (reason) {
          // A different, bounded owner may authorize Comic after the generic
          // NOVEL workspace refuses access. Never use a malformed scope response,
          // cancelled read, or retired identity as a reason to try another owner.
          if (module !== 'IMAGE' || !(reason instanceof ApiError) || reason.status !== 403
            || reason.problem.code === 'STUDIO_RESPONSE_SCOPE_MISMATCH' || abort.signal.aborted || !current()) throw reason;
          setOverview(undefined); setComicWorkspace(undefined); setSelected(undefined); setRows([]); setStorage(undefined);
          return { comic: await client.comicWorkspace(abort.signal) };
        }
      }, abort.signal);
      if ('comic' in result) {
        if (current() && epoch === overviewEpoch.current && !abort.signal.aborted) { setComicWorkspace(result.comic); verifiedCallback.current?.(projectId); }
        return;
      }
      const value = result.overview;
      if (value.project.id !== projectId || value.project.entry_kind !== 'NEUTRAL_STUDIO') throw new Error('当前项目尚未启用独立工作区，请返回项目列表重新选择。');
      if (!value.capabilities || !value.preferences || !Number.isSafeInteger(value.preferences.version) || !Array.isArray(value.preferences.intents)) throw new Error('项目能力或偏好数据不可用，请重新读取。');
      if (current() && epoch === overviewEpoch.current && !abort.signal.aborted) { setComicWorkspace(undefined); setOverview(value); verifiedCallback.current?.(projectId); }
    } catch (reason) { if (current() && epoch === overviewEpoch.current && !abort.signal.aborted) setError(apiErrorView(reason, '项目读取失败。').message); }
    finally { if (current() && epoch === overviewEpoch.current) setLoading(false); }
  }, [client, current, guarded, projectId, module]);
  useEffect(() => { alive.current = true; void refresh(); return () => { alive.current = false; retirePendingNodeResume(); nodeResumeSource.current = undefined; targetObservationContextEpoch.current++; retireTargetObservation(); overviewEpoch.current++; storageEpoch.current++; selectionEpoch.current++; overviewReading.current?.abort(); storageRequest.current?.abort(); }; }, [refresh, retirePendingNodeResume, retireTargetObservation]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty || promptDirty || busyRef.current || comicBusyRef.current || leaveRisk.current.dirty || unknownLeaveRisk() || leaveRisk.current.comicInFlight) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, promptDirty]);
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
    // The bounded resume is source-free and consumes only its exact Job. Avoid
    // starting an unrelated asset read/semaphore during its destination mount.
    if (productionView && !nodeResumeActive && !storyboardHandoff && overview && !denied) void loadProductionAssets();
  }, [productionView, nodeResumeActive, !!storyboardHandoff, overview?.project.id, denied, loadProductionAssets]);
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
      if (lastImport.current?.body !== identity) lastImport.current = { body: identity, key: crypto.randomUUID(), unknown: true };
      lastImport.current.unknown = true;
      try {
        const imported = await guardedWrite(() => client.importAsset({ filename: body.filename, kind: body.kind as 'image' | 'video' | 'audio', content_base64: body.content_base64, idempotency_key: lastImport.current!.key }));
        lastImport.current!.unknown = false;
        // Saving provenance is a second mutation. A failed declaration never repeats the import.
        try { const asset = await guardedWrite(() => declared(imported)); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); return asset; }
        catch (reason) { if (!current()) throw reason; setPendingDeclaration(imported); setNotice('文件已保存，来源声明尚未保存。可仅重试声明，无需重新上传。'); return imported; }
      } finally { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }
    },
    download: asset => overview?.capabilities.manual_export === true ? guarded(() => client.download(asset.id)) : Promise.reject(new Error('当前无法导出资产。')),
    remove: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能删除资产。')); busyRef.current = true; setBusy(true); return guardedWrite(() => client.remove(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }); },
    trash: async () => { const value = await guarded(() => client.assets(true)); const items = value.items.filter(asset => !!asset.deleted_at); return { items, total: items.length }; },
    restore: asset => { if (!writable || busyRef.current || dirtyRef.current) return Promise.reject(new Error('当前不能恢复资产。')); busyRef.current = true; setBusy(true); return guardedWrite(() => client.restore(asset.id, asset.version!)).finally(() => { busyRef.current = false; if (current()) { setBusy(false); invalidateStorage(); } }); },
  }), [cacheKey, writable, dirty, busy, overview?.capabilities.manual_import, overview?.capabilities.manual_export, overview?.capabilities.media_validator_configured, current, guarded, guardedWrite, client, declared, invalidateStorage]);
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
  const navigate = (action: () => void, novelExit = false) => {
    const authorized = current(), retiredExit = !authorized && novelExit;
    if (!authorized && (!retiredExit || !alive.current || studioRetired.current || novelExitCommitted.current || !sameStudioIdentity())) return;
    editorTicket.current++; pendingEditor.current = undefined; retirePendingNodeResume(); targetObservationContextEpoch.current++; retireTargetObservation();
    if (navigationBusy(retiredExit)) { setNotice('当前操作尚未结束，请等待结果确认后再离开。'); return; }
    const needsConfirmation = retiredExit ? leaveRisk.current.dirty || unknownLeaveRisk()
      : dirty || comicDirtyRef.current || storyboardDirtyRef.current || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current || workflowDirtyRef.current || promptDirtyRef.current;
    if (needsConfirmation) {
      setDiscard(false); setAcknowledgeUnknown(false);
      setPendingNavigation(retiredExit ? { kind: 'NOVEL', epoch: navigationEpoch.current } : { kind: 'CURRENT', action: () => { nodeResumeSource.current = undefined; action(); }, epoch: navigationEpoch.current }); return;
    }
    nodeResumeSource.current = undefined;
    if (retiredExit) { novelExitCommitted.current = true; onModuleChange('NOVEL'); } else action();
  };
  const relationshipEpoch = selectionEpoch.current;
  const openRelationshipAsset = (expected: AssetReferencePin) => {
    if (!current() || busyRef.current || expected.kind !== 'ASSET' || relationshipEpoch !== selectionEpoch.current) return;
    const sourceEpoch = selectionEpoch.current;
    navigate(() => {
      if (!current() || busyRef.current || sourceEpoch !== selectionEpoch.current) return;
      const epoch = ++selectionEpoch.current;
      busyRef.current = true; setBusy(true); setReadingAsset(true);
      void guarded(() => client.asset(expected.id)).then(asset => {
        if (!current() || epoch !== selectionEpoch.current) return;
        if (asset.id !== expected.id || asset.novel_id !== projectId || (asset.branch_id ?? null) !== (context.scope?.branchId || null)
          || asset.deleted_at || asset.version !== expected.version || asset.sha256 !== expected.digest) {
          setNotice('关联来源的版本、摘要或范围已变化；未打开最新版本，原资产选择保持不变。'); return;
        }
        refreshedAsset(asset); setRelationshipReviewEpoch(selectionEpoch.current); setWorkspaceView('ASSETS');
        setNotice('已打开关联时的精确原资产版本。未修改关联，也未导出文件。');
      }).catch(reason => { if (current() && epoch === selectionEpoch.current) setNotice(apiErrorView(reason, '关联原资产当前无法读取，未改变选择。').message); })
        .finally(() => { busyRef.current = false; if (current()) { setBusy(false); setReadingAsset(false); } });
    });
  };
  const openApprovedAsset = (job: ProductionJob) => {
    if (job.status !== 'APPROVED' || !job.output_candidate || !Number.isSafeInteger(job.approved_asset_version)
      || !job.approved_asset_version || job.novel_id !== projectId) return;
    // Capture the approved version, not the earlier private candidate version.
    const expected = { ...job.output_candidate, version: job.approved_asset_version };
    navigate(() => {
      if (!current() || busyRef.current) return;
      // Explicit draft discard remounts production; retain its original job if the asset read fails.
      setProductionJob({ client: productionClient, job });
      const epoch = ++selectionEpoch.current;
      busyRef.current = true; setBusy(true); setReadingAsset(true);
      void guarded(() => client.asset(expected.id)).then(asset => {
        if (!current() || epoch !== selectionEpoch.current) return;
        if (asset.deleted_at || asset.id !== expected.id || asset.version !== expected.version
          || asset.sha256 !== expected.digest || asset.kind !== expected.kind) {
          setNotice('原任务已审核素材的版本、摘要或类型已变化，或素材已移除。未改选其他素材，请重新核对原记录。');
          return;
        }
        refreshedAsset(asset); setWorkspaceView('ASSETS');
        setNotice(`已打开原任务 ${job.id} 的已审核素材 ${asset.filename} · v${asset.version}。下载仍需在素材中明确选择。`);
      }).catch(reason => { if (current() && epoch === selectionEpoch.current) setNotice(apiErrorView(reason, '原任务已审核素材当前无法读取。未改选其他素材，请重新核对原记录。').message); })
        .finally(() => { busyRef.current = false; if (current()) { setBusy(false); setReadingAsset(false); } });
    });
  };
  const discardNavigationDrafts = () => {
    setComicOpen(false); comicDraftChanged(false);
    setLineageDirty(false); setRelationshipDirty(false); setFormRevision(value => value + 1); preferenceController.discard(); graph.discard();
    storyboardDraftChanged(false); setStoryboardHandoff(undefined); mediaDraftChanged(false); timelineDraftChanged(false); maskDraftChanged(false); promptDraftChanged(false); workflow.skip(); setProductionRevision(value => value + 1); setProductionJob(undefined);
  };
  const openStoryboard: OpenStoryboardEditor = (request, isOriginCurrent) => {
    if (!current() || busyRef.current || editorPreparing.current || editorSession || !graphView || (module !== 'IMAGE' && module !== 'VIDEO') || !isOriginCurrent()) return;
    retirePendingNodeResume(); nodeResumeSource.current = undefined;
    const ticket = ++editorTicket.current, sourceSelection = selectionEpoch.current, originModule = module;
    const valid = () => current() && editorTicket.current === ticket && editorLocation.current === originModule && sourceSelection === selectionEpoch.current && isOriginCurrent();
    const prepare = async () => {
      if (!valid() || busyRef.current || editorPreparing.current || pendingEditor.current !== prepare || preferenceController.pending) return;
      editorPreparing.current = true; busyRef.current = true; setBusy(true); setNotice('正在核对原分镜，输入将在核对成功后才放弃。');
      try {
        const capabilities = await guarded(() => directorSource.capabilities());
        if (!valid()) return;
        checkedStoryboardCapabilities(capabilities);
        const receipt = await guarded(() => directorSource.export(request.target.id));
        if (!valid()) return;
        const prepared = prepareStoryboardEditor(request, receipt, capabilities);
        // No await between final validation and commit. The destination consumes this
        // immutable prepared receipt, so a later network failure cannot lose drafts.
        if (!valid()) return;
        pendingEditor.current = undefined; setPendingNavigation(undefined); setDiscard(false);
        busyRef.current = false; setBusy(false);
        discardNavigationDrafts();
        setEditorSession({ prepared, ticket, module: originModule });
      } catch (reason) {
        if (current() && editorTicket.current === ticket) setNotice(apiErrorView(reason, '未打开原分镜，未保存输入仍保留。').message);
      } finally {
        editorPreparing.current = false; busyRef.current = false;
        if (alive.current) setBusy(false);
      }
    };
    pendingEditor.current = prepare;
    if (dirtyRef.current || promptDirtyRef.current || storyboardDirtyRef.current || mediaDirtyRef.current || timelineDirtyRef.current || maskDirtyRef.current || workflowDirtyRef.current) {
      setDiscard(false); setPendingNavigation({ kind: 'CURRENT', action: () => {}, epoch: navigationEpoch.current });
    } else void prepare();
  };
  const openProductionNodeResume = (job: StudioProductionTask, isSelectionCurrent: () => boolean) => {
    if (!current() || busyRef.current || workspaceViewRef.current !== 'TASKS' || !isSelectionCurrent()) return;
    retirePendingNodeResume(); editorTicket.current++; pendingEditor.current = undefined;
    navigationEpoch.current++; setPendingNavigation(undefined); setDiscard(false);
    const readOnly = ['RUNNING', 'UNKNOWN', 'CANCELLED'].includes(job.status);
    if (job.owner !== 'image' || job.status !== 'QUEUED' && !readOnly) {
      setNotice('此节点任务状态暂不支持续接。当前仅支持排队任务，以及运行中、未知或已取消任务的只读元数据；不会改选最新任务或新建节点。'); return;
    }
    const ticket = nodeResumeTicket.current, sourceSelection = selectionEpoch.current, originModule = module;
    const controller = new AbortController(), selectedJob = structuredClone(job);
    const valid = () => current() && !controller.signal.aborted && nodeResumeTicket.current === ticket
      && pendingNodeResume.current === prepare && selectionEpoch.current === sourceSelection
      && editorLocation.current === originModule && workspaceViewRef.current === 'TASKS';
    const prepare = async () => {
      // The selector lease only belongs to TASKS. Freeze its UI synchronously,
      // then use this owned read ticket; navigation must not carry that lease.
      if (!valid() || !isSelectionCurrent()) {
        if (current() && nodeResumeTicket.current === ticket) {
          pendingNodeResume.current = undefined; setPendingNavigation(undefined); setDiscard(false);
          setNotice('原任务选择已变化，未放弃当前输入；请重新明确选择原节点任务。');
        }
        return;
      }
      if (busyRef.current || editorPreparing.current || preferenceController.pending) return;
      nodeResumeReading.current = { ticket, controller }; busyRef.current = true; setBusy(true);
      setNotice(readOnly ? '正在核对原节点任务的只读元数据与原画布；核对成功前保留当前输入。' : '正在核对原排队节点任务与原画布；核对成功前保留当前输入。');
      try {
        const prepared = await prepareCanvasImageNodeResume({ selected: selectedJob, projectId,
          branchId: context.scope?.branchId || null, client, production: productionClient,
          isCurrent: valid, read: guarded, signal: controller.signal, readOnly });
        if (!valid()) return;
        // No await after this final check: failed reads never discard drafts.
        pendingNodeResume.current = undefined; setPendingNavigation(undefined); setDiscard(false); setAcknowledgeUnknown(false);
        // Destination hooks read the synchronous semaphore during their first
        // committed render. Retire this completed read before mounting them.
        nodeResumeReading.current = undefined; busyRef.current = false; setBusy(false);
        discardNavigationDrafts();
        const source: NodeResumeSource = { ...prepared, ticket: ++nodeResumeSourceTicket.current,
          selectionEpoch: sourceSelection, module: originModule };
        nodeResumeSource.current = source;
        setTaskTarget(undefined); setStoryboardHandoff(undefined); setAssetHandoff(undefined); setMediaHandoff(undefined);
        setProductionJob({ client: productionClient, job: prepared.job, resume: source }); setWorkspaceView('PRODUCTION');
        setNotice(prepared.readOnly ? '已只读续接精确的原节点任务。仅可明确读取当前回执或下载已读元数据；此入口不执行、对账、取消或读取候选媒体。' : '已续接精确的原排队节点任务。未恢复浏览器画布或自动执行；执行仍需重新预览并明确确认。');
      } catch (reason) {
        if (current() && nodeResumeTicket.current === ticket && !controller.signal.aborted) {
          pendingNodeResume.current = undefined; setPendingNavigation(undefined); setDiscard(false);
          setNotice(apiErrorView(reason, '原节点任务未能续接，未保存输入仍保留。').message);
        }
      } finally {
        if (nodeResumeReading.current?.ticket === ticket) {
          nodeResumeReading.current = undefined; busyRef.current = false; if (alive.current) setBusy(false);
        }
      }
    };
    pendingNodeResume.current = prepare;
    if (dirtyRef.current || promptDirtyRef.current || comicDirtyRef.current || storyboardDirtyRef.current || mediaDirtyRef.current
      || timelineDirtyRef.current || maskDirtyRef.current || workflowDirtyRef.current) {
      setDiscard(false); setAcknowledgeUnknown(false); setPendingNavigation({ kind: 'CURRENT', action: () => {}, epoch: navigationEpoch.current, nodeResumeTicket: ticket });
    } else void prepare();
  };
  const confirmNavigation = () => {
    if (!pendingNavigation || pendingNavigation.epoch !== navigationEpoch.current) return;
    const retiredExit = pendingNavigation.kind === 'NOVEL';
    if (retiredExit) {
      if (!alive.current || studioRetired.current || novelExitCommitted.current || !sameStudioIdentity()
        || (leaveRisk.current.dirty && !discard) || (unknownLeaveRisk() && !acknowledgeUnknown)) return;
    } else if (!discard || !current()) return;
    if (navigationBusy(retiredExit)) { setNotice('当前操作尚未结束，未放弃输入或离开。请先核对结果。'); return; }
    if (pendingNavigation.kind === 'CURRENT' && pendingNavigation.nodeResumeTicket !== undefined) {
      if (pendingNavigation.nodeResumeTicket === nodeResumeTicket.current && pendingNodeResume.current) void pendingNodeResume.current();
      return;
    }
    if (!retiredExit && pendingEditor.current) { void pendingEditor.current(); return; }
    setPendingNavigation(undefined); setDiscard(false); setAcknowledgeUnknown(false);
    // Retired controllers cannot discard, save, execute, cancel or replay. The
    // original IDs and unknown-result markers remain available for later review.
    if (pendingNavigation.kind === 'NOVEL') { nodeResumeSource.current = undefined; novelExitCommitted.current = true; onModuleChange('NOVEL'); }
    else { discardNavigationDrafts(); pendingNavigation.action(); }
  };
  const retiredExitPending = pendingNavigation?.kind === 'NOVEL';
  const discardScopeCurrent = current() && !denied && !identityRetired;
  const visibleDiscardTraces = discardTraceRows.filter(row => discardScopeCurrent && row.ownerKey === cacheKey
    && row.projectId === projectId && row.incarnation === overview?.project.incarnation);
  const hiddenDiscardUnknown = discardTraceRows.filter(row => row.state === 'UNKNOWN' && !visibleDiscardTraces.includes(row)).length;
  const resumedNode = productionJob?.client === productionClient ? productionJob.resume : undefined;
  const resumeSourceCurrent = () => !!resumedNode && current() && workspaceViewRef.current === 'PRODUCTION'
    && nodeResumeSource.current === resumedNode && productionJobRef.current?.resume === resumedNode
    && productionJobRef.current.client === productionClient && resumedNode.selectionEpoch === selectionEpoch.current
    && resumedNode.module === editorLocation.current && resumedNode.ticket === nodeResumeSourceTicket.current;
  const sidebar = comicOnly ? <div className="independent-studio-sidebar"><h2>独立漫画</h2><p>空白漫画页和书册沿用原项目保存，无需小说来源。</p><Button onClick={() => navigate(onProjectChoice)}>返回项目列表</Button></div> : <div className="independent-studio-sidebar"><h2>独立创作</h2><p>图片、视频和声音共享项目资产。连接其它模块由你决定。</p><Button onClick={() => navigate(onProjectChoice)}>返回项目列表</Button>
    <StudioWorkspacePreferencesForm controller={preferenceController} locked={storyboardDirty || graph.dirty || mediaDirty || timelineDirty || maskDirty} />
    <details onToggle={event => { if (event.currentTarget.open && !storage && overview) void loadStorage(); }}><summary>项目存储</summary>{storageLoading && <StatusMessage>正在核对项目存储…</StatusMessage>}{storage ? <><p>有效资产 {storage.assets.count} 项 · {storage.assets.bytes} 字节</p><p>回收站 {storage.trash.count} 项 · {storage.trash.bytes} 字节</p>
      {storage.admission?.state === 'READY' && <p>当前可导入容量估算：{storage.admission.available_import_bytes} 字节；已扣除安全预留空间和项目配额。</p>}
      {storage.admission?.state === 'LOW_SPACE_OR_QUOTA' && <StatusMessage tone="warning">空间或项目配额不足，当前无法继续导入。已有资产仍可查看和导出。</StatusMessage>}
      {storage.admission?.state === 'UNAVAILABLE' && <StatusMessage tone="warning">当前无法确认存储容量，导入将由服务端安全校验。</StatusMessage>}
      {!storage.admission && <p>容量校验状态尚未提供，上传仍由服务端核对。</p>}
      <p>以上为查询时估算；实际上传会再次校验。回收站仍占用空间，不会自动清理。</p><p>模型目录仅引用；缓存单独管理；导出位置由下载时选择。</p><p>本入口不清理或移动任何外部模型文件。</p></> : <p>展开后读取服务端统计。</p>}<Button disabled={!overview || storageLoading} onClick={() => void loadStorage()}>刷新存储统计</Button></details>
  </div>;
  const maskEpoch = selectionEpoch.current;
  const relationshipReview = relationshipReviewEpoch !== undefined && relationshipReviewEpoch === selectionEpoch.current;
  const main = <div className="independent-studio">
    {overview && !denied && <div className="studio-graph-actions" aria-label="独立工作区内容"><Button aria-pressed={workspaceView === 'START'} onClick={() => navigate(() => setWorkspaceView('START'))}>创作开始</Button><Button aria-pressed={workspaceView === 'TASKS'} onClick={() => navigate(() => setWorkspaceView('TASKS'))}>任务中心</Button><Button aria-pressed={workspaceView === 'ASSETS'} onClick={() => navigate(() => setWorkspaceView('ASSETS'))}>素材工作区</Button>{interfaceMode === 'PROFESSIONAL' && <Button aria-pressed={graphView} onClick={() => navigate(() => setWorkspaceView('GRAPH'))}>创作图</Button>}<Button aria-pressed={productionView} onClick={() => navigate(() => setWorkspaceView('PRODUCTION'))}>制作操作</Button><InterfaceModeSwitch mode={interfaceMode} onChange={changeInterfaceMode} /></div>}
    {module === 'IMAGE' && (workspaceView === 'ASSETS' || comicOnly) && (overview || comicWorkspace) && !denied && !identityRetired && <Panel title="漫画制作 Comic">
      <Button aria-expanded={comicOpen} onClick={() => navigate(() => setComicOpen(!comicOpen))}>{comicOpen ? '关闭漫画制作' : '打开漫画制作'}</Button>
      {comicOpen && !comicWorkspace && <StatusMessage tone={comicError ? 'error' : undefined}>{comicError || '正在核对漫画权限…'}</StatusMessage>}
      {comicOpen && comicWorkspace && <StudioComicPanel sourceFree={comicWorkspace.source_free} canMutate={comicWorkspace.capabilities.can_mutate} canReview={comicWorkspace.capabilities.can_review && !denied} projectId={projectId} context={context} isCurrent={current} onDirtyChange={comicDraftChanged} onBusyChange={comicBusyChanged} />}
    </Panel>}
    {workspaceView === 'TASKS' && overview && !denied && <TaskCenterPanel projectId={projectId}
      transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })}
      scope={context.scope} identity={cacheKey} active={workspaceView === 'TASKS' && overview && !denied && !identityRetired}
      denied={denied || identityRetired} busy={busy} isCurrent={current} read={guarded} mutate={graphMutation}
      onNavigate={target => {
        if (!current() || busyRef.current) return;
        const epoch = selectionEpoch.current;
        navigate(() => { if (current() && epoch === selectionEpoch.current && !busyRef.current) setTaskTarget(previous => previous && JSON.stringify(previous.target) === JSON.stringify(target) ? previous : { id: crypto.randomUUID(), target: structuredClone(target) }); });
      }}
      onUnavailable={deny} />}
    {workspaceView === 'TASKS' && overview && !denied && !identityRetired && <StudioProductionTasksPanel
      projectId={projectId} branchId={context.scope?.branchId ?? null} identity={cacheKey} client={productionClient}
      active={workspaceView === 'TASKS' && overview && !denied && !identityRetired} denied={denied || identityRetired}
      busy={busy} isBusy={operationPending} isCurrent={current} read={guarded} onUnavailable={deny} onSelectionRetired={retireTargetObservation}
      canPrepareImageNodeDiscard={writable}
      onInspectCanvasTarget={(job, isSelectionCurrent) => {
        if (!current() || busyRef.current || workspaceViewRef.current !== 'TASKS' || editorLocation.current !== module
          || productionClientRef.current !== productionClient || targetObservationContextEpoch.current !== targetObservationRenderEpoch || !isSelectionCurrent()) return;
        const ticket = ++targetObservationEpoch.current, sourceSelection = selectionEpoch.current, originModule = module;
        const originalClient = productionClient;
        const source = { job: structuredClone(job), key: `${cacheKey}:target:${ticket}`,
          isCurrent: () => current() && targetObservationEpoch.current === ticket && isSelectionCurrent()
            && targetObservationContextEpoch.current === targetObservationRenderEpoch
            && sourceSelection === selectionEpoch.current && editorLocation.current === originModule
            && workspaceViewRef.current === 'TASKS' && productionClientRef.current === originalClient };
        setJobObservation(undefined); setDiscardPreparation(undefined); setTargetObservation({ ticket, source });
      }}
      onInspectImageNodeJob={(job, isSelectionCurrent) => {
        if (!current() || busyRef.current || workspaceViewRef.current !== 'TASKS' || editorLocation.current !== module
          || productionClientRef.current !== productionClient || targetObservationContextEpoch.current !== targetObservationRenderEpoch || !isSelectionCurrent()) return;
        const ticket = ++targetObservationEpoch.current, sourceSelection = selectionEpoch.current, originModule = module;
        const originalClient = productionClient;
        const source = { job: structuredClone(job), key: `${cacheKey}:job:${ticket}`,
          isCurrent: () => current() && targetObservationEpoch.current === ticket && isSelectionCurrent()
            && targetObservationContextEpoch.current === targetObservationRenderEpoch
            && sourceSelection === selectionEpoch.current && editorLocation.current === originModule
            && workspaceViewRef.current === 'TASKS' && productionClientRef.current === originalClient };
        setTargetObservation(undefined); setDiscardPreparation(undefined); setJobObservation({ ticket, source });
      }}
      onPrepareImageNodeDiscard={(job, isSelectionCurrent) => {
        if (!current() || busyRef.current || !writable || workspaceViewRef.current !== 'TASKS' || editorLocation.current !== module
          || productionClientRef.current !== productionClient || targetObservationContextEpoch.current !== targetObservationRenderEpoch
          || discardPermission.current.generation !== discardPermissionGeneration || !isSelectionCurrent()) return;
        const target = canvasImageNodeInCommand(job.command); if (!target) return;
        const ticket = ++targetObservationEpoch.current, sourceSelection = selectionEpoch.current, originModule = module;
        const originalClient = productionClient, capturedJob = structuredClone(job);
        const source = { job: capturedJob, key: `${cacheKey}:discard:${ticket}`,
          isCurrent: () => current() && targetObservationEpoch.current === ticket && isSelectionCurrent()
            && targetObservationContextEpoch.current === targetObservationRenderEpoch && sourceSelection === selectionEpoch.current
            && editorLocation.current === originModule && workspaceViewRef.current === 'TASKS' && productionClientRef.current === originalClient
            && discardPermission.current.value && discardPermission.current.generation === discardPermissionGeneration };
        const key = JSON.stringify([projectId, target.incarnation, capturedJob.id, capturedJob.version, capturedJob.request_digest]);
        const claim = () => {
          if (discardClaims.current.has(key)) return false;
          discardClaims.current.add(key);
          discardTraces.current.set(key, { key, ownerKey: cacheKey, projectId, incarnation: target.incarnation, jobId: capturedJob.id,
            requestId: capturedJob.request_id, requestDigest: capturedJob.request_digest, version: capturedJob.version,
            target: canonicalImageNode(target), state: 'UNKNOWN' });
          publishDiscardTraces(); return true;
        };
        const onConfirmed = (receipt: StudioImageNodeJobDiscard) => {
          if (!source.isCurrent() || receipt.job.id !== capturedJob.id || receipt.job.version !== capturedJob.version + 1
            || receipt.job.request_digest !== capturedJob.request_digest || receipt.job.status !== 'CANCELLED'
            || receipt.job.request_id !== capturedJob.request_id || receipt.incarnation !== target.incarnation
            || canonicalImageNode(receipt.target) !== canonicalImageNode(target) || receipt.job.attempt !== 0
            || receipt.job.output_candidate !== null || receipt.job.receipt_digest !== null || receipt.job.cancellation_mode !== 'LOCAL_RESULT_DISCARD'
            || receipt.local_result_discarded !== true || receipt.remote_stop_confirmed !== false || receipt.automatic_actions !== false) return;
          const trace = discardTraces.current.get(key); if (trace) { trace.state = 'ACK_CONFIRMED'; publishDiscardTraces(); }
        };
        setTargetObservation(undefined); setJobObservation(undefined); setDiscardPreparation({ ticket, source, claim, onConfirmed });
      }}
      onOpen={(job, isSelectionCurrent) => {
        if (!isSelectionCurrent() || !current() || busyRef.current) return;
        if (job.command && Object.hasOwn(job.command, 'canvas_image_node')) { openProductionNodeResume(job, isSelectionCurrent); return; }
        const epoch = selectionEpoch.current;
        navigate(() => {
          if (!isSelectionCurrent() || !current() || busyRef.current || epoch !== selectionEpoch.current) return;
          setTaskTarget(undefined); setStoryboardHandoff(undefined); setAssetHandoff(undefined); setMediaHandoff(undefined);
          setProductionJob({ client: productionClient, job }); setWorkspaceView('PRODUCTION');
        });
      }} />}
    {workspaceView === 'TASKS' && overview && !denied && !identityRetired && targetObservation && targetObservation.source.isCurrent()
      && <CanvasImageNodeTargetPanel key={targetObservation.source.key} projectId={projectId} branchId={context.scope?.branchId ?? null}
        client={productionClient} source={targetObservation.source} read={guarded}
        onUnavailable={() => { if (targetObservationEpoch.current === targetObservation.ticket && targetObservation.source.isCurrent()) deny(); }}
        onClose={() => { if (targetObservationEpoch.current === targetObservation.ticket) retireTargetObservation(); }} />}
    {workspaceView === 'TASKS' && overview && !denied && !identityRetired && jobObservation && jobObservation.source.isCurrent()
      && <CanvasImageNodeJobObservationPanel key={jobObservation.source.key} projectId={projectId} branchId={context.scope?.branchId ?? null}
        client={productionClient} source={jobObservation.source} read={guarded}
        onObserved={snapshot => { if (targetObservationEpoch.current === jobObservation.ticket && jobObservation.source.isCurrent()) observedDiscardState(snapshot); }}
        onUnavailable={() => { if (targetObservationEpoch.current === jobObservation.ticket && jobObservation.source.isCurrent()) deny(); }}
        onClose={() => { if (targetObservationEpoch.current === jobObservation.ticket) retireTargetObservation(); }} />}
    {workspaceView === 'TASKS' && overview && !denied && !identityRetired && discardPreparation && discardPreparation.source.isCurrent()
      && <CanvasImageNodeJobDiscardPanel key={discardPreparation.source.key} projectId={projectId} branchId={context.scope?.branchId ?? null}
        client={productionClient} source={discardPreparation.source} read={guarded} mutate={guardedDiscardWrite} canMutate={writable}
        claim={discardPreparation.claim} onConfirmed={discardPreparation.onConfirmed}
        onUnavailable={() => { if (targetObservationEpoch.current === discardPreparation.ticket && discardPreparation.source.isCurrent()) deny(); }}
        onClose={() => { if (targetObservationEpoch.current === discardPreparation.ticket) retireTargetObservation(); }} />}
    {workspaceView === 'TASKS' && overview && !denied && !identityRetired && taskTarget && <TaskOwnerResult key={taskTarget.id}
      projectId={projectId} scope={context.scope} identity={cacheKey} target={taskTarget.target} transport={taskTransport}
      busy={busy} isCurrent={current} read={guarded} onClose={() => setTaskTarget(undefined)} />}
    {startVisible && <StudioStartPanel controller={entry} onOpenProject={id => {
      if (id === projectId) { navigate(() => setWorkspaceView(resume.state === 'SAVED' ? resume.location.view : 'ASSETS')); setNotice('已回到本项目保存的位置。'); return; }
      setNotice(`项目“${id}”已经存在；请从项目列表打开它，当前工作区不会自动切换，也不会为它新建任何内容。`);
    }} mode={interfaceMode} onModeChange={changeInterfaceMode} />}
    {workspaceView === 'ASSETS' && overview && !denied && (
      <PromptWorkspace
        key={`prompts:${cacheKey}`}
        projectId={projectId}
        branchId={null}
        actor={cacheKey}
        transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })}
        scope={context.scope}
        mode={interfaceMode}
        writable={writable}
        denied={denied || identityRetired}
        onDirtyChange={promptDraftChanged} />
    )}
    {workspaceView === 'ASSETS' && overview && <Panel title="独立素材工作区"><p>无需小说、章节或模型，导入素材即可保存和导出。</p><p>上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。</p>{overview && <Badge tone="info">{!writable ? overview.capabilities.can_review === true ? '仅审核与读取' : '只读' : overview.capabilities.media_validator_configured ? '手工导入可用' : '媒体校验工具缺失'} · 不需要模型</Badge>}{overview && !overview.capabilities.media_validator_configured && <p>图片、视频和音频导入需要 FFmpeg / ffprobe 校验工具。当前可查看和导出已保存资产，未调用模型。</p>}</Panel>}
    {module === 'VIDEO' && workspaceView === 'ASSETS' && overview && !denied && <StudioVideoReferencePanel scope={client} assets={rows}
      blocked={busy || dirty} canSave={writable} isCurrent={current}
      onPreview={(asset, window, signal) => guarded(() => client.previewVideoReference(asset, window, signal), signal)}
      onSave={async (asset, review, selectedIndex, signal) => {
        if (!current() || !writable || busyRef.current || dirtyRef.current || signal.aborted) throw new Error('请先处理当前输入并核对写入权限。');
        const identity = JSON.stringify([asset.id, asset.version, asset.sha256, review.preview_digest, selectedIndex, review.frames[selectedIndex].png_sha256]);
        if (lastVideoReferenceSave.current?.unknown && lastVideoReferenceSave.current.body !== identity) throw new Error('上次参考帧保存结果未知，请先核对相同原视频和采样帧，不要另建请求。');
        if (lastVideoReferenceSave.current?.body !== identity) lastVideoReferenceSave.current = {body:identity,key:crypto.randomUUID(),unknown:false};
        const request = lastVideoReferenceSave.current;
        try {
          request.unknown = true;
          const result = await graphMutation(() => client.saveVideoReference(asset, review, selectedIndex, request.key, signal));
          if (!current()) return;
          request.unknown = false; refreshedAsset(result.asset);
          setNotice(result.receipt.replayed ? '已核对原来的视频参考帧素材，未重复创建。' : '视频参考帧已保存到原素材库，保留视频来源版本与时间戳。图片到视频可通过现有素材入口另行明确使用；未调用模型。');
          await loadProductionAssets();
        } catch (reason) {
          if (current()) setNotice('参考帧保存结果未确认。请先核对素材库；相同视频、采样与所选帧重试将复用本会话原请求。刷新页面前请先核对，避免重复创建。');
          throw reason;
        } finally { if (current()) invalidateStorage(); }
      }} />}
    {workspaceView === 'ASSETS' && overview && !denied && <StudioModelReferencePanel scope={client} assets={rows} blocked={busy || dirty} canImport={writable && overview.capabilities.manual_import === true} canExport={overview.capabilities.manual_export === true} isCurrent={current}
      onInspect={asset => guarded(() => client.inspectModelReference(asset))}
      onMesh={(asset,signal) => guarded(() => client.inspectModelMesh(asset,signal),signal)}
      onScene={(asset,signal) => guarded(() => client.inspectModelScene(asset,signal),signal)}
      onDepth={(asset,camera,signal) => guarded(() => client.exportModelDepth(asset,camera,signal),signal)}
      onClay={(asset,camera,signal) => guarded(() => client.exportModelClay(asset,camera,signal),signal)}
      canSaveClay={writable}
      onSaveClay={async (asset,review) => {
        if(!current()||!writable||busyRef.current||dirtyRef.current)throw new Error('请先处理当前输入并核对写入权限。');
        const identity=JSON.stringify([asset.id,asset.version,asset.sha256,review.clay_export]);
        if(lastClaySave.current?.unknown&&lastClaySave.current.body!==identity)throw new Error('上次灰模保存结果未知，请回到相同素材和视角核对，不要另建请求。');
        if(lastClaySave.current?.body!==identity)lastClaySave.current={body:identity,key:crypto.randomUUID(),unknown:false};
        const request=lastClaySave.current;
        try {
          request.unknown=true;
          const result=await graphMutation(()=>client.saveModelClay(asset,review,request.key));
          if(!current())return;request.unknown=false;refreshedAsset(result.asset);
          setNotice(result.receipt.replayed?'已核对原来的灰模参考素材，未重复创建。':'灰模参考已保存到素材库，保留原 GLB 版本与摘要；未调用模型。');
        } catch(reason) {
          if(current())setNotice('灰模保存结果未确认。请先核对素材库，或回到相同视角重新预览并确认；本会话将复用原请求。刷新页面前请先核对，避免重复创建。');
          throw reason;
        } finally {if(current())invalidateStorage();}
      }}
      onCameras={(asset,signal) => guarded(() => client.inspectModelCameras(asset,signal),signal)}
      onCameraExport={(asset,selection,signal) => guarded(() => client.exportModelCamera(asset,selection,signal),signal)}
      onMaterials={(asset,signal) => guarded(() => client.inspectModelMaterials(asset,signal),signal)}
      onImport={async body => {
        if (!current() || !writable || overview.capabilities.manual_import !== true || busyRef.current || dirtyRef.current) throw new Error('请先处理当前输入并核对项目写入权限。');
        busyRef.current = true; setBusy(true); setNotice('');
        const identity = JSON.stringify([body.filename,'model',body.content_base64]);
        if (lastImport.current?.body !== identity) lastImport.current = {body:identity,key:crypto.randomUUID(),unknown:true};
        lastImport.current.unknown = true;
        try {
          const imported = await guardedWrite(() => client.importModelReference({contract:'studio-static-glb-import/1',...body,idempotency_key:lastImport.current!.key}));
          lastImport.current!.unknown = false;
          let asset = imported;
          try {asset = await guardedWrite(() => declared(imported));setPendingDeclaration(undefined);}
          catch (reason) {if(!current())throw reason;setPendingDeclaration(imported);setNotice('GLB 文件已保存，来源声明尚未保存。可仅重试声明，无需重新上传。');}
          if(current())refreshedAsset(asset);return asset;
        } finally {busyRef.current=false;if(current()){setBusy(false);invalidateStorage();}}
      }} />}
    {loading && <StatusMessage>正在核对项目与权限…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
    {discardTraceRows.length > 0 && <section aria-label="原任务放弃采用结果记录">{visibleDiscardTraces.map(row => <StatusMessage key={row.key} tone={row.state === 'UNKNOWN' ? 'warning' : 'info'}>
      <p>{row.state === 'UNKNOWN' ? '本地采用资格修改结果待核对（UNKNOWN）；此页面不会再次发送相同版本。请显式重新读取同一任务的新版本。'
        : row.state === 'STATE_CONFIRMED' ? '原任务状态已核对为 CANCELLED；未确认远端停止，也未确认是哪一次请求造成该状态。'
        : '已收到原 owner 的 CANCELLED 回执，仅确认本地采用资格已放弃；未确认远端停止。'}</p>
      <p>原任务 ID：{row.jobId} · 原请求摘要：<code>{row.requestDigest}</code></p>
      <p>这些发送登记只保留在当前页面会话，不保证重开浏览器后的请求去重。</p>
    </StatusMessage>)}
      {hiddenDiscardUnknown > 0 && <StatusMessage tone="warning">原范围有 {hiddenDiscardUnknown} 条本地采用修改结果待核对（UNKNOWN）。原任务标识与摘要已隐藏；请恢复原身份后从原项目任务列表核对。</StatusMessage>}
    </section>}
    {denied ? <EmptyState title="当前会话无权访问此项目" detail="私人预览已关闭。重新核对身份与范围后再打开。" /> : !overview && !comicWorkspace && !loading ? <Button onClick={() => void refresh()}>重新读取项目</Button> : null}
    {pendingNavigation && (!denied || retiredExitPending) && <section className="creative-navigation-confirm" role="alert">
      <p>{retiredExitPending ? '授权失效前的未保存输入与待核对请求仍受保护。返回小说仅用于原入口重新验证；离开不会保存、取消或重复提交。' : storyboardDirty ? '分镜图片接收输入或保存结果仍待核对。离开只放弃本地接收状态，不会取消已经发出的保存；返回后须核对原文档。' : mediaDirty || timelineDirty ? '制作输入尚未保存，或请求结果仍待核对。离开只放弃本地输入，不会取消远端任务；重新打开后先读取原任务回执。' : graph.directorPending ? '有未保存的创作图／导演输入。放弃只移除本地草稿，不代表远端写入失败；若保存回执未知，返回后先核对原文档目录，避免重复创建。' : graph.dirty ? '有未保存的创作图输入。可以继续编辑，或确认放弃后离开。' : preferenceController.blocked ? '偏好保存结果尚待核对。离开不代表请求失败，再次操作前仍需读取服务端版本。' : '有未保存的偏好、来源声明或资产关联。可以继续编辑，或确认放弃后离开。'}</p>
      {(!retiredExitPending || leaveRisk.current.dirty) && <label><input type="checkbox" disabled={navigationBusy(retiredExitPending)} checked={discard} onChange={event => setDiscard(event.target.checked)} />确认放弃未保存输入</label>}
      {retiredExitPending && unknownLeaveRisk() && <><p>原请求结果仍待核对。原范围：{productionLeaveScope}。{leaveRisk.current.requestIds.length > 0 && `原请求标识：${leaveRisk.current.requestIds.join('、')}`}</p>{leaveRisk.current.productionRequests.map(request => <p key={request}>原请求归属：{request}</p>)}<label><input type="checkbox" disabled={navigationBusy(true)} checked={acknowledgeUnknown} onChange={event => setAcknowledgeUnknown(event.target.checked)} />确认保留原请求待核对后离开</label></>}
      <Button disabled={navigationBusy(retiredExitPending) || (retiredExitPending ? (leaveRisk.current.dirty && !discard) || (unknownLeaveRisk() && !acknowledgeUnknown) : !discard)} onClick={confirmNavigation}>确认离开</Button>
      <Button onClick={() => { editorTicket.current++; pendingEditor.current = undefined; retirePendingNodeResume(); setPendingNavigation(undefined); setDiscard(false); setAcknowledgeUnknown(false); }}>{retiredExitPending ? '留在当前页' : '继续编辑'}</Button>
    </section>}
    {pendingDeclaration && !denied && workspaceView === 'ASSETS' && <Button disabled={!writable || busy || lineageDirty || relationshipDirty} onClick={() => { if (busyRef.current || lineageDirtyRef.current || relationshipDirtyRef.current) return; busyRef.current = true; setBusy(true); void guardedWrite(() => declared(pendingDeclaration)).then(asset => { refreshedAsset(asset); setPendingDeclaration(undefined); setNotice('资产与外部导入来源已保存。'); }).catch(reason => { if (current()) setNotice(apiErrorView(reason, '来源声明仍未保存，文件已保留。').message); }).finally(() => { busyRef.current = false; if (alive.current) setBusy(false); }); }}>仅重试外部导入声明</Button>}
    {graphView && overview && !denied && graph.content}
    {productionView && overview && !denied && !storyboardHandoff && <ProductionDashboard controller={workflow} selectedModuleId={workflowModule}
      onSelectModule={setWorkflowModule} selectedKind={workflowAssetKind} onSelectKind={setWorkflowAssetKind} />}
    {productionView && overview && !denied && !storyboardHandoff && interfaceMode === 'PROFESSIONAL' && <StudioWorkspaceOperationPanel identity={cacheKey} denied={denied} busy={busy}
      isCurrent={current} read={guarded} loadContracts={client.productionContracts} requestedStage={productionStage}
      onStageChange={setProductionStage} onUnavailable={deny} onOpenSurface={view => navigate(() => setWorkspaceView(view))} />}
    {productionView && overview && !denied && interfaceMode === 'NOVICE' && <Panel title="制作操作（新手模式）">
      <p>新手模式只展开主要操作：素材执行、时间线与任务中心都在本页或“任务中心”里。制作操作契约、阶段与来源详情属于专业视图。</p>
      <p>两种模式使用同一份项目、素材、任务与草稿；切换不会转换、复制或删除任何数据。</p>
      <Button onClick={() => changeInterfaceMode('PROFESSIONAL')}>切换到专业模式查看契约与参数</Button>
    </Panel>}
    {productionView && overview && !denied && !storyboardHandoff && <>
      {!resumedNode && <Button disabled={busy} onClick={() => void loadProductionAssets()}>读取当前素材版本</Button>}
      <StudioMediaExecutionPanel leaveGuard={leaveGuard} key={`media:${cacheKey}:${productionRevision}:${resumedNode?.ticket ?? 'ordinary'}`} client={productionClient} assets={rows} assetHandoff={mediaHandoff}
        canMutate={!resumedNode?.readOnly && writable && !preferenceDirty && !lineageDirty && !relationshipDirty} canReview={!resumedNode?.readOnly && overview.capabilities.can_review === true}
        busy={busy} isBusy={operationPending} isCurrent={resumedNode ? resumeSourceCurrent : current} read={guarded} mutate={graphMutation} cutoutExecution={cutoutExecution}
        resumeOnly={!!resumedNode} resumeReadOnly={resumedNode?.readOnly === true} canvasNodeTask={resumedNode ? { binding: resumedNode.binding, initialPrompt: resumedNode.initialPrompt, isCurrent: resumeSourceCurrent } : undefined}
        onDirtyChange={mediaDraftChanged} onUnavailable={deny} externalJob={productionJob?.client === productionClient ? productionJob.job : undefined} onApproved={productionApproved} onOpenApprovedAsset={openApprovedAsset} />
      {!resumedNode && <StudioTimelineEditor leaveGuard={leaveGuard} key={`timeline:${cacheKey}:${productionRevision}:${module}`} mediaKind={module === 'AUDIO' ? 'AUDIO' : 'VIDEO'} client={productionClient} assets={rows} projectId={projectId} assetHandoff={assetHandoff}
        canMutate={writable && !preferenceDirty && !lineageDirty && !relationshipDirty} busy={busy} isBusy={operationPending}
        isCurrent={current} read={guarded} mutate={graphMutation} onDirtyChange={timelineDraftChanged} onUnavailable={deny}
        onJob={job => { if (current()) setProductionJob({ client: productionClient, job }); }} />}
    </>}
    {productionView && storyboardHandoff && overview && !denied && !identityRetired && <StudioStoryboardAssetHandoff key={storyboardHandoff.id}
      exactImage={storyboardHandoff} client={directorSource} studio={client} production={productionClient}
      active editable={writable && !preferenceDirty && !lineageDirty && !relationshipDirty && !graph.dirty && !mediaDirty && !timelineDirty && !maskDirty && !workflowDirty && !promptDirty}
      busy={busy} isBusy={operationPending} isCurrent={() => current() && selectionEpoch.current === storyboardHandoff.selectionEpoch && !lineageDirtyRef.current && !relationshipDirtyRef.current && !graphDirtyRef.current && !mediaDirtyRef.current && !timelineDirtyRef.current && !maskDirtyRef.current && !workflowDirtyRef.current && !promptDirtyRef.current}
      perform={storyboardPerform} ownsOperation={storyboardOwnsOperation} onDirtyChange={storyboardDraftChanged} onDenied={deny}
      onClose={() => navigate(() => { setStoryboardHandoff(undefined); storyboardDraftChanged(false); })} />}
    {workspaceView === 'ASSETS' && overview && !denied && relationshipReview && <section aria-label="关联原资产精确版本审阅"><h3>关联原资产精确版本审阅</h3><p>右侧保留刚核对的原资产版本。当前素材目录暂时关闭，避免随后读取的最新详情替代关联版本。</p><Button disabled={busy} onClick={() => navigate(() => { selectionEpoch.current++; setRelationshipReviewEpoch(undefined); setNotice('已返回当前素材浏览。目录和详情按当前版本读取；不代表关联时的历史版本。'); })}>返回当前素材浏览</Button></section>}
    {workspaceView === 'ASSETS' && overview && !denied && !relationshipReview && <AssetLibraryPanel novelId={projectId} adapter={adapter} selectedAssetId={selected?.id} onSelectAsset={asset => navigate(() => { selectionEpoch.current += 1; setFormRevision(value => value + 1); setSelected(asset); setLineageDirty(false); setRelationshipDirty(false); })} />}
    {workspaceView === 'ASSETS' && overview && !denied && !relationshipReview && <AssetBrowserPanel projectId={projectId}
      transport={assetTransport}
      scope={context.scope} identity={cacheKey} active={workspaceView === 'ASSETS' && !denied && !identityRetired}
      denied={denied || identityRetired} busy={busy} isCurrent={current} read={guarded} mutate={graphMutation}
      selectedId={selected?.id} onSelect={assetId => navigate(() => { void refreshSelectedAsset(assetId); })}
      onSendTo={(target, reference) => {
        if (target !== 'TIMELINE' && target !== 'IMAGE' && target !== 'VIDEO' && target !== 'STORYBOARD') { setNotice(`已准备把素材 ${reference.asset_id} · v${reference.version} · 摘要 ${reference.digest.slice(0, 12)}… 送往 ${target}。目标模块不会被自动执行，请在对应工作区明确使用该版本；这里只传递原资产 ID、版本与摘要。`); return; }
        const epoch = selectionEpoch.current;
        navigate(() => {
          if (!current() || epoch !== selectionEpoch.current) return;
          const exact = { ...reference };
          const handoff = { id: crypto.randomUUID(), reference: exact, readAsset: () => guarded(() => client.asset(exact.asset_id)) };
          if (target === 'STORYBOARD') { setStoryboardHandoff({ ...handoff, selectionEpoch: epoch }); storyboardDraftChanged(true); setAssetHandoff(undefined); setMediaHandoff(undefined); }
          else if (target === 'IMAGE' || target === 'VIDEO') { setStoryboardHandoff(undefined); setMediaHandoff({ ...handoff, target }); setAssetHandoff(undefined); }
          else { setStoryboardHandoff(undefined); setAssetHandoff(handoff); setMediaHandoff(undefined); }
          setWorkspaceView('PRODUCTION');
        });
      }}
      onUnavailable={deny} />}
    {productionView && overview && !denied && !storyboardHandoff && <>
      <Button aria-expanded={guideOpen} onClick={() => setGuideOpen(true)}>按需打开项目提示助手</Button>
      {guideOpen && <ProjectGuidePanel projectId={projectId} identity={cacheKey} active denied={denied} workflow={overview}
        onNavigate={target => { if (target === 'STORYBOARD') { setNotice('分镜工作区在创作模块的导演/分镜检查器旁按需打开。'); return; } navigate(() => setWorkspaceView(target as StudioWorkspaceView)); }}
        onUnavailable={deny} />}
      <Button aria-expanded={modelOpen} onClick={() => setModelOpen(true)}>按需打开模型中心</Button>
      {modelOpen && <ModelCenterPanel projectId={projectId}
        transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })}
        scope={context.scope} identity={cacheKey} active denied={denied} busy={busy} isCurrent={current}
        read={guarded} mutate={graphMutation} onUnavailable={deny} />}
      <Button aria-expanded={deliveryOpen} onClick={() => setDeliveryOpen(true)}>按需打开统一导出与工程交接</Button>
      {deliveryOpen && <DeliveryCenterPanel projectId={projectId}
        transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })}
        scope={context.scope} identity={cacheKey} active denied={denied} busy={busy} isCurrent={current}
        read={guarded} mutate={graphMutation} onUnavailable={deny} />}
    </>}
    {module === 'IMAGE' && workspaceView === 'ASSETS' && overview && !denied && selected && <StudioManualMaskPanel leaveGuard={leaveGuard}
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
    <StudioAssetDeclarationForm key={`${selected.id}:${selected.version}:${formRevision}`} row={lineageAsset(selected)} assets={rows.map(lineageAsset)} readOnly={!writable || busy || relationshipDirty || maskDirty} onDirtyChange={lineageDraftChanged} saved={() => {}} saveLineage={async body => { if (busyRef.current || !writable || relationshipDirtyRef.current || maskDirtyRef.current) throw new Error('请先保存或放弃关联输入，再保存来源声明。'); busyRef.current = true; setBusy(true); try { const value = await guardedWrite(() => client.lineage(selected.id, body)); refreshedAsset(value); setNotice('来源声明已保存。'); return value; } finally { busyRef.current = false; if (alive.current) setBusy(false); } }} />
    <Button disabled={busy} onClick={() => navigate(() => { void refreshSelectedAsset(selected.id); })}>重新读取当前资产</Button>
  </section>}
    <AssetRelationshipsPanel key={`${relationshipRenderEpoch.current}:${selected.id}:${selected.version}:${formRevision}`} asset={selected} client={client} canMutate={writable} canReview={overview?.capabilities.can_review === true && !denied} blocked={lineageDirty || maskDirty} busy={busy} isCurrent={current} read={guarded} onDirtyChange={relationshipDraftChanged} onOpenAsset={openRelationshipAsset} mutate={async operation => {
      if (busyRef.current || lineageDirtyRef.current || maskDirtyRef.current || !current()) throw new Error('请先保存或放弃来源输入，再修改关联。');
      busyRef.current = true; setBusy(true);
      try { const asset = await guardedWrite(operation); refreshedAsset(asset); setNotice('关联已保存，原文件和引用内容未改变。'); return asset; }
      finally { busyRef.current = false; if (alive.current) setBusy(false); }
    }} />
  </>;
  const retiredNotice = <EmptyState title="身份已改变" detail="原范围的服务端信息已关闭。请重新核对身份与项目后打开工作区。" />;
  if (editorSession && editorSession.module === module && editorSession.ticket === editorTicket.current && !denied && !identityRetired) return <StudioProductionLeaveContext.Provider value={leaveGuard}><CreativeWorkspace enabled novelId={projectId} context={context} scope={scope} actor={actor}
    chapterCount={0} manuscriptReady={false} novelMain={null} novelSidebar={null} novelInspector={null} novelStatus={null} commonStatus={status}
    storyboardHost={{ module: editorSession.module, prepared: editorSession.prepared, returnLabel: '返回独立创作图',
      isCurrent: () => current() && editorTicket.current === editorSession.ticket && editorLocation.current === editorSession.module }}
    onExit={() => { editorTicket.current++; setEditorSession(undefined); setNotice('已返回独立创作图；分镜沿原文档保存，图绑定未改变。'); }}
    onModuleChange={next => { editorTicket.current++; setEditorSession(undefined); onModuleChange(next); }} /></StudioProductionLeaveContext.Provider>;
  return <StudioProductionLeaveContext.Provider value={leaveGuard}><AppShell module={module} onModuleChange={next => navigate(() => onModuleChange(next), next === 'NOVEL')} scope={identityRetired ? { workspace: '待核对', project: '待核对', storyline: '待核对', branch: '待核对' } : { ...scope, project: overview?.project.title || comicWorkspace?.project.title || scope.project }} projectNoun={comicOnly || overview?.project.entry_kind === 'NEUTRAL_STUDIO' ? '项目' : undefined} actor={identityRetired ? '身份待核对' : actor} sidebar={identityRetired ? retiredNotice : sidebar} main={identityRetired ? graphView ? graph.content : retiredNotice : main}
    inspector={identityRetired ? graphView ? graph.inspector : retiredNotice : denied ? <EmptyState title="权限失效" detail="重新核对身份与项目范围后再打开。" /> : comicOnly ? <EmptyState title="漫画制作" detail="页面和书册权限由原漫画入口核对。" /> : graphView ? graph.inspector : productionView ? <><Panel title="制作操作"><p>当前阶段：{productionStage}</p><p>在主工作区核对输入、版本、来源和审核要求。实际任务的权限、状态与回执由原执行入口确认。</p></Panel>{!storyboardHandoff && <ProductionInspectorPanel controller={workflow} selectedModuleId={workflowModule} selectedKind={workflowAssetKind} onSelectKind={setWorkflowAssetKind} modelSource={modelSource}/>}</> : <AssetInspector asset={selected} novelId={projectId} downloadAsset={adapter.download} isCurrent={current} showReferences={false} extra={extra} />}
    status={<>{identityRetired ? '身份已改变' : denied ? '权限失效' : loading ? '正在核对' : error ? '读取失败' : busy ? readingAsset || preferenceController.pending === 'READ' ? '读取中' : '操作中' : dirty || pendingDeclaration ? '未保存或待核对' : '已保存'} · {comicOnly ? '独立漫画' : productionView ? '制作操作' : graphView ? '创作图' : '独立素材'} · 模型调用记录见运行回执{!identityRetired && status}</>} /></StudioProductionLeaveContext.Provider>;
}
