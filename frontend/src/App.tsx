import { useStyleDNALeaveGuard } from './experimental/useStyleDNALeaveGuard';
import { Button } from './ui/primitives';
import { useLocalTutorIntegration, type EditorSelection } from './interop/entry';
import type { HostRoute } from './interop/client';
import { assertCurrentHandoff, currentInteropSurface, currentInteropTaskId, interopFeatureRoutes } from './interop/navigation';
import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  QueryClient,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  api,
  ApiError,
  Chapter,
  type CollaborationContext,
  Novel,
  Scope,
  setCollaborationContext,
  getCollaborationContext,
} from "./api";
import { useStudio } from "./store";
import { useLastChapter } from "./workspace/defaultui/useLastChapter";
import { lastChapterIdentityPending, lastPosStatus } from "./workspace/defaultui/lastPosGate";
import { DefaultTasksDrawer } from "./workspace/defaultui/DefaultTasksDrawer";
import { readLocalWorkspaceSelection, rememberLocalWorkspaceSelection, readLocalStudioSelection } from "./workspaceSelection";
import { ChapterEditor, proseDocument } from "./Editor";
import {
  drafts,
  exportDraftText,
  type DraftDurability,
  type LocalDraft,
  conflicts,
  conflictResolutionDrafts,
  PersistentConflict,
} from "./drafts";
import {
  rebaseNewerDraft,
  recoveryKey,
  SingleFlight,
} from "./collaborationGuards";
import { ConflictDialog } from "./ConflictDialog";
import { UnifiedWorkspacePreviewHost } from "./workspace/state/identityBootstrap"; // [HERMIA-FE-20261025 U1fix]
import { RevisionPanel, type RevisionDetail } from "./RevisionPanel";
import { CollaborationPanel } from "./CollaborationPanels";
import { AppShell, type StudioModule, SettingsPathGateway } from "./ui/AppShell";
import { t as i18nT, tz, useLocale, formatNumber } from "./i18n"; // [HERMIA-FE-20261025 I18N P1] string-only: status bar / desk labels
import { selectedScopeLabels } from "./ui/scopeLabels";
import { ModuleWorkspaceRoutes } from "./ui/ModuleWorkspaceRoutes";
import { EMPTY_EDITOR_SELECTION, shouldRestoreNovelWriteOnEnter } from "./ui/moduleSwitchIsolation";
import { ModuleStartGate, markModuleStartGateDismissed, shouldOpenModuleStartGate } from "./ui/ModuleStartGate"; // [HERMIA-FE-20261022] H-UX-START-01
import { CreativeWorkspace } from "./creative/CreativeWorkspace";
import { BlankProjectEntry } from './creative/BlankProjectEntry';
import { IndependentStudioWorkspace, isManualStudioModule } from './creative/IndependentStudioWorkspace';
import { createStudioProject, studioClient } from './creative/studioClient';
import { WorkflowPanel } from './novel/WorkflowPanel';
import { ImageQueuePanel } from './novel/ImageQueuePanel';
import { MotionTaskWorkspace } from './novel/MotionTaskWorkspace';
import { AssetLibraryPanel } from "./novel/AssetLibraryPanel";
import { EntityAssetPanel } from "./novel/EntityAssetPanel";
import { VisionAnalysisPanel } from "./novel/VisionAnalysisPanel";
import { ImageGenerationPanel } from "./novel/ImageGenerationPanel";
import { MultimodalDirectorWorkspace } from "./novel/MultimodalDirectorWorkspace";
import { VisualContextPanel } from "./novel/VisualContextPanel";
import { SpeechSynthesisPanel } from "./novel/SpeechSynthesisPanel";
import { PluginManagerPanel } from "./novel/PluginManagerPanel";
import { AudiobookManifestPanel } from "./novel/AudiobookManifestPanel";
import { AssetWorkspaceRoute } from "./ui/AssetWorkspaceRoute";
import { WorkflowWorkspaceRoute } from "./ui/WorkflowWorkspaceRoute";
import {
  reduceSaveState,
  SaveControls,
  saveStateLabel,
  recoveryStateLabel,
  type SaveState,
} from "./ui/SaveControls";
import { EntryExperience } from "./novel/EntryExperience";
import { SampleJourneyGuide } from "./novel/SampleJourneyGuide";
import { ChapterTree } from "./novel/ChapterTree";
import { CharacterEditor, CharacterConsistencyPanel, CharacterEvolutionPanel, ForeshadowingEditor, ForeshadowingTrackerPanel, LocationEditor, OutlineEditor, RelationshipEditor, RelationshipGraph, SceneEditor, StoryDatabase, StoryRouteEditor, TimelineEditor, VolumeEditor, WorldSummaryEditor, WorldRulesPanel, type CharacterDraft, type ForeshadowingDraft, type LocationDraft, type OutlineDraft, type RelationshipDraft, type SceneDraft, type StoryRouteDraft, type TimelineDraft, type VolumeDraft, type StoryDatabaseKind } from "./novel/StoryDatabase";
import {
  AiWritingPanel,
  type AiOperation,
  type AiVariantDraft,
} from "./novel/AiWritingPanel";
import { VisualTextWorkflow } from "./novel/VisualTextWorkflow";
import { RuntimeDiagnostics } from "./novel/RuntimeDiagnostics";
import { AgentJobHistory, AgentTeamPanel } from "./novel/AgentTeamPanel";
import { AgentActivityCenter } from "./novel/AgentActivityCenter";
import { NovelImportPanel } from "./novel/NovelImportPanel";
import { AdaptationPanel } from "./novel/AdaptationPanel";
import { ScreenplayPanel } from "./novel/ScreenplayPanel";
import { ExportPanel } from "./novel/ExportPanel";
import { CapabilityRoadmapPanel } from "./ui/CapabilityRoadmapPanel";
import { NovelOverviewPanel } from "./novel/NovelOverviewPanel";
import { ResearchPanel } from "./novel/ResearchPanel";
import { ContinuityCheckPanel } from "./novel/ContinuityCheckPanel";
import { FeatureLauncher } from "./ui/FeatureLauncher";
// [HERMIA-FE-20261022 M1-2] shared action/panel registry + command search
import { useWorkbench } from "./workbench/useWorkbench";
import { isNovelPanel } from "./workbench/novelActions";
import { LifecycleTracker } from "./workbench/lifecycle";
import { bindRestoreConfirmation, gateRestore, syncRestoreLifecycle } from "./workbench/revisionRestore";
import { CommandSearch } from "./workbench/CommandSearch";
import { useWorkbenchLayout, registerLayoutActions, shouldLeaveExecOrDirector } from "./workbench/useWorkbenchLayout";
import { decideNovelPrimaryCta, countOpenContinuityWarnings } from "./workbench/novelCta"; // [HERMIA-FE-20261022 N-UX-08]
import { novelSecondaryEntry, scrollNovelSecondaryAnchor, type NovelSecondaryEntryId } from "./workbench/novelSecondaryEntries"; // [HERMIA-FE-20261022 N-UX-11]
import { FEATURE_GROUP_DEFAULTS } from "./ui/FeatureLauncher";
import { resetLayout, type LayoutScope } from "./workbench/layout";
import { DeferredExperimentalWorkbench as ExperimentalWorkbench } from "./experimental/DeferredExperimentalWorkbench";
import { EXPERIMENTAL_GROUPS, EXPERIMENTAL_TABS } from "./experimental/experimentalNavigation";
import { experimentalFeatures, experimentalClient } from "./experimental/api";
import { WritingReferenceRail, defaultWritingPreferences, type WritingFocusPreferences } from "./experimental/WritingFocusPanel";
import type { WorkspaceNavigation, WorkspaceAnchor, ResumeResult } from "./experimental/uxClient";
import { authorContextRequest, authorContextVariants, authorVariantsKey, authorRequestKey, type AuthorVariantsReceipt, type AuthorVariantsResult, type AuthorPreviewReceipt } from "./novel/authorContextClient";
import { AiControlCenter } from "./ui/AiControlCenter";
import { MediaProviderSettings } from "./ui/MediaProviderSettings";
import "./ui/capability.css";
import DesignSystemFixture from "./ui/DesignSystemFixture";
import { isPackagedDesktopHost } from "./packagedHost";
import { generationRecovery, type RecoverableGeneration } from "./generationRecovery";
import { GenerationRecoveryPicker } from "./novel/GenerationRecoveryPicker";
import { WorldBuildingDashboard } from "./novel/WorldBuildingDashboard";
import { publishTaskSummary, summarizeTasks } from "./ui/taskSummary";
import { SourcePrivacyControl } from "./novel/SourcePrivacyControl";
import { CreationWorkbenchPanel } from "./novel/CreationWorkbenchPanel";
import { StoryPlanningWorkspace } from "./novel/StoryPlanningWorkspace";
import "./style.css";
import "./ux.css";
import "./collaboration.css";
import "./ui/ui.css";
import "./ui/FeatureLauncher.css";
import "./experimental/workspaceResume.css";
import "./rebuild/protoShell.css"; // [HERMIA-FE-20261022 REBUILD-W2] 原型外壳，最后加载
import { NovelStructureRail, NovelChapterColumn, type RailPanel } from "./rebuild/novel/NovelStructureRail"; // [HERMIA-FE-20261022 REBUILD-W3] [HERMIA-FE-20261022 R1]
import { NovelOrient, NovelModTabs } from "./rebuild/novel/NovelOrient"; // [HERMIA-FE-20261022 R1]
import { NovelAssist, type QuickOp } from "./rebuild/novel/NovelAssist"; // [HERMIA-FE-20261022 REBUILD-W3]
import { gateNovel, novelPanelAllowed, NOVEL_PRO_PANELS, NOVEL_PRO_TABS, NOVEL_PRO_LINKS } from "./rebuild/novel/novelMode"; // [HERMIA-FE-20261022 U4]
import { NovelStartEmpty } from "./rebuild/novel/NovelStartEmpty"; // [HERMIA-FE-20261022 REBUILD-W3]
import "./rebuild/novel/novelRebuild.css"; // [HERMIA-FE-20261022 REBUILD-W3] 小说工作区按原型重做
import { UnifiedWorkspacePreview, unifiedWorkspacePreviewEnabled } from "./workspace/UnifiedWorkspacePreview"; // [HERMIA-FE-20261023 M1] opt-in preview
export function cacheCreatedNovel(c: QueryClient, n: Novel) {
  c.setQueryData<Novel[]>(["novels"], (x) =>
    x?.some((v) => v.id === n.id) ? x : [...(x || []), n],
  );
}
export function shouldLoadLocalNovels(sessionToken: string, scope?: Scope) {
  return !sessionToken && !scope;
}
export function workingVariantIds(variants: AiVariantDraft[]) {
  return variants.filter((item) => item.status === "working").map((item) => item.id);
}
export const VARIANT_TIMEOUT_ERROR = "候选生成超时，请重新生成此候选。";
export function isGenerationTerminal(status: string) {
  return ["COMPLETED", "FAILED", "CANCELLED", "ACCEPTED", "REJECTED", "ACCEPTING", "ACCEPTANCE_UNCERTAIN"].includes(status);
}
export function draftStateFromGeneration(status: string): "working" | "failed" | "ready" {
  if (["QUEUED", "GENERATING", "ACCEPTING"].includes(status)) return "working";
  return status === "COMPLETED" ? "ready" : "failed";
}
export function isRecoveredDraftStale(baseVersion?: number, currentVersion?: number) {
  return baseVersion !== undefined && currentVersion !== undefined && baseVersion !== currentVersion;
}
export async function recoverGenerationJob(
  jobId: string,
  load: (id: string) => Promise<any>,
  update: (state: any) => void,
  options: { attempts?: number; intervalMs?: number; wait?: (ms: number) => Promise<void>; isActive?: () => boolean } = {},
) {
  const attempts = options.attempts ?? 300;
  const intervalMs = options.intervalMs ?? 500;
  const wait = options.wait ?? ((ms: number) => new Promise<void>((ok) => setTimeout(ok, ms)));
  for (let attempt = 0; attempt < attempts; attempt++) {
    if (options.isActive && !options.isActive()) return undefined;
    const state = await load(jobId);
    if (options.isActive && !options.isActive()) return undefined;
    update(state);
    if (isGenerationTerminal(state.status)) return state;
    await wait(intervalMs);
  }
  return undefined;
}
type GenerationOrigin = { namespace: string; chapterId: string; novelId: string; identity: string; epoch: number; serial: number; baseVersion?: number; context: CollaborationContext };
type GenerationObservation = GenerationOrigin & { active: boolean; sources: Set<EventSource> };
export default function App() {
  useLocale(); // [HERMIA-FE-20261025 I18N P1] re-render on 中/EN switch (no state/behaviour change)
  // [HERMIA-FE-20261023 M1] opt-in only (?uw=1). Value is fixed for the page load, so hook order stays stable.
  // [HERMIA-FE-20261025 U1fix] MUST-FIX 3: the preview host runs the existing collaboration bootstrap (real actor) first.
  if (unifiedWorkspacePreviewEnabled()) return <UnifiedWorkspacePreviewHost />;
  return <LegacyApp />;
}

function LegacyApp() {
  const packagedHost = isPackagedDesktopHost();
  const qc = useQueryClient(),
    s = useStudio(),
    namespace = recoveryKey(s.scope, s.sessionToken) || "file",
    saveGate = useRef(new SingleFlight<any>()),
    cancelledVariantIds = useRef(new Set<string>());
  const editorIdentity = revisionStoreIdentity(s);
  const editorEpoch = useRef(0), mounted = useRef(true), savePending = useRef(false);
  const [generationRecoveryRevision, refreshGenerationRecovery] = useState(0);
  const [generationRecoveryUnverified, setGenerationRecoveryUnverified] = useState(false);
  const generationSerial = useRef(0);
  const generationObserver = useRef<GenerationObservation>();
  const generationCreating = useRef<GenerationObservation>();
  const generationAction = useRef<{ origin: GenerationOrigin; id: string; kind: string }>();
  const [scopeEpoch, setScopeEpoch] = useState(0);
  const [hydratedIdentity, setHydratedIdentity] = useState<string>();
  const [durability, setDurability] = useState<DraftDurability>('none');
  const [composing, setComposing] = useState(false);
  const buffer = useRef<{ identity: string; value: LocalDraft }>();
  useLayoutEffect(() => {
    mounted.current = true;
    let previous = revisionStoreIdentity(useStudio.getState());
    const unsubscribe = useStudio.subscribe(state => {
      observeStudioEntry(state);
      const next = revisionStoreIdentity(state);
      if (next !== previous) {
        previous = next;
        editorEpoch.current += 1;
        stopGenerationObservation();
        setScopeEpoch(editorEpoch.current);
      }
    });
    return () => { mounted.current = false; stopGenerationObservation(); unsubscribe(); };
  }, []);
  const styleOwnerIdentity = revisionStoreIdentity({ ...s, chapterId: '' });
  const styleLeave = useStyleDNALeaveGuard(() => mounted.current
    && revisionStoreIdentity({ ...useStudio.getState(), chapterId: '' }) === styleOwnerIdentity, styleOwnerIdentity);
  useLayoutEffect(() => {
    let previous = revisionStoreIdentity({ ...useStudio.getState(), chapterId: '' });
    return useStudio.subscribe(state => {
      const next = revisionStoreIdentity({ ...state, chapterId: '' });
      if (next !== previous) { previous = next; styleLeave.retire(); }
    });
  }, [styleLeave.retire]);
  const experimentalFlags = useQuery({ queryKey: ["experimental-features", namespace], queryFn: ({ signal }) => experimentalFeatures(signal, {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}), retry: false, staleTime: 30000 });
  const hasExperimental = Object.entries(experimentalFlags.data?.features || {}).some(([key, value]) => value === true && key !== 'experimental.local_tutor_interop_v1');
  const writingRecovery = experimentalFlags.data?.features['experimental.writing_recovery_v2'] === true;
  const workspaceTools = experimentalFlags.data?.features['experimental.workspace_tools_v2'] === true;
  const independentStudios = experimentalFlags.data?.features['experimental.narrative_production_v2'] === true;
  const writingFocus = experimentalFlags.data?.features['experimental.writing_focus_v2'] === true;
  const characterMind = experimentalFlags.data?.features['experimental.character_mind_v2'] === true && experimentalFlags.data?.features['experimental.author_context_inspector_v2'] === true;
  const [characterViewpoint, setCharacterViewpoint] = useState<{ identity: string; chapterId: string; characterId: string; sceneId?: string; epoch: number }>();
  const activeCharacterId = characterMind && characterViewpoint?.identity === namespace && characterViewpoint?.chapterId === s.chapterId && characterViewpoint?.epoch === scopeEpoch ? characterViewpoint.characterId : undefined;
  const activeSceneId = activeCharacterId ? characterViewpoint?.sceneId : undefined;
  useEffect(() => { setCharacterViewpoint(undefined); }, [namespace, scopeEpoch, characterMind]);
  const [focusActive, setFocusActive] = useState(false), [writingPreferences, setWritingPreferences] = useState<WritingFocusPreferences>(defaultWritingPreferences), [referenceRevision, setReferenceRevision] = useState(0);
  const [referencesVisible, setReferencesVisible] = useState(true);
  const [projectChoiceOpen, setProjectChoiceOpen] = useState(false);
  const [projectRecoveryNotice, setProjectRecoveryNotice] = useState('');
  const workspaceClient = useMemo(() => experimentalClient(s.novelId, {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}), [namespace, s.novelId, s.actor?.id]);
  const focusPreferencesTouched = useRef(false);
  const persistedFocusPreferences = useQuery({
    queryKey: ['writing-focus-preferences', namespace, s.novelId, s.actor?.id],
    queryFn: ({ signal }) => workspaceClient.get<{ preferences: WritingFocusPreferences }>('/writing-focus/preferences', signal),
    enabled: writingFocus && !!s.novelId, retry: false,
  });
  useEffect(() => { focusPreferencesTouched.current = false; setFocusActive(false); setReferencesVisible(true); setWritingPreferences(defaultWritingPreferences); }, [namespace, s.novelId, s.actor?.id, writingFocus]);
  useEffect(() => {
    if (writingFocus && persistedFocusPreferences.data && !focusPreferencesTouched.current)
      setWritingPreferences(persistedFocusPreferences.data.preferences);
  }, [writingFocus, persistedFocusPreferences.data]);

  const lastWorkspace = useQuery({
    queryKey: ['workspace-resume', namespace, s.novelId, s.actor?.id],
    queryFn: ({ signal }) => workspaceClient.get<ResumeResult>('/workspace/resume', signal),
    enabled: workspaceTools && !!s.novelId, retry: false, refetchOnWindowFocus: false,
  });
  const [experimentalTab, setExperimentalTab] = useState<string>();
  const [workspaceSection, setWorkspaceSection] = useState<'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'>('resume');
  const [editorAnchor, setEditorAnchor] = useState<{ identity: string; anchor: WorkspaceAnchor }>();
  const [pendingAnchor, setPendingAnchor] = useState<{ namespace: string; chapterId: string; version: number; requestId: number; offset: number; scroll: number }>();
  const anchorSequence = useRef(0);
  const [corruptDraft, setCorruptDraft] = useState<{ identity: string; raw: string }>();
  const [draftRecoveryEpoch, setDraftRecoveryEpoch] = useState(0);
  const [recoveryOffline, setRecoveryOffline] = useState(() => typeof navigator !== 'undefined' && navigator.onLine === false);
  useEffect(() => {
    const update = () => setRecoveryOffline(navigator.onLine === false);
    addEventListener('online', update); addEventListener('offline', update);
    return () => { removeEventListener('online', update); removeEventListener('offline', update); };
  }, []);
  const [taskTarget, setTaskTarget] = useState<{ namespace: string; novelId: string; id: string; authority?: string; parent_id?: string; version?: number }>();
  const [storyTarget, setStoryTarget] = useState<{ namespace: string; novelId: string; requestId: number; id: string; record_kind: NonNullable<WorkspaceNavigation['record_kind']> }>();
  const [pendingGenerationOpen, setPendingGenerationOpen] = useState<{ namespace: string; novelId: string; actorId?: string; chapterId: string; jobId: string }>();

  const [token, setToken] = useState(s.sessionToken),
    [scopeDraft, setScopeDraft] = useState<Scope>(
      s.scope || {
        workspaceId: "",
        projectId: "",
        storylineId: "",
        branchId: "",
      },
    ),
    [text, setText] = useState(""),
    [doc, setDoc] = useState<any>(),
    [baseVersion, setBaseVersion] = useState(0),
    [saveState, setSaveState] = useState<SaveState>("saved"),
    [shellMessage, setShellMessage] = useState(""),
    [reorderingChapters, setReorderingChapters] = useState(false),
    [panel, setPanel] = useState("write"), // [HERMIA-FE-20261022] N-P0-02 cold start = pure Editor shell (not history)
    [conflict, setConflict] = useState<PersistentConflict>(),
    [tool, setTool] = useState("continue"),
    [instruction, setInstruction] = useState(""),
    [selection, setSelection] = useState<EditorSelection>({ from: 0, to: 0, text: "" }),
    [job, setJob] = useState<any>();
  const [featureGroups, setFeatureGroups] = useState<Record<string, boolean>>(() => {
    const defaults = { create: true, production: true, collaboration: false, system: false };
    if (typeof window === "undefined") return defaults;
    try { return { ...defaults, ...JSON.parse(localStorage.getItem("studio-feature-groups") || "{}")} } catch { return defaults; }
  });
  useEffect(() => { try { localStorage.setItem("studio-feature-groups", JSON.stringify(featureGroups)); } catch { /* storage may be unavailable in private hosts */ } }, [featureGroups]);
  const [interopControlTab, setInteropControlTab] = useState<'models'>();
  const [interopControlSurface, setInteropControlSurface] = useState('settings');
  const [interopTask, setInteropTask] = useState<{ id: string; status: string; chapterId?: string }>();
  useLayoutEffect(() => { setInteropTask(undefined); }, [namespace, s.novelId, s.chapterId]);
  const [creativeWorkbenchOpen, setCreativeWorkbenchOpen] = useState(false);
  const [requestedStudioProject, setRequestedStudioProject] = useState<string>();
  const [requestedStudioAsset, setRequestedStudioAsset] = useState<string>();
  const requestedStudioEntry = useRef<object>();
  const studioEntryInstance = useId();
  // Module intent belongs to this entry, not a chapter or another authority.
  // Keep credentials in memory; only the opaque instance/epoch enters query keys.
  const studioEntryApplied = useRef({ identity: '', baseIdentity: '', actorId: undefined as string | undefined,
    epoch: 0, explicit: false, applied: false });
  function observeStudioEntry(state: ReturnType<typeof useStudio.getState>) {
    const identity = revisionStoreIdentity({ ...state, chapterId: '' });
    const previous = studioEntryApplied.current;
    if (previous.identity === identity) return;
    const baseIdentity = revisionStoreIdentity({ ...state, actor: undefined, chapterId: '' });
    // The original bootstrap fills an unknown actor in this same connection.
    // Preserve its intent and callbacks, while refreshing the captured transport.
    if (previous.baseIdentity === baseIdentity && previous.actorId === undefined && state.actor?.id) {
      previous.identity = identity; previous.actorId = state.actor.id; previous.epoch++;
    } else studioEntryApplied.current = { identity, baseIdentity, actorId: state.actor?.id,
      epoch: previous.epoch + 1, explicit: false, applied: false };
  }
  observeStudioEntry(s);
  const studioEntry = studioEntryApplied.current;
  const studioEntryEpoch = studioEntry.epoch;
  const [studioModule, setStudioModule] = useState<StudioModule>("NOVEL"),
    [draftAction, setDraftAction] = useState<"accept" | "reject">(),
    [generationStarting, setGenerationStarting] = useState(false),
    [variantCancelling, setVariantCancelling] = useState(false),
    [generationRecovering, setGenerationRecovering] = useState(false),
    [variantDrafts, setVariantDrafts] = useState<AiVariantDraft[]>([]),
    [activeVariant, setActiveVariant] = useState(0);
  // [HERMIA-FE-20261022] H-UX-START-01 · cold-start six-module gate (session; #skip)
  // [HERMIA-FE-20261022 REBUILD-W3] /novels 是明确的写作入口：不弹起步弹窗，不自动跳到媒体工作区；?novel=<id> 可直接打开某部作品
  const novelsRoute = typeof location !== 'undefined' && location.pathname.startsWith('/novels');
  const [aiQuickOp, setAiQuickOp] = useState<{ op: QuickOp; nonce: number }>(); // [HERMIA-FE-20261022 R1] 右栏 AI 快捷入口
  const [startGateOpen, setStartGateOpen] = useState(() => shouldOpenModuleStartGate() && !novelsRoute);
  const commitStudioModule = useCallback((module: StudioModule) => {
    if (!mounted.current || studioEntryApplied.current !== studioEntry
        || revisionStoreIdentity({ ...useStudio.getState(), chapterId: '' }) !== studioEntry.identity) return;
    // Clicking the current module is explicit too; React may not render again.
    studioEntry.explicit = true;
    // [HERMIA-FE-20261022 X-UX-08] media/NLE → NOVEL restores write 四象限; clear selection so it does not leak into other modules
    const restoreWrite = shouldRestoreNovelWriteOnEnter(studioModule, module);
    setStudioModule(module);
    if (restoreWrite) {
      setPanel("write");
      setSelection({ ...EMPTY_EDITOR_SELECTION });
    }
  }, [studioEntry, studioModule]);
  const navigateStudioModule = useCallback((module: StudioModule) => {
    if (module === studioModule) { commitStudioModule(module); return; }
    styleLeave.request(current => { if (current()) commitStudioModule(module); });
  }, [studioModule, commitStudioModule, styleLeave.request]);

  // [HERMIA-FE-20261022 M1-2] Legacy guarded navigation kept as the ONLY real navigation path;
  // registry actions and command search call it, unknown ids fall back to it directly.
  // [HERMIA-FE-20261022 H-P0-01] Novel panels always land in NOVEL so ChapterTree + AiWriting stay visible.
  const legacySelectPanel = (next: string) => {
    // Novel feature ids (history/creation/story/check/…) keep ChapterTree + AiWriting by forcing NOVEL.
    const needsNovel = isNovelPanel(next);
    if (next === panel && (!needsNovel || studioModule === 'NOVEL')) return;
    styleLeave.request(current => {
      if (!current()) return;
      if (needsNovel) commitStudioModule('NOVEL');
      if (next !== panel) setPanel(next);
    });
  };
  // [HERMIA-FE-20261022 overnight] T1 focus hooks — no new FL ids (AiWriting/ChapterTree/Editor).
  const focusNovelSurface = useCallback((target: 'aiWriting' | 'chapterTree' | 'editor') => {
    if (target === 'aiWriting') {
      document.querySelector<HTMLElement>('.novel-writer-dock__section--ai')?.scrollIntoView({block: 'nearest'});
      document.querySelector<HTMLElement>('.novel-writer-dock__section--ai summary')?.focus?.();
    } else if (target === 'chapterTree') {
      document.querySelector<HTMLElement>('.workspace-sidebar--novel .tree, .workspace-sidebar--novel')?.scrollIntoView({block: 'nearest'});
      (document.querySelector('.workspace-sidebar--novel button, .workspace-sidebar--novel [role="treeitem"]') as HTMLElement | null)?.focus?.();
    } else {
      const el = document.querySelector<HTMLElement>('.app-shell[data-module="NOVEL"] .ProseMirror, .app-shell[data-module="NOVEL"] .editor');
      el?.focus?.();
      el?.scrollIntoView?.({block: 'nearest'});
    }
  }, []);
  const workbench = useWorkbench(legacySelectPanel, { projectId: s.novelId || null, clientId: namespace, documentId: s.chapterId || null, identity: s.actor?.id ?? null }, [], focusNovelSurface, navigateStudioModule);
  // [HERMIA-FE-20261022 H-P1-01] layout.mode basic|pro — unique source loadLayout/saveLayout
  const layoutScope = useMemo<LayoutScope>(() => ({
    userId: s.actor?.id || 'local-author',
    projectId: s.novelId || 'no-project',
    projectInstanceId: namespace || 'default',
  }), [s.actor?.id, s.novelId, namespace]);
  const {mode: shellMode, setMode: setShellModeRaw} = useWorkbenchLayout(layoutScope, workbench.panels);
  const applyShellMode = useCallback((mode: 'basic' | 'pro') => {
    const prev = shellMode;
    setShellModeRaw(mode);
    // basic: collapse production FL group (S1); user may re-expand until next switch to basic
    if (mode === 'basic') {
      setFeatureGroups(current => ({...current, production: false}));
    }
    // pro→basic: leave exec/director chrome, keep selection / objectRef
    if (prev === 'pro' && mode === 'basic') {
      const leaveSurface = shouldLeaveExecOrDirector(panel, creativeWorkbenchOpen);
      setCreativeWorkbenchOpen(false);
      if (leaveSurface) {
        styleLeave.request(current => {
          if (!current()) return;
          if (panel !== 'write') setPanel('write');
        });
      }
    }
  }, [shellMode, setShellModeRaw, panel, styleLeave, creativeWorkbenchOpen]);
  // [HERMIA-FE-20261022 U4] 普通模式下停在专业面板（一致性/版本/研究）时回落写作台，章节与草稿不动
  useEffect(() => { if (!novelPanelAllowed(panel, shellMode)) setPanel('write'); }, [panel, shellMode]);
  // Cold start: if persisted mode is basic, fold production once shellMode known
  useEffect(() => {
    if (shellMode === 'basic') setFeatureGroups(current => current.production === false ? current : {...current, production: false});
  }, [shellMode]);
  useEffect(() => {
    return registerLayoutActions(workbench.actions, {
      getMode: () => shellMode,
      setMode: applyShellMode,
      reset: () => {
        try {
          resetLayout(window.localStorage, layoutScope);
        } catch { /* ignore */ }
        setShellModeRaw('basic');
        setFeatureGroups({...FEATURE_GROUP_DEFAULTS, production: false});
      },
    });
  }, [workbench.actions, shellMode, applyShellMode, layoutScope, setShellModeRaw]);
  const independentClient = useMemo(() => studioClient(s.novelId, { sessionToken: s.sessionToken, actor: s.actor, scope: s.scope }), [studioEntry, studioEntryEpoch]);
  const studioProject = useQuery({ queryKey: ['independent-project', namespace, s.novelId, studioEntryInstance, studioEntryEpoch], queryFn: ({ signal }) => independentClient.overview(signal), enabled: independentStudios && !!s.novelId, retry: false });
  const neutralStudio = independentStudios && studioProject.data?.project?.id === s.novelId && studioProject.data.project.entry_kind === 'NEUTRAL_STUDIO';
  useEffect(() => {
    if (!independentStudios || !s.novelId || studioEntryApplied.current !== studioEntry
        || studioEntry.applied || !studioProject.isSuccess || studioProject.data?.project.id !== s.novelId) return;
    if (!neutralStudio || studioEntry.explicit || novelsRoute) { studioEntry.applied = true; return; }
    void styleLeave.request(current => {
      if (!current() || studioEntryApplied.current !== studioEntry || studioEntry.explicit) return;
      studioEntry.applied = true;
      const hint = !s.sessionToken && !s.scope && !packagedHost ? readLocalStudioSelection(s.novelId) : undefined;
      requestedStudioEntry.current = studioEntry;
      setRequestedStudioProject(s.novelId); setRequestedStudioAsset(hint?.state === 'SAVED' ? hint.assetId : undefined);
      setStudioModule(hint?.state === 'SAVED' ? hint.module : 'IMAGE');
    });
  }, [styleLeave.request, independentStudios, studioEntry, s.novelId, s.sessionToken, s.scope, packagedHost, studioProject.isSuccess, studioProject.data, neutralStudio]);
  const studioVerified = useCallback((id: string) => { void qc.invalidateQueries({ queryKey: ['independent-project', namespace, id] }); }, [qc, namespace]);
  useEffect(
    () =>
      setCollaborationContext({
        sessionToken: s.sessionToken,
        actor: s.actor,
        scope: s.scope,
      }),
    [s.sessionToken, s.actor, s.scope],
  );
  useEffect(() => {
    const update = (event: Event) => {
      const { chapterId, server } = (event as CustomEvent).detail;
      if (chapterId !== useStudio.getState().chapterId || server?.id !== chapterId) return;
      qc.setQueryData(["chapter", namespace, chapterId], server);
      drafts.remove(chapterId, namespace);
      conflicts.remove(chapterId, namespace);
      setBaseVersion(server.version);
    };
    addEventListener("studio:use-server-version", update);
    return () => removeEventListener("studio:use-server-version", update);
  }, [qc, namespace]);
  const hasCompleteScope =
    !!s.scope &&
    !!s.scope.projectId &&
    !!s.scope.storylineId &&
    !!s.scope.branchId;
  const bootstrap = useQuery({
    queryKey: ["bootstrap", namespace],
    queryFn: () => api.bootstrap(s.scope!),
    enabled: (!!s.sessionToken || packagedHost) && hasCompleteScope,
    retry: false,
  });
  useEffect(() => {
    const a = bootstrap.data?.actor;
    if (a && a.actor_id !== s.actor?.id)
      s.setCollaboration(
        s.sessionToken,
        {
          id: a.actor_id,
          displayName: a.actor_id,
          workspaceId: bootstrap.data!.scope.workspace_id,
        },
        s.scope,
      );
  }, [bootstrap.data]);
  const novels = useQuery({
    queryKey: ["novels"],
    queryFn: api.novels,
    refetchOnMount: workspaceTools ? 'always' : true,
    enabled: !packagedHost && shouldLoadLocalNovels(s.sessionToken, s.scope),
  });  useEffect(() => { // [HERMIA-FE-20261022 REBUILD-W3]
    if (!novelsRoute || !novels.data) return;
    const wanted = new URLSearchParams(location.search).get('novel');
    if (wanted && wanted !== useStudio.getState().novelId && novels.data.some(row => row.id === wanted)) s.setNovel(wanted);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novelsRoute, novels.data]);

  const mediaTasks = useQuery({
    queryKey: ["media-tasks", s.novelId],
    queryFn: () => api.mediaTasks(s.novelId),
    enabled: !!s.novelId,
    retry: false,
    refetchInterval: 5000,
  });
  useEffect(() => {
    if (!mediaTasks.data) return;
    publishTaskSummary("audiobook", mediaTasks.data.audiobook || []);
    publishTaskSummary("motion", mediaTasks.data.motion || []);
  }, [mediaTasks.data, studioModule]);
  const chapters = useQuery({
    queryKey: ["chapters", namespace, s.novelId],
    queryFn: () =>
      s.scope ? api.scopedChapters(s.scope) : api.chapters(s.novelId),
    retry: 1, // [HERMIA-FE-20261025 DUI P0-3] fail fast into one error state instead of ~7s of "正在读取章节…"
    enabled: !!s.novelId,
  });
  // [HERMIA-FE-20261022 N-UX-08] Honest continuity open-count for CTA (shared key with ContinuityCheckPanel)
  const continuityFindingsQ = useQuery({
    queryKey: ["continuity-findings", s.novelId],
    queryFn: () => api.continuityFindings(s.novelId),
    enabled: !!s.novelId,
    retry: false,
    staleTime: 30000,
  });
  const writingGoal = useQuery({
    queryKey: ["writing-goal", s.novelId],
    queryFn: () => api.writingGoal(s.novelId),
    enabled: !!s.novelId,
    retry: false,
  });
  const archived = useQuery({
    queryKey: ["archived-chapters", namespace, s.novelId],
    queryFn: () => api.archivedChapters(s.novelId),
    enabled: !!s.novelId,
  });
  const textModels = useQuery({
    queryKey: ["text-models"],
    queryFn: api.textModels,
    retry: false,
  });
  const selectedProviderId = s.textModel?.providerId,
    selectedModelId = s.textModel?.modelId;
  const routeDiagnostics = useQuery({
    queryKey: [
      "text-runtime-diagnostics",
      s.novelId,
      s.scope,
      selectedProviderId,
      selectedModelId,
    ],
    queryFn: () => s.scope
      ? api.textRuntimeDiagnostics(s.scope, selectedProviderId!, selectedModelId!)
      : api.localTextRuntimeDiagnostics(s.novelId, selectedProviderId!, selectedModelId!, {sessionToken:s.sessionToken}),
    enabled: !!s.novelId && !!selectedProviderId && !!selectedModelId,
    retry: false,
  });
  const runtimeHealth = useQuery({
    queryKey: ["runtime-health"],
    queryFn: api.health,
    enabled: packagedHost,
    retry: false,
    refetchInterval: packagedHost ? 1000 : false,
  });
  const credentialConfigured = Boolean(
    runtimeHealth.data?.providers?.deepseek?.configured,
  );
  const refreshCredentialState = async () =>
    Boolean(
      (await runtimeHealth.refetch()).data?.providers?.deepseek?.configured,
    );
  const saveVaultCredential = async (value: string) => {
    try {
      await api.saveCredential("deepseek", value);
      await runtimeHealth.refetch();
      return true;
    } catch {
      return false;
    }
  };
  const deleteVaultCredential = async () => {
    try {
      await api.deleteCredential("deepseek");
      await runtimeHealth.refetch();
      return true;
    } catch {
      return false;
    }
  };
  const testVaultCredential = async () => {
    try {
      return (await api.testCredential("deepseek")).reachable;
    } catch {
      return false;
    }
  };
  const chapter = useQuery({
    queryKey: ["chapter", namespace, s.chapterId],
    queryFn: () => api.chapter(s.chapterId),
    enabled: !!s.chapterId,
  });
  useEffect(() => {
    if (!pendingAnchor) return;
    if (pendingAnchor.namespace !== namespace || (!workspaceTools && !writingFocus)) { setPendingAnchor(undefined); return; }
    if (chapter.data?.id !== pendingAnchor.chapterId || hydratedIdentity !== editorIdentity) return;
    if (chapter.data.version !== pendingAnchor.version || saveState !== 'saved') {
      setPendingAnchor(undefined);
      setShellMessage('章节已有新版本或未保存草稿，已保留当前内容；未套用旧光标。');
    }
  }, [pendingAnchor, namespace, workspaceTools, writingFocus, hydratedIdentity, editorIdentity, saveState, chapter.data?.id, chapter.data?.version]);

  // A scope change retires only local observers. The server task and its
  // original-scope recovery record remain available; panel changes do neither.
  useLayoutEffect(() => {
    stopGenerationObservation();
    setJob(undefined); setVariantDrafts([]); setActiveVariant(0); setSelection({ from: 0, to: 0, text: '' });
    setGenerationStarting(false); setGenerationRecovering(false); setGenerationRecoveryUnverified(false); setVariantCancelling(false); setDraftAction(undefined);
  }, [editorIdentity, scopeEpoch]);
  useEffect(() => {
    if (!chapter.data?.id || chapter.data.id !== s.chapterId) return;
    const saved = generationRecovery.load(namespace, chapter.data.id);
    if (!saved || (saved.actorId !== undefined && saved.actorId !== s.actor?.id)) return;
    const observer = beginGenerationObservation();
    setGenerationRecovering(true);
    setGenerationRecoveryUnverified(true);
    // Cached output is a recovery candidate, not current read authorization.
    // Revalidate even COMPLETED/ready tasks before exposing original or output.
    void (async () => {
      try {
        const states = await readVerifiedRecovery(observer, saved);
        if (!isObservingGeneration(observer)) return;
        setGenerationRecoveryUnverified(false);
        await displayVerifiedRecovery(observer, saved, states);
      } catch {
        if (isObservingGeneration(observer)) setShellMessage('生成草稿尚未通过权限与来源核对，内容仍保留；恢复连接或权限后可重新打开。');
      } finally {
        if (isObservingGeneration(observer)) setGenerationRecovering(false);
      }
    })();
    return () => { observer.active = false; observer.sources.forEach(source => source.close()); observer.sources.clear(); };
  }, [chapter.data?.id, namespace, editorIdentity, scopeEpoch]);
  useEffect(() => {
    // Entry installs a candidate connection before a project is selected in the store.
    // A late local inventory/retry must not replace that in-progress explicit connection.
    const current = getCollaborationContext();
    if (current.sessionToken !== s.sessionToken
        || current.scope?.workspaceId !== s.scope?.workspaceId
        || current.scope?.projectId !== s.scope?.projectId
        || current.scope?.storylineId !== s.scope?.storylineId
        || current.scope?.branchId !== s.scope?.branchId) return;
    // Wait for current server flags and the original project inventory. A hint
    // cannot select a foreign/missing project or redirect an authenticated scope.
    if (packagedHost || !shouldLoadLocalNovels(s.sessionToken, s.scope) || experimentalFlags.isPending) return;
    const routeNovel = novelsRoute ? new URLSearchParams(location.search).get('novel') : null; // [HERMIA-FE-20261022 REBUILD-W3]
    const routeHit = routeNovel && novels.data?.some(row => row.id === routeNovel) ? routeNovel : undefined;
    if (routeHit && !s.novelId) { s.setNovel(routeHit); return; }
    if (!workspaceTools && !independentStudios) { if (!s.novelId && novels.data?.[0]) s.setNovel(novels.data[0].id); return; }
    if (novels.isFetching || !novels.isSuccess) return;
    if (s.novelId) {
      if (novels.data.some(row => row.id === s.novelId) && !rememberLocalWorkspaceSelection(s.novelId))
        setProjectRecoveryNotice('当前浏览器无法记住项目选择；服务端工作现场仍保留，下次请手动选择作品。');
      return;
    }
    if (projectChoiceOpen) return;
    const selected = readLocalWorkspaceSelection();
    if (selected.state === 'SAVED') {
      if (novels.data.some(row => row.id === selected.projectId)) s.setNovel(selected.projectId);
      else setProjectRecoveryNotice('上次项目当前不存在或不可访问。请选择一个可用作品；不会改跳到其他项目或分支。');
    } else if (selected.state === 'EMPTY') {
      if (novels.data[0]) s.setNovel(novels.data[0].id);
    } else setProjectRecoveryNotice('上次项目选择损坏或浏览器存储不可用。请选择作品；正文和服务端工作现场未改变。');
  }, [novels.data, novels.isFetching, novels.isSuccess, experimentalFlags.isPending, workspaceTools, independentStudios, packagedHost, s.novelId, s.sessionToken, s.scope, projectChoiceOpen]);
  // [HERMIA-FE-20261025 UWPORT-S1] reopen returns to the last chapter (real identity only; else 仅本次会话); missing chapter ⇒ first.
  // [UWPORT-P0] Vera reopen race: while the collaboration bootstrap is still deciding the actor, neither pick by memory nor write.
  const bootstrapActorId = bootstrap.data?.actor?.actor_id;
  // [UWPORT-P1-1] a bootstrap that errored while a token/scope exists is still "undetermined": the real actor may come back
  // on refetch, so session-mode memory must neither pick nor write (Vera recover.json "online").
  const identityPending = lastChapterIdentityPending({ isLoading: bootstrap.isLoading, isError: bootstrap.isError, bootstrapActorId, actorId: s.actor?.id });
  const lastPositionMode = useLastChapter({ actorId: s.actor?.id, scope: s.scope, novelId: s.novelId, chapterId: s.chapterId, rows: chapters.data, setChapter: s.setChapter, identityPending });
  // BACKPORT CANDIDATE (U02): hydrate before exposing an editable surface, and
  // prefer the current draft even when its rich-text document is absent.
  useLayoutEffect(() => { setComposing(false); }, [editorIdentity, scopeEpoch]);
  useLayoutEffect(() => {
    if (!chapter.data || chapter.data.id !== s.chapterId) {
      setHydratedIdentity(undefined);
      setConflict(undefined);
      return;
    }
    const inspected = drafts.inspect(chapter.data.id, namespace);
    if (writingRecovery && inspected.state === 'CORRUPT') {
      setCorruptDraft({ identity: editorIdentity, raw: inspected.raw });
      setHydratedIdentity(undefined); setConflict(undefined); setSaveState('failed');
      return;
    }
    setCorruptDraft(undefined);
    const d = inspected.state === 'READY' ? inspected.value : undefined;
    let savedConflict = conflicts.load(chapter.data.id, namespace);
    if (d && savedConflict && (savedConflict.local.content !== d.content
        || savedConflict.local.baseVersion !== d.baseVersion
        || JSON.stringify(savedConflict.local.document) !== JSON.stringify(d.document))) {
      // A later local candidate wins the comparison UI. Archive the older
      // conflict and invalidate its manual-resolution input before reopening.
      savedConflict = { ...savedConflict, local: d, detectedAt: new Date().toISOString() };
      conflicts.save(savedConflict, namespace);
    }
    const value: LocalDraft = d ?? {
      chapterId: chapter.data.id, content: chapter.data.content,
      document: chapter.data.document, baseVersion: chapter.data.version,
      updatedAt: new Date().toISOString(),
    };
    buffer.current = { identity: editorIdentity, value };
    setText(value.content);
    setDoc(value.document);
    setBaseVersion(value.baseVersion);
    setDurability(d ? drafts.durability(d.chapterId, namespace) : 'none');
    setHydratedIdentity(editorIdentity);
    if (d && d.baseVersion !== chapter.data.version) {
      const value = savedConflict?.server.version === chapter.data.version ? savedConflict : {
        chapterId: d.chapterId, local: d, server: chapter.data, detectedAt: new Date().toISOString(),
      };
      conflicts.save(value, namespace);
      setConflict(value);
      setSaveState('conflict');
    } else {
      setConflict(savedConflict);
      setSaveState(current => reduceSaveState(current, {
        type: 'hydrate', hasDraft: !!d, hasConflict: !!savedConflict,
      }));
    }
  }, [namespace, editorIdentity, scopeEpoch, chapter.data?.id, chapter.data?.version, writingRecovery, draftRecoveryEpoch]);
  type SaveRequest = LocalDraft & {
    namespace: string; identity: string; epoch: number; context: CollaborationContext; novelId: string;
  };
  const isCurrentSave = (value: SaveRequest) => mounted.current
    && value.epoch === editorEpoch.current
    && value.identity === revisionStoreIdentity(useStudio.getState());
  const save = useMutation({
    mutationFn: (value: SaveRequest) => saveGate.current.run(async () => {
      // Recovered text/manual merges may lack a rich document. Submit literal
      // prose as a document too, so every acknowledgement can prove which
      // candidate it persisted without comparing the server Markdown projection.
      const submittedDocument = value.document ?? proseDocument(value.content);
      const result = await api.saveChapter(value.chapterId, value.content, value.baseVersion, submittedDocument, 'USER', value.context);
      // A transport success without an authoritative chapter/version is unknown,
      // not a save receipt. Retain the candidate and require an explicit retry.
      if (!result || result.id !== value.chapterId || !Number.isInteger(result.version)
          || result.version <= value.baseVersion || typeof result.content !== 'string'
          || JSON.stringify(result.document) !== JSON.stringify(submittedDocument)) {
        throw new Error('INVALID_SAVE_RECEIPT');
      }
      return result as Chapter;
    }),
    onSuccess: (result: Chapter, value) => {
      if (!isCurrentSave(value)) return;
      const currentServer = qc.getQueryData<Chapter>(['chapter', value.namespace, value.chapterId]);
      if (currentServer && currentServer.version > result.version) {
        const local = drafts.load(value.chapterId, value.namespace) ?? value;
        const conflictValue = { chapterId: value.chapterId, local, server: currentServer, detectedAt: new Date().toISOString() };
        conflicts.save(conflictValue, value.namespace);
        setConflict(conflictValue);
        setSaveState('conflict');
        return;
      }
      const newer = rebaseNewerDraft(drafts.load(value.chapterId, value.namespace), value, result.version);
      if (newer) {
        setDurability(drafts.save(newer, value.namespace).durability);
        buffer.current = { identity: value.identity, value: newer };
      } else {
        drafts.remove(value.chapterId, value.namespace);
        conflicts.remove(value.chapterId, value.namespace);
        conflictResolutionDrafts.remove(value.chapterId, value.namespace);
        buffer.current = { identity: value.identity, value: { ...value, baseVersion: result.version } };
        setDurability('none');
        setConflict(undefined);
      }
      setBaseVersion(result.version);
      // Update the cache only after the newer candidate has its rebased version.
      qc.setQueryData(['chapter', value.namespace, value.chapterId], result);
      void qc.invalidateQueries({ queryKey: ['writing-goal', value.novelId] });
      setSaveState(current => reduceSaveState(current, { type: 'save-succeeded', hasNewerChanges: !!newer }));
    },
    onError: async (error: unknown, value) => {
      if (!isCurrentSave(value)) return;
      // Establish a terminal state before the optional conflict fetch. A second
      // network failure must not leave the editor claiming that it is Saving.
      setSaveState('failed');
      if (error instanceof ApiError && error.status === 409) {
        try {
          const server = await api.chapter(value.chapterId, value.context);
          if (!isCurrentSave(value) || server.id !== value.chapterId) return;
          const local = drafts.load(value.chapterId, value.namespace) ?? value;
          const conflictValue = { chapterId: value.chapterId, local, server, detectedAt: new Date().toISOString() };
          conflicts.save(conflictValue, value.namespace);
          setConflict(conflictValue);
          setSaveState('conflict');
        } catch { /* Keep the draft and the visible retry/export state. */ }
      }
    },
    onSettled: () => { savePending.current = false; },
  });
  const dispatchSave = () => {
    const current = buffer.current;
    if (composing || !chapter.data || hydratedIdentity !== editorIdentity || !current
        || current.identity !== revisionStoreIdentity(useStudio.getState())
        || saveState === 'conflict' || savePending.current || save.isPending || saveGate.current.active) return;
    const value: SaveRequest = { ...current.value, namespace, identity: editorIdentity,
      epoch: editorEpoch.current, novelId: s.novelId,
      context: { sessionToken: s.sessionToken, actor: s.actor && { ...s.actor }, scope: s.scope && { ...s.scope } },
    };
    setDurability(drafts.save(current.value, namespace).durability);
    // Synchronous latch also covers repeated clicks before React Query starts.
    savePending.current = true;
    setSaveState('saving');
    save.mutate(value);
  };
  function compositionChanged(next: boolean) {
    if (next && buffer.current?.identity === editorIdentity) {
      // Reserve the pre-composition base before a server update can arrive,
      // including the gap before the IME emits its first document transaction.
      setDurability(drafts.save(buffer.current.value, namespace).durability);
      setSaveState(current => current === 'saved' ? 'dirty' : current);
    }
    if (!next && saveState === 'conflict') reopenConflict();
    setComposing(next);
  }
  function edit(content: string, document: any) {
    if (hydratedIdentity !== editorIdentity || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    const value = { chapterId: s.chapterId, content, document,
      baseVersion: buffer.current?.identity === editorIdentity ? buffer.current.value.baseVersion : baseVersion,
      updatedAt: new Date().toISOString() };
    buffer.current = { identity: editorIdentity, value };
    setText(content);
    setDoc(document);
    // A closed conflict dialog does not authorize autosaving over its server.
    setSaveState(current => current === 'conflict' ? 'conflict' : reduceSaveState(current, { type: 'edit' }));
    setDurability(drafts.save(value, namespace).durability);
  }
  useEffect(() => {
    if (writingRecovery && recoveryOffline || composing || hydratedIdentity !== editorIdentity || saveState !== 'dirty' || save.isPending || saveGate.current.active) return;
    const timeout = setTimeout(dispatchSave, 900);
    return () => clearTimeout(timeout);
  }, [text, doc, saveState, namespace, s.chapterId, baseVersion, save.isPending, composing, hydratedIdentity, editorIdentity, writingRecovery, recoveryOffline]);
  useEffect(() => {
    if (!writingRecovery || saveState === 'saved') return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    addEventListener('beforeunload', warn);
    return () => removeEventListener('beforeunload', warn);
  }, [writingRecovery, saveState]);
  function reopenConflict() {
    const previous = conflicts.load(s.chapterId, namespace);
    if (!previous) return;
    const current = drafts.load(s.chapterId, namespace);
    const value = current && current.content !== previous.local.content
      ? { ...previous, local: current, detectedAt: new Date().toISOString() } : previous;
    conflicts.save(value, namespace);
    setConflict(value);
  }
  function exportCurrentDraft() {
    try { exportDraftText(buffer.current?.identity === editorIdentity ? buffer.current.value.content : text); }
    catch { setShellMessage('无法下载恢复文本。请在正文中全选并复制到本机文件，再关闭页面。'); }
  }
  function stopGenerationObservation() {
    const observer = generationObserver.current;
    if (!observer) return;
    observer.active = false;
    observer.sources.forEach(source => source.close());
    observer.sources.clear();
  }
  function captureGenerationOrigin() {
    return { namespace, chapterId: s.chapterId, novelId: s.novelId, identity: editorIdentity,
      epoch: editorEpoch.current, serial: generationSerial.current, baseVersion: chapter.data?.version,
      context: { sessionToken: s.sessionToken, actor: s.actor && { ...s.actor }, scope: s.scope && { ...s.scope } } };
  }
  function beginGenerationObservation(): GenerationObservation {
    stopGenerationObservation();
    generationSerial.current += 1;
    const observer = { ...captureGenerationOrigin(), active: true, sources: new Set<EventSource>() };
    generationObserver.current = observer;
    return observer;
  }
  function isCurrentGeneration(origin: GenerationOrigin) {
    return mounted.current && origin.epoch === editorEpoch.current && origin.serial === generationSerial.current
      && origin.identity === revisionStoreIdentity(useStudio.getState());
  }
  function isObservingGeneration(observer: GenerationObservation) {
    return observer.active && generationObserver.current === observer && isCurrentGeneration(observer);
  }
  function retainGeneration(observer: GenerationOrigin, value: RecoverableGeneration) {
    generationRecovery.save(observer.namespace, { ...value, chapterId: observer.chapterId, actorId: observer.context.actor?.id }, !isCurrentGeneration(observer) || ('active' in observer && !isObservingGeneration(observer as GenerationObservation)));
    // Refresh identifiers only for this origin, never a late candidate's prose.
    if (mounted.current && observer.identity === revisionStoreIdentity(useStudio.getState())) refreshGenerationRecovery(value => value + 1);
  }
  function generationVersionFlags(origin: GenerationOrigin, version?: number) {
    const currentVersion = qc.getQueryData<Chapter>(['chapter', origin.namespace, origin.chapterId])?.version;
    const stale = isRecoveredDraftStale(version, currentVersion);
    return { acceptBlocked: stale, acceptBlockedReason: stale ? '正文已在生成期间发生变化，请先处理版本冲突。' : undefined };
  }
  async function observeSingleGeneration(observer: GenerationObservation, initial: any, eventsUrl?: string) {
    let current = initial;
    const update = (state: any, streamed = false) => {
      if (!isObservingGeneration(observer)) return;
      const version = typeof state.base_chapter_version === 'number' ? state.base_chapter_version : current.base_chapter_version;
      current = { id: initial.id, original: initial.original,
        status: typeof state.status === 'string' ? state.status : current.status,
        output: streamed && typeof state.chunk === 'string' ? (current.output || '') + state.chunk
          : typeof state.output === 'string' ? state.output : current.output || '',
        error: typeof state.error === 'string' ? state.error : current.error,
        latency_ms: typeof state.latency_ms === 'number' ? state.latency_ms : current.latency_ms,
        base_chapter_version: version, ...generationVersionFlags(observer, version) };
      retainGeneration(observer, { chapterId: observer.chapterId, jobId: current.id, original: current.original,
        baseChapterVersion: current.base_chapter_version, job: current });
      setJob(current);
    };
    const poll = async () => {
      try {
        const terminal = await recoverGenerationJob(initial.id, id => api.job(id, observer.context), state => update(state), {
          isActive: () => isObservingGeneration(observer),
        });
        if (!terminal && isObservingGeneration(observer)) update({ status: 'FAILED', error: '生成连接中断且恢复超时，请重试' });
      } catch {
        if (isObservingGeneration(observer)) update({ status: 'FAILED', error: '生成连接中断，恢复失败，请重试' });
      }
    };
    if (!isObservingGeneration(observer)) return;
    update(initial);
    if (isGenerationTerminal(initial.status)) return;
    // Authenticated scopes cannot attach headers to EventSource. They always
    // poll with the captured session and branch, including local session hosts.
    if (!eventsUrl || observer.context.scope || observer.context.sessionToken || packagedHost) { await poll(); return; }
    const source = new EventSource(eventsUrl);
    observer.sources.add(source);
    const close = () => { source.close(); observer.sources.delete(source); };
    let recovering = false;
    source.onmessage = event => {
      if (!isObservingGeneration(observer)) { close(); return; }
      try {
        const state = JSON.parse(event.data);
        update(state, true);
        if (isGenerationTerminal(state.status)) close();
      } catch { source.onerror?.(new Event('error')); }
    };
    source.onerror = async () => {
      if (recovering) return;
      recovering = true; close();
      if (isObservingGeneration(observer)) await poll();
    };
  }
  async function observeVariantGenerations(observer: GenerationObservation, initial: AiVariantDraft[]) {
    let candidates = initial;
    const publish = () => {
      if (!isObservingGeneration(observer)) return;
      candidates = candidates.filter(item => !cancelledVariantIds.current.has(item.id));
      retainGeneration(observer, { chapterId: observer.chapterId, variants: candidates });
      setVariantDrafts([...candidates]);
    };
    publish();
    await Promise.all(initial.filter(item => item.status === 'working').map(async candidate => {
      try {
        const terminal = await recoverGenerationJob(candidate.id, id => api.job(id, observer.context), state => {
          if (!isObservingGeneration(observer) || cancelledVariantIds.current.has(candidate.id)) return;
          candidates = candidates.map(item => item.id === candidate.id ? { ...item,
            output: state.output ?? item.output, status: state.status === 'COMPLETED' ? 'ready' : isGenerationTerminal(state.status) ? 'failed' : 'working',
            error: state.error, ...generationVersionFlags(observer, state.base_chapter_version ?? item.baseChapterVersion) } : item);
          publish();
        }, { isActive: () => isObservingGeneration(observer) && !cancelledVariantIds.current.has(candidate.id) });
        if (!terminal && isObservingGeneration(observer) && !cancelledVariantIds.current.has(candidate.id)) {
          candidates = candidates.map(item => item.id === candidate.id ? { ...item, status: 'failed', error: VARIANT_TIMEOUT_ERROR } : item);
          publish();
        }
      } catch {
        if (!isObservingGeneration(observer)) return;
        candidates = candidates.map(item => item.id === candidate.id ? { ...item, status: 'failed', error: '生成连接中断，恢复失败，请重试' } : item);
        publish();
      }
    }));
  }
  const cancelGeneration = useMutation({
    mutationFn: ({ id, origin }: { id: string; origin: GenerationOrigin }) => api.cancel(id, origin.context),
    onSuccess: (_result, { id, origin }) => {
      if (!isCurrentGeneration(origin)) return;
      setJob((current: any) => current?.id === id ? { ...current, status: 'CANCELLED' } : current);
      const saved = generationRecovery.load(origin.namespace, origin.chapterId);
      if (saved?.jobId === id) generationRecovery.remove(origin.namespace, origin.chapterId);
      stopGenerationObservation();
    },
  });
  async function runAI(
    operation: string = tool,
    request: string = instruction,
    style = '',
    previewReceipt?: AuthorPreviewReceipt,
  ) {
    if (!chapter.data || generationStarting || (generationCreating.current && isObservingGeneration(generationCreating.current)) || job?.status === 'GENERATING'
        || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    if (activeCharacterId && (!previewReceipt || !['continue', 'brainstorm'].includes(operation))) return;
    if (experimentalFlags.data?.features['experimental.author_context_inspector_v2'] === true && !previewReceipt) {
      setJob({ id: 'generation-failed', status: 'FAILED', output: '', error: '请先检查本次真实请求，再生成草稿。' }); return;
    }
    if (operation === 'rewrite' && !selection.text) {
      setJob({ id: 'selection-required', status: 'FAILED', output: '', error: '请先在正文中选择需要改写的文字。' }); return;
    }
    const observer = beginGenerationObservation();
    generationCreating.current = observer;
    const original = operation === 'rewrite' ? selection.text : text;
    setGenerationStarting(true);
    try {
      const payload = {
        novel_id: observer.novelId, chapter_id: observer.chapterId, instruction: request, style,
        style_profile_id: s.writingInputs?.styleProfileId, plot_plan_id: s.writingInputs?.plotPlanId,
        profile: s.mode, provider_id: s.textModel?.providerId, model_id: s.textModel?.modelId,
        source: activeCharacterId ? '' : selection.text, selected_text: activeCharacterId ? '' : selection.text,
        ...(activeCharacterId ? { character_id: activeCharacterId, scene_id: activeSceneId, style: '', style_profile_id: undefined, plot_plan_id: undefined, profile: 'LOCAL_ONLY' as const } : {}),
      };
      if (previewReceipt && (saveState !== 'saved' || previewReceipt.chapterVersion !== chapter.data.version))
        throw new Error('正文或预检版本已改变，请先保存并重新检查。');
      if (previewReceipt && authorRequestKey({ ...payload, request_scope: previewReceipt.requestBody.request_scope,
          provider_id: payload.provider_id || '', model_id: payload.model_id || '', operation,
          chapter_version: previewReceipt.chapterVersion }, observer.context) !== previewReceipt.requestKey)
        throw new Error('预检范围或输入已改变，请重新检查。');
      const result = previewReceipt
        ? await authorContextRequest<any>(observer.novelId, 'generate', {
            ...payload, request_scope: previewReceipt.requestBody.request_scope, provider_id: payload.provider_id || '', model_id: payload.model_id || '',
            operation, chapter_version: previewReceipt.chapterVersion, preview_digest: previewReceipt.previewDigest, generation_request_id: previewReceipt.requestId,
          }, observer.context)
        : await api.generate(operation, payload, observer.context);
      const initial = { id: result.job_id, status: 'GENERATING', output: '', original,
        base_chapter_version: result.base_chapter_version ?? observer.baseVersion };
      retainGeneration(observer, { chapterId: observer.chapterId, jobId: initial.id, original,
        baseChapterVersion: initial.base_chapter_version, job: initial });
      if (!isObservingGeneration(observer)) return;
      setGenerationRecoveryUnverified(false);
      await observeSingleGeneration(observer, initial, result.events_url);
    } catch {
      if (isObservingGeneration(observer)) setJob({ id: 'generation-failed', status: 'FAILED', output: '', error: '生成失败，请重试' });
    } finally {
      if (generationCreating.current === observer) generationCreating.current = undefined;
      if (isObservingGeneration(observer)) setGenerationStarting(false);
    }
  }
  async function runAIVariants(operation: string, request: string, count: number, style = '', previewReceipt?: AuthorVariantsReceipt) {
    if (activeCharacterId) return;
    if (!chapter.data || generationStarting || (generationCreating.current && isObservingGeneration(generationCreating.current)) || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    if (operation === 'rewrite' && !selection.text) {
      setJob({ id: 'selection-required', status: 'FAILED', output: '', error: '请先在正文中选择需要改写的文字。' }); return;
    }
    const observer = beginGenerationObservation();
    generationCreating.current = observer;
    const original = operation === 'rewrite' ? selection.text : text;
    setGenerationStarting(true); setVariantDrafts([]); setActiveVariant(0); setJob(undefined);
    try {
      const payload = {
        novel_id: observer.novelId, chapter_id: observer.chapterId, instruction: request, style,
        style_profile_id: s.writingInputs?.styleProfileId, plot_plan_id: s.writingInputs?.plotPlanId,
        profile: s.mode, provider_id: s.textModel?.providerId || '', model_id: s.textModel?.modelId || '',
        source: selection.text, selected_text: selection.text,
      };
      if (previewReceipt && (saveState !== 'saved' || previewReceipt.chapterVersion !== chapter.data.version
          || authorVariantsKey({ ...payload, operation, chapter_version: chapter.data.version,
            request_scope: previewReceipt.requestBody.request_scope }, count, observer.context) !== previewReceipt.requestKey))
        throw new Error('方案预检范围或输入已改变，请重新检查。');
      const response = previewReceipt
        ? await authorContextVariants<AuthorVariantsResult>(observer.novelId, 'generate-variants', previewReceipt.batch, observer.context)
        : await api.generateVariants(operation, { ...payload, count }, observer.context);
      const candidates: AiVariantDraft[] = response.variants.map(item => ({
        id: item.job_id, variantIndex: item.variant_index, baseChapterVersion: item.base_chapter_version,
        tracked: 'receipt_state' in item ? item.receipt_state === 'RECORDED' : true,
        output: '', original, status: ['FAILED', 'CANCELLED', 'UNKNOWN'].includes('status' in item ? item.status : '') ? 'failed' : 'working',
        ...(['FAILED', 'CANCELLED', 'UNKNOWN'].includes('status' in item ? item.status : '') ? { error: '部分方案未启动或结果未知；请核对原任务，不会自动重新发送。' } : {}),
      }));
      retainGeneration(observer, { chapterId: observer.chapterId, variants: candidates });
      if (isObservingGeneration(observer)) { setGenerationRecoveryUnverified(false); await observeVariantGenerations(observer, candidates); }
    } catch {
      if (previewReceipt) {
        // The review already supplies exact original job IDs. Preserve them on
        // an ambiguous transport failure; never generate replacement requests.
        const unknown: AiVariantDraft[] = previewReceipt.jobIds.map((id, index) => ({ id, variantIndex: index + 1,
          baseChapterVersion: previewReceipt.chapterVersion, original, output: '', status: 'failed', tracked: false,
          error: '部分方案未启动或结果未知；请核对原任务，不会自动重新发送。' }));
        retainGeneration(observer, { chapterId: observer.chapterId, variants: unknown });
        if (isObservingGeneration(observer)) setVariantDrafts(unknown);
      } else if (isObservingGeneration(observer)) setJob({ id: 'generation-failed', status: 'FAILED', output: '', error: '多方案生成失败，请重试' });
    } finally {
      if (generationCreating.current === observer) generationCreating.current = undefined;
      if (isObservingGeneration(observer)) setGenerationStarting(false);
    }
  }
  async function cancelActiveGeneration() {
    if (variantCancelling || cancelGeneration.isPending) return;
    const origin = captureGenerationOrigin();
    const workingIds = workingVariantIds(variantDrafts);
    if (workingIds.length) {
      setVariantCancelling(true);
      workingIds.forEach(id => cancelledVariantIds.current.add(id));
      try {
        await Promise.all(workingIds.map(id => api.cancel(id, origin.context)));
        if (!isCurrentGeneration(origin)) return;
        const remaining = variantDrafts.filter(item => !workingIds.includes(item.id));
        setVariantDrafts(remaining); setActiveVariant(0);
        retainGeneration(origin, { chapterId: origin.chapterId, variants: remaining });
      } catch {
        if (isCurrentGeneration(origin)) setShellMessage('取消结果尚未确认，请在任务中心核对。');
      } finally {
        if (isCurrentGeneration(origin)) setVariantCancelling(false);
      }
      return;
    }
    if (job?.id) cancelGeneration.mutate({ id: job.id, origin });
  }
  async function retryVariant(draft: AiVariantDraft) {
    if (draft.status !== 'failed' || !variantDrafts.some(item => item.id === draft.id)) return;
    const observer = beginGenerationObservation();
    const originalCandidates = variantDrafts;
    setVariantDrafts(current => current.map(item => item.id === draft.id ? { ...item, status: 'working', error: undefined } : item));
    try {
      const response = await api.retryGeneration(draft.id, observer.context);
      const candidates: AiVariantDraft[] = originalCandidates.map(item => item.id === draft.id ? {
        ...draft, id: response.job_id, status: 'working', output: '', error: undefined, baseChapterVersion: response.base_chapter_version,
      } : item);
      retainGeneration(observer, { chapterId: observer.chapterId, variants: candidates, retryOf: draft.id });
      if (isObservingGeneration(observer)) await observeVariantGenerations(observer, candidates);
    } catch {
      if (isObservingGeneration(observer)) setVariantDrafts(current => current.map(item => item.id === draft.id ? { ...item, status: 'failed', error: '生成失败，请重试' } : item));
    }
  }
  async function retryDraft(draft: { id: string; status: string }) {
    const variant = variantDrafts.find(item => item.id === draft.id);
    if (variant) return retryVariant(variant);
    if (draft.status !== 'failed' || job?.id !== draft.id) return;
    const observer = beginGenerationObservation();
    const previous = job;
    setJob((current: any) => ({ ...current, status: 'GENERATING', output: '', error: undefined }));
    try {
      const response = await api.retryGeneration(draft.id, observer.context);
      const initial = { ...previous, id: response.job_id, status: 'GENERATING', output: '', error: undefined, base_chapter_version: response.base_chapter_version };
      retainGeneration(observer, { chapterId: observer.chapterId, jobId: initial.id, original: initial.original, baseChapterVersion: initial.base_chapter_version, job: initial, retryOf: draft.id });
      if (isObservingGeneration(observer)) await observeSingleGeneration(observer, initial);
    } catch {
      if (isObservingGeneration(observer)) setJob((current: any) => ({ ...current, status: 'FAILED', error: '生成连接中断，恢复失败，请重试' }));
    }
  }
  async function openDraftConflict(draft: { output: string }) {
    if (!chapter.data) return;
    const origin = captureGenerationOrigin();
    const variant = variantDrafts.find(item => item.output === draft.output);
    const generationVersion = variant?.baseChapterVersion ?? job?.base_chapter_version ?? chapter.data.version;
    const server = await api.chapter(origin.chapterId, origin.context);
    if (!isCurrentGeneration(origin)) return;
    const local = { chapterId: origin.chapterId, content: draft.output, document: undefined, baseVersion: generationVersion, updatedAt: new Date().toISOString() };
    const value = { chapterId: origin.chapterId, local, server, detectedAt: new Date().toISOString() };
    conflicts.save(value, origin.namespace); setConflict(value); setSaveState('conflict');
  }
  function verifyRecoveredState(origin: GenerationOrigin, state: any, id: string, chapterId = origin.chapterId) {
    const scope = origin.context.scope;
    if (state.id !== id || state.novel_id !== origin.novelId || state.chapter_id !== chapterId
        || !Number.isInteger(state.base_chapter_version) || typeof state.output !== 'string'
        || (state.status !== 'QUEUED' && state.status !== 'GENERATING' && state.status !== 'SETTLING' && !isGenerationTerminal(state.status))
        || (origin.context.actor?.id && state.actor_id !== origin.context.actor.id)
        || (scope && (state.scope?.workspace_id !== scope.workspaceId || state.scope?.project_id !== scope.projectId
          || state.scope?.storyline_id !== scope.storylineId || state.scope?.branch_id !== scope.branchId))) throw new Error('RECOVERY_SOURCE_CHANGED');
  }
  async function readVerifiedRecovery(origin: GenerationOrigin, value: RecoverableGeneration): Promise<any[]> {
    if (!isCurrentGeneration(origin) || value.chapterId !== origin.chapterId
        || (value.actorId !== undefined && value.actorId !== origin.context.actor?.id)) throw new Error('RECOVERY_SCOPE_CHANGED');
    const ids = value.jobId ? [value.jobId] : value.variants?.map(item => item.id) ?? [];
    if (!ids.length || ids.length > 8) throw new Error('INVALID_RECOVERY_GROUP');
    const states = await Promise.all(ids.map(id => api.job(id, origin.context)));
    if (!isCurrentGeneration(origin)) throw new Error('RECOVERY_SCOPE_CHANGED');
    states.forEach((state, index) => verifyRecoveredState(origin, state, ids[index]));
    return states;
  }
  async function displayVerifiedRecovery(observer: GenerationObservation, value: RecoverableGeneration, states: any[]) {
    if (value.jobId) {
      const state = states[0];
      const initial = { id: value.jobId, status: state.status, output: state.output || '', original: value.original,
        base_chapter_version: state.base_chapter_version, error: state.error, ...generationVersionFlags(observer, state.base_chapter_version) };
      retainGeneration(observer, { chapterId: observer.chapterId, jobId: value.jobId, original: value.original,
        baseChapterVersion: state.base_chapter_version, job: initial });
      setVariantDrafts([]); setActiveVariant(0);
      await observeSingleGeneration(observer, initial);
    } else {
      const candidates: AiVariantDraft[] = value.variants!.map((item, index) => ({ ...item, output: states[index].output || '',
        status: states[index].status === 'COMPLETED' ? 'ready' : isGenerationTerminal(states[index].status) ? 'failed' : 'working',
        baseChapterVersion: states[index].base_chapter_version, error: states[index].error,
        ...generationVersionFlags(observer, states[index].base_chapter_version) }));
      retainGeneration(observer, { chapterId: observer.chapterId, variants: candidates });
      setJob(undefined); setActiveVariant(0); await observeVariantGenerations(observer, candidates);
    }
  }
  async function reopenRetainedGeneration(value: RecoverableGeneration) {
    const origin = captureGenerationOrigin();
    if (!writingRecovery) throw new Error('RECOVERY_DISABLED');
    const states = await readVerifiedRecovery(origin, value);
    if (!isCurrentGeneration(origin)) return;
    const observer = beginGenerationObservation();
    setGenerationRecoveryUnverified(false);
    void displayVerifiedRecovery(observer, value, states);
  }
  const workspaceRestoreSequence = useRef(0);
  const workspaceRestoreState = useRef({ saveState, composing, hydratedIdentity, editorIdentity });
  workspaceRestoreState.current = { saveState, composing, hydratedIdentity, editorIdentity };
  useLayoutEffect(() => { workspaceRestoreSequence.current++; }, [editorIdentity, scopeEpoch, panel, experimentalTab, workspaceSection, workspaceTools, writingFocus]);
  const generationOpenSequence = useRef(0);
  // Closing this surface, choosing another task or disabling either entry
  // invalidates pending reads without cancelling the original generation.
  useLayoutEffect(() => { generationOpenSequence.current += 1; },
    [panel, experimentalTab, workspaceSection, workspaceTools, experimentalFlags.data?.features['experimental.model_broker_v2']]);
  async function openExistingGeneration(jobId: string, chapterId: string, signal?: AbortSignal, navigationCurrent?: () => boolean): Promise<void> {
    if (!navigationCurrent) { if (!await styleLeave.request(current => openExistingGeneration(jobId, chapterId, signal, current), signal)) throw new Error('NAVIGATION_CANCELLED'); return; }
    if (!navigationCurrent()) return;
    const origin = captureGenerationOrigin();
    const entryEnabled = () => {
      const current = qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace]);
      return current?.features['experimental.model_broker_v2'] === true || current?.features['experimental.workspace_tools_v2'] === true;
    };
    if (!entryEnabled() || signal?.aborted || !jobId || !chapterId) throw new Error('GENERATION_ENTRY_DISABLED');
    const ticket = ++generationOpenSequence.current;
    const current = () => navigationCurrent() && !signal?.aborted && ticket === generationOpenSequence.current && isCurrentGeneration(origin) && entryEnabled();
    // Verify at the originating authority before navigating. Only identifiers
    // survive navigation; the destination performs another current read.
    const value = { chapterId, jobId, actorId: origin.context.actor?.id };
    const initial = await api.job(jobId, origin.context);
    if (!current()) throw new Error('RECOVERY_SCOPE_CHANGED');
    verifyRecoveredState(origin, initial, jobId, chapterId);
    if (chapterId !== origin.chapterId) {
      setPendingGenerationOpen({ namespace, novelId: s.novelId, actorId: s.actor?.id, chapterId, jobId });
      s.setChapter(chapterId); setPanel('history'); return;
    }
    const states = await readVerifiedRecovery(origin, value);
    if (!current()) throw new Error('RECOVERY_SCOPE_CHANGED');
    const observer = beginGenerationObservation();
    setGenerationRecoveryUnverified(false); setPanel('history');
    await displayVerifiedRecovery(observer, { ...value, original: states[0].source || chapter.data?.content || '' }, states);
  }
  useEffect(() => {
    if (!pendingGenerationOpen) return;
    const value = pendingGenerationOpen;
    if (panel !== 'history' || value.namespace !== namespace || value.novelId !== s.novelId || value.actorId !== s.actor?.id || value.chapterId !== s.chapterId) {
      setPendingGenerationOpen(undefined); return;
    }
    if (hydratedIdentity !== editorIdentity || chapter.data?.id !== value.chapterId) return;
    setPendingGenerationOpen(undefined);
    const ticket = generationOpenSequence.current + 1;
    void openExistingGeneration(value.jobId, value.chapterId).catch(() => {
      if (generationOpenSequence.current === ticket && revisionStoreIdentity(useStudio.getState()) === editorIdentity)
        setShellMessage('无法打开生成记录，请检查当前项目、权限和版本后，从原任务入口重试。正文草稿未改变。');
    });
  }, [pendingGenerationOpen, namespace, s.novelId, s.actor?.id, s.chapterId, hydratedIdentity, editorIdentity, chapter.data?.id, panel]);
  function clearRecoveredTask(origin: GenerationOrigin, id: string) {
    const saved = generationRecovery.load(origin.namespace, origin.chapterId);
    if (saved?.jobId === id || saved?.variants?.some(item => item.id === id)) generationRecovery.remove(origin.namespace, origin.chapterId);
  }
  async function acceptGeneratedDraft(draft: { id: string; output: string }) {
    if (generationAction.current && isCurrentGeneration(generationAction.current.origin)) return;
    const origin = captureGenerationOrigin();
    if (!isCurrentGeneration(origin)) return;
    const action = { origin, id: draft.id, kind: 'accept' };
    generationAction.current = action;
    const variant = variantDrafts.find(item => item.id === draft.id);
    const generationVersion = variant?.baseChapterVersion ?? job?.base_chapter_version;
    const peers = variantDrafts.filter(item => item.id !== draft.id).map(item => item.id);
    setDraftAction('accept');
    const showConflict = async () => {
      const server = await api.chapter(origin.chapterId, origin.context);
      if (!isCurrentGeneration(origin)) return;
      const local = { chapterId: origin.chapterId, content: draft.output, document: undefined,
        baseVersion: generationVersion ?? origin.baseVersion ?? server.version, updatedAt: new Date().toISOString() };
      const value = { chapterId: origin.chapterId, local, server, detectedAt: new Date().toISOString() };
      conflicts.save(value, origin.namespace); setConflict(value); setSaveState('conflict');
      setJob((current: any) => current?.id === draft.id ? { ...current, error: '正文已有更新，AI 草稿已保留，请先处理冲突。', acceptBlocked: true } : current);
    };
    try {
      if (isRecoveredDraftStale(generationVersion, chapter.data?.version)) { await showConflict(); return; }
      const accepted = await api.accept(draft.id, draft.output, generationVersion, origin.context);
      await Promise.all(peers.map(id => api.reject(id, origin.context).catch(() => undefined)));
      clearRecoveredTask(origin, draft.id);
      if (!isCurrentGeneration(origin)) return;
      stopGenerationObservation(); setVariantDrafts([]); setActiveVariant(0); setJob(undefined);
      const saved = accepted?.chapter ?? await api.chapter(origin.chapterId, origin.context);
      if (!isCurrentGeneration(origin)) return;
      if (saved?.id) {
        qc.setQueryData(['chapter', origin.namespace, saved.id], saved);
        void qc.invalidateQueries({ queryKey: ['chapters', origin.namespace, origin.novelId] });
        if (saved.id !== origin.chapterId) s.setChapter(saved.id);
      }
    } catch (error) {
      if (!isCurrentGeneration(origin)) return;
      if (error instanceof ApiError && error.status === 409) {
        try { await showConflict(); } catch { if (isCurrentGeneration(origin)) setShellMessage('版本冲突查询未完成，AI 草稿已保留。'); }
      } else setShellMessage('采用结果未确认，请先在任务中心和版本记录中核对。');
    } finally {
      if (generationAction.current === action) generationAction.current = undefined;
      if (isCurrentGeneration(origin)) setDraftAction(undefined);
    }
  }
  async function rejectGeneratedDraft(draft: { id: string }) {
    if (generationAction.current && isCurrentGeneration(generationAction.current.origin)) return;
    const origin = captureGenerationOrigin();
    if (!isCurrentGeneration(origin)) return;
    const action = { origin, id: draft.id, kind: 'reject' };
    generationAction.current = action;
    const remaining = variantDrafts.filter(item => item.id !== draft.id);
    setDraftAction('reject');
    try {
      await api.reject(draft.id, origin.context);
      clearRecoveredTask(origin, draft.id);
      if (remaining.length) retainGeneration(origin, { chapterId: origin.chapterId, variants: remaining });
      if (!isCurrentGeneration(origin)) return;
      setVariantDrafts(remaining); setActiveVariant(0);
      if (job?.id === draft.id) { stopGenerationObservation(); setJob(undefined); }
    } catch {
      if (isCurrentGeneration(origin)) setShellMessage('拒绝结果未确认，草稿已保留，请重试。');
    } finally {
      if (generationAction.current === action) generationAction.current = undefined;
      if (isCurrentGeneration(origin)) setDraftAction(undefined);
    }
  }
  async function navigateInterop(route: HostRoute, signal: AbortSignal, navigationCurrent?: () => boolean): Promise<void> {
    if (!navigationCurrent) { if (!await styleLeave.request(current => navigateInterop(route, signal, current), signal)) throw new Error('NAVIGATION_CANCELLED'); return; }
    if (!navigationCurrent() || signal.aborted) return;
    const context = { sessionToken: s.sessionToken, scope: s.scope, actor: s.actor };
    assertCurrentHandoff(route, context, s.novelId);
    const current = () => navigationCurrent() && !signal.aborted && mounted.current && revisionStoreIdentity(useStudio.getState()) === editorIdentity;
    if (!current()) return;
    // Navigating is explicit and read-only. Existing draft/review paths retain ownership.
    if (route.action === 'OPEN_FEATURE') {
      const target = interopFeatureRoutes[route.feature || ''];
      if (!target) throw new ApiError({ status: 404, code: 'HANDOFF_TARGET_NOT_FOUND', message: '' });
      if (target.experimental && experimentalFlags.data?.features[`experimental.${target.experimental}`] !== true)
        throw new ApiError({ status: 403, code: 'CAPABILITY_NOT_SUPPORTED', message: '' });
      setInteropControlTab(target.controlTab);
      if (target.controlTab) setInteropControlSurface('model-center');
      if (target.experimental) setExperimentalTab(target.experimental);
      if (target.panel) setPanel(target.panel);
      commitStudioModule(target.module); return;
    }
    if (route.action === 'OPEN_PROJECT') {
      if (route.project_id !== s.novelId) throw new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: '' });
      commitStudioModule('NOVEL'); setPanel('overview'); return;
    }
    if (route.action === 'OPEN_CHAPTER') {
      if (!route.chapter_id) throw new ApiError({ status: 404, code: 'HANDOFF_TARGET_NOT_FOUND', message: '' });
      const safe = () => {
        const live = workspaceRestoreState.current;
        return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
          && !drafts.load(route.chapter_id!, namespace) && !conflicts.load(route.chapter_id!, namespace);
      };
      if (!safe()) throw new ApiError({ status: 409, code: 'SOURCE_CHANGED', message: '' });
      const target = await api.chapter(route.chapter_id, context);
      if (!current()) return;
      if (!safe() || target.novel_id !== s.novelId || target.id !== route.chapter_id || route.chapter_version !== undefined && target.version !== route.chapter_version)
        throw new ApiError({ status: 409, code: 'SOURCE_CHANGED', message: '' });
      s.setChapter(target.id); commitStudioModule('NOVEL'); setPanel('history'); return;
    }
    if (!route.task_id || route.task_kind !== 'generation' || !['PENDING', 'QUEUED', 'RUNNING', 'WAITING', 'FAILED', 'COMPLETED', 'CANCELLED', 'BLOCKED', 'UNKNOWN'].includes(route.task_status || ''))
      throw new ApiError({ status: 404, code: 'HANDOFF_TARGET_NOT_FOUND', message: '' });
    // This bounded receipt comes from the original task authority in the host.
    // Do not fetch prompts/output or enter Generation Review from an advice link.
    setInteropTask({ id: route.task_id, status: route.task_status!, chapterId: route.chapter_id });
    commitStudioModule('NOVEL'); setPanel('agents');
  }
  const localTutorSurface = studioModule === 'CONTROL' ? interopControlSurface : currentInteropSurface(studioModule, panel, experimentalTab);
  const localTutor = useLocalTutorIntegration({
    context: { sessionToken: s.sessionToken, scope: s.scope, actor: s.actor }, projectId: s.novelId,
    module: studioModule, surface: localTutorSurface,
    chapterId: studioModule === 'NOVEL' ? s.chapterId || undefined : undefined,
    chapterVersion: chapter.data?.version, taskId: currentInteropTaskId(localTutorSurface, job?.id),
    selection: studioModule === 'NOVEL' ? selection : undefined,
    sourceReady: studioModule === 'NOVEL' && saveState === 'saved' && !composing && !savePending.current && hydratedIdentity === editorIdentity && !!chapter.data,
    onNavigate: navigateInterop,
    simple: shellMode !== 'pro', // [HERMIA-FE-20261025 DUI P0-4]
  });
  async function openLocalSample(id: string) {
    const origin = useStudio.getState();
    if (!workspaceTools || packagedHost || origin.sessionToken || origin.scope || origin.novelId) return;
    const identity = revisionStoreIdentity(origin);
    // Sample creation does not run NovelHome's original query invalidation.
    // Hold explicit project choice while refreshing the original inventory.
    setProjectChoiceOpen(true);
    try {
      await qc.invalidateQueries({ queryKey: ['novels'], refetchType: 'none' });
      const currentProjects = await qc.fetchQuery({ queryKey: ['novels'], queryFn: api.novels, staleTime: 0 });
      if (revisionStoreIdentity(useStudio.getState()) !== identity) return;
      const currentFlags = qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', namespace]);
      if (!currentFlags?.features['experimental.workspace_tools_v2']) return;
      if (!currentProjects.some(project => project.id === id)) {
        setProjectRecoveryNotice('练习项目当前不存在或不可访问，请核对项目列表。');
        return;
      }
      setProjectChoiceOpen(false); setProjectRecoveryNotice('');
      useStudio.getState().setNovel(id);
    } catch {
      if (revisionStoreIdentity(useStudio.getState()) === identity)
        setProjectRecoveryNotice('项目列表未核对完成，练习内容已保留。请恢复连接后重新打开。');
    }
  }
  if (!s.novelId && !s.scope?.workspaceId)
    return (
      <EntryExperience
        independentStudioEnabled={independentStudios}
        packagedHost={packagedHost}
        initialToken={s.sessionToken}
        onOpenLocalSample={id => { void openLocalSample(id); }}
        onEnter={(nextToken, nextScope) =>
          s.setCollaboration(nextToken, undefined, nextScope)
        }
        localHome={<>{(workspaceTools || independentStudios) && projectRecoveryNotice && <section className="notice" role="status">{projectRecoveryNotice}</section>}<NovelHome onCreated={id => { setProjectChoiceOpen(false); setProjectRecoveryNotice(''); s.setNovel(id); }} />{independentStudios && !s.sessionToken && !s.scope && !packagedHost && <BlankProjectEntry createProject={async title => {
          const origin = revisionStoreIdentity(useStudio.getState());
          const row = await createStudioProject(title, { sessionToken: s.sessionToken, actor: s.actor, scope: s.scope });
          if (origin !== revisionStoreIdentity(useStudio.getState())) throw new Error('会话已改变。项目已保留，请从原项目列表打开。');
          if (!row.studio_ready || row.requires_scope_selection) throw new Error('项目已创建，需要从授权创作空间选择后打开。');
          cacheCreatedNovel(qc, { ...row, genre: '', chapter_count: 0, word_count: 0, status: 'Writing' });
          s.setNovel(row.id); requestedStudioEntry.current = studioEntryApplied.current;
          setProjectChoiceOpen(false); setRequestedStudioProject(row.id); setRequestedStudioAsset(undefined); setStudioModule('IMAGE');
        }} />}</>}
      />
    );
  const scope = s.scope;
  const localNovelTitle =
    novels.data?.find((n) => n.id === s.novelId)?.title || "当前小说";
  const shellScope = selectedScopeLabels(scope, localNovelTitle);
  const currentStudioRequest = requestedStudioEntry.current === studioEntry && requestedStudioProject === s.novelId;
  // [HERMIA-FE-20261022] H-UX-START-01 · overlay; skip/NOVEL → write; media modules never land in novel center
  const dismissStartGate = () => { markModuleStartGateDismissed(); setStartGateOpen(false); };
  const moduleStartGate = startGateOpen ? (
    <ModuleStartGate
      onPick={(module) => {
        dismissStartGate();
        if (module === "NOVEL") {
          commitStudioModule("NOVEL");
          setPanel("write");
        } else {
          commitStudioModule(module);
        }
      }}
      onSkip={() => {
        dismissStartGate();
        commitStudioModule("NOVEL");
        setPanel("write");
      }}
    />
  ) : null;
  // [HERMIA-FE-20261022 R2] 图片页按原型重做：中性项目进图片也走新图片页；只有从资产显式送来素材时才进旧的独立创作工作台。
  if (independentStudios && isManualStudioModule(studioModule) && (currentStudioRequest || (neutralStudio && studioModule !== 'IMAGE'))) return <>{moduleStartGate}{localTutor.dialog}<IndependentStudioWorkspace projectId={s.novelId} context={{ sessionToken: s.sessionToken, actor: s.actor, scope }} scope={shellScope} actor={s.actor?.displayName || '本机作者'} module={studioModule} requestedAssetId={currentStudioRequest ? requestedStudioAsset : undefined} onModuleChange={navigateStudioModule} onOpenBroker={experimentalFlags.data?.features['experimental.model_broker_v2'] === true ? () => styleLeave.request(current => { if (current()) { commitStudioModule('NOVEL'); setCreativeWorkbenchOpen(false); setExperimentalTab('model_broker_v2'); setPanel('experimental'); } }) : undefined} onVerified={studioVerified} status={localTutor.entry} onProjectChoice={() => { setProjectChoiceOpen(true); setRequestedStudioProject(undefined); setRequestedStudioAsset(undefined); requestedStudioEntry.current = undefined; studioEntryApplied.current = { ...studioEntryApplied.current, identity: '' }; if (scope) s.setCollaboration(s.sessionToken, s.actor, undefined); else s.setNovel(''); }} /></>;
  if (studioModule !== "NOVEL") return <>{moduleStartGate}{localTutor.dialog}<ModuleWorkspaceRoutes localAiOnboarding={independentStudios ? {context: {sessionToken: s.sessionToken, actor: s.actor, scope: s.scope}, projectId: s.novelId} : undefined} projectNoun={neutralStudio ? '项目' : undefined} interopEntry={localTutor.entry} interopSettings={localTutor.settings} controlTab={interopControlTab} onControlSurfaceChange={setInteropControlSurface} key={JSON.stringify([s.sessionToken,s.actor?.id,s.novelId,scope?.workspaceId,scope?.projectId,scope?.storylineId,scope?.branchId])} module={studioModule} onModuleChange={navigateStudioModule} novelId={s.novelId} actor={s.actor?.displayName || "本机作者"} scope={shellScope} shellMode={shellMode} onShellModeChange={applyShellMode} /></>;
  const saveDisplayLabel = chapter.data
    ? (writingRecovery ? recoveryStateLabel(saveState, durability, composing, recoveryOffline) : saveStateLabel(saveState))
    // [HERMIA-FE-20261025 DUI P0-3] Only claim "opening" while a chapter is actually being fetched.
    : chapter.isFetching ? i18nT("save.opening") : chapters.isError ? i18nT("chapter.unreadable") : i18nT("chapter.notOpen");
  // [HERMIA-FE-20261025 VERA-FIX P0-3] 一屏一状态：章节列表读取中/失败且没有已打开章节时，中间与右栏只跟随同一状态，不再出现空态卡片与「选择或新建章节」CTA。
  const chaptersPending: 'loading' | 'error' | undefined = chapter.data ? undefined : chapters.isError ? 'error' : chapters.isLoading ? 'loading' : undefined;
  const taskSummary = summarizeTasks(job?.status ? [{ status: job.status }] : []);
  const archivedItems = Array.isArray(archived.data)
    ? archived.data
    : ((archived.data as unknown as { items?: Chapter[] } | undefined)?.items || []);
  const writingGoalValue = writingGoal.data && [writingGoal.data.current_words, writingGoal.data.target_words,
    writingGoal.data.current_chapters, writingGoal.data.target_chapters, writingGoal.data.words_progress]
    .every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0) ? writingGoal.data : undefined;
  // [HERMIA-FE-20261022 REBUILD-W3] 左栏按原型：作品结构 + 小说面板（带状态标签）；旧章节管理与全部功能收起
  // [HERMIA-FE-20261022 R1] 状态词按原型；「已接通」只给读写都走后端的面板，其余如实「部分实现」
  const novelRailPanels: RailPanel[] = gateNovel<RailPanel>([ // [HERMIA-FE-20261022 U4] 普通隐藏 一致性/版本/研究
    { id: 'overview', label: '总览', status: 'ok' },
    { id: 'write', label: '写作台', status: 'ok' },
    { id: 'story', label: '大纲 · 人物 · 世界观', status: 'ok' },
    { id: 'check', label: '一致性 · 待审设定', status: 'ok' },
    { id: 'history', label: '版本 / 修订', status: 'ok', disabled: !chapter.data, title: chapter.data ? undefined : '先打开一个章节' },
    { id: 'creation', label: '创作方案', status: 'part' },
    { id: 'knowledge', label: '导入', status: 'part' },
    { id: 'exports', label: '导出', status: 'part', title: '可导出与下载；取消 / 重试还没接上' },
    { id: 'research', label: '研究', status: 'part' },
    { id: 'screenplay', label: '影视剧本', status: 'part' },
    { id: 'adaptation', label: '改编', status: 'part' },
    { id: 'workflow', label: '工作流', status: 'part' },
    { id: 'agents', label: 'AI 任务', status: 'part' },
  ], NOVEL_PRO_PANELS, shellMode);
  const openNovelPanel = (id: string) => styleLeave.request(current => { if (current()) { commitStudioModule('NOVEL'); setPanel(id); } });
  const createNextChapter = async () => {
    const title = `第 ${(chapters.data?.length || 0) + 1} 章`;
    try {
      const created = scope ? await api.scopedCreateChapter(scope, title) : await api.createChapter(s.novelId, title);
      await chapters.refetch(); await writingGoal.refetch(); s.setChapter(created.id); setPanel('write');
    } catch { setShellMessage('新建章节失败，请稍后重试。'); }
  };
  const novelRailChapters = (chapters.data || []).map(c => ({ id: c.id, number: c.number, title: c.title, wordCount: c.word_count, status: c.id === s.chapterId ? saveDisplayLabel : undefined })); // [HERMIA-FE-20261022 R1]
  // [HERMIA-FE-20261022 R1] 原型 WS.NOVEL tabs，只放能落到现有面板的页签（圣经无独立面板，不放）
  const openNovelEntry = (id: NovelSecondaryEntryId) => styleLeave.request(current => {
    if (!current()) return;
    const entry = novelSecondaryEntry(id);
    commitStudioModule('NOVEL'); setPanel(entry.panel);
    window.setTimeout(() => scrollNovelSecondaryAnchor(entry.anchor), 80);
  });
  const novelModTabs = gateNovel([ // [HERMIA-FE-20261022 U4] 普通隐藏 设定/一致性/版本
    { id: 'overview', label: '总览', selected: panel === 'overview', onClick: () => openNovelPanel('overview') },
    { id: 'writer', label: '写作台', selected: panel === 'write', onClick: () => openNovelPanel('write') },
    { id: 'outline', label: '大纲', selected: panel === 'story', onClick: () => openNovelEntry('story-planning') },
    { id: 'cast', label: '人物', onClick: () => openNovelPanel('story') },
    { id: 'canon', label: '设定', onClick: () => openNovelEntry('pending-canon') },
    { id: 'continuity', label: '一致性', selected: panel === 'check', onClick: () => openNovelEntry('continuity') },
    { id: 'revision', label: '版本', selected: panel === 'history', disabled: !chapter.data, onClick: () => openNovelPanel('history') },
  ], NOVEL_PRO_TABS, shellMode);
  const sidebar = (
    <NovelStructureRail
      pro={shellMode === 'pro' /* [HERMIA-FE-20261025 DUI P0-2] */}
      chapters={novelRailChapters}
      selectedId={s.chapterId}
      loading={chapters.isLoading}
      error={chapters.error ? i18nT("ct.retryLater") /* [HERMIA-FE-20261025 VERA-FIX P2] 不外露原始错误文本 */ : null}
      onSelect={id => { s.setChapter(id); if (panel !== 'write') openNovelPanel('write'); }}
      onCreate={s.novelId ? () => { void createNextChapter(); } : undefined}
      panels={novelRailPanels}
      activePanel={panel}
      onOpenPanel={openNovelPanel}
      more={<div className="tree sidebar-layout">
      {/* [HERMIA-FE-20261022 R1] 章节管理 + 全部功能统一收进「更多」 */}
      <div className="sidebar-chapter-scroll" data-testid="chapter-tree-scroll">
        {!creativeWorkbenchOpen && experimentalFlags.data?.features["experimental.narrative_production_v2"] === true && <div className="creative-workbench-entry"><Button disabled={composing} onClick={() => styleLeave.request(current => { if (current()) { commitStudioModule('NOVEL'); setCreativeWorkbenchOpen(true); } })}>打开 V2 创作工作台</Button></div>}
        <ChapterTree
          chapters={(chapters.data || []).map((c) => ({
            id: c.id,
            title: c.title,
            status: c.id === s.chapterId ? saveDisplayLabel : undefined,
            wordCount: c.word_count,
            version: c.version,
            number: c.number,
          }))}
           archived={archivedItems.map((c) => ({
            id: c.id,
            title: c.title,
            number: c.number,
            version: c.version,
          }))}
          selectedId={s.chapterId}
          loading={chapters.isLoading}
          error={chapters.error ? i18nT("ct.retryLater") /* [HERMIA-FE-20261025 VERA-FIX P2] 不外露原始错误文本 */ : null}
          onSelect={s.setChapter}
          onCreate={async (title) => {
            const created = scope
              ? await api.scopedCreateChapter(scope, title)
              : await api.createChapter(s.novelId, title);
            await chapters.refetch();
            await writingGoal.refetch();
            s.setChapter(created.id);
          }}
          onRename={async (id, title) => {
            const current = (chapters.data || []).find((c) => c.id === id);
            if (!current) return;
            await api.renameChapter(id, title, current.version);
            await chapters.refetch();
            await writingGoal.refetch();
            if (id === s.chapterId) await chapter.refetch();
          }}
          reordering={reorderingChapters}
          onReorder={scope?undefined:async(sourceId,targetId)=>{
            const rows=chapters.data||[],from=rows.findIndex(c=>c.id===sourceId),to=rows.findIndex(c=>c.id===targetId);
            if(from<0||to<0||from===to)return;
            if(Math.abs(to-from)!==1){setShellMessage('请拖到相邻章节，逐章调整顺序。');return}
            const direction=from<to?'down':'up';
            setReorderingChapters(true);setShellMessage('');
            try{await api.moveChapter(sourceId,direction);await chapters.refetch();setShellMessage('章节顺序已保存。')}
            catch(e){await chapters.refetch();setShellMessage(e instanceof ApiError&&e.status===409?'章节顺序发生冲突，已恢复原顺序。':'章节排序失败，已恢复原顺序。')}
            finally{setReorderingChapters(false)}
          }}
          onArchive={async (c) => {
            const current = (chapters.data || []).find((x) => x.id === c.id);
            if (!current) return;
            try {
              setShellMessage("");
              await api.archiveChapter(c.id, current.version);
              await Promise.all([chapters.refetch(), archived.refetch(), writingGoal.refetch()]);
              if (s.chapterId === c.id) {
                const next = (chapters.data || []).find((x) => x.id !== c.id);
                s.setChapter(next?.id || "");
              }
            } catch (e) {
              setShellMessage(
                e instanceof ApiError && e.status === 409
                  ? "章节已发生变化，请刷新后重试。"
                  : "移出章节失败",
              );
            }
          }}
          onRestore={async (c) => {
            try {
              setShellMessage("");
              await api.restoreArchivedChapter(c.id, c.version || 1);
              await Promise.all([chapters.refetch(), archived.refetch(), writingGoal.refetch()]);
            } catch (e) {
              setShellMessage(
                e instanceof ApiError && e.status === 409
                  ? "章节已发生变化，请刷新后重试。"
                  : "恢复章节失败",
              );
            }
          }}
          onDelete={scope?undefined:async(c)=>{
            try {
              setShellMessage("");
              await api.deleteChapter(c.id);
              await Promise.all([chapters.refetch(),archived.refetch(),writingGoal.refetch()]);
              setShellMessage(`已永久删除章节“${c.title}”。`);
            } catch {
              setShellMessage("永久删除章节失败，请稍后重试。");
            }
          }}
        />
      </div>
      <CommandSearch workbench={workbench} onLegacy={legacySelectPanel} />
      <FeatureLauncher
        selectedId={panel}
        extraGroups={hasExperimental ? EXPERIMENTAL_GROUPS : undefined}
        expandedGroups={featureGroups}
        onSelect={next => { void workbench.open(next, legacySelectPanel); }}
        onToggleGroup={(id) => setFeatureGroups((current) => ({ ...current, [id]: !current[id] }))}
      />
      </div>}
    />
  );
  function openStorySourceChapter(chapterId: string, signal?: AbortSignal) {
    if (!chapterId || signal?.aborted || panel !== 'story' || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    const origin = captureGenerationOrigin(), ticket = ++workspaceRestoreSequence.current;
    const originBuffer = JSON.stringify(buffer.current);
    const current = () => mounted.current && !signal?.aborted && ticket === workspaceRestoreSequence.current
      && origin.epoch === editorEpoch.current && origin.identity === revisionStoreIdentity(useStudio.getState());
    const safeBuffer = () => {
      const live = workspaceRestoreState.current;
      return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
        && JSON.stringify(buffer.current) === originBuffer
        && !drafts.load(origin.chapterId, origin.namespace) && !conflicts.load(origin.chapterId, origin.namespace)
        && !drafts.load(chapterId, origin.namespace) && !conflicts.load(chapterId, origin.namespace);
    };
    if (!safeBuffer()) { setShellMessage('请先保存或处理当前或目标章节的草稿，再打开资料来源。当前内容已保留。'); return; }
    void api.chapter(chapterId, origin.context).then(value => {
      if (!current()) return;
      if (!safeBuffer()) { setShellMessage('核对资料来源期间出现新输入，已保留草稿。请保存后再次打开。'); return; }
      if (value.id !== chapterId || value.novel_id !== origin.novelId || value.is_archived) throw new Error('STORY_SOURCE_UNAVAILABLE');
      qc.setQueryData<Chapter>(['chapter', origin.namespace, chapterId], current => current && current.version > value.version ? current : value);
      s.setChapter(chapterId); setPanel('history');
    }).catch(() => { if (current()) setShellMessage('原来源章节当前不可读或权限已撤销，未切换章节。当前草稿已保留。'); });
  }
  function navigateWorkspace(target: WorkspaceNavigation, navigationCurrent?: () => boolean) {
    if (!navigationCurrent) { styleLeave.request(current => navigateWorkspace(target, current), target.signal); return; }
    if (!navigationCurrent()) return;
    if (!hasExperimental || revisionStoreIdentity(useStudio.getState()) !== editorIdentity || target.signal?.aborted) return;
    if (target.task_authority === 'revision_model_job' && (target.kind !== 'feature' || target.feature !== 'revision_intelligence_v2'
      || !target.chapter_id || !Number.isInteger(target.version) || !target.version)) return;
    const workspaceTicket = ++workspaceRestoreSequence.current;
    generationOpenSequence.current += 1;
    setPendingGenerationOpen(undefined);
    setStoryTarget(undefined); setTaskTarget(undefined);
    if (target.task_authority === 'adaptation') {
      if (!workspaceTools || experimentalFlags.data?.features['experimental.adaptation_lifecycle_v1'] !== true || target.kind !== 'feature' || target.feature !== 'adaptation_lifecycle_v1'
        || !target.parent_id || !target.id || !Number.isInteger(target.version) || !target.version
        || target.novel_id !== s.novelId || (target.branch_id || undefined) !== s.scope?.branchId) {
        setShellMessage('原改编任务的项目、分支或版本定位无效；未打开其他方案。'); return;
      }
      const origin = captureGenerationOrigin(), originalBuffer = JSON.stringify(buffer.current);
      const current = () => navigationCurrent() && mounted.current && !target.signal?.aborted && workspaceTicket === workspaceRestoreSequence.current
        && origin.epoch === editorEpoch.current && origin.identity === revisionStoreIdentity(useStudio.getState())
        && qc.getQueryData<{features:Record<string,boolean>}>(['experimental-features',origin.namespace])?.features['experimental.adaptation_lifecycle_v1'] === true;
      const safeBuffer = () => {
        const live = workspaceRestoreState.current;
        return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
          && JSON.stringify(buffer.current) === originalBuffer && !drafts.load(origin.chapterId, origin.namespace)
          && !conflicts.load(origin.chapterId, origin.namespace);
      };
      if (!safeBuffer()) { setShellMessage('当前有未保存草稿，请先保存或处理冲突，再打开原改编任务。当前内容已保留。'); return; }
      void api.adaptationTask(origin.novelId, target.parent_id, target.id, s.scope?.branchId, origin.context).then(result => {
        if (!current()) return;
        if (!safeBuffer()) { setShellMessage('核对改编任务期间出现新输入，已保留草稿。请保存后再次打开。'); return; }
        if (result.proposal_id !== target.parent_id || result.task?.id !== target.id || result.proposal_revision !== target.version
          || result.stale) throw new Error('ADAPTATION_NAVIGATION_STALE');
        setTaskTarget({namespace:origin.namespace,novelId:origin.novelId,id:target.id,authority:'adaptation',parent_id:target.parent_id,version:target.version});
        setPanel('adaptation');
      }).catch(() => { if (current()) setShellMessage('原改编任务已过期、不可读或权限已撤销。请刷新任务后重新核对；未切换正文或打开其他方案。'); });
      return;
    }
    if (target.novel_id && (target.novel_id !== s.novelId || (target.branch_id || undefined) !== s.scope?.branchId)) {
      if (!workspaceTools || packagedHost || s.sessionToken || s.scope || target.branch_id) {
        setShellMessage('请通过原工作区与分支选择器切换此来源；不会把当前会话或主线正文借给另一分支。当前草稿未改变。');
        return;
      }
      const origin = captureGenerationOrigin(), destination = target.novel_id;
      const originBuffer = JSON.stringify(buffer.current);
      const chapterId = target.kind === 'chapter' ? target.id : target.kind === 'generation' || target.task_authority === 'revision_model_job' ? target.chapter_id : undefined;
      const current = () => navigationCurrent() && mounted.current && !target.signal?.aborted && workspaceTicket === workspaceRestoreSequence.current
        && origin.epoch === editorEpoch.current && origin.identity === revisionStoreIdentity(useStudio.getState())
        && qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace])?.features['experimental.workspace_tools_v2'] === true
        && (target.task_authority !== 'revision_model_job' || qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace])?.features['experimental.revision_intelligence_v2'] === true);
      const safeBuffer = () => {
        const live = workspaceRestoreState.current;
        return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
          && JSON.stringify(buffer.current) === originBuffer
          && !drafts.load(origin.chapterId, origin.namespace) && !conflicts.load(origin.chapterId, origin.namespace)
          && (!chapterId || !drafts.load(chapterId, origin.namespace) && !conflicts.load(chapterId, origin.namespace));
      };
      if (!safeBuffer()) { setShellMessage('当前或目标章节有未保存草稿，请先保存或处理冲突，再打开另一作品的搜索结果。当前内容已保留。'); return; }
      void (async () => {
        // Search metadata is not project authority: refresh the original inventory.
        const projects = await qc.fetchQuery({ queryKey: ['novels'], queryFn: api.novels, staleTime: 0 });
        if (!current()) return;
        if (!projects.some(project => project.id === destination)) throw new Error('SEARCH_PROJECT_UNAVAILABLE');
        const destinationChapter = chapterId ? await api.chapter(chapterId, origin.context) : undefined;
        if (!current()) return;
        if (destinationChapter && (destinationChapter.id !== chapterId || destinationChapter.novel_id !== destination
          || target.kind === 'chapter' && destinationChapter.version !== target.version)) throw new Error('SEARCH_SOURCE_CHANGED');
        if (target.kind === 'generation' || target.task_authority === 'revision_model_job') {
          if (!chapterId || !destinationChapter) throw new Error('SEARCH_TASK_SOURCE_UNAVAILABLE');
          const original = await api.job(target.id, origin.context);
          if (!current()) return;
          if (original.novel_id !== destination || original.chapter_id !== chapterId) throw new Error('SEARCH_TASK_SCOPE_CHANGED');
          if (target.task_authority === 'revision_model_job' && (original.id !== target.id || original.experimental_origin !== 'revision_comparison_model'
            || original.base_chapter_version !== target.version)) throw new Error('SEARCH_TASK_SOURCE_CHANGED');
        }
        if (!current()) return;
        if (!safeBuffer()) { setShellMessage('核对搜索来源期间出现新输入，已保留草稿；请保存后再次打开。'); return; }
        const feature = target.feature || target.id;
        const safePanels = new Set(['audiobook', 'overview', 'editor', 'write', 'creation', 'story', 'history', 'workflow', 'screenplay', 'assets', 'exports', 'knowledge', 'research', 'agents', 'diagnostics', 'settings']);
        const experimental = EXPERIMENTAL_TABS.some(([key]) => key === feature);
        if (target.kind === 'feature' && !safePanels.has(feature)
          && !(experimental && experimentalFlags.data?.features[`experimental.${feature}`] === true)) return;
        if (destinationChapter) qc.setQueryData(['chapter', origin.namespace, chapterId], destinationChapter);
        setProjectChoiceOpen(false); setProjectRecoveryNotice('');
        useStudio.getState().setNovel(destination);
        if (target.task_authority) setTaskTarget({ namespace: origin.namespace, novelId: destination, id: target.id, authority: target.task_authority, parent_id: target.parent_id });
        if (chapterId && destinationChapter) {
          useStudio.getState().setChapter(chapterId);
          setPendingAnchor({ namespace: origin.namespace, chapterId, version: destinationChapter.version,
            requestId: ++anchorSequence.current, offset: target.anchor?.offset || 0, scroll: target.anchor?.scroll || 0 });
          if (target.task_authority === 'revision_model_job') { setExperimentalTab(feature); setPanel('experimental'); }
          else setPanel('history');
          if (target.kind === 'generation') setPendingGenerationOpen({ namespace: origin.namespace, novelId: destination,
            actorId: s.actor?.id, chapterId, jobId: target.id });
        } else if (experimental) { setExperimentalTab(feature); setPanel('experimental'); }
        else {
          if (feature === 'story' && target.record_kind) setStoryTarget({ namespace: origin.namespace, novelId: destination, requestId: workspaceTicket, id: target.id, record_kind: target.record_kind });
          setPanel(feature === 'editor' ? 'write' : feature);
        }
        setShellMessage('已通过原项目与来源权限核对，打开另一作品的搜索结果。未执行或重新提交任何任务。');
      })().catch(() => { if (current()) setShellMessage('搜索目标当前不可读或版本已变，未切换作品。请刷新结果并重新核对；当前草稿已保留。'); });
      return;
    }
    if (target.kind === 'feature' && target.task_authority === 'revision_model_job') {
      if (!workspaceTools || target.feature !== 'revision_intelligence_v2' || !target.chapter_id || !target.version
        || experimentalFlags.data?.features['experimental.revision_intelligence_v2'] !== true) return;
      const origin = captureGenerationOrigin(), chapterId = target.chapter_id;
      const originalBuffer = JSON.stringify(buffer.current);
      const current = () => navigationCurrent() && mounted.current && !target.signal?.aborted && workspaceTicket === workspaceRestoreSequence.current
        && origin.epoch === editorEpoch.current && origin.identity === revisionStoreIdentity(useStudio.getState())
        && qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace])?.features['experimental.workspace_tools_v2'] === true
        && qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace])?.features['experimental.revision_intelligence_v2'] === true;
      const safeBuffer = () => {
        const live = workspaceRestoreState.current;
        return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
          && JSON.stringify(buffer.current) === originalBuffer && !drafts.load(origin.chapterId, origin.namespace)
          && !conflicts.load(origin.chapterId, origin.namespace) && !drafts.load(chapterId, origin.namespace) && !conflicts.load(chapterId, origin.namespace);
      };
      if (!safeBuffer()) { setShellMessage('当前或目标章节有未保存草稿，请先保存或处理冲突，再打开原版本比较任务。当前内容已保留。'); return; }
      void Promise.all([api.chapter(chapterId, origin.context), api.job(target.id, origin.context)]).then(([value, original]) => {
        if (!current()) return;
        if (!safeBuffer()) { setShellMessage('核对原版本比较任务期间出现新输入，已保留草稿；请保存后再次打开。'); return; }
        if (value.id !== chapterId || value.novel_id !== origin.novelId || original.id !== target.id || original.novel_id !== origin.novelId
          || original.chapter_id !== chapterId || original.base_chapter_version !== target.version
          || original.experimental_origin !== 'revision_comparison_model') throw new Error('SEARCH_TASK_SOURCE_CHANGED');
        qc.setQueryData(['chapter', origin.namespace, chapterId], value);
        setTaskTarget({ namespace: origin.namespace, novelId: origin.novelId, id: target.id, authority: target.task_authority });
        s.setChapter(chapterId); setExperimentalTab('revision_intelligence_v2'); setPanel('experimental');
      }).catch(() => { if (current()) setShellMessage('原版本比较任务或来源章节当前不可读，未切换章节。请刷新任务后重试；当前草稿已保留。'); });
      return;
    }
    if (target.kind === 'generation') {
      if (!workspaceTools || !target.id || !target.chapter_id || !Number.isInteger(target.version) || !target.version) return;
      const ticket = generationOpenSequence.current + 1;
      const origin = captureGenerationOrigin();
      void openExistingGeneration(target.id, target.chapter_id, target.signal, navigationCurrent).catch(() => {
        if (!target.signal?.aborted && generationOpenSequence.current === ticket && isCurrentGeneration(origin))
          setShellMessage('无法打开生成记录，请刷新任务并核对当前权限与来源。正文草稿未改变。');
      });
      return;
    }
    if (target.kind === 'chapter') {
      if (!target.id || !Number.isInteger(target.version) || !target.version) return;
      const open = () => {
        setPendingAnchor({ namespace, chapterId: target.id, version: target.version!,
          requestId: ++anchorSequence.current, offset: target.anchor?.offset || 0, scroll: target.anchor?.scroll || 0 });
        s.setChapter(target.id); setPanel('history');
      };
      if (!target.workspace) { open(); return; }
      const origin = captureGenerationOrigin();
      const current = () => navigationCurrent() && mounted.current && !target.signal?.aborted && workspaceTicket === workspaceRestoreSequence.current
        && origin.epoch === editorEpoch.current && origin.identity === revisionStoreIdentity(useStudio.getState())
        && qc.getQueryData<{ features: Record<string, boolean> }>(['experimental-features', origin.namespace])?.features['experimental.workspace_tools_v2'] === true;
      const safeBuffer = () => {
        const live = workspaceRestoreState.current;
        return live.saveState === 'saved' && !live.composing && !savePending.current && live.hydratedIdentity === live.editorIdentity
          && !drafts.load(origin.chapterId, origin.namespace) && !drafts.load(target.id, origin.namespace) && !conflicts.load(target.id, origin.namespace);
      };
      if (!safeBuffer()) { setShellMessage('当前或目标章节有未保存草稿，请先保存或处理冲突，再恢复工作现场。当前内容已保留。'); return; }
      // Re-open through the original chapter authority, even when React Query
      // has a cached destination. A delayed response cannot replace newer work.
      void api.chapter(target.id, origin.context).then(value => {
        if (!current()) return;
        if (!safeBuffer()) { setShellMessage('恢复期间出现新输入，已保留草稿；请保存后再次恢复。'); return; }
        if (value.id !== target.id || value.novel_id !== origin.novelId || value.version !== target.version) {
          setShellMessage('章节版本已变化，未套用旧现场。请重新核对并选择打开当前版本。'); return;
        }
        qc.setQueryData(['chapter', origin.namespace, target.id], value);
        const restored = target.workspace!;
        if (writingFocus && restored.focus_state === 'READY' && restored.focus_preferences) {
          focusPreferencesTouched.current = true;
          setWritingPreferences(restored.focus_preferences); setFocusActive(restored.view.focus_active);
          setReferencesVisible(restored.view.references_visible); setReferenceRevision(value => value + 1);
        }
        setWorkspaceSection(restored.layout.section);
        setShellMessage(restored.focus_state === 'CHANGED' ? '章节位置已核对；固定参考与阅读偏好已有新版本，保留当前设置。' : '已恢复核对过的章节位置。未重新提交任何任务。');
        open();
      }).catch(() => { if (current()) setShellMessage('原章节当前不可读，未恢复现场。请核对权限或刷新后重试，当前内容已保留。'); });
      return;
    }
    const feature = target.feature || target.id;
    if (target.task_authority) setTaskTarget({ namespace, novelId: s.novelId, id: target.id, authority: target.task_authority, parent_id: target.parent_id });
    const experimental = EXPERIMENTAL_TABS.find(([key]) => key === feature);
    if (experimental) {
      if (experimentalFlags.data?.features[`experimental.${feature}`] !== true) return;
      setExperimentalTab(feature); setPanel('experimental'); return;
    }
    if (feature === 'story' && target.record_kind) setStoryTarget({ namespace, novelId: s.novelId, requestId: workspaceTicket, id: target.id, record_kind: target.record_kind });
    const safePanels = new Set(['audiobook', 'overview', 'editor', 'write', 'creation', 'story', 'history', 'workflow', 'screenplay', 'assets', 'exports', 'knowledge', 'research', 'agents', 'diagnostics', 'settings']);
    if (safePanels.has(feature)) setPanel(feature === 'editor' ? 'write' : feature);
  }
  const openWorkspaceSearch = workspaceTools ? () => styleLeave.request(current => {
    if (!current()) return;
    commitStudioModule('NOVEL'); setWorkspaceSection('search'); setExperimentalTab('workspace_tools_v2'); setPanel('experimental');
  }) : undefined;
  const mainWorkspace = (
    <div className="workspace novel-writing-workspace">
      {!(creativeWorkbenchOpen && experimentalFlags.data?.features["experimental.narrative_production_v2"] === true) && styleLeave.dialog}
      {/* [HERMIA-FE-20261022 R1] 原型模块页签条 + 168px 独立章节列 + 写作台 */}
      <NovelModTabs tabs={novelModTabs} />
      <div className="nv-stage">
      {panel === 'write' ? <NovelChapterColumn
        chapters={novelRailChapters}
        selectedId={s.chapterId}
        loading={chapters.isLoading /* [HERMIA-FE-20261025 DUI P0-3] */}
        error={chapters.error ? i18nT("ct.retryLater") /* [HERMIA-FE-20261025 VERA-FIX2] 中栏亦不传原始错误 */ : null}
        onSelect={id => s.setChapter(id)}
        onCreate={s.novelId ? () => { void createNextChapter(); } : undefined}
      /> : null}
      <div className="nv-desk">
      {/* [HERMIA-FE-20261022 REBUILD-W3] 写作台头部按原型 nd-head / nd-tools */}
      <div className="nv-desk__head">
        <h2>{tz(chapter.data ? `第 ${chapter.data.number} 章 · ${chapter.data.title || '未命名'}` : (panel === 'write' ? '未选择章节' : (novelRailPanels.find(p => p.id === panel)?.label || '小说')))}</h2>
        {panel === 'write' && chapter.data && shellMode === 'pro' /* [HERMIA-FE-20261025 DUI P0-2] */ ? <span className="nv-badge nv-badge--ok">{tz('写作台')}</span> : null}
        {panel === 'write' && chapter.data && shellMode === 'pro' ? <span className="nv-badge nv-badge--local">{i18nT('pat.version', { v: chapter.data.version })}</span> : null}
        <span className="nv-spacer" />
        {panel !== 'write' ? <button type="button" className="nv-btn" data-back-to-writer="true" onClick={() => openNovelPanel('write')}>{i18nT('desk.back')}</button> : null}
        {panel === 'write' && chapter.data && shellMode === 'pro' /* [HERMIA-FE-20261022 U4] 版本对比仅专业 */ ? <button type="button" className="nv-btn" onClick={() => openNovelPanel('history')}>{i18nT('desk.history')}</button> : null}
      </div>
      <div className={panel === 'write' ? 'novel-workspace-chrome' : 'novel-workspace-chrome nv-hide'}>
      <div className={chapter.data ? 'editorbar nv-desk__tools' : 'editorbar nv-desk__tools nv-hide'}>
        <div className="novel-editor-metadata">
        <small>{i18nT('pat.chars', { n: formatNumber(text.trim().length) })}</small>
        {writingGoal.data && !writingGoalValue && <p className="notice" role="status">{i18nT('desk.goalBad')}</p>}
        {writingGoalValue && (
          <div className="writing-goal" aria-label="写作目标进度">
            <span>{i18nT('pat.goal', { cur: formatNumber(writingGoalValue.current_words), target: formatNumber(writingGoalValue.target_words) })}</span>
            <span>第 {writingGoalValue.current_chapters} / {writingGoalValue.target_chapters} 章</span>
            <div className="writing-goal__bar" role="progressbar" aria-valuenow={Math.round(writingGoalValue.words_progress)} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: `${Math.min(100, Math.max(0, writingGoalValue.words_progress))}%` }} />
            </div>
            <strong>{Math.round(writingGoalValue.words_progress)}%</strong>
          </div>
        )}
        </div>
        <SaveControls
          state={saveState}
          ready={!!chapter.data && hydratedIdentity === editorIdentity}
          onSave={dispatchSave}
          composing={composing}
          recovery={writingRecovery ? { durability, offline: recoveryOffline, onExport: exportCurrentDraft, onConflict: reopenConflict } : undefined}
        />
      </div>
      {workspaceTools && <section className="notice workspace-resume-summary" aria-label="当前项目上次工作">
        {projectRecoveryNotice && <p className="workspace-resume-summary__recovery">{projectRecoveryNotice}</p>}
        {!packagedHost && shouldLoadLocalNovels(s.sessionToken, s.scope) && <Button onClick={() => styleLeave.request(current => { if (!current()) return; const live = workspaceRestoreState.current; const chapterId = useStudio.getState().chapterId; if (live.saveState !== 'saved' || live.composing || savePending.current || (chapterId && (live.hydratedIdentity !== live.editorIdentity || drafts.load(chapterId, namespace)))) { setShellMessage('请先保存或处理当前草稿，再切换本机作品。当前内容已保留。'); return; } setProjectChoiceOpen(true); setProjectRecoveryNotice('请选择本机作品；会记住本次明确选择。'); s.setNovel(''); })}>切换本机作品</Button>}
        <div className="workspace-resume-summary__content">
          {lastWorkspace.isFetching ? <span>正在核对上次工作现场…</span> : lastWorkspace.isError ? <span>工作现场暂时不可读，手工写作仍可继续。</span> : lastWorkspace.data?.item ? <><strong>上次工作：{lastWorkspace.data.item.chapter_title || '已保存停止点'}</strong><p className="workspace-resume-summary__note">{lastWorkspace.data.item.stopping_note || '没有停止点备注。'}</p></> : <span>可保存当前位置、筛选与下次事项。</span>}
        </div>
        {!lastWorkspace.isFetching && (lastWorkspace.isError ? <Button onClick={() => void lastWorkspace.refetch()}>重试读取上次现场</Button> : <Button onClick={() => styleLeave.request(current => { if (current()) { setWorkspaceSection('resume'); setExperimentalTab('workspace_tools_v2'); setPanel('experimental'); } })}>{lastWorkspace.data?.item ? '查看上次工作现场' : '保存当前工作现场'}</Button>)}
      </section>}
      {writingRecovery && corruptDraft?.identity === editorIdentity && <section className="notice" role="alert" aria-label="本机草稿恢复需要处理">
        <p>本机草稿记录损坏，尚未覆盖或丢弃。请先导出原始记录供恢复，再明确选择是否使用后端版本。</p>
        <Button onClick={() => { try { exportDraftText(corruptDraft.raw, 'writing-recovery-original.txt'); } catch { setShellMessage('原始草稿下载失败，记录仍保留。请保持此页打开并检查浏览器下载权限后重试。'); } }}>导出原始草稿记录</Button>
        <Button onClick={() => { if (revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return; drafts.remove(s.chapterId, namespace); setCorruptDraft(undefined); setDraftRecoveryEpoch(value => value + 1); }}>丢弃损坏记录并打开后端版本</Button>
      </section>}
      {writingRecovery && recoveryOffline && <section className="notice" role="status">浏览器报告网络离线。修改仍保留在当前浏览器草稿中；可以手动尝试保存到本机后端。只有收到后端回执才会显示已保存。</section>}
      {writingRecovery && durability === 'memory' && <section className="notice" role="alert">
        本机草稿写入失败。当前修改仅在此页面内存中，关闭、刷新或断电可能丢失。请导出当前草稿。
      </section>}
      </div>
      <div className={`${writingFocus && referencesVisible ? 'writing-editor-row writing-focus-split' : 'writing-editor-row'} nv-desk__body${panel === 'write' ? '' : ' nv-hide'}`}>
      {chapter.data && hydratedIdentity === editorIdentity ? (
        <ChapterEditor
          writingPreferences={writingFocus ? writingPreferences : undefined}
          key={`${namespace}:${s.chapterId}:${s.actor?.id || 'local'}:${scopeEpoch}`}
          content={text}
          document={doc}
          onChange={edit}
          onSelection={setSelection}
          onCompositionChange={compositionChanged}
          onAnchorChange={workspaceTools || writingFocus ? anchor => setEditorAnchor({ identity: editorIdentity, anchor }) : undefined}
          restoreAnchor={pendingAnchor && pendingAnchor.chapterId === s.chapterId && pendingAnchor.namespace === namespace && pendingAnchor.version === chapter.data.version && saveState === 'saved' ? pendingAnchor : undefined}
        />
      ) : chapters.isSuccess && (chapters.data || []).length === 0 && !corruptDraft && s.novelId ? (
        // [HERMIA-FE-20261022 REBUILD-W3] 空项目：原型「你想从哪里开始？」
        // [HERMIA-FE-20261022 R1] 空项目按原型写作台空态（不另起大标题页）
        <NovelStartEmpty onCreate={() => { void createNextChapter(); }} choices={[
          { id: 'story', title: '先做故事规划', desc: '人物、世界观与大纲', onClick: () => openNovelPanel('story') },
          { id: 'import', title: '导入已有稿件', desc: '把已有文本导入为章节', onClick: () => openNovelPanel('knowledge') },
        ]} />
      ) : chaptersPending && corruptDraft?.identity !== editorIdentity ? (
        // [HERMIA-FE-20261025 VERA-FIX P0-3] 状态已由左侧章节列宣告（role=status/alert），这里只静默镜像，无 CTA
        <section className="notice" data-desk-state={chaptersPending}>
          <strong>{i18nT(chaptersPending === 'error' ? 'rail.error' : 'rail.loading')}</strong>
        </section>
      ) : (
        <section className="notice" aria-live="polite">
          <strong>{corruptDraft?.identity === editorIdentity ? i18nT('desk.recoverFirst') : i18nT('desk.nothingOpen')}</strong>
          <p>{i18nT('desk.pickHint')}</p>
        </section>
      )}
      {writingFocus && referencesVisible && s.novelId && <WritingReferenceRail key={`${namespace}:${s.novelId}`} client={workspaceClient} revision={referenceRevision} />}
      </div>
      <div className={panel === 'write' ? 'nv-desk__panel nv-desk__panel--empty' : 'nv-desk__panel'}>
      {panel === 'settings' && localTutor.settings}
      {panel === 'agents' && interopTask && <section className="panel" aria-label="已授权的 Tutor 任务目标"><h2>任务详情 · 只读</h2><p>任务：{interopTask.id}</p><p>状态：{interopTask.status}</p><p>章节：{interopTask.chapterId || '无'}</p><p>状态来自原任务服务；未重新运行或接受任何生成。</p></section>}
      {panel === "experimental" ? <ExperimentalWorkbench leaveGuard={styleLeave} key={`${namespace}:${s.novelId}`} novelId={s.novelId} requestedTask={(workspaceTools || taskTarget?.authority === 'planning_proposal' || taskTarget?.authority === 'simulator_run') && taskTarget?.namespace === namespace && taskTarget.novelId === s.novelId ? taskTarget : undefined} chapter={chapter.data} context={{sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}} flags={experimentalFlags.data} onNavigate={navigateWorkspace} currentAnchor={saveState === "saved" && editorAnchor?.identity === editorIdentity ? editorAnchor.anchor : undefined} requestedTab={experimentalTab} workspaceSection={workspaceSection} workspaceView={{ focus_active: focusActive, references_visible: referencesVisible }} onWorkspaceViewChange={view => { if (!workspaceTools || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return; setFocusActive(view.focus_active); setReferencesVisible(view.references_visible); }} onWorkspaceSaved={() => { void lastWorkspace.refetch(); }} focusActive={focusActive} onFocusChange={setFocusActive} onPreferencesChange={preferences => { focusPreferencesTouched.current = true; setWritingPreferences(preferences); }} onReferencesChange={() => setReferenceRevision(value => value + 1)} localDraftState={chapter.data ? [{ chapter_id: chapter.data.id, chapter_version: chapter.data.version, state: saveState === 'saved' ? 'SAVED' : saveState === 'failed' ? 'SAVE_FAILED' : 'UNSAVED' }] : []} saveFailure={saveState === 'failed' || saveState === 'conflict'} currentSelection={selection} saved={saveState === 'saved'} onChapterSaved={value => {
        if (revisionStoreIdentity(useStudio.getState()) !== editorIdentity || value.id !== s.chapterId || value.novel_id !== s.novelId) return;
        qc.setQueryData<Chapter>(['chapter', namespace, value.id], current => current && current.version > value.version ? current : value);
        void qc.invalidateQueries({ queryKey: ['chapters', namespace, s.novelId] });
      }} revisionGeneration={{ enabled: experimentalFlags.data?.features['experimental.selection_assistant_v2'] === true && experimentalFlags.data?.features['experimental.author_context_inspector_v2'] === true, novelId: s.novelId, context: {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}, providerId:s.textModel?.providerId, modelId:s.textModel?.modelId, profile:s.mode }} onOpenGeneration={openExistingGeneration} onUseStyle={id => styleLeave.request(current => { if (!current()) return; if (revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return; setCharacterViewpoint(undefined); s.setWritingInputs({ ...s.writingInputs, styleProfileId: id }); setPanel('history'); })} activeCharacterId={activeCharacterId} onExitCharacter={() => setCharacterViewpoint(undefined)} onUseCharacter={characterMind ? (characterId, chapterId, sceneId) => styleLeave.request(current => { if (!current()) return; if (revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return; if (chapterId !== s.chapterId) { s.setChapter(chapterId); setShellMessage('已打开人物视角对应章节，请再次核对知识后选择人物视角。'); return; } setCharacterViewpoint({ identity: namespace, chapterId, characterId, sceneId, epoch: scopeEpoch }); setPanel('history'); }) : undefined} /> : <Panel key={`${namespace}:${s.novelId}`} type={panel} taskTarget={workspaceTools && taskTarget?.namespace === namespace && taskTarget.novelId === s.novelId ? taskTarget : undefined} storyTarget={workspaceTools && storyTarget?.namespace === namespace && storyTarget.novelId === s.novelId ? storyTarget : undefined} chapter={chapter.data} scope={scope} sessionToken={s.sessionToken} novelId={s.novelId} onOpenChapter={s.setChapter} onOpenStorySourceChapter={openStorySourceChapter}
        onOpenStudioModule={navigateStudioModule}
        pro={shellMode === 'pro' /* [HERMIA-FE-20261022 U5] */}
        onRestored={(restored) => {
          // Feed the existing hydration path. It retains drafts and creates a
          // persistent conflict when a restored server version overtakes them.
          if (revisionStoreIdentity(useStudio.getState()) !== revisionStoreIdentity(s)
              || restored.id !== s.chapterId || restored.novel_id !== s.novelId) return;
          qc.setQueryData<Chapter>(["chapter", namespace, s.chapterId], current =>
            current && current.version > restored.version ? current : restored);
          void qc.invalidateQueries({ queryKey: ["chapters", namespace, s.novelId] });
        }} />}
      </div>
      </div>
      </div>
    </div>
  );
  // [HERMIA-FE-20261022 W-P0-06] Right dock: outline / cast / AI — default expanded, no empty void.
  const outlineItems = (chapters.data || []).slice(0, 12).map(c => ({
    id: c.id,
    label: `第 ${c.number} 章 · ${c.title || '未命名'}`,
    hint: c.id === s.chapterId ? i18nT('as.currentlyWriting') : undefined, // [HERMIA-FE-20261025 VERA-FIX P2]
  }));
  const draftReady = !!(job && draftStateFromGeneration(job.status) === 'ready' && job.output);
  // [HERMIA-FE-20261022 N-UX-08] CTA state machine — adopt > continuity > continue; count is honest (error/loading → 0)
  const continuityWarningCount = countOpenContinuityWarnings(continuityFindingsQ.data);
  const ctaDecision = decideNovelPrimaryCta({
    draftReady,
    continuityWarningCount: shellMode === 'pro' ? continuityWarningCount : 0, // [HERMIA-FE-20261022 U4] 普通主按钮不跳连续性检查
    hasChapter: !!chapter.data,
  });
  const primaryCta = ctaDecision.kind === 'adopt'
    ? {label: ctaDecision.label, kind: ctaDecision.kind, onClick: () => { if (draftReady && job) void acceptGeneratedDraft(job); }, disabled: draftAction === 'accept'}
    : ctaDecision.kind === 'continuity'
      ? {label: ctaDecision.label, kind: ctaDecision.kind, onClick: () => styleLeave.request(current => { if (current()) { commitStudioModule('NOVEL'); setPanel('check'); } })}
      : ctaDecision.kind === 'continue'
        ? {label: ctaDecision.label, kind: ctaDecision.kind, onClick: () => {
            const el = document.querySelector<HTMLElement>('.app-shell[data-module="NOVEL"] .ProseMirror, .app-shell[data-module="NOVEL"] .editor');
            el?.focus?.();
            el?.scrollIntoView?.({block: 'nearest'});
          }}
        : {label: ctaDecision.label, kind: ctaDecision.kind, onClick: () => {
            document.querySelector<HTMLElement>('.workspace-sidebar--novel')?.focus?.();
          }};
  const novelSaveLocation = scope ? '保存位置：协作服务' : '保存位置：本机'; // [HERMIA-FE-20261022 REBUILD-W3]
  const inspector = (
    <NovelAssist
      // [HERMIA-FE-20261022 REBUILD-W3] 右栏按原型：当前章节 / 下一步 / 大纲 / 角色 / AI 写作
      saveLocation={novelSaveLocation}
      links={gateNovel([ // [HERMIA-FE-20261022 U4] 普通只留 生成草稿 / 大纲
        { id: 'draft', label: '生成草稿', onClick: () => { document.querySelector('.novel-writer-dock__section--ai')?.scrollIntoView({block: 'nearest'}); } },
        ...(['story-planning', 'continuity', 'pending-canon'] as NovelSecondaryEntryId[]).map(id => ({ id, label: novelSecondaryEntry(id).label, onClick: () => styleLeave.request(current => {
          if (!current()) return;
          const entry = novelSecondaryEntry(id);
          commitStudioModule('NOVEL'); setPanel(entry.panel);
          window.setTimeout(() => scrollNovelSecondaryAnchor(entry.anchor), 80);
        }) })),
        ...(chapter.data ? [{ id: 'history', label: '版本历史', onClick: () => openNovelPanel('history') }] : []),
      ], NOVEL_PRO_LINKS, shellMode)}
      onOpenStory={() => openNovelPanel('story')}
      onOpenCheck={shellMode === 'pro' ? () => openNovelPanel('check') : undefined /* [HERMIA-FE-20261022 U4] */}
      chapterTitle={chapter.data ? `第 ${chapter.data.number} 章 · ${chapter.data.title || '未命名'}` : chaptersPending ? i18nT(chaptersPending === 'error' ? 'chapter.unreadable' : 'rail.loading') : "未选择章节"}
      chapterMeta={chapter.data ? `${text.trim().length} 字 · 版本 ${chapter.data.version}` : chaptersPending ? "" : "从左侧作品结构选择或新建章节" /* [HERMIA-FE-20261025 VERA-FIX P0-3] */}
      pendingState={chaptersPending /* [HERMIA-FE-20261025 VERA-FIX P0-3] 读取中/失败时隐藏「下一步」主按钮 */}
      saveLabel={chapter.data ? saveDisplayLabel : undefined}
      primaryCta={primaryCta}
      outlineItems={outlineItems}
      castNote={activeCharacterId ? `当前人物视角：${activeCharacterId}` : undefined}
      hasChapter={!!chapter.data}
      onQuickOp={op => setAiQuickOp(prev => ({ op, nonce: (prev?.nonce || 0) + 1 }))}
      aiStatus={draftReady ? '有候选待你确认' : undefined}
      onSelectOutline={(id) => styleLeave.request(current => { if (current()) { s.setChapter(id); commitStudioModule('NOVEL'); setPanel('write'); } })}
      ai={<>
      <AiWritingPanel
      requestedOperation={aiQuickOp}
      authorPreview={chapter.data ? {
        enabled: experimentalFlags.data?.features['experimental.author_context_inspector_v2'] === true,
        chapterId: chapter.data.id, chapterVersion: chapter.data.version, source: selection.text,
        characterId: activeCharacterId, sceneId: activeSceneId, onExitCharacter: () => setCharacterViewpoint(undefined),
        profile: s.mode, styleProfileId: s.writingInputs?.styleProfileId, plotPlanId: s.writingInputs?.plotPlanId,
        context: {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}, saved: saveState === 'saved',
      } : undefined}
      novelId={s.novelId}
      chapterNumber={chapter.data?.number}
      contextTarget={s.mode === "LOCAL_ONLY" ? "local" : "cloud"}
      variants={variantDrafts}
      activeVariant={activeVariant}
      onSelectVariant={setActiveVariant}
      onGenerateVariants={runAIVariants}
      onRetry={retryDraft}
      onResolveConflict={openDraftConflict}
      packagedMode={packagedHost}
      credentialConfigured={credentialConfigured}
      onCredentialRefresh={refreshCredentialState}
      // DesktopHost is the only supported credential entry point for V1.
      // The browser helper must never persist or forward a provider secret.
      vaultMode={!packagedHost}
      onSaveVault={saveVaultCredential}
      onDeleteVault={deleteVaultCredential}
      onTestVault={testVaultCredential}
      models={textModels.data || []}
      selection={s.textModel}
      onSelectionChange={s.setTextModel}
      readiness={routeDiagnostics.data}
      readinessLoading={routeDiagnostics.isLoading}
      readinessError={!!routeDiagnostics.error}
      onOpenDiagnostics={() => styleLeave.request(current => { if (current()) setPanel("diagnostics"); })}
      generating={generationStarting || job?.status === "GENERATING"}
      cancelling={cancelGeneration.isPending || variantCancelling}
      cancelled={job?.status === "CANCELLED"}
      recovering={generationRecovering}
      accepting={draftAction === "accept"}
      rejecting={draftAction === "reject"}
      error={job?.error}
      draft={
        job && !["CANCELLED", "ACCEPTED", "REJECTED"].includes(job.status)
          ? {
              id: job.id,
              output: job.output || "",
              original: job.original,
              status: draftStateFromGeneration(job.status),
              error: job.error,
              latency_ms: job.latency_ms,
              acceptBlocked: job.acceptBlocked || ["ACCEPTING", "ACCEPTANCE_UNCERTAIN"].includes(job.status),
              acceptBlockedReason: job.acceptBlockedReason || (job.status === "ACCEPTANCE_UNCERTAIN" ? "采用结果待核对。请检查正文与待审核 Canon，不要重复采用。" : undefined),
              tracked: !["generation-failed", "selection-required"].includes(job.id),
            }
          : undefined
      }
      onGenerate={(operation: AiOperation, request, style, receipt) =>
        runAI(operation, request, style, receipt)
      }
      onCancel={cancelActiveGeneration}
      onAccept={acceptGeneratedDraft}
      onReject={rejectGeneratedDraft}
      />
      </>}
      extras={<>
      {workspaceTools && <SampleJourneyGuide novelId={s.novelId} context={{ sessionToken: s.sessionToken, scope: s.scope, actor: s.actor }} chapter={chapter.data} saved={saveState === 'saved'} onNavigate={feature => navigateWorkspace({ kind: 'feature', id: feature, feature })} />}
      <WritingGoalPanel novelId={s.novelId} />
      {chapter.data&&<SourcePrivacyControl key={`${namespace}:${chapter.data.id}`} chapter={chapter.data} context={{sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}}/>}
      {writingRecovery && chapter.data && <GenerationRecoveryPicker key={`${namespace}:${s.chapterId}:${scopeEpoch}`}
        namespace={namespace} chapterId={s.chapterId} actorId={s.actor?.id} revision={generationRecoveryRevision} includeCurrent={generationRecoveryUnverified}
        onRecover={reopenRetainedGeneration} />}
      {experimentalFlags.data?.features['experimental.revision_intelligence_v2'] === true && chapter.data && <Button disabled={!selection.text || saveState !== 'saved'} onClick={() => styleLeave.request(current => { if (current()) { setExperimentalTab('revision_intelligence_v2'); setPanel('experimental'); } })}>修订选区与逐段接受</Button>}
      </>}
    />
  );
  return (
    <>
      {moduleStartGate}
      {localTutor.dialog}
      {
        creativeWorkbenchOpen && experimentalFlags.data?.features["experimental.narrative_production_v2"] === true ? <CreativeWorkspace navigationConfirmation={styleLeave.dialog}
          enabled={true} novelId={s.novelId} context={{ sessionToken: s.sessionToken, actor: s.actor, scope: s.scope }} scope={shellScope} actor={s.actor?.displayName || "本机作者"}
          chapter={chapter.data} savedChapters={chapters.data} savedChaptersReady={chapters.isSuccess && !chapters.isFetching} onRefreshSavedChapters={() => { void chapters.refetch(); }} chapterCount={chapters.data?.length || 0} manuscriptReady={saveState === 'saved' && !composing && !savePending.current && hydratedIdentity === editorIdentity}
          novelMain={mainWorkspace} novelSidebar={sidebar} novelInspector={inspector} novelStatus={<>{i18nT("status.save", { v: tz(saveDisplayLabel) })} · {i18nT("status.conn", { v: i18nT(scope ? "status.connCloud" : "status.connLocal") })}{localTutor.entry}</>}
          commonStatus={<>{i18nT("status.conn", { v: i18nT(scope ? "status.connCloud" : "status.connLocal") })}{localTutor.entry}</>}
          onExit={approved => styleLeave.request(current => { if (current() && (!approved || approved())) setCreativeWorkbenchOpen(false); })} onModuleChange={(value, approved) => styleLeave.request(current => { if (current() && (!approved || approved())) { setCreativeWorkbenchOpen(false); commitStudioModule(value); } })} onGlobalSearch={openWorkspaceSearch}
        /> : <AppShell
          module={studioModule}
          onModuleChange={navigateStudioModule}
          scope={shellScope}
          projectNoun={neutralStudio ? '项目' : undefined}
          actor={s.actor?.displayName || "本机作者"}
          onGlobalSearch={openWorkspaceSearch}
          focusMode={writingFocus && focusActive}
          onExitFocus={() => setFocusActive(false)}
          shellMode={shellMode}
          onShellModeChange={applyShellMode}
          writingContext={{
            // [HERMIA-FE-20261022 N-UX-08] Author book title; empty → ContextBar「未命名小说」
            bookTitle: novels.data?.find((n) => n.id === s.novelId)?.title?.trim() || undefined,
            chapterLabel: chapter.data ? `第 ${chapter.data.number} 章 · ${chapter.data.title || '未命名'}` : undefined,
            saveLabel: chapter.data ? saveDisplayLabel : undefined,
            onOpenOverview: () => styleLeave.request(current => { if (current()) { commitStudioModule('NOVEL'); setPanel('overview'); } }),
            // [HERMIA-FE-20261022 N-UX-09] Sink primary CTA to ContextBar when right dock width → 0
            collapsedCta: { label: primaryCta.label, kind: primaryCta.kind, onClick: primaryCta.onClick, disabled: primaryCta.disabled },
            // [HERMIA-FE-20261022 REBUILD-W3] 上下文条：保存位置 + 任务 / 候选 / 审核（打开一致性与待审设定）
            saveLocation: novelSaveLocation,
            onOpenReview: () => openNovelPanel('check'),
            reviewCount: continuityWarningCount || undefined,
          }}
          sidebarClassName="workspace-sidebar--novel"
          sidebar={sidebar}
          banner={studioModule === 'NOVEL' ? <NovelOrient
            what={novels.data?.find(n => n.id === s.novelId)?.title ? `《${novels.data?.find(n => n.id === s.novelId)?.title}》${chapter.data ? ` · 第 ${chapter.data.number} 章 · ${chapter.data.title || '未命名'}` : ''}` : '还没有打开作品'}
            can="写作台改章 · AI 生成先成候选、你采用后才进正文 · 设定需审核才进正典"
            effect={`${novelSaveLocation.replace('保存位置：', '自动保存到')}；采用候选不会覆盖已批准设定`}
          /> : undefined}
          main={mainWorkspace}
          inspector={inspector}
          status={
            <>
              {i18nT("status.save", { v: tz(saveDisplayLabel) })} · {i18nT("status.conn", { v: i18nT(scope ? "status.connCloud" : "status.connLocal") })}
              {` · ${i18nT("status.ai", { v: i18nT(taskSummary.total ? (taskSummary.running ? "status.aiRunning" : taskSummary.failed ? "status.aiFailed" : taskSummary.succeeded ? "status.aiDone" : "status.aiQueued") : "status.aiNone") })}`}
              {shellMessage ? ` · ${shellMessage}` : ""}
              {lastPosStatus(s.novelId, lastPositionMode, bootstrap.isError, i18nT)}
              {localTutor.entry}
              {/* [HERMIA-FE-20261025 UWPORT-S2] tasks/results/history drawer (port of the unified loop) */}
              {s.novelId ? <>{" "}<DefaultTasksDrawer key={`${namespace}|${s.novelId}`} novelId={s.novelId} actor={s.actor} scope={s.scope} sessionToken={s.sessionToken} /></> : null}
            </>
          }
        />
      }{" "}
      {conflict && !composing && (
        <ConflictDialog
          key={`${namespace}:${conflict.chapterId}:${conflict.detectedAt}`}
          value={conflict}
          namespace={namespace}
          onClose={() => setConflict(undefined)}
          onResolutionDraft={(resolution) => {
            const next = {
              chapterId: conflict.chapterId,
              content: resolution.content,
              document: undefined,
              baseVersion: resolution.serverVersion,
              updatedAt: resolution.updatedAt,
            };
            setDurability(drafts.save(next, namespace).durability);
            // An explicit merge resolves this comparison, not the pending save.
            // Retain the old candidates in history, and synchronize the already
            // reviewed server base so a delayed query cannot reopen it.
            conflicts.resolve(conflict.chapterId, namespace);
            qc.setQueryData<Chapter>(['chapter', namespace, conflict.chapterId], current =>
              !current || current.version > conflict.server.version ? current : { ...current, content: conflict.server.content, document: conflict.server.document, version: conflict.server.version });
            buffer.current = { identity: editorIdentity, value: next };
            setText(next.content);
            setDoc(next.document);
            setBaseVersion(next.baseVersion);
            setConflict(undefined);
            setSaveState((current) =>
              reduceSaveState(current, { type: "edit" }),
            );
          }}
          onUseServer={() => {
            setText(conflict.server.content);
            setDoc(conflict.server.document);
            setBaseVersion(conflict.server.version);
            buffer.current = { identity: editorIdentity, value: {
              chapterId: conflict.chapterId, content: conflict.server.content, document: conflict.server.document,
              baseVersion: conflict.server.version, updatedAt: new Date().toISOString(),
            } };
            setDurability('none');
            drafts.remove(conflict.chapterId, namespace);
            conflicts.remove(conflict.chapterId, namespace);
            conflictResolutionDrafts.remove(conflict.chapterId, namespace);
            setConflict(undefined);
            setSaveState((current) =>
              reduceSaveState(current, {
                type: "hydrate",
                hasDraft: false,
                hasConflict: false,
              }),
            );
          }}
        />
      )}
    </>
  );
}
function WritingGoalPanel({ novelId }: { novelId: string }) {
  const qc = useQueryClient();
  const goal = useQuery({ queryKey: ["writing-goal", novelId], queryFn: () => api.writingGoal(novelId), enabled: !!novelId });
  const [targetWords, setTargetWords] = useState(100000);
  const [targetChapters, setTargetChapters] = useState(50);
  const [deadline, setDeadline] = useState("");
  useEffect(() => { if (goal.data) { setTargetWords(goal.data.target_words); setTargetChapters(goal.data.target_chapters); setDeadline(goal.data.deadline || ""); } }, [goal.data]);
  const save = useMutation({ mutationFn: () => api.updateWritingGoal(novelId, { target_words: targetWords, target_chapters: targetChapters, deadline: deadline || undefined }), onSuccess: () => qc.invalidateQueries({ queryKey: ["writing-goal", novelId] }) });
  if (goal.isLoading) return <section className="panel"><p>正在加载写作目标…</p></section>;
  return <section className="panel writing-goal-panel"><h2>项目概览</h2><p>设置本小说的创作目标，进度会同步显示在编辑器顶部。</p><label>目标字数<input type="number" min={1} value={targetWords} onChange={(e) => setTargetWords(Number(e.target.value))} /></label><label>目标章节<input type="number" min={1} value={targetChapters} onChange={(e) => setTargetChapters(Number(e.target.value))} /></label><label>截止日期<input type="date" value={deadline ? deadline.slice(0, 10) : ""} onChange={(e) => setDeadline(e.target.value)} /></label><button className="primary" disabled={save.isPending || targetWords < 1 || targetChapters < 1} onClick={() => save.mutate()}>{save.isPending ? "保存中…" : "保存写作目标"}</button>{save.isSuccess && <small className="notice">目标已更新</small>}{save.error && <small className="notice">保存失败，请重试</small>}</section>;
}
function VideoProviderSettings(){const [provider,setProvider]=useState('custom');const [endpoint,setEndpoint]=useState('');const [model,setModel]=useState('');const [enabled,setEnabled]=useState(true);const [message,setMessage]=useState('');const [health,setHealth]=useState<any>();async function save(){await api.configureVideoProvider(provider,{endpoint,model_id:model||'video-model',enabled});setMessage('Provider 配置已保存');setHealth(await api.videoProviderHealth(provider))}return <section className="panel"><h2>视频 Provider 设置</h2><label>Provider ID<input value={provider} onChange={e=>setProvider(e.target.value)}/></label><label>Endpoint<input value={endpoint} onChange={e=>setEndpoint(e.target.value)} placeholder="https://…"/></label><label>Model<input value={model} onChange={e=>setModel(e.target.value)} placeholder="video-model"/></label><label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>启用 Provider</label><button className="primary" onClick={save}>保存并检查</button>{message&&<p className="notice">{message}</p>}{health&&<p className="notice">状态：{health.health}</p>}</section>}
function VideoProviderSettingsV2(){
 const [provider,setProvider]=useState('custom'); const [endpoint,setEndpoint]=useState(''); const [model,setModel]=useState(''); const [enabled,setEnabled]=useState(true); const [message,setMessage]=useState(''); const [health,setHealth]=useState<any>();
 useEffect(()=>{api.videoProviderConfig('custom').then(config=>{setEndpoint(config.endpoint||'');setModel(config.model_id||'');setEnabled(config.enabled!==false)}).catch(()=>{})},[]);
 async function save(){await api.configureVideoProvider(provider,{endpoint,model_id:model||'video-model',enabled});setMessage('Provider 配置已保存');setHealth(await api.videoProviderHealth(provider));}
 return <section className="panel"><h2>视频 Provider 设置</h2><label>Provider ID<input value={provider} onChange={e=>setProvider(e.target.value)}/></label><label>Endpoint<input value={endpoint} onChange={e=>setEndpoint(e.target.value)} placeholder="https://…"/></label><label>Model<input value={model} onChange={e=>setModel(e.target.value)} placeholder="video-model"/></label><label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>启用 Provider</label><button className="primary" onClick={save}>保存并检查</button>{message&&<p className="notice">{message}</p>}{health&&<p className="notice">状态：{health.health}</p>}</section>;
}
function VideoCallbackSecurityStatus(){const [status,setStatus]=useState<any>();useEffect(()=>{api.videoCallbackSecurity().then(setStatus).catch(()=>{})},[]);return status?<p className="notice">回调令牌：{status.configured?'已配置':'未配置'} · 请求头：{status.header}</p>:<p className="notice">正在检查回调安全状态…</p>}
type StorySearchTarget = { requestId: number; id: string; record_kind: NonNullable<WorkspaceNavigation['record_kind']> };
function Panel({
  type,
  storyTarget,
  taskTarget,
  chapter,
  scope,
  sessionToken,
  novelId,
  onOpenChapter,
  onOpenStorySourceChapter,
  onRestored,
  onOpenStudioModule,
  pro = true,
}: {
  /** [HERMIA-FE-20261022 U5] 普通模式隐藏专业检查 */
  pro?: boolean;
  type: string;
  storyTarget?: StorySearchTarget;
  taskTarget?: { id: string; authority?: string; parent_id?: string; version?: number };
  chapter?: Chapter;
  scope?: Scope;
  novelId: string;
  onOpenChapter: (id:string)=>void;
  onOpenStorySourceChapter: (id:string, signal?:AbortSignal)=>void;
  onRestored: (chapter: Chapter) => void;
  sessionToken: string;
  /** [HERMIA-FE-20261022 X-UX-09] settings gateway → CONTROL/PLUGIN */
  onOpenStudioModule?: (module: StudioModule) => void;
}) {
  const queryClient = useQueryClient();
  if (!scope && ["members", "permissions", "audit", "snapshots"].includes(type))
    return (
      <section className="panel">
        <h2>团队协作</h2>
        <p className="notice">进入团队创作空间后可查看成员、权限和协作记录。</p>
      </section>
    );
  // [HERMIA-FE-20261022 N-P0-02 / W-P0-06] Editor-first; next-step CTA lives in right dock (Lumen §4.4). No media in novel center.
  // [HERMIA-FE-20261022 REBUILD-W3] 写作台本身就是中栏正文，不再显示说明卡
  if (type === "write") return null;
  if (type === "history")
    return chapter ? <RevisionHistory chapter={chapter} scope={scope} sessionToken={sessionToken} onRestored={onRestored} /> : null;
  if (type === "story" && taskTarget?.authority === "world_rule") return <WorldRulesPanel novelId={novelId} requestedRuleId={taskTarget.id} />;
  if (type === "story")
    return novelId ? (
      <StoryDatabasePanel key={`${novelId}:${scope?.branchId || 'local'}`} novelId={novelId} pro={pro} chapter={chapter} scope={scope} target={storyTarget} onOpenChapter={onOpenChapter} onOpenStorySourceChapter={onOpenStorySourceChapter} />
    ) : (
      <section className="panel" data-novel-path="story-world">
        <h2>故事资料库</h2>
        <p className="notice">
          {/* [HERMIA-FE-20261022 N-UX-10] */}
          请先打开一部小说，再查看人物、世界观设定和大纲。
        </p>
      </section>
    );
  if (type === "workflow" && taskTarget?.authority === "workflow_definition") return <WorkflowPanel novelId={novelId} requestedWorkflowId={taskTarget.id} />;
  if (type === "workflow") return taskTarget?.authority === 'workflows' ? <WorkflowPanel novelId={novelId} requestedRunId={taskTarget.id} requestedWorkflowId={taskTarget.parent_id} /> : <VisualWorkflowPanel scope={scope} />;
  if (type === 'audiobook') return <AudiobookManifestPanel novelId={novelId} requestedTaskId={taskTarget?.authority === 'audio_tts' ? taskTarget.id : undefined} />;
  if (type === "overview") return <NovelOverviewPanel novelId={novelId} />;
  if (type === "check") return <ContinuityCheckPanel projectId={novelId} chapter={chapter} />;
  if (type === "diagnostics") return <RuntimeDiagnosticsPanel scope={scope} />;
  if (type === "agents") return <>{chapter&&<AgentActivityCenter novelId={chapter.novel_id} />}{chapter&&<AgentJobHistory novelId={chapter.novel_id} requestedTaskId={taskTarget?.authority === 'agents' ? taskTarget.id : undefined} />}<AgentTeamPanel chapter={chapter} /></>;
  if (type === "adaptation") return <AdaptationPanel novelId={novelId} branchId={scope?.branchId} requestedProposalId={taskTarget?.authority === "adaptation" ? taskTarget.parent_id : undefined} requestedTaskId={taskTarget?.authority === "adaptation" ? taskTarget.id : undefined} requestedRevision={taskTarget?.authority === "adaptation" ? taskTarget.version : undefined} />;
  if (type === "screenplay" && taskTarget?.authority === 'motion' && taskTarget.parent_id) return <MotionTaskWorkspace key={`${novelId}:${taskTarget.parent_id}:${taskTarget.id}`} novelId={novelId} screenplayId={taskTarget.parent_id} taskIds={[taskTarget.id]} />;
  if (type === "screenplay") return <ScreenplayPanel novelId={chapter?.novel_id} scope={scope||null} sessionToken={sessionToken} />;
  if (type === "assets" && taskTarget?.authority === 'images') return <ImageQueuePanel novelId={novelId} requestedTaskId={taskTarget.id} draft={{ provider_id: '', model_id: '', prompt: '' }} />;
  if (type === "assets") return <AssetLibraryPanel novelId={novelId} requestedAssetId={taskTarget?.authority === "asset_record" ? taskTarget.id : undefined} />;
  if (type === "exports") return <ExportPanel requestedTaskId={taskTarget?.authority === 'exports' ? taskTarget.id : undefined} novelId={chapter?.novel_id || useStudio.getState().novelId || ""} scope={scope||null} sessionToken={sessionToken} />;
  if (type === "knowledge") return <NovelImportPanel key={`${novelId}:${scope?.branchId||"local"}:${sessionToken}`} requestContext={{sessionToken,scope}} novelId={chapter?.novel_id || useStudio.getState().novelId || ""} chapterId={chapter?.id} />;
  if (type === "creation" || type === "comments") return <CreationWorkbenchPanel key={`${novelId}:${scope?.branchId||"local"}:${sessionToken}`} novelId={novelId} chapter={chapter} initialComments={type === "comments"} context={{sessionToken,scope}} onPlanningApplied={() => { for (const queryKey of [["novel-detail",novelId],["novel-outline",novelId],["story-database"],["world-rules",novelId],["ai-context-preview"],["ai-context-preview-world-rules"],["ai-context-preview-canon"]]) void queryClient.invalidateQueries({queryKey}); }} />;
  if (type === "research") return <ResearchPanel novelId={novelId} />;
  if (type === "settings") return (
    <SettingsPathGateway onOpenModule={onOpenStudioModule}>
      <AiControlCenter />
      <MediaProviderSettings />
      <VideoCallbackSecurityStatus />
    </SettingsPathGateway>
  );
  if (type === "roadmap") return <CapabilityRoadmapPanel />;
  return (
    <CollaborationPanel type={type} scope={scope} chapterId={chapter?.id} />
  );
}
function VisualWorkflowPanel({ scope }: { scope?: Scope }) {
  const selected = useStudio((value) => value.textModel);
  const models = useQuery({
    queryKey: ["text-models"],
    queryFn: api.textModels,
    retry: false,
  });
  const providerId = selected?.providerId,
    modelId = selected?.modelId;
  const query = useQuery({
    queryKey: ["visual-text-workflow", scope, providerId, modelId],
    queryFn: () => api.visualTextWorkflow(scope!, providerId!, modelId!),
    enabled: !!scope && !!providerId && !!modelId,
    retry: false,
  });
  if (!scope) return <VisualTextWorkflow error="协作工作区尚未连接" />;
  return (
    <VisualTextWorkflow
      workflow={query.data}
      loading={models.isLoading || query.isLoading}
      unauthorized={
        query.error instanceof ApiError && query.error.status === 403
      }
      error={query.error ? String(query.error) : null}
    />
  );
}
function RuntimeDiagnosticsPanel({ scope }: { scope?: Scope }) {
  const selected = useStudio((value) => value.textModel),
    providerId = selected?.providerId,
    modelId = selected?.modelId;
  const query = useQuery({
    queryKey: ["text-runtime-diagnostics", scope, providerId, modelId],
    queryFn: () => api.textRuntimeDiagnostics(scope!, providerId!, modelId!),
    enabled: !!scope && !!providerId && !!modelId,
    retry: false,
  });
  if (!scope) return <RuntimeDiagnostics error="协作工作区尚未连接" />;
  return (
    <RuntimeDiagnostics
      diagnostics={query.data}
      loading={query.isLoading}
      unauthorized={
        query.error instanceof ApiError && query.error.status === 403
      }
      error={query.error ? String(query.error) : null}
    />
  );
}
export function StoryDatabasePanel({
  pro = true,
  chapter,
  novelId,
  target,
  scope,
  onOpenChapter,
  onOpenStorySourceChapter,
}: {
  pro?: boolean;
  chapter?: Chapter;
  novelId?: string;
  target?: StorySearchTarget;
  scope?: Scope;
  onOpenChapter:(id:string)=>void;
  onOpenStorySourceChapter?:(id:string, signal?:AbortSignal)=>void;
}) {
  const queryClient=useQueryClient();
  const storyNovelId=novelId||chapter?.novel_id||scope?.projectId||'';
  const [kind, setKind] = useState<StoryDatabaseKind>("characters");
  const [selectedCharacter,setSelectedCharacter]=useState<Partial<CharacterDraft>>();
  const [selectedLocation,setSelectedLocation]=useState<Partial<LocationDraft>>();
  const [selectedTimeline,setSelectedTimeline]=useState<Partial<TimelineDraft>>();
  const [selectedForeshadowing,setSelectedForeshadowing]=useState<Partial<ForeshadowingDraft>>();
  const [selectedRelationship,setSelectedRelationship]=useState<Partial<RelationshipDraft>>();
  const [selectedVolume,setSelectedVolume]=useState<Partial<VolumeDraft>>();
  const [selectedScene,setSelectedScene]=useState<Partial<SceneDraft>>();
  const [selectedStoryRoute,setSelectedStoryRoute]=useState<Partial<StoryRouteDraft>>();
  const novel=useQuery({queryKey:["novel-detail",storyNovelId],queryFn:()=>api.novel(storyNovelId),enabled:!scope});
  const outline=useQuery({queryKey:["novel-outline",storyNovelId],queryFn:()=>api.outline(storyNovelId),enabled:!scope});
  const storyChapters=useQuery({queryKey:["story-chapters",storyNovelId],queryFn:()=>api.chapters(storyNovelId),enabled:!scope});
  const saveWorld=useMutation({mutationFn:(value:string)=>api.updateNovel(storyNovelId,{world_summary:value}),onSuccess:(value)=>queryClient.setQueryData(["novel-detail",storyNovelId],value)});
  const saveOutline=useMutation({mutationFn:(value:OutlineDraft)=>api.updateOutline(storyNovelId,value),onSuccess:(value)=>queryClient.setQueryData(["novel-outline",storyNovelId],value)});
    const resources = [
      "characters",
      "canon",
    "locations",
    "timeline",
    "foreshadowing",
    "relationships",
    "volumes",
    "scenes",
    "story_routes",
  ] as const;
  const queries = useQueries({
    queries: resources.map((resource) => ({
      queryKey: ["story-database", scope, storyNovelId, resource],
      queryFn: async () =>
        scope
          ? (await api.storyDatabase(scope, resource)).items
          : resource==='story_routes'?api.storyRoutes(storyNovelId):api.resource(storyNovelId, resource),
    })),
  });
  const [targetState, setTargetState] = useState('');
  const targetNavigationEpoch = useRef(0);
  useEffect(() => {
    if (!target) { setTargetState(''); return; }
    const mappings = { character: ['characters', 0], location: ['locations', 2], timeline: ['timeline', 3], foreshadowing: ['foreshadowing', 4], volume: ['volumes', 6], scene: ['scenes', 7] } as const;
    const mapping = mappings[target.record_kind];
    if (!mapping) return;
    let active = true; const ticket = ++targetNavigationEpoch.current;
    setTargetState('正在核对搜索来源…');
    // Always reread the original owner; a warmed list is not a navigation receipt.
    void queries[mapping[1]].refetch().then(result => {
      if (!active || ticket !== targetNavigationEpoch.current) return;
      const row = !result.error && ((result.data || []) as any[]).find(item => String(item.id) === target.id && !item.is_archived && !item.hidden && !item.secret);
      if (!row) { setTargetState('该搜索来源当前不可读或已移除，请返回搜索刷新结果。'); return; }
      setKind(mapping[0]);
      const select = { character: setSelectedCharacter, location: setSelectedLocation, timeline: setSelectedTimeline, foreshadowing: setSelectedForeshadowing, volume: setSelectedVolume, scene: setSelectedScene };
      select[target.record_kind](row);
      setTargetState(`已定位当前记录：${String(row.name || row.title || target.id)}。未更改资料。`);
    }).catch(() => { if (active && ticket === targetNavigationEpoch.current) setTargetState('来源核对失败，请返回搜索刷新结果。'); });
    return () => { active = false; };
  }, [target?.requestId, target?.id, target?.record_kind, storyNovelId, scope?.branchId]);
  const saveCharacter=useMutation({mutationFn:(value:CharacterDraft)=>api.upsertCharacter(storyNovelId,value.id,value),onSuccess:()=>{setSelectedCharacter(undefined);return queries[0].refetch();}});
  const saveLocation=useMutation({mutationFn:(value:LocationDraft)=>api.upsertLocation(storyNovelId,value.id,value),onSuccess:()=>{setSelectedLocation(undefined);return queries[2].refetch();}});
  const saveTimeline=useMutation({mutationFn:(value:TimelineDraft)=>api.upsertTimelineEvent(storyNovelId,value.id,value),onSuccess:()=>{setSelectedTimeline(undefined);return queries[3].refetch();}});
  const saveForeshadowing=useMutation({mutationFn:(value:ForeshadowingDraft)=>api.upsertForeshadowing(storyNovelId,value.id,value),onSuccess:()=>{setSelectedForeshadowing(undefined);return queries[4].refetch();}});
  const saveRelationship=useMutation({mutationFn:(value:RelationshipDraft)=>api.upsertRelationship(storyNovelId,value.id,value),onSuccess:()=>{setSelectedRelationship(undefined);return queries[5].refetch();}});
  const saveVolume=useMutation({mutationFn:(value:VolumeDraft)=>api.upsertVolume(storyNovelId,value.id,value),onSuccess:()=>{setSelectedVolume(undefined);return queries[6].refetch();}});
  const saveScene=useMutation({mutationFn:(value:SceneDraft)=>api.upsertScene(storyNovelId,value.id,value),onSuccess:()=>{setSelectedScene(undefined);return queries[7].refetch();}});
  const saveStoryRoute=useMutation({mutationFn:(value:StoryRouteDraft)=>api.upsertStoryRoute(storyNovelId,value.id,value),onSuccess:()=>{setSelectedStoryRoute(undefined);return queries[8].refetch();}});
  const kinds: StoryDatabaseKind[] = [
    "outline",
    "volumes",
    "scenes",
    "story_routes",
    "characters",
    "world",
    "locations",
    "timeline",
    "foreshadowing",
    "relationships",
  ];
  const sections = kinds.map((sectionKind) => {const resourceIndex=sectionKind==='outline'?-1:(["characters","world","locations","timeline","foreshadowing","relationships","volumes","scenes","story_routes"] as StoryDatabaseKind[]).indexOf(sectionKind);return ({
    kind: sectionKind,
    availability: (sectionKind === "world" ? "partial" : "available") as
      "partial" | "available",
    loading: sectionKind==='outline'?outline.isLoading:queries[resourceIndex].isLoading,
    error: sectionKind==='outline'?(outline.error?String(outline.error):null):(queries[resourceIndex].error ? String(queries[resourceIndex].error) : null),
    records: sectionKind==='outline'?[]:((queries[resourceIndex].data || []) as any[]).map((row, index) => ({
      id: String(row.id || index),
      title: String(
        row.name || row.title || row.fact_type || row.event || "未命名记录",
      ),
      summary: String(
        row.summary || row.description || row.fact || row.content || "",
      ),
      status: row.status ? String(row.status) : undefined,
    })),
  })});
    return (
      <>
        {/* [HERMIA-FE-20261022 N-UX-10] novel 设定/World* — not storyboard BibleWorkspace */}
        <p className="notice" role="note" data-novel-path="story-world">
          小说设定与世界观（FL <strong>story</strong> · World* / 规划 / 角色）。分镜侧 Bible 契约面不在此路径；勿从 VIDEO/分镜入口找小说设定。
        </p>
        {targetState && <p className="notice" role="status">{targetState}</p>}
        <StoryPlanningWorkspace
          novelTitle={novel.data?.title||"当前小说"}
          outline={(outline.data||{}) as any}
          volumes={(queries[6].data||[]) as any[]}
          chapters={(storyChapters.data||[]) as any[]}
          scenes={(queries[7].data||[]) as any[]}
          timeline={(queries[3].data||[]) as any[]}
          foreshadowing={(queries[4].data||[]) as any[]}
          loading={[outline,storyChapters,queries[3],queries[4],queries[6],queries[7]].some(item=>item.isLoading)}
          error={[outline,storyChapters,queries[3],queries[4],queries[6],queries[7]].some(item=>item.error)?"故事规划读取失败，请检查连接后重试。":undefined}
          onOpen={(targetKind,id)=>{targetNavigationEpoch.current++;setKind(targetKind);if(id&&targetKind==='volumes')setSelectedVolume(((queries[6].data||[]) as any[]).find(item=>String(item.id)===id));if(id&&targetKind==='scenes')setSelectedScene(((queries[7].data||[]) as any[]).find(item=>String(item.id)===id));}}
          onOpenChapter={onOpenChapter}
        />
        <WorldBuildingDashboard
          characters={(queries[0].data || []) as any[]}
          locations={(queries[2].data || []) as any[]}
          timeline={(queries[3].data || []) as any[]}
          foreshadowing={(queries[4].data || []) as any[]}
          relationships={(queries[5].data || []) as any[]}
          loading={[queries[0],queries[2],queries[3],queries[4],queries[5]].some(item=>item.isLoading)}
          errors={{relationships:queries[5].error?"人物关系读取失败":undefined,timeline:queries[3].error?"时间线读取失败":undefined,foreshadowing:queries[4].error?"伏笔读取失败":undefined}}
          onOpen={(targetKind,id)=>{targetNavigationEpoch.current++;setKind(targetKind);if(id){if(targetKind==='relationships')setSelectedRelationship(((queries[5].data||[]) as any[]).find(item=>String(item.id)===id));if(targetKind==='timeline')setSelectedTimeline(((queries[3].data||[]) as any[]).find(item=>String(item.id)===id));if(targetKind==='foreshadowing')setSelectedForeshadowing(((queries[4].data||[]) as any[]).find(item=>String(item.id)===id));}}}
        />
        <StoryDatabase sections={sections} activeKind={kind} onSelectKind={value=>{targetNavigationEpoch.current++;setKind(value)}} onSelectRecord={(selectedKind,id)=>{targetNavigationEpoch.current++;if(selectedKind==='characters'){const row=((queries[0].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedCharacter(row);}if(selectedKind==='locations'){const row=((queries[2].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedLocation(row);}if(selectedKind==='timeline'){const row=((queries[3].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedTimeline(row);}if(selectedKind==='foreshadowing'){const row=((queries[4].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedForeshadowing(row);}if(selectedKind==='relationships'){const row=((queries[5].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedRelationship(row);}if(selectedKind==='volumes'){const row=((queries[6].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedVolume(row);}if(selectedKind==='scenes'){const row=((queries[7].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedScene(row);}if(selectedKind==='story_routes'){const row=((queries[8].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedStoryRoute(row);}}}/>
        {kind==="outline"&&!scope&&<OutlineEditor value={outline.data} saving={saveOutline.isPending} onSave={async(value)=>{await saveOutline.mutateAsync(value);}}/>}
        {kind==="volumes"&&!scope&&<VolumeEditor value={selectedVolume} saving={saveVolume.isPending} onSave={async(value)=>{await saveVolume.mutateAsync(value);}}/>}
        {kind==="scenes"&&!scope&&<>
          <SceneEditor value={selectedScene} volumes={((queries[6].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} chapters={(storyChapters.data||[]).map(row=>({id:row.id,title:row.title}))} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} saving={saveScene.isPending} onSave={async(value)=>{await saveScene.mutateAsync(value);}}/>
          {selectedScene?.id&&<EntityAssetPanel novelId={storyNovelId} sceneId={String(selectedScene.id)}/>}
          {selectedScene?.id&&<VisionAnalysisPanel novelId={storyNovelId} sceneId={String(selectedScene.id)}/>}
        </>}
        {kind==="story_routes"&&!scope&&<StoryRouteEditor value={selectedStoryRoute} routes={((queries[8].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveStoryRoute.isPending} onSave={async(value)=>{await saveStoryRoute.mutateAsync(value);}}/>}
        {kind==="characters"&&!scope&&<>
          <CharacterEditor novelId={storyNovelId} value={selectedCharacter} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} saving={saveCharacter.isPending} onSave={async(value)=>{await saveCharacter.mutateAsync(value);}}/>
          <CharacterEvolutionPanel novelId={storyNovelId} characterId={selectedCharacter?.id as string|undefined} characterName={selectedCharacter?.name as string|undefined}/>
          {pro&&chapter&&<CharacterConsistencyPanel novelId={storyNovelId} draft={chapter.content||''} chapter={chapter.number} characters={(queries[0].data||[]) as any[]}/>}
          {selectedCharacter?.id&&<EntityAssetPanel novelId={storyNovelId} characterId={String(selectedCharacter.id)}/>}
          {selectedCharacter?.id&&<VisionAnalysisPanel novelId={storyNovelId} characterId={String(selectedCharacter.id)}/>}
          {selectedCharacter?.id&&<SpeechSynthesisPanel novelId={storyNovelId} characterId={String(selectedCharacter.id)}/>}
        </>}
        {kind==="locations"&&!scope&&<LocationEditor novelId={storyNovelId} value={selectedLocation} saving={saveLocation.isPending} onSave={async(value)=>{await saveLocation.mutateAsync(value);}}/>}
        {kind==="timeline"&&!scope&&<TimelineEditor novelId={storyNovelId} onOpenChapter={onOpenStorySourceChapter} value={selectedTimeline} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} chapters={(storyChapters.data||[]).map(row=>({id:row.id,title:row.title}))} saving={saveTimeline.isPending} onSave={async(value)=>{await saveTimeline.mutateAsync(value);}}/>}
        {kind==="foreshadowing"&&!scope&&<>{chapter&&<ForeshadowingTrackerPanel novelId={storyNovelId} records={(queries[4].data||[]) as any[]} currentChapter={chapter.number}/>}<ForeshadowingEditor novelId={storyNovelId} onOpenChapter={onOpenStorySourceChapter} value={selectedForeshadowing} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} events={((queries[3].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveForeshadowing.isPending} onSave={async(value)=>{await saveForeshadowing.mutateAsync(value);}}/></>}
        {kind==="relationships"&&!scope&&<RelationshipEditor novelId={storyNovelId} value={selectedRelationship} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} events={((queries[3].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveRelationship.isPending} onSave={async(value)=>{await saveRelationship.mutateAsync(value);}}/>}
        {kind==="world"&&!scope&&<><WorldSummaryEditor value={novel.data?.world_summary??novel.data?.long_term_summary??""} saving={saveWorld.isPending} onSave={async(value)=>{await saveWorld.mutateAsync(value);}}/><WorldRulesPanel novelId={novel.data?.id || ""}/></>}
      </>
    );
}
let revisionObserverSequence = 0;
function revisionStoreIdentity(state: Pick<ReturnType<typeof useStudio.getState>, "sessionToken" | "actor" | "scope" | "novelId" | "chapterId">) {
  return JSON.stringify([state.sessionToken, state.actor?.id, state.actor?.workspaceId,
    state.novelId, state.chapterId, state.scope?.workspaceId, state.scope?.projectId,
    state.scope?.storylineId, state.scope?.branchId]);
}

type RevisionHistoryProps = {
  chapter: Chapter;
  scope?: Scope;
  sessionToken: string;
  onRestored: (chapter: Chapter) => void;
};

export function RevisionHistory(props: RevisionHistoryProps) {
  const storeIdentity = useStudio(revisionStoreIdentity);
  const actor = useStudio(state => state.actor);
  const [scopeEpoch, setScopeEpoch] = useState(0);
  useLayoutEffect(() => {
    let observed = revisionStoreIdentity(useStudio.getState());
    return useStudio.subscribe(state => {
      const next = revisionStoreIdentity(state);
      if (next !== observed) { observed = next; setScopeEpoch(value => value + 1); }
    });
  }, []);
  // Identity comparisons remain in memory. Only this opaque observer ID enters
  // React Query keys, so neither cache keys nor dehydrated caches contain tokens.
  const identity = JSON.stringify([storeIdentity, scopeEpoch, props.chapter.novel_id, props.chapter.id,
    props.sessionToken, props.scope?.workspaceId, props.scope?.projectId,
    props.scope?.storylineId, props.scope?.branchId]);
  const observer = useRef<{ identity: string; id: string }>();
  if (!observer.current || observer.current.identity !== identity) observer.current = {
    identity,
    id: globalThis.crypto?.randomUUID?.() || `revision-${Date.now()}-${++revisionObserverSequence}-${Math.random()}`,
  };
  const context: CollaborationContext = {
    sessionToken: props.sessionToken,
    actor: actor && { ...actor },
    scope: props.scope && { ...props.scope },
  };
  return <ScopedRevisionHistory key={observer.current.id} {...props}
    context={context} observerId={observer.current.id} storeIdentity={storeIdentity} />;
}

function ScopedRevisionHistory({ chapter, scope, onRestored, context, observerId, storeIdentity }:
  RevisionHistoryProps & { context: CollaborationContext; observerId: string; storeIdentity: string }) {
  const [selected, setSelected] = useState<number>();
  const epoch = useRef(0);
  const mounted = useRef(true);
  const restorePending = useRef(false);
  const restoreLife = useRef(new LifecycleTracker()); // [HERMIA-FE-20261022 H-P0-02]
  useLayoutEffect(() => {
    mounted.current = true;
    let observed = revisionStoreIdentity(useStudio.getState());
    // Invalidates even an A→B→A change batched into one React render.
    const unsubscribe = useStudio.subscribe(state => {
      const next = revisionStoreIdentity(state);
      if (next !== observed) { observed = next; epoch.current += 1; restoreLife.current.invalidate(); }
    });
    // StrictMode replays setup/cleanup while React Query reuses its pending
    // promise. Only identity changes advance the authority epoch; a genuine
    // unmount is fenced by this observer's permanently inactive mounted ref.
    return () => { mounted.current = false; unsubscribe(); };
  }, []);
  const current = (ticket: number) => mounted.current && ticket === epoch.current
    && revisionStoreIdentity(useStudio.getState()) === storeIdentity;
  const q = useQuery({
    queryKey: ["revision-history", observerId, chapter.id, chapter.version],
    gcTime: 0,
    queryFn: async () => {
      const ticket = epoch.current;
      try {
        const rows = scope ? await api.history(scope, chapter.id, context) : await api.legacyHistory(chapter.id, context);
        return current(ticket) ? rows : [];
      } catch (error) {
        if (!current(ticket)) return [];
        throw error;
      }
    },
  });
  const detail = useQuery({
    queryKey: ["revision-detail", observerId, chapter.id, selected],
    gcTime: 0,
    queryFn: async () => {
      const ticket = epoch.current;
      try {
        const row = await api.revisionDetail(scope!, chapter.id, selected!, context);
        return current(ticket) ? row : null;
      } catch (error) {
        if (!current(ticket)) return null;
        throw error;
      }
    },
    enabled: !!scope && selected !== undefined,
  });
  const preview: any = scope
    ? detail.data
    : q.data?.find((x) => x.version === selected);
  const revisions = (q.data || []).map((v) => ({
    version: v.version,
    createdAt: v.timestamp || v.created_at || "",
    actorLabel: v.operator || v.actor_id || "Unknown",
    reason: v.reason,
    source: v.source,
  }));
  const revisionSummary = revisions.find(revision => revision.version === selected);
  const selectedRevision: RevisionDetail | null =
    selected === undefined || !preview || !revisionSummary
      ? null
      : {
          ...revisionSummary,
          comparison: {
            historicalLabel: `历史版本 ${selected}`,
            historicalText: revisionDocumentText(preview.document),
            currentLabel: `当前正文（版本 ${chapter.version}）`,
            currentText: chapter.content,
          },
        };
  return (
    <RevisionPanel
      revisions={revisions}
      currentVersion={chapter.version}
      selectedRevision={selectedRevision}
      loading={q.isLoading}
      detailLoading={detail.isLoading}
      error={q.error ? String(q.error) : null}
      detailError={detail.error ? String(detail.error) : null}
      onSelectRevision={setSelected}
      onRestore={async (request) => {
        // [HERMIA-FE-20261022 H-P0-02] Chapter-scoped confirm + lifecycle epoch (A→B→A safe).
        const target = {novelId: chapter.novel_id, chapterId: chapter.id, revisionVersion: request.revisionVersion, expectedCurrentVersion: request.expectedCurrentVersion};
        const token = syncRestoreLifecycle(restoreLife.current, target);
        const binding = bindRestoreConfirmation(token, target);
        const ticket = epoch.current;
        if (!current(ticket) || restorePending.current) return;
        const gate = gateRestore(binding, restoreLife.current, target);
        if (!gate.ok) throw { kind: "error", message: gate.reason };
        restorePending.current = true;
        try {
          const restored = await api.restore(
            chapter.id, request.revisionVersion, request.expectedCurrentVersion, context,
          );
          if (!current(ticket)) return;
          // Late result: re-gate after await (chapter/project may have switched).
          const late = gateRestore(binding, restoreLife.current, target);
          if (!late.ok || !current(ticket)) return;
          if (restored.id !== chapter.id || restored.novel_id !== chapter.novel_id)
            throw new Error("恢复结果与当前章节不一致，请刷新后检查。");
          onRestored(restored);
        } catch (error: any) {
          if (!current(ticket)) return;
          if (error?.status === 409)
            throw { kind: "conflict", message: error.message, currentVersion: error.problem?.details?.actual_version };
          if (error?.status === 403)
            throw { kind: "unauthorized", message: error.message };
          throw error;
        } finally {
          if (current(ticket)) restorePending.current = false;
        }
      }}
    />
  );
}
export function revisionDocumentText(document: unknown): string {
  if (!document || typeof document !== "object")
    return "无法完整显示此历史版本的正文。";
  const root = document as { text?: unknown; content?: unknown };
  if (typeof root.text === "string") return root.text;
  if (!Array.isArray(root.content)) return "无法完整显示此历史版本的正文。";
  const read = (node: any): string =>
    typeof node?.text === "string"
      ? node.text
      : Array.isArray(node?.content)
        ? node.content.map(read).join("")
        : "";
  const blocks = root.content
    .map((node: any) => read(node).trimEnd())
    .filter(Boolean);
  return blocks.length ? blocks.join("\n\n") : "此历史版本没有可显示的正文。";
}
function History({ chapter, scope }: { chapter: Chapter; scope?: Scope }) {
  const [selected, setSelected] = useState<number>();
  const q = useQuery({
    queryKey: ["history", scope, chapter.id],
    queryFn: () =>
      scope ? api.history(scope, chapter.id) : api.legacyHistory(chapter.id),
  });
  const detail = useQuery({
    queryKey: ["revision-detail", scope, chapter.id, selected],
    queryFn: () => api.revisionDetail(scope!, chapter.id, selected!),
    enabled: !!scope && selected !== undefined,
  });
  const preview = scope
    ? detail.data
    : q.data?.find((x) => x.version === selected);
  return (
    <section className="panel">
      <h2>版本历史</h2>
      {q.data?.map((v) => (
        <article key={v.version}>
          <b>v{v.version}</b>
          <span>{v.reason || v.source}</span>
          <button onClick={() => setSelected(v.version)}>查看/恢复</button>
          {selected === v.version && preview && (
            <div>
              <pre>{JSON.stringify(preview.document, null, 2)}</pre>
              <p>恢复会创建新版本。确认恢复 v{v.version}？</p>
              <button
                onClick={() =>
                  api
                    .restore(chapter.id, v.version, chapter.version)
                    .then(() => location.reload())
                }
              >
                确认恢复
              </button>
              <button onClick={() => setSelected(undefined)}>取消</button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}
function Connection({
  token,
  setToken,
  scope,
  setScope,
  connect,
  legacy,
}: {
  token: string;
  setToken: (x: string) => void;
  scope: Scope;
  setScope: (x: Scope) => void;
  connect: () => void;
  legacy: any;
}) {
  return (
    <div className="home">
      <h1>连接协作项目</h1>
      <section className="connect">
        <label>
          会话令牌
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        {(["workspaceId", "projectId", "storylineId", "branchId"] as const).map(
          (k) => (
            <label key={k}>
              {k}
              <input
                value={scope[k]}
                onChange={(e) => setScope({ ...scope, [k]: e.target.value })}
              />
            </label>
          ),
        )}
        <button
          disabled={!token || Object.values(scope).some((v) => !v)}
          onClick={connect}
        >
          进入项目
        </button>
      </section>
      {legacy}
    </div>
  );
}
function NovelHome({ onCreated }: { onCreated: (id: string) => void }) {
  const c = useQueryClient(),
    q = useQuery({ queryKey: ["novels"], queryFn: api.novels });
  const [title, setTitle] = useState("");
  return (
    <section>
      <h2>本机作品</h2>
      <p>创建或打开保存在本机的小说。</p>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="小说名称"
        aria-label="小说名称"
      />
      <button
        onClick={() =>
          api.createNovel(title, "").then((n) => {
            cacheCreatedNovel(c, n);
            onCreated(n.id);
          })
        }
      >
        创建小说
      </button>
      {q.data?.map((n) => (
        <button onClick={() => onCreated(n.id)} key={n.id}>
          {n.title}
        </button>
      ))}
      <NovelImportPanel onImported={(novel) => { cacheCreatedNovel(c, novel); onCreated(novel.id); }} />
    </section>
  );
}
