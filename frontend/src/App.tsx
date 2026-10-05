import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
} from "./api";
import { useStudio } from "./store";
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
import { RevisionPanel, type RevisionDetail } from "./RevisionPanel";
import { CollaborationPanel } from "./CollaborationPanels";
import { AppShell, StudioModule } from "./ui/AppShell";
import { ModuleWorkspaceRoutes } from "./ui/ModuleWorkspaceRoutes";
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
import { ExperimentalWorkbench, EXPERIMENTAL_GROUPS, EXPERIMENTAL_TABS } from "./experimental/ExperimentalWorkbench";
import { experimentalFeatures, experimentalClient } from "./experimental/api";
import { WritingReferenceRail, defaultWritingPreferences, type WritingFocusPreferences } from "./experimental/WritingFocusPanel";
import type { WorkspaceNavigation, WorkspaceAnchor } from "./experimental/uxClient";
import { authorContextRequest, type AuthorPreviewReceipt } from "./novel/authorContextClient";
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
  const experimentalFlags = useQuery({ queryKey: ["experimental-features", namespace], queryFn: ({ signal }) => experimentalFeatures(signal, {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}), retry: false, staleTime: 30000 });
  const hasExperimental = Object.values(experimentalFlags.data?.features || {}).some(value => value === true);
  const writingRecovery = experimentalFlags.data?.features['experimental.writing_recovery_v2'] === true;
  const workspaceTools = experimentalFlags.data?.features['experimental.workspace_tools_v2'] === true;
  const writingFocus = experimentalFlags.data?.features['experimental.writing_focus_v2'] === true;
  const [focusActive, setFocusActive] = useState(false), [writingPreferences, setWritingPreferences] = useState<WritingFocusPreferences>(defaultWritingPreferences), [referenceRevision, setReferenceRevision] = useState(0);
  const workspaceClient = useMemo(() => experimentalClient(s.novelId, {sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}), [namespace, s.novelId, s.actor?.id]);
  const focusPreferencesTouched = useRef(false);
  const persistedFocusPreferences = useQuery({
    queryKey: ['writing-focus-preferences', namespace, s.novelId, s.actor?.id],
    queryFn: ({ signal }) => workspaceClient.get<{ preferences: WritingFocusPreferences }>('/writing-focus/preferences', signal),
    enabled: writingFocus && !!s.novelId, retry: false,
  });
  useEffect(() => { focusPreferencesTouched.current = false; setFocusActive(false); setWritingPreferences(defaultWritingPreferences); }, [namespace, s.novelId, writingFocus]);
  useEffect(() => {
    if (writingFocus && persistedFocusPreferences.data && !focusPreferencesTouched.current)
      setWritingPreferences(persistedFocusPreferences.data.preferences);
  }, [writingFocus, persistedFocusPreferences.data]);

  const [experimentalTab, setExperimentalTab] = useState<string>();
  const [workspaceSection, setWorkspaceSection] = useState<'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'>('resume');
  const [editorAnchor, setEditorAnchor] = useState<{ identity: string; anchor: WorkspaceAnchor }>();
  const [pendingAnchor, setPendingAnchor] = useState<{ namespace: string; chapterId: string; version: number; requestId: number; offset: number; scroll: number }>();
  const anchorSequence = useRef(0);

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
    [panel, setPanel] = useState("history"),
    [conflict, setConflict] = useState<PersistentConflict>(),
    [tool, setTool] = useState("continue"),
    [instruction, setInstruction] = useState(""),
    [selection, setSelection] = useState({ from: 0, to: 0, text: "" }),
    [job, setJob] = useState<any>();
  const [featureGroups, setFeatureGroups] = useState<Record<string, boolean>>(() => {
    const defaults = { create: true, production: true, collaboration: false, system: false };
    if (typeof window === "undefined") return defaults;
    try { return { ...defaults, ...JSON.parse(localStorage.getItem("studio-feature-groups") || "{}")} } catch { return defaults; }
  });
  useEffect(() => { try { localStorage.setItem("studio-feature-groups", JSON.stringify(featureGroups)); } catch { /* storage may be unavailable in private hosts */ } }, [featureGroups]);
  const [studioModule, setStudioModule] = useState<StudioModule>("NOVEL"),
    [draftAction, setDraftAction] = useState<"accept" | "reject">(),
    [generationStarting, setGenerationStarting] = useState(false),
    [variantCancelling, setVariantCancelling] = useState(false),
    [generationRecovering, setGenerationRecovering] = useState(false),
    [variantDrafts, setVariantDrafts] = useState<AiVariantDraft[]>([]),
    [activeVariant, setActiveVariant] = useState(0);
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
    enabled: !packagedHost && shouldLoadLocalNovels(s.sessionToken, s.scope),
  });
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
    enabled: !!s.novelId,
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
    if (!s.novelId && novels.data?.[0]) s.setNovel(novels.data[0].id);
  }, [novels.data]);
  useEffect(() => {
    if (!s.chapterId && chapters.data?.[0]) s.setChapter(chapters.data[0].id);
  }, [chapters.data]);
  // BACKPORT CANDIDATE (U02): hydrate before exposing an editable surface, and
  // prefer the current draft even when its rich-text document is absent.
  useLayoutEffect(() => { setComposing(false); }, [editorIdentity, scopeEpoch]);
  useLayoutEffect(() => {
    if (!chapter.data || chapter.data.id !== s.chapterId) {
      setHydratedIdentity(undefined);
      setConflict(undefined);
      return;
    }
    const d = drafts.load(chapter.data.id, namespace);
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
  }, [namespace, editorIdentity, scopeEpoch, chapter.data?.id, chapter.data?.version]);
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
    if (composing || hydratedIdentity !== editorIdentity || saveState !== 'dirty' || save.isPending || saveGate.current.active) return;
    const timeout = setTimeout(dispatchSave, 900);
    return () => clearTimeout(timeout);
  }, [text, doc, saveState, namespace, s.chapterId, baseVersion, save.isPending, composing, hydratedIdentity, editorIdentity]);
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
        source: selection.text, selected_text: selection.text,
      };
      if (previewReceipt && (saveState !== 'saved' || previewReceipt.chapterVersion !== chapter.data.version))
        throw new Error('正文或预检版本已改变，请先保存并重新检查。');
      const result = previewReceipt
        ? await authorContextRequest<any>(observer.novelId, 'generate', {
            ...payload, provider_id: payload.provider_id || '', model_id: payload.model_id || '',
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
  async function runAIVariants(operation: string, request: string, count: number, style = '') {
    if (!chapter.data || generationStarting || (generationCreating.current && isObservingGeneration(generationCreating.current)) || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    if (operation === 'rewrite' && !selection.text) {
      setJob({ id: 'selection-required', status: 'FAILED', output: '', error: '请先在正文中选择需要改写的文字。' }); return;
    }
    const observer = beginGenerationObservation();
    generationCreating.current = observer;
    const original = operation === 'rewrite' ? selection.text : text;
    setGenerationStarting(true); setVariantDrafts([]); setActiveVariant(0); setJob(undefined);
    try {
      const response = await api.generateVariants(operation, {
        novel_id: observer.novelId, chapter_id: observer.chapterId, instruction: request, style,
        style_profile_id: s.writingInputs?.styleProfileId, plot_plan_id: s.writingInputs?.plotPlanId,
        profile: s.mode, provider_id: s.textModel?.providerId, model_id: s.textModel?.modelId,
        source: selection.text, selected_text: selection.text, count,
      }, observer.context);
      const candidates: AiVariantDraft[] = response.variants.map(item => ({
        id: item.job_id, variantIndex: item.variant_index, baseChapterVersion: item.base_chapter_version,
        output: '', original, status: 'working',
      }));
      retainGeneration(observer, { chapterId: observer.chapterId, variants: candidates });
      if (isObservingGeneration(observer)) { setGenerationRecoveryUnverified(false); await observeVariantGenerations(observer, candidates); }
    } catch {
      if (isObservingGeneration(observer)) setJob({ id: 'generation-failed', status: 'FAILED', output: '', error: '多方案生成失败，请重试' });
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
  async function readVerifiedRecovery(origin: GenerationOrigin, value: RecoverableGeneration): Promise<any[]> {
    if (!isCurrentGeneration(origin) || value.chapterId !== origin.chapterId
        || (value.actorId !== undefined && value.actorId !== origin.context.actor?.id)) throw new Error('RECOVERY_SCOPE_CHANGED');
    const ids = value.jobId ? [value.jobId] : value.variants?.map(item => item.id) ?? [];
    if (!ids.length || ids.length > 8) throw new Error('INVALID_RECOVERY_GROUP');
    const states = await Promise.all(ids.map(id => api.job(id, origin.context)));
    if (!isCurrentGeneration(origin)) throw new Error('RECOVERY_SCOPE_CHANGED');
    states.forEach((state, index) => {
      const scope = origin.context.scope;
      if (state.id !== ids[index] || state.novel_id !== origin.novelId || state.chapter_id !== origin.chapterId
          || !Number.isInteger(state.base_chapter_version) || typeof state.output !== 'string'
          || (state.status !== 'QUEUED' && state.status !== 'GENERATING' && !isGenerationTerminal(state.status))
          || (origin.context.actor?.id && state.actor_id !== origin.context.actor.id)
          || (scope && (state.scope?.workspace_id !== scope.workspaceId || state.scope?.project_id !== scope.projectId
            || state.scope?.storyline_id !== scope.storylineId || state.scope?.branch_id !== scope.branchId))) throw new Error('RECOVERY_SOURCE_CHANGED');
    });
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
  if (!s.novelId && !s.scope?.workspaceId)
    return (
      <EntryExperience
        packagedHost={packagedHost}
        initialToken={s.sessionToken}
        onEnter={(nextToken, nextScope) =>
          s.setCollaboration(nextToken, undefined, nextScope)
        }
        localHome={<NovelHome onCreated={s.setNovel} />}
      />
    );
  const scope = s.scope;
  if (studioModule !== "NOVEL") return <ModuleWorkspaceRoutes key={JSON.stringify([s.sessionToken,s.actor?.id,s.novelId,scope?.workspaceId,scope?.projectId,scope?.storylineId,scope?.branchId])} module={studioModule} onModuleChange={setStudioModule} novelId={s.novelId} actor={s.actor?.displayName || "本机作者"} scope={{workspace:scope?.workspaceName || "本机作品", project:scope?.projectName || "当前小说", storyline:scope?.storylineName || "默认故事线", branch:scope?.branchName || "主线"}} />;
  const localNovelTitle =
    novels.data?.find((n) => n.id === s.novelId)?.title || "当前小说";
  const shellScope = scope
    ? {
        workspace: scope.workspaceName || "当前工作区",
        project: scope.projectId ? scope.projectName || "当前小说" : "",
        storyline: scope.storylineId ? scope.storylineName || "默认故事线" : "",
        branch: scope.branchId ? scope.branchName || "主分支" : "",
      }
    : {
        workspace: "本机作品",
        project: localNovelTitle,
        storyline: "默认故事线",
        branch: "主线",
      };
  const saveDisplayLabel = chapter.data
    ? (writingRecovery ? recoveryStateLabel(saveState, durability, composing) : saveStateLabel(saveState))
    : "正在打开章节…";
  const taskSummary = summarizeTasks(job?.status ? [{ status: job.status }] : []);
  const archivedItems = Array.isArray(archived.data)
    ? archived.data
    : ((archived.data as unknown as { items?: Chapter[] } | undefined)?.items || []);
  const sidebar = (
    <div className="tree sidebar-layout">
      <div className="novel-sidebar-heading"><span>小说结构</span><strong>章节导航</strong></div>
      <div className="sidebar-chapter-scroll" data-testid="chapter-tree-scroll">
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
          error={chapters.error ? String(chapters.error) : null}
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
      <div className="novel-sidebar-heading novel-sidebar-heading--tools"><span>工作区</span><strong>创作工具</strong></div>
      <FeatureLauncher
        selectedId={panel}
        extraGroups={hasExperimental ? EXPERIMENTAL_GROUPS : undefined}
        expandedGroups={featureGroups}
        onSelect={setPanel}
        onToggleGroup={(id) => setFeatureGroups((current) => ({ ...current, [id]: !current[id] }))}
      />
    </div>
  );
  function navigateWorkspace(target: WorkspaceNavigation) {
    if ((!workspaceTools && !writingFocus) || revisionStoreIdentity(useStudio.getState()) !== editorIdentity) return;
    if (target.kind === 'chapter') {
      if (!target.id || !Number.isInteger(target.version) || !target.version) return;
      setPendingAnchor({ namespace, chapterId: target.id, version: target.version,
        requestId: ++anchorSequence.current, offset: target.anchor?.offset || 0, scroll: target.anchor?.scroll || 0 });
      s.setChapter(target.id);
      setPanel('history');
      return;
    }
    const feature = target.feature || target.id;
    const experimental = EXPERIMENTAL_TABS.find(([key]) => key === feature);
    if (experimental) {
      if (experimentalFlags.data?.features[`experimental.${feature}`] !== true) return;
      setExperimentalTab(feature); setPanel('experimental'); return;
    }
    const safePanels = new Set(['editor', 'creation', 'story', 'history', 'workflow', 'screenplay', 'assets', 'exports', 'knowledge', 'research', 'agents', 'diagnostics', 'settings']);
    if (safePanels.has(feature)) setPanel(feature === 'editor' ? 'history' : feature);
  }
  const openWorkspaceSearch = workspaceTools ? () => {
    setStudioModule('NOVEL'); setWorkspaceSection('search'); setExperimentalTab('workspace_tools_v2'); setPanel('experimental');
  } : undefined;
  const mainWorkspace = (
    <div className="workspace novel-writing-workspace">
      <div className="editorbar">
        <div className="editorbar__identity"><span>当前章节</span><b>{chapter.data?.title || "未选择章节"}</b></div>
        <small>{text.trim() ? `${text.trim().length} 字` : "0 字"}</small>
        {writingGoal.data && (
          <div className="writing-goal" aria-label="写作目标进度">
            <span>目标 {writingGoal.data.current_words.toLocaleString()} / {writingGoal.data.target_words.toLocaleString()} 字</span>
            <span>第 {writingGoal.data.current_chapters} / {writingGoal.data.target_chapters} 章</span>
            <div className="writing-goal__bar" role="progressbar" aria-valuenow={Math.round(writingGoal.data.words_progress)} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: `${Math.min(100, Math.max(0, writingGoal.data.words_progress))}%` }} />
            </div>
            <strong>{Math.round(writingGoal.data.words_progress)}%</strong>
          </div>
        )}
        <SaveControls
          state={saveState}
          ready={!!chapter.data && hydratedIdentity === editorIdentity}
          onSave={dispatchSave}
          composing={composing}
          recovery={writingRecovery ? { durability, onExport: exportCurrentDraft, onConflict: reopenConflict } : undefined}
        />
      </div>
      {writingRecovery && durability === 'memory' && <section className="notice" role="alert">
        本机草稿写入失败。当前修改仅在此页面内存中，关闭、刷新或断电可能丢失。请导出当前草稿。
      </section>}
      <div className={writingFocus ? 'writing-editor-row writing-focus-split' : 'writing-editor-row'}>
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
      ) : (
        <section className="notice" aria-live="polite">
          <strong>当前还没有打开的章节</strong>
          <p>在左侧新建或选择章节，开始写作。</p>
        </section>
      )}
      {writingFocus && s.novelId && <WritingReferenceRail key={`${namespace}:${s.novelId}`} client={workspaceClient} revision={referenceRevision} />}
      </div>
      {panel === "experimental" ? <ExperimentalWorkbench key={`${namespace}:${s.novelId}`} novelId={s.novelId} chapter={chapter.data} context={{sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}} flags={experimentalFlags.data} onNavigate={navigateWorkspace} currentAnchor={saveState === "saved" && editorAnchor?.identity === editorIdentity ? editorAnchor.anchor : undefined} requestedTab={experimentalTab} workspaceSection={workspaceSection} focusActive={focusActive} onFocusChange={setFocusActive} onPreferencesChange={preferences => { focusPreferencesTouched.current = true; setWritingPreferences(preferences); }} onReferencesChange={() => setReferenceRevision(value => value + 1)} /> : <Panel type={panel} chapter={chapter.data} scope={scope} sessionToken={s.sessionToken} novelId={s.novelId} onOpenChapter={s.setChapter}
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
  );
  const inspector = (
    <div className="novel-inspector-stack">
      <section className="novel-inspector-context" aria-label="当前写作上下文"><span>当前章节</span><strong>{chapter.data?.title || "未选择章节"}</strong><small>{chapter.data ? `第 ${chapter.data.number} 章 · 版本 ${chapter.data.version}` : "从左侧章节树选择章节"}</small></section>
      <WritingGoalPanel novelId={s.novelId} />
      {chapter.data&&<SourcePrivacyControl key={`${namespace}:${chapter.data.id}`} chapter={chapter.data} context={{sessionToken:s.sessionToken,scope:s.scope,actor:s.actor}}/>}
      {writingRecovery && chapter.data && <GenerationRecoveryPicker key={`${namespace}:${s.chapterId}:${scopeEpoch}`}
        namespace={namespace} chapterId={s.chapterId} actorId={s.actor?.id} revision={generationRecoveryRevision} includeCurrent={generationRecoveryUnverified}
        onRecover={reopenRetainedGeneration} />}
      <AiWritingPanel
      authorPreview={chapter.data ? {
        enabled: experimentalFlags.data?.features['experimental.author_context_inspector_v2'] === true,
        chapterId: chapter.data.id, chapterVersion: chapter.data.version, source: selection.text,
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
      onOpenDiagnostics={() => setPanel("diagnostics")}
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
      onGenerate={(operation: AiOperation, request, style) =>
        runAI(operation, request, style)
      }
      onCancel={cancelActiveGeneration}
      onAccept={acceptGeneratedDraft}
      onReject={rejectGeneratedDraft}
      />
    </div>
  );
  return (
    <>
      {
        <AppShell
          module={studioModule}
          onModuleChange={setStudioModule}
          scope={shellScope}
          actor={s.actor?.displayName || "本机作者"}
          onGlobalSearch={openWorkspaceSearch}
          focusMode={writingFocus && focusActive}
          onExitFocus={() => setFocusActive(false)}
          sidebarClassName="workspace-sidebar--novel"
          sidebar={sidebar}
          main={mainWorkspace}
          inspector={inspector}
          status={
            <>
              保存：{saveDisplayLabel} · 连接：{scope ? "协作服务" : "本机"}
              {taskSummary.total ? ` · AI 任务：${taskSummary.running ? "生成中" : taskSummary.failed ? "失败" : taskSummary.succeeded ? "已完成" : "排队中"}` : " · AI 任务：无运行任务"}
              {shellMessage ? ` · ${shellMessage}` : ""}
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
function Panel({
  type,
  chapter,
  scope,
  sessionToken,
  novelId,
  onOpenChapter,
  onRestored,
}: {
  type: string;
  chapter?: Chapter;
  scope?: Scope;
  novelId: string;
  onOpenChapter: (id:string)=>void;
  onRestored: (chapter: Chapter) => void;
  sessionToken: string;
}) {
  if (!scope && ["members", "permissions", "audit", "snapshots"].includes(type))
    return (
      <section className="panel">
        <h2>团队协作</h2>
        <p className="notice">进入团队创作空间后可查看成员、权限和协作记录。</p>
      </section>
    );
  if (type === "history")
    return chapter ? <RevisionHistory chapter={chapter} scope={scope} sessionToken={sessionToken} onRestored={onRestored} /> : null;
  if (type === "story")
    return chapter ? (
      <StoryDatabasePanel chapter={chapter} scope={scope} onOpenChapter={onOpenChapter} />
    ) : (
      <section className="panel">
        <h2>故事资料库</h2>
        <p className="notice">
          请先新建或选择一个章节，再查看当前小说的人物和世界设定。
        </p>
      </section>
    );
  if (type === "workflow") return <VisualWorkflowPanel scope={scope} />;
  if (type === "overview") return <NovelOverviewPanel novelId={novelId} />;
  if (type === "check") return <ContinuityCheckPanel projectId={novelId} chapter={chapter} />;
  if (type === "diagnostics") return <RuntimeDiagnosticsPanel scope={scope} />;
  if (type === "agents") return <>{chapter&&<AgentActivityCenter novelId={chapter.novel_id} />}{chapter&&<AgentJobHistory novelId={chapter.novel_id} />}<AgentTeamPanel chapter={chapter} /></>;
  if (type === "adaptation") return <AdaptationPanel novelId={chapter?.novel_id} branchId={scope?.branchId} />;
  if (type === "screenplay") return <ScreenplayPanel novelId={chapter?.novel_id} scope={scope||null} sessionToken={sessionToken} />;
  if (type === "assets") return <AssetLibraryPanel novelId={chapter?.novel_id || useStudio.getState().novelId || ""} />;
  if (type === "exports") return <ExportPanel novelId={chapter?.novel_id || useStudio.getState().novelId || ""} scope={scope||null} sessionToken={sessionToken} />;
  if (type === "knowledge") return <NovelImportPanel key={`${novelId}:${scope?.branchId||"local"}:${sessionToken}`} requestContext={{sessionToken,scope}} novelId={chapter?.novel_id || useStudio.getState().novelId || ""} chapterId={chapter?.id} />;
  if (type === "creation" || type === "comments") return <CreationWorkbenchPanel key={`${novelId}:${scope?.branchId||"local"}:${sessionToken}`} novelId={novelId} chapter={chapter} initialComments={type === "comments"} context={{sessionToken,scope}} />;
  if (type === "research") return <ResearchPanel novelId={novelId} />;
  if (type === "settings") return <><AiControlCenter /><MediaProviderSettings /><VideoCallbackSecurityStatus /></>;
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
function StoryDatabasePanel({
  chapter,
  scope,
  onOpenChapter,
}: {
  chapter: Chapter;
  scope?: Scope;
  onOpenChapter:(id:string)=>void;
}) {
  const queryClient=useQueryClient();
  const [kind, setKind] = useState<StoryDatabaseKind>("characters");
  const [selectedCharacter,setSelectedCharacter]=useState<Partial<CharacterDraft>>();
  const [selectedLocation,setSelectedLocation]=useState<Partial<LocationDraft>>();
  const [selectedTimeline,setSelectedTimeline]=useState<Partial<TimelineDraft>>();
  const [selectedForeshadowing,setSelectedForeshadowing]=useState<Partial<ForeshadowingDraft>>();
  const [selectedRelationship,setSelectedRelationship]=useState<Partial<RelationshipDraft>>();
  const [selectedVolume,setSelectedVolume]=useState<Partial<VolumeDraft>>();
  const [selectedScene,setSelectedScene]=useState<Partial<SceneDraft>>();
  const [selectedStoryRoute,setSelectedStoryRoute]=useState<Partial<StoryRouteDraft>>();
  const novel=useQuery({queryKey:["novel-detail",chapter.novel_id],queryFn:()=>api.novel(chapter.novel_id),enabled:!scope});
  const outline=useQuery({queryKey:["novel-outline",chapter.novel_id],queryFn:()=>api.outline(chapter.novel_id),enabled:!scope});
  const storyChapters=useQuery({queryKey:["story-chapters",chapter.novel_id],queryFn:()=>api.chapters(chapter.novel_id),enabled:!scope});
  const saveWorld=useMutation({mutationFn:(value:string)=>api.updateNovel(chapter.novel_id,{long_term_summary:value}),onSuccess:(value)=>queryClient.setQueryData(["novel-detail",chapter.novel_id],value)});
  const saveOutline=useMutation({mutationFn:(value:OutlineDraft)=>api.updateOutline(chapter.novel_id,value),onSuccess:(value)=>queryClient.setQueryData(["novel-outline",chapter.novel_id],value)});
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
      queryKey: ["story-database", scope, chapter.novel_id, resource],
      queryFn: async () =>
        scope
          ? (await api.storyDatabase(scope, resource)).items
          : resource==='story_routes'?api.storyRoutes(chapter.novel_id):api.resource(chapter.novel_id, resource),
    })),
  });
  const saveCharacter=useMutation({mutationFn:(value:CharacterDraft)=>api.upsertCharacter(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedCharacter(undefined);return queries[0].refetch();}});
  const saveLocation=useMutation({mutationFn:(value:LocationDraft)=>api.upsertLocation(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedLocation(undefined);return queries[2].refetch();}});
  const saveTimeline=useMutation({mutationFn:(value:TimelineDraft)=>api.upsertTimelineEvent(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedTimeline(undefined);return queries[3].refetch();}});
  const saveForeshadowing=useMutation({mutationFn:(value:ForeshadowingDraft)=>api.upsertForeshadowing(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedForeshadowing(undefined);return queries[4].refetch();}});
  const saveRelationship=useMutation({mutationFn:(value:RelationshipDraft)=>api.upsertRelationship(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedRelationship(undefined);return queries[5].refetch();}});
  const saveVolume=useMutation({mutationFn:(value:VolumeDraft)=>api.upsertVolume(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedVolume(undefined);return queries[6].refetch();}});
  const saveScene=useMutation({mutationFn:(value:SceneDraft)=>api.upsertScene(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedScene(undefined);return queries[7].refetch();}});
  const saveStoryRoute=useMutation({mutationFn:(value:StoryRouteDraft)=>api.upsertStoryRoute(chapter.novel_id,value.id,value),onSuccess:()=>{setSelectedStoryRoute(undefined);return queries[8].refetch();}});
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
          onOpen={(targetKind,id)=>{setKind(targetKind);if(id&&targetKind==='volumes')setSelectedVolume(((queries[6].data||[]) as any[]).find(item=>String(item.id)===id));if(id&&targetKind==='scenes')setSelectedScene(((queries[7].data||[]) as any[]).find(item=>String(item.id)===id));}}
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
          onOpen={(targetKind,id)=>{setKind(targetKind);if(id){if(targetKind==='relationships')setSelectedRelationship(((queries[5].data||[]) as any[]).find(item=>String(item.id)===id));if(targetKind==='timeline')setSelectedTimeline(((queries[3].data||[]) as any[]).find(item=>String(item.id)===id));if(targetKind==='foreshadowing')setSelectedForeshadowing(((queries[4].data||[]) as any[]).find(item=>String(item.id)===id));}}}
        />
        <StoryDatabase sections={sections} activeKind={kind} onSelectKind={setKind} onSelectRecord={(selectedKind,id)=>{if(selectedKind==='characters'){const row=((queries[0].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedCharacter(row);}if(selectedKind==='locations'){const row=((queries[2].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedLocation(row);}if(selectedKind==='timeline'){const row=((queries[3].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedTimeline(row);}if(selectedKind==='foreshadowing'){const row=((queries[4].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedForeshadowing(row);}if(selectedKind==='relationships'){const row=((queries[5].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedRelationship(row);}if(selectedKind==='volumes'){const row=((queries[6].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedVolume(row);}if(selectedKind==='scenes'){const row=((queries[7].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedScene(row);}if(selectedKind==='story_routes'){const row=((queries[8].data||[]) as any[]).find(item=>String(item.id)===id);setSelectedStoryRoute(row);}}}/>
        {kind==="outline"&&!scope&&<OutlineEditor value={outline.data} saving={saveOutline.isPending} onSave={async(value)=>{await saveOutline.mutateAsync(value);}}/>}
        {kind==="volumes"&&!scope&&<VolumeEditor value={selectedVolume} saving={saveVolume.isPending} onSave={async(value)=>{await saveVolume.mutateAsync(value);}}/>}
        {kind==="scenes"&&!scope&&<>
          <SceneEditor value={selectedScene} volumes={((queries[6].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} chapters={(storyChapters.data||[]).map(row=>({id:row.id,title:row.title}))} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} saving={saveScene.isPending} onSave={async(value)=>{await saveScene.mutateAsync(value);}}/>
          {selectedScene?.id&&<EntityAssetPanel novelId={chapter.novel_id} sceneId={String(selectedScene.id)}/>} 
          {selectedScene?.id&&<VisionAnalysisPanel novelId={chapter.novel_id} sceneId={String(selectedScene.id)}/>} 
        </>}
        {kind==="story_routes"&&!scope&&<StoryRouteEditor value={selectedStoryRoute} routes={((queries[8].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveStoryRoute.isPending} onSave={async(value)=>{await saveStoryRoute.mutateAsync(value);}}/>}
        {kind==="characters"&&!scope&&<>
          <CharacterEditor value={selectedCharacter} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} saving={saveCharacter.isPending} onSave={async(value)=>{await saveCharacter.mutateAsync(value);}}/>
          <CharacterEvolutionPanel novelId={chapter.novel_id} characterId={selectedCharacter?.id as string|undefined} characterName={selectedCharacter?.name as string|undefined}/>
          <CharacterConsistencyPanel novelId={chapter.novel_id} draft={chapter.content||''} chapter={chapter.number} characters={(queries[0].data||[]) as any[]}/>
          {selectedCharacter?.id&&<EntityAssetPanel novelId={chapter.novel_id} characterId={String(selectedCharacter.id)}/>} 
          {selectedCharacter?.id&&<VisionAnalysisPanel novelId={chapter.novel_id} characterId={String(selectedCharacter.id)}/>} 
          {selectedCharacter?.id&&<SpeechSynthesisPanel novelId={chapter.novel_id} characterId={String(selectedCharacter.id)}/>} 
        </>}
        {kind==="locations"&&!scope&&<LocationEditor value={selectedLocation} saving={saveLocation.isPending} onSave={async(value)=>{await saveLocation.mutateAsync(value);}}/>}
        {kind==="timeline"&&!scope&&<TimelineEditor value={selectedTimeline} locations={((queries[2].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} chapters={(storyChapters.data||[]).map(row=>({id:row.id,title:row.title}))} saving={saveTimeline.isPending} onSave={async(value)=>{await saveTimeline.mutateAsync(value);}}/>}
        {kind==="foreshadowing"&&!scope&&<><ForeshadowingTrackerPanel novelId={chapter.novel_id} records={(queries[4].data||[]) as any[]} currentChapter={chapter.number}/><ForeshadowingEditor value={selectedForeshadowing} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} events={((queries[3].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveForeshadowing.isPending} onSave={async(value)=>{await saveForeshadowing.mutateAsync(value);}}/></>}
        {kind==="relationships"&&!scope&&<RelationshipEditor value={selectedRelationship} characters={((queries[0].data||[]) as any[]).map(row=>({id:String(row.id),name:String(row.name)}))} events={((queries[3].data||[]) as any[]).map(row=>({id:String(row.id),title:String(row.title)}))} saving={saveRelationship.isPending} onSave={async(value)=>{await saveRelationship.mutateAsync(value);}}/>}
        {kind==="world"&&!scope&&<><WorldSummaryEditor value={novel.data?.long_term_summary||""} saving={saveWorld.isPending} onSave={async(value)=>{await saveWorld.mutateAsync(value);}}/><WorldRulesPanel novelId={novel.data?.id || ""}/></>}
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
  useLayoutEffect(() => {
    mounted.current = true;
    let observed = revisionStoreIdentity(useStudio.getState());
    // Invalidates even an A→B→A change batched into one React render.
    const unsubscribe = useStudio.subscribe(state => {
      const next = revisionStoreIdentity(state);
      if (next !== observed) { observed = next; epoch.current += 1; }
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
        const ticket = epoch.current;
        if (!current(ticket) || restorePending.current) return;
        restorePending.current = true;
        try {
          const restored = await api.restore(
            chapter.id, request.revisionVersion, request.expectedCurrentVersion, context,
          );
          if (!current(ticket)) return;
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

