import { useEffect, useRef, useState } from "react";
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
  Novel,
  Scope,
  setCollaborationContext,
} from "./api";
import { useStudio } from "./store";
import { ChapterEditor } from "./Editor";
import {
  drafts,
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
import { CapabilityPlaceholder } from "./ui/CapabilityPlaceholder";
import { CapabilityRoadmapPanel } from "./ui/CapabilityRoadmapPanel";
import { FeatureLauncher } from "./ui/FeatureLauncher";
import { AiControlCenter } from "./ui/AiControlCenter";
import "./ui/capability.css";
import DesignSystemFixture from "./ui/DesignSystemFixture";
import { isPackagedDesktopHost } from "./packagedHost";
import { generationRecovery } from "./generationRecovery";
import { WorldBuildingDashboard } from "./novel/WorldBuildingDashboard";
import { summarizeTasks } from "./ui/taskSummary";
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
  return ["COMPLETED", "FAILED", "CANCELLED"].includes(status);
}
export function isRecoveredDraftStale(baseVersion?: number, currentVersion?: number) {
  return baseVersion !== undefined && currentVersion !== undefined && baseVersion !== currentVersion;
}
export async function recoverGenerationJob(
  jobId: string,
  load: (id: string) => Promise<any>,
  update: (state: any) => void,
  options: { attempts?: number; intervalMs?: number; wait?: (ms: number) => Promise<void> } = {},
) {
  const attempts = options.attempts ?? 300;
  const intervalMs = options.intervalMs ?? 500;
  const wait = options.wait ?? ((ms: number) => new Promise<void>((ok) => setTimeout(ok, ms)));
  for (let attempt = 0; attempt < attempts; attempt++) {
    const state = await load(jobId);
    update(state);
    if (isGenerationTerminal(state.status)) return state;
    await wait(intervalMs);
  }
  return undefined;
}
export default function App() {
  const packagedHost = isPackagedDesktopHost();
  const qc = useQueryClient(),
    s = useStudio(),
    namespace = recoveryKey(s.scope, s.sessionToken) || "file",
    active = useRef({ namespace, chapterId: s.chapterId }),
    dispatched = useRef<any>(),
    saveGate = useRef(new SingleFlight<any>()),
    cancelledVariantIds = useRef(new Set<string>());
  active.current = { namespace, chapterId: s.chapterId };
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
      s.scope,
      selectedProviderId,
      selectedModelId,
    ],
    queryFn: () =>
      api.textRuntimeDiagnostics(
        s.scope!,
        selectedProviderId!,
        selectedModelId!,
      ),
    enabled: !!s.scope && !!selectedProviderId && !!selectedModelId,
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
    if (!chapter.data?.id || job || variantDrafts.length) return;
    const saved = generationRecovery.load(namespace, chapter.data.id);
    if (!saved) return;
    setGenerationRecovering(true);
    if (saved.variants?.length) {
      setVariantDrafts(saved.variants);
      Promise.all(saved.variants.map(async (variant) => {
        try {
          const state = await api.job(variant.id);
          const updated: AiVariantDraft = {...variant,output:state.output||variant.output,status:state.status==="COMPLETED"?"ready":isGenerationTerminal(state.status)?"failed":"working",error:state.error};
          if (isRecoveredDraftStale(updated.baseChapterVersion,chapter.data.version)) {
            updated.acceptBlocked=true;updated.acceptBlockedReason="正文已在生成期间发生变化，请先处理版本冲突。";
          }
          setVariantDrafts((current)=>current.map((item)=>item.id===variant.id?updated:item));
          if (!isGenerationTerminal(state.status)) await recoverGenerationJob(variant.id,api.job,(next)=>setVariantDrafts((current)=>current.map((item)=>item.id===variant.id?{...item,output:next.output||item.output,status:next.status==="COMPLETED"?"ready":isGenerationTerminal(next.status)?"failed":"working",error:next.error}:item)));
        } catch {setVariantDrafts((current)=>current.map((item)=>item.id===variant.id?{...item,status:"failed",error:"生成连接中断，恢复失败，请重试"}:item));}
      })).finally(()=>{generationRecovery.remove(namespace,chapter.data.id);setGenerationRecovering(false)});
    } else if (saved.jobId) {
      setJob({id:saved.jobId,status:"GENERATING",output:"",original:saved.original,base_chapter_version:saved.baseChapterVersion});
      recoverGenerationJob(saved.jobId,api.job,(state)=>setJob((current:any)=>({...current,...state,output:state.output||current?.output||"",acceptBlocked:isRecoveredDraftStale(state.base_chapter_version??saved.baseChapterVersion,chapter.data.version),acceptBlockedReason:isRecoveredDraftStale(state.base_chapter_version??saved.baseChapterVersion,chapter.data.version)?"正文已在生成期间发生变化，请先处理版本冲突。":undefined}))).finally(()=>{generationRecovery.remove(namespace,chapter.data.id);setGenerationRecovering(false)});
    }
  }, [chapter.data?.id, namespace]);
  useEffect(() => {
    if (!s.novelId && novels.data?.[0]) s.setNovel(novels.data[0].id);
  }, [novels.data]);
  useEffect(() => {
    if (!s.chapterId && chapters.data?.[0]) s.setChapter(chapters.data[0].id);
  }, [chapters.data]);
  useEffect(() => {
    if (!chapter.data) return;
    const d = drafts.load(chapter.data.id, namespace),
      savedConflict = conflicts.load(chapter.data.id, namespace);
    setText(d?.content ?? chapter.data.content);
    setDoc(d?.document ?? chapter.data.document);
    setBaseVersion(d?.baseVersion ?? chapter.data.version);
    if (d && d.baseVersion !== chapter.data.version) {
      const v = savedConflict || {
        chapterId: d.chapterId,
        local: d,
        server: chapter.data,
        detectedAt: new Date().toISOString(),
      };
      conflicts.save(v, namespace);
      setConflict(v);
      setSaveState((current) =>
        reduceSaveState(current, { type: "save-failed", conflict: true }),
      );
    } else {
      setConflict(savedConflict);
      setSaveState((current) =>
        reduceSaveState(current, {
          type: "hydrate",
          hasDraft: !!d,
          hasConflict: !!savedConflict,
        }),
      );
    }
  }, [namespace, chapter.data?.id, chapter.data?.version]);
  const save = useMutation({
    mutationFn: () =>
      saveGate.current.run(() => {
        const v = {
          namespace,
          chapterId: s.chapterId,
          baseVersion,
          content: text,
          document: doc,
        };
        dispatched.current = v;
        return api
          .saveChapter(v.chapterId, v.content, v.baseVersion, v.document)
          .then((x) => ({ x, v }));
      }),
    onMutate: () =>
      setSaveState((current) =>
        reduceSaveState(current, { type: "save-started" }),
      ),
    onSuccess: ({ x, v }) => {
      if (
        active.current.namespace !== v.namespace ||
        active.current.chapterId !== v.chapterId
      )
        return;
      const newer = rebaseNewerDraft(
        drafts.load(x.id, v.namespace),
        v,
        x.version,
      );
      setBaseVersion(x.version);
      qc.setQueryData(["chapter", v.namespace, x.id], x);
      qc.invalidateQueries({ queryKey: ["writing-goal", s.novelId] });
      if (newer) {
        drafts.save(newer, v.namespace);
        setSaveState((current) =>
          reduceSaveState(current, {
            type: "save-succeeded",
            hasNewerChanges: true,
          }),
        );
      } else {
        drafts.remove(x.id, v.namespace);
        conflicts.remove(x.id, v.namespace);
        conflictResolutionDrafts.remove(x.id, v.namespace);
        setSaveState((current) =>
          reduceSaveState(current, {
            type: "save-succeeded",
            hasNewerChanges: false,
          }),
        );
      }
    },
    onError: async (e: ApiError) => {
      const v = dispatched.current;
      if (
        !v ||
        active.current.namespace !== v.namespace ||
        active.current.chapterId !== v.chapterId
      )
        return;
      if (e.status === 409) {
        const server = await api.chapter(v.chapterId);
        if (active.current.namespace !== v.namespace) return;
        const local = drafts.load(v.chapterId, v.namespace);
        if (!local) {
          setSaveState((current) =>
            reduceSaveState(current, { type: "save-failed" }),
          );
          return;
        }
        const conflictValue = {
          chapterId: v.chapterId,
          local,
          server,
          detectedAt: new Date().toISOString(),
        };
        conflicts.save(conflictValue, v.namespace);
        setConflict(conflictValue);
        setSaveState((current) =>
          reduceSaveState(current, { type: "save-failed", conflict: true }),
        );
      } else
        setSaveState((current) =>
          reduceSaveState(current, { type: "save-failed" }),
        );
    },
  });
  const dispatchSave = () => {
    if (!save.isPending && !saveGate.current.active) save.mutate();
  };
  function edit(content: string, document: any) {
    setText(content);
    setDoc(document);
    setSaveState((current) => reduceSaveState(current, { type: "edit" }));
    drafts.save(
      {
        chapterId: s.chapterId,
        content,
        document,
        baseVersion,
        updatedAt: new Date().toISOString(),
      },
      namespace,
    );
  }
  useEffect(() => {
    if (saveState !== "dirty" || save.isPending || saveGate.current.active)
      return;
    const t = setTimeout(dispatchSave, 900);
    return () => clearTimeout(t);
  }, [
    text,
    doc,
    saveState,
    namespace,
    s.chapterId,
    baseVersion,
    save.isPending,
  ]);
  const cancelGeneration = useMutation({
    mutationFn: (id: string) => api.cancel(id),
    onSuccess: () =>
      setJob((current: any) =>
        current ? { ...current, status: "CANCELLED" } : current,
      ),
  });
  async function runAI(
    operation: string = tool,
    request: string = instruction,
    style = "",
  ) {
    if (!chapter.data || generationStarting || job?.status === "GENERATING")
      return;
    if (operation === "rewrite" && !selection.text) {
      setJob({
        id: "selection-required",
        status: "FAILED",
        output: "",
        error: "请先在正文中选择需要改写的文字。",
      });
      return;
    }
    setGenerationStarting(true);
    try {
      const r = await api.generate(operation, {
        novel_id: s.novelId,
        chapter_id: s.chapterId,
        instruction: request,
        style,
        profile: s.mode,
        provider_id: s.textModel?.providerId,
        model_id: s.textModel?.modelId,
        source: selection.text,
        selected_text: selection.text,
      });
      setJob({
        id: r.job_id,
        status: "GENERATING",
        output: "",
        original: operation === "rewrite" ? selection.text : text,
        base_chapter_version: r.base_chapter_version ?? chapter.data.version,
      });
      generationRecovery.save(namespace,{chapterId:s.chapterId,jobId:r.job_id,original:operation === "rewrite" ? selection.text : text,baseChapterVersion:r.base_chapter_version ?? chapter.data.version});
      if (s.scope) {
        for (let i = 0; i < 300; i++) {
          const x = await api.job(r.job_id);
          setJob((j: any) => ({ ...j, ...x }));
          if (["COMPLETED", "FAILED", "CANCELLED"].includes(x.status)) break;
          await new Promise((ok) => setTimeout(ok, 500));
        }
      } else {
        const es = new EventSource(r.events_url);
        let recovering = false;
        es.onmessage = (e) => {
          const x = JSON.parse(e.data);
          setJob((j: any) => ({
            ...j,
            ...x,
            output: (j?.output || "") + (x.chunk || ""),
          }));
          if (["COMPLETED", "FAILED", "CANCELLED"].includes(x.status))
            {es.close();generationRecovery.remove(namespace,s.chapterId)}
        };
        es.onerror = async () => {
          if (recovering) return;
          recovering = true;
          es.close();
          try {
            const recovered = await recoverGenerationJob(
              r.job_id,
              api.job,
              (state) => setJob((current: any) => ({ ...current, ...state, output: state.output || current?.output || "" })),
            );
            if (!recovered) {
              await api.cancel(r.job_id).catch(() => undefined);
              setJob((current: any) => ({
                ...current,
                status: "FAILED",
                error: "生成连接中断且恢复超时，请重试",
              }));
            }
          } catch {
            setJob((current: any) => ({
              ...current,
              status: "FAILED",
              error: "生成连接中断，恢复失败，请重试",
            }));
          }
        };
      }
    } catch {
      setJob({
        id: "generation-failed",
        status: "FAILED",
        output: "",
        error: "生成失败，请重试",
      });
    } finally {
      setGenerationStarting(false);
    }
  }
  async function runAIVariants(
    operation: string,
    request: string,
    count: number,
    style = "",
  ) {
    if (!chapter.data || generationStarting) return;
    if (operation === "rewrite" && !selection.text) {
      setJob({
        id: "selection-required",
        status: "FAILED",
        output: "",
        error: "请先在正文中选择需要改写的文字。",
      });
      return;
    }
    setGenerationStarting(true);
    setVariantDrafts([]);
    setActiveVariant(0);
    setJob(undefined);
    try {
      const response = await api.generateVariants(operation, {
        novel_id: s.novelId,
        chapter_id: s.chapterId,
        instruction: request,
        style,
        profile: s.mode,
        provider_id: s.textModel?.providerId,
        model_id: s.textModel?.modelId,
        source: selection.text,
        selected_text: selection.text,
        count,
      });
      const original = operation === "rewrite" ? selection.text : text;
      let candidates: AiVariantDraft[] = response.variants.map((item) => ({
        id: item.job_id,
        variantIndex: item.variant_index,
        baseChapterVersion: item.base_chapter_version,
        output: "",
        original,
        status: "working",
      }));
      setVariantDrafts(candidates);
      generationRecovery.save(namespace,{chapterId:s.chapterId,variants:candidates});
      await Promise.all(
        response.variants.map(async (item, index) => {
          let terminal = false;
          for (let attempt = 0; attempt < 300; attempt++) {
            const state = await api.job(item.job_id);
            if (cancelledVariantIds.current.has(item.job_id)) break;
            candidates = candidates.map((candidate, i) =>
              i === index
                ? {
                    ...candidate,
                    output: state.output || "",
                    status:
                      state.status === "COMPLETED"
                        ? "ready"
                        : state.status === "FAILED"
                          ? "failed"
                          : "working",
                    error: state.error,
                  }
                : candidate,
            );
            setVariantDrafts([...candidates]);
            generationRecovery.save(namespace,{chapterId:s.chapterId,variants:candidates});
            if (isGenerationTerminal(state.status)) {
              terminal = true;
              break;
            }
            await new Promise((ok) => setTimeout(ok, 500));
          }
          if (!terminal && !cancelledVariantIds.current.has(item.job_id)) {
            await api.cancel(item.job_id).catch(() => undefined);
            candidates = candidates.map((candidate, i) =>
              i === index
                ? { ...candidate, status: "failed", error: VARIANT_TIMEOUT_ERROR }
                : candidate,
            );
            setVariantDrafts([...candidates]);
          }
        }),
      );
      generationRecovery.remove(namespace,s.chapterId);
    } catch {
      setJob({
        id: "generation-failed",
        status: "FAILED",
        output: "",
        error: "多方案生成失败，请重试",
      });
    } finally {
      setGenerationStarting(false);
    }
  }
  async function cancelActiveGeneration() {
    if (variantCancelling || cancelGeneration.isPending) return;
    const workingIds = workingVariantIds(variantDrafts);
    if (workingIds.length) {
      setVariantCancelling(true);
      workingIds.forEach((id) => cancelledVariantIds.current.add(id));
      try {
        await Promise.all(workingIds.map((id) => api.cancel(id).catch(() => undefined)));
        setVariantDrafts((current) =>
          current.filter((item) => !cancelledVariantIds.current.has(item.id)),
        );
        setActiveVariant(0);
      } finally {
        setVariantCancelling(false);
      }
      return;
    }
    if (job?.id) cancelGeneration.mutate(job.id);
  }
  async function retryVariant(draft: AiVariantDraft) {
    const index = variantDrafts.findIndex((item) => item.id === draft.id);
    if (index < 0 || draft.status !== "failed") return;
    setVariantDrafts((current) =>
      current.map((item) =>
        item.id === draft.id ? { ...item, status: "working", error: undefined } : item,
      ),
    );
    try {
      const response = await api.retryGeneration(draft.id);
      const replacement: AiVariantDraft = {
        ...draft,
        id: response.job_id,
        status: "working",
        output: "",
        error: undefined,
        baseChapterVersion: response.base_chapter_version,
      };
      setVariantDrafts((current) =>
        current.map((item) => (item.id === draft.id ? replacement : item)),
      );
      let terminal = false;
      for (let attempt = 0; attempt < 300; attempt++) {
        const state = await api.job(response.job_id);
        const updated: AiVariantDraft = {
          ...replacement,
          output: state.output || "",
          status:
            state.status === "COMPLETED"
              ? "ready"
              : state.status === "FAILED" || state.status === "CANCELLED"
                ? "failed"
                : "working",
          error: state.error,
        };
        setVariantDrafts((current) =>
          current.map((item) => (item.id === response.job_id ? updated : item)),
        );
        if (isGenerationTerminal(state.status)) {
          terminal = true;
          break;
        }
        await new Promise((ok) => setTimeout(ok, 500));
      }
      if (!terminal) {
        await api.cancel(response.job_id).catch(() => undefined);
        setVariantDrafts((current) =>
          current.map((item) =>
            item.id === response.job_id
              ? { ...item, status: "failed", error: VARIANT_TIMEOUT_ERROR }
              : item,
          ),
        );
      }
    } catch {
      setVariantDrafts((current) =>
        current.map((item) =>
          item.id === draft.id
            ? { ...item, status: "failed", error: "生成失败，请重试" }
            : item,
        ),
      );
    }
  }
  async function retryDraft(draft: { id: string; status: string }) {
    const variant = variantDrafts.find((item) => item.id === draft.id);
    if (variant) return retryVariant(variant);
    if (draft.status !== "failed") return;
    setJob((current: any) => ({ ...current, status: "GENERATING", output: "", error: undefined }));
    try {
      const response = await api.retryGeneration(draft.id);
      setJob((current: any) => ({...current,id:response.job_id,status:"GENERATING",base_chapter_version:response.base_chapter_version}));
      generationRecovery.save(namespace,{chapterId:s.chapterId,jobId:response.job_id,original:job?.original,baseChapterVersion:response.base_chapter_version});
      const recovered = await recoverGenerationJob(response.job_id,api.job,(state)=>setJob((current:any)=>({...current,...state,output:state.output||current?.output||""})));
      if (!recovered) setJob((current:any)=>({...current,status:"FAILED",error:"生成连接中断且恢复超时，请重试"}));
    } catch {
      setJob((current:any)=>({...current,status:"FAILED",error:"生成连接中断，恢复失败，请重试"}));
    } finally {
      generationRecovery.remove(namespace,s.chapterId);
    }
  }
  async function openDraftConflict(draft: { output: string }) {
    if (!chapter.data) return;
    const variant=variantDrafts.find((item)=>item.output===draft.output);
    const generationVersion=variant?.baseChapterVersion??job?.base_chapter_version??chapter.data.version;
    const server=await api.chapter(s.chapterId);
    const local={chapterId:s.chapterId,content:draft.output,document:undefined,baseVersion:generationVersion,updatedAt:new Date().toISOString()};
    const value={chapterId:s.chapterId,local,server,detectedAt:new Date().toISOString()};
    conflicts.save(value,namespace);setConflict(value);
    setSaveState((current)=>reduceSaveState(current,{type:"save-failed",conflict:true}));
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
  if (studioModule !== "NOVEL") return <ModuleWorkspaceRoutes module={studioModule} onModuleChange={setStudioModule} novelId={s.novelId} actor={s.actor?.displayName || "本机作者"} scope={{workspace:scope?.workspaceName || "本机作品", project:scope?.projectName || "当前小说", storyline:scope?.storylineName || "默认故事线", branch:scope?.branchName || "主线"}} />;
  const moduleShell = (status: React.ReactNode, main: React.ReactNode) => (
    <AppShell module={studioModule} onModuleChange={setStudioModule}
      scope={{workspace: scope?.workspaceName || "本机作品", project: scope?.projectName || "当前小说", storyline: scope?.storylineName || "默认故事线", branch: scope?.branchName || "主线"}}
      actor={s.actor?.displayName || "本机作者"} sidebar={<></>} main={main} inspector={<></>} status={status} />
  );
  if ((studioModule as string) === "IMAGE")
    return <AppShell module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} sidebar={<></>} main={<><MultimodalDirectorWorkspace mode="image" novelId={s.novelId}/><VisualContextPanel novelId={s.novelId}/><VisionAnalysisPanel novelId={s.novelId}/><ImageGenerationPanel novelId={s.novelId}/></>} inspector={<></>} status={<>图片工作区</>} />;
  if ((studioModule as string) === "VIDEO")
    return <AppShell module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} sidebar={<></>} main={s.novelId?<><MultimodalDirectorWorkspace mode="video" novelId={s.novelId}/><ScreenplayPanel novelId={s.novelId}/></>:<p className="novel-help">请先打开小说项目，再进入视频工作区。</p>} inspector={<></>} status={<>视频工作区</>} />;
  if ((studioModule as string) === "AUDIO")
    return <AppShell module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} sidebar={<></>} main={<><SpeechSynthesisPanel novelId={s.novelId}/><AudiobookManifestPanel novelId={s.novelId}/></>} inspector={<></>} status={<>声音工作区</>} />;
  if ((studioModule as string) === "PLUGIN")
    return <AppShell module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} sidebar={<></>} main={<PluginManagerPanel/>} inspector={<></>} status={<>插件管理</>} />;
  if ((studioModule as string) === "WORKFLOW")
    return <WorkflowWorkspaceRoute module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} novelId={s.novelId}/>;
  if ((studioModule as string) === "ASSETS")
    return <AssetWorkspaceRoute module={studioModule} onModuleChange={setStudioModule} scope={{workspace:scope?.workspaceName||"本机作品",project:scope?.projectName||"当前小说",storyline:scope?.storylineName||"默认故事线",branch:scope?.branchName||"主线"}} actor={s.actor?.displayName||"本机作者"} novelId={s.novelId}/>;
  if (studioModule !== "NOVEL")
    return (
      <DesignSystemFixture
        initialModule={studioModule}
        onModuleChange={setStudioModule}
        runtimeScope={
          scope
            ? {
                workspace: scope.workspaceName || "当前工作区",
                project: scope.projectName || "当前小说",
                storyline: scope.storylineName || "默认故事线",
                branch: scope.branchName || "主分支",
              }
            : {
                workspace: "本机作品",
                project: "当前小说",
                storyline: "默认故事线",
                branch: "主线",
              }
        }
        runtimeActor={s.actor?.displayName || "本机作者"}
        runtimeStatus={<>保存：{saveStateLabel(saveState)}</>}
      />
    );
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
    ? saveStateLabel(saveState)
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
        />
      </div>
      <div className="novel-sidebar-heading novel-sidebar-heading--tools"><span>工作区</span><strong>创作工具</strong></div>
      <FeatureLauncher
        selectedId={panel}
        expandedGroups={featureGroups}
        onSelect={setPanel}
        onToggleGroup={(id) => setFeatureGroups((current) => ({ ...current, [id]: !current[id] }))}
      />
    </div>
  );
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
          ready={!!chapter.data}
          onSave={dispatchSave}
        />
      </div>
      {chapter.data ? (
        <ChapterEditor
          content={text}
          document={doc}
          onChange={edit}
          onSelection={setSelection}
        />
      ) : (
        <section className="notice" aria-live="polite">
          <strong>当前还没有打开的章节</strong>
          <p>在左侧新建或选择章节，开始写作。</p>
        </section>
      )}
      <Panel type={panel} chapter={chapter.data} scope={scope} novelId={s.novelId} onOpenChapter={s.setChapter} />
    </div>
  );
  const inspector = (
    <div className="novel-inspector-stack">
      <section className="novel-inspector-context" aria-label="当前写作上下文"><span>当前章节</span><strong>{chapter.data?.title || "未选择章节"}</strong><small>{chapter.data ? `第 ${chapter.data.number} 章 · 版本 ${chapter.data.version}` : "从左侧章节树选择章节"}</small></section>
      <WritingGoalPanel novelId={s.novelId} />
      <AiWritingPanel
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
        job && job.status !== "CANCELLED"
          ? {
              id: job.id,
              output: job.output || "",
              original: job.original,
              status:
                job.status === "GENERATING"
                  ? "working"
                  : job.status === "FAILED"
                    ? "failed"
                    : "ready",
              error: job.error,
              latency_ms: job.latency_ms,
              acceptBlocked: job.acceptBlocked,
              acceptBlockedReason: job.acceptBlockedReason,
              tracked: !["generation-failed", "selection-required"].includes(job.id),
            }
          : undefined
      }
      onGenerate={(operation: AiOperation, request, style) =>
        runAI(operation, request, style)
      }
      onCancel={cancelActiveGeneration}
      onAccept={async (draft) => {
        setDraftAction("accept");
        try {
          const variant=variantDrafts.find(item=>item.id===draft.id);
          const generationVersion=variant?.baseChapterVersion??job?.base_chapter_version;
          if (isRecoveredDraftStale(generationVersion,chapter.data?.version)) {
            const server=await api.chapter(s.chapterId);
            const local={chapterId:s.chapterId,content:draft.output,document:undefined,baseVersion:generationVersion,updatedAt:new Date().toISOString()};
            const value={chapterId:s.chapterId,local,server,detectedAt:new Date().toISOString()};
            conflicts.save(value,namespace);setConflict(value);
            setSaveState((current)=>reduceSaveState(current,{type:"save-failed",conflict:true}));
            setJob((current:any)=>({...current,error:"正文已有更新，AI 草稿已保留，请先处理冲突。",acceptBlocked:true,acceptBlockedReason:"正文已在生成期间发生变化，请先处理版本冲突。"}));
            return;
          }
          const accepted = await api.accept(draft.id,draft.output,generationVersion);
          await Promise.all(variantDrafts.filter(item=>item.id!==draft.id).map(item=>api.reject(item.id).catch(()=>undefined)));
          setVariantDrafts([]);setActiveVariant(0);
          setJob(undefined);
          if (accepted?.chapter?.id && accepted.chapter.id !== s.chapterId) {
            await chapters.refetch();
            s.setChapter(accepted.chapter.id);
          } else {
            await chapter.refetch();
          }
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            const server = await api.chapter(s.chapterId);
            const local = {
              chapterId: s.chapterId,
              content: draft.output,
              document: undefined,
              baseVersion: job.base_chapter_version,
              updatedAt: new Date().toISOString(),
            };
            const value = {
              chapterId: s.chapterId,
              local,
              server,
              detectedAt: new Date().toISOString(),
            };
            conflicts.save(value, namespace);
            setConflict(value);
            setSaveState((current) =>
              reduceSaveState(current, { type: "save-failed", conflict: true }),
            );
            setJob((current: any) => ({
              ...current,
              error: "正文已有更新，AI 草稿已保留，请先处理冲突。",
            }));
            return;
          }
          throw error;
        } finally {
          setDraftAction(undefined);
        }
      }}
      onReject={async (draft) => {
        setDraftAction("reject");
        try {
          await api.reject(draft.id);
          if(variantDrafts.length){const remaining=variantDrafts.filter(item=>item.id!==draft.id);setVariantDrafts(remaining);setActiveVariant(0)}else setJob(undefined);
        } finally {
          setDraftAction(undefined);
        }
      }}
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
      {conflict && (
        <ConflictDialog
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
            drafts.save(next, namespace);
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
function ContinuityCheckPanel({ projectId }: { projectId: string }) {
  const rules = useQuery({ queryKey: ["world-rules", projectId, "APPROVED"], queryFn: () => api.worldRules(projectId, "APPROVED"), enabled: !!projectId });
  const qc=useQueryClient();
  const stored=useQuery({queryKey:["continuity-findings",projectId],queryFn:()=>api.continuityFindings(projectId),enabled:!!projectId});
  const [facts, setFacts] = useState("{\n  \"events\": [],\n  \"locations\": [],\n  \"knowledge\": []\n}");
  const [result, setResult] = useState<any>();
  const [error, setError] = useState("");
  const [filter,setFilter]=useState('ALL');
  async function run() { try { setError(""); const parsed = JSON.parse(facts); setResult(await api.continuityCheck(projectId, { ...parsed, world_rules: rules.data?.items || [] })); qc.invalidateQueries({queryKey:["continuity-findings",projectId]}); } catch (reason) { setError(reason instanceof SyntaxError ? "事实 JSON 格式错误" : "检查失败，请稍后重试"); } }
  const rows=[...(result?.findings||[]),...(stored.data||[])].filter((item,index,all)=>all.findIndex(other=>other.id===item.id)===index).filter(item=>filter==='ALL'||item.finding_type===filter);
  const types=Array.from(new Set([...(result?.findings||[]),...(stored.data||[])].map(item=>item.finding_type).filter(Boolean)));
  return <section className="panel"><h2>一致性检查</h2><p>检查人物、时间线和已批准世界规则。输入格式为 JSON。</p><textarea value={facts} onChange={e => setFacts(e.target.value)} rows={9} style={{ width: "100%" }} /><button className="primary" onClick={run} disabled={!projectId}>运行检查</button>{error && <p role="alert">{error}</p>}{(rules.isError||stored.isError)&&<p role="alert">问题清单加载失败，请稍后重试。</p>}<div><strong>问题清单</strong>{stored.isLoading&&<p role="status">正在加载历史问题…</p>}<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">全部类型</option>{types.map(type=><option key={type} value={type}>{type}</option>)}</select>{!stored.isLoading&&!rows.length&&<p className="notice">暂无问题</p>}{rows.map((item:any)=><p key={item.id} className="notice">[{item.severity}] {item.description} {item.status==='RESOLVED'?<small>已处理</small>:<button onClick={async()=>{try{await api.resolveContinuityFinding(projectId,item.id);qc.invalidateQueries({queryKey:["continuity-findings",projectId]});setResult((old:any)=>old?{...old,findings:old.findings.map((x:any)=>x.id===item.id?{...x,status:'RESOLVED'}:x)}:old)}catch{setError('标记问题失败，请稍后重试')}}}>标记已处理</button>}</p>)}</div></section>;
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
  novelId,
  onOpenChapter,
}: {
  type: string;
  chapter?: Chapter;
  scope?: Scope;
  novelId: string;
  onOpenChapter: (id:string)=>void;
}) {
  if (!scope && ["members", "permissions", "audit", "snapshots"].includes(type))
    return (
      <section className="panel">
        <h2>团队协作</h2>
        <p className="notice">进入团队创作空间后可查看成员、权限和协作记录。</p>
      </section>
    );
  if (type === "history")
    return chapter ? <RevisionHistory chapter={chapter} scope={scope} /> : null;
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
  if (type === "overview") return <WritingGoalPanel novelId={novelId} />;
  if (type === "check") return <ContinuityCheckPanel projectId={novelId} />;
  if (type === "diagnostics") return <RuntimeDiagnosticsPanel scope={scope} />;
  if (type === "agents") return <>{chapter&&<AgentActivityCenter novelId={chapter.novel_id} />}{chapter&&<AgentJobHistory novelId={chapter.novel_id} />}<AgentTeamPanel chapter={chapter} /></>;
  if (type === "adaptation") return <AdaptationPanel novelId={chapter?.novel_id} branchId={scope?.branchId} />;
  if (type === "screenplay") return <ScreenplayPanel novelId={chapter?.novel_id} />;
  if (type === "assets") return <AssetLibraryPanel novelId={chapter?.novel_id || useStudio.getState().novelId || ""} />;
  if (type === "exports") return <ExportPanel novelId={chapter?.novel_id || useStudio.getState().novelId || ""} />;
  if (type === "knowledge") return <NovelImportPanel novelId={chapter?.novel_id || useStudio.getState().novelId || ""} />;
  if (type === "research") return <CapabilityPlaceholder title="研究资料" service="Research Assistant" description="资料库、参考文献与研究笔记窗口已预留，暂不读取外部网络。" apiPrefix="/api/v1/research" />;
  if (type === "settings") return <><AiControlCenter /><VideoProviderSettingsV2 /><VideoCallbackSecurityStatus /></>;
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
function RevisionHistory({
  chapter,
  scope,
}: {
  chapter: Chapter;
  scope?: Scope;
}) {
  const [selected, setSelected] = useState<number>();
  const q = useQuery({
    queryKey: ["revision-history", scope, chapter.id],
    queryFn: () =>
      scope ? api.history(scope, chapter.id) : api.legacyHistory(chapter.id),
  });
  const detail = useQuery({
    queryKey: ["revision-detail", scope, chapter.id, selected],
    queryFn: () => api.revisionDetail(scope!, chapter.id, selected!),
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
  const selectedRevision: RevisionDetail | null =
    selected === undefined || !preview
      ? null
      : {
          ...revisions.find((v) => v.version === selected)!,
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
        try {
          await api.restore(
            chapter.id,
            request.revisionVersion,
            request.expectedCurrentVersion,
          );
          location.reload();
        } catch (error: any) {
          if (error?.status === 409)
            throw {
              kind: "conflict",
              message: error.message,
              currentVersion: error.problem?.details?.actual_version,
            };
          if (error?.status === 403)
            throw { kind: "unauthorized", message: error.message };
          throw error;
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

