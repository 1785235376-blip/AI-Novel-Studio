import {ScriptScreenplayBridge} from './ScriptScreenplayBridge';
import { useStudio } from '../store';
import { checkedStoryboardReceipt, checkedStoryboardCapabilities, type StoryboardEditorHost } from './storyboardEditorHandoff';
import type { StoryboardReceipt } from './studioStoryboardContract';
import { useLocalHostSession } from '../localHostSession';
import { studioClient, studioTransport } from './studioClient';
import { studioProductionClient } from './studioProductionClient';
import { StoryboardProductionPanel } from './StoryboardProductionPanel';
// UX-PRODUCT batch 3 (UX-05): the shot workspace reuses the same receipt/document
// context as the inspector above; explicit Prompt adoption uses its original gated owner.
import { StoryboardWorkspacePanel } from '../storyboard/StoryboardWorkspacePanel';
import { ScreenplayPresetPanel } from './ScreenplayPresetPanel';
import { instantiateScreenplayPreset, type ScreenplayPreset } from './screenplayPresets';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AIEnvironmentSummary } from '../AIEnvironmentSummary';
import { api, ApiError, type Chapter, type CollaborationContext } from '../api';
import { AppShell, type ScopeLabels, type StudioModule } from '../ui/AppShell';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { creativeClient, type CreativeHistory } from './client';
import { AssetBrowser, type AssetSelection } from './AssetBrowser';
import { ProjectTimeline } from './ProjectTimeline';
import { CreativeCanvas } from './CreativeCanvas';
import { DirectorSheetExportPanel } from './DirectorSheetExportPanel';
import { ScreenplayExportPanel } from './ScreenplayExportPanel';
import { ProductionTimeline } from './ProductionTimeline';
import { AIDirectorPanel } from './AIDirectorPanel';
import { SourceAdaptationPanel } from './SourceAdaptationPanel';
import { WORKSPACE_MODES, creativeAuthoringProblems, documentInput, modeForDocument, newDocument, newScene, type CreativeAsset, type CreativeCapabilities, type CreativeDocument, type CreativeInput, type CreativeReferences, type WorkspaceMode } from './types';
import './creative.css';

type Draft = { value: CreativeInput; base?: CreativeDocument; dirty: boolean; blocked?: boolean };
type Operation = { kind: 'SAVE' | 'VERIFY' | 'DERIVE' | 'RESTORE'; mode: WorkspaceMode; draft: Draft };
// Compare the original writable projection, preserving exact values and array
// order while allowing File/PG object keys to arrive in a different order.
function canonicalInput(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalInput);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0).map(([key, child]) => [key, canonicalInput(child)]));
  return value;
}
const sameInput = (value: CreativeInput, base: CreativeDocument) => JSON.stringify(canonicalInput(documentInput(value))) === JSON.stringify(canonicalInput(documentInput(base)));
export type CreativeWorkspaceProps = { storyboardHost?: StoryboardEditorHost; enabled: boolean; novelId: string; context: CollaborationContext; scope: ScopeLabels; actor: string; chapter?: Chapter; savedChapters?: Chapter[]; savedChaptersReady?: boolean; onRefreshSavedChapters?: () => void; chapterCount: number; manuscriptReady: boolean; novelMain: ReactNode; novelSidebar: ReactNode; novelInspector: ReactNode; novelStatus: ReactNode; commonStatus?: ReactNode; onExit: () => void; onModuleChange: (module: StudioModule) => void; onGlobalSearch?: () => void };
/** This route supplies module content to the one protected AppShell. It never owns manuscript writes. */
export function CreativeWorkspace(props: CreativeWorkspaceProps) {
  const identity = JSON.stringify([props.novelId, props.context.sessionToken, props.context.localHostToken, props.context.actor?.id, props.context.scope]);
  if (!props.enabled) return <EmptyState title="V2 创作工作台未启用" detail="实验功能默认关闭，V1 验收模式不加载此工作台。" />;
  return <CreativeWorkspaceSession key={identity} {...props} />;
}
function CreativeWorkspaceSession({ novelId, context, scope, actor, chapter, savedChapters, savedChaptersReady, onRefreshSavedChapters, chapterCount, manuscriptReady, novelMain, novelSidebar, novelInspector, novelStatus, commonStatus, onExit, onModuleChange, onGlobalSearch, storyboardHost }: CreativeWorkspaceProps) {
  const client = useMemo(() => creativeClient(novelId, context), [novelId, context.sessionToken, context.localHostToken, context.actor?.id, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const loadSavedChapter = useCallback((id: string) => api.chapter(id, context), [client]);
  const [intake] = useState(() => {
    if (!storyboardHost) return undefined;
    try {
      if (!storyboardHost.isCurrent()) throw new Error('交接请求已经失效。');
      checkedStoryboardCapabilities(storyboardHost.prepared.capabilities);
      const row = checkedStoryboardReceipt(storyboardHost.prepared.request, storyboardHost.prepared.receipt);
      return { row, capabilities: storyboardHost.prepared.capabilities, requestId: storyboardHost.prepared.request.requestId };
    } catch { return undefined; }
  });
  const [mode, setMode] = useState<WorkspaceMode>(storyboardHost ? 'STORYBOARD' : 'NOVEL'), [capabilities, setCapabilities] = useState<CreativeCapabilities | undefined>(intake?.capabilities), [documents, setDocuments] = useState<CreativeDocument[]>(intake ? [intake.row] : []), [drafts, setDrafts] = useState<Partial<Record<WorkspaceMode, Draft>>>(intake ? { STORYBOARD: { value: documentInput(intake.row), base: intake.row, dirty: false } } : {}), [loading, setLoading] = useState(!storyboardHost), [documentsReady, setDocumentsReady] = useState(!!intake), [operation, setOperation] = useState<Operation>(), [directorBusy, setDirectorBusy] = useState(false), [error, setError] = useState(storyboardHost && !intake ? '分镜交接请求无效，请返回创作图重新核对。' : ''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false), [references, setReferences] = useState<CreativeReferences>(), [assets, setAssets] = useState<CreativeAsset[]>(), [assetLoading, setAssetLoading] = useState(false), [assetError, setAssetError] = useState(false), [asset, setAsset] = useState<AssetSelection>(), [sceneId, setSceneId] = useState<string>(), [shotId, setShotId] = useState<string>(), [history, setHistory] = useState<CreativeHistory>(), [restoreVersion, setRestoreVersion] = useState<number>(), [pendingNavigation, setPendingNavigation] = useState<(() => void)>(), [discardChecked, setDiscardChecked] = useState(false), [serverCandidate, setServerCandidate] = useState<CreativeDocument>();
  const busy = operation !== undefined;
  const hostOwner = useRef(useLocalHostSession.getState().epoch);
  const hostEpoch = useLocalHostSession(state => !context.scope && !context.actor ? state.epoch : 0);
  const production = useMemo(() => studioProductionClient(novelId, context), [client]);
  const studio = useMemo(() => studioClient(novelId, context), [client]);
  const [productionDirty, setProductionDirty] = useState(false);
  const [productionReceipt, setProductionReceipt] = useState<StoryboardReceipt>();
  // UX-05: the shot workspace reads on demand only, so opening the creative module
  // never adds a request or duplicate evidence to the existing inspector.
  const [shotsOpen, setShotsOpen] = useState(false);
  const [adaptationDraft, setAdaptationDraft] = useState<Record<string, unknown>>();
  const keepAdaptationDraft = useCallback((value: Record<string, unknown> | undefined) => setAdaptationDraft(value), []);
  const revoked = useRef(false);
  const mounted = useRef(true), mutationLock = useRef(false), readEpoch = useRef(0), assetEpoch = useRef(0);
  const currentMode = useRef(mode); currentMode.current = mode;
  const currentDrafts = useRef(drafts); currentDrafts.current = drafts;
  const draft = drafts[mode], dirtyModes = Object.entries(drafts).filter(([, value]) => value?.dirty).map(([key]) => key as WorkspaceMode);
  const hostRef = useRef(storyboardHost); hostRef.current = storyboardHost;
  const requestKey = storyboardHost ? JSON.stringify(storyboardHost.prepared.request) : undefined;
  const admittedKey = useRef(intake ? requestKey : undefined);
  const admittedRequest = useRef(intake?.requestId);
  const observedRequest = useRef(requestKey);
  const retiredRequests = useRef(new Set<string>());
  if (observedRequest.current !== requestKey) { if (observedRequest.current !== undefined) retiredRequests.current.add(observedRequest.current); observedRequest.current = requestKey; }
  const hostCurrent = () => !hostRef.current || !retiredRequests.current.has(JSON.stringify(hostRef.current.prepared.request)) && hostRef.current.isCurrent() && admittedKey.current === JSON.stringify(hostRef.current.prepared.request);
  if (storyboardHost && !storyboardHost.isCurrent()) revoked.current = true;
  const canEdit = hostCurrent() && !revoked.current && capabilities?.enabled === true && capabilities.can_mutate === true && !denied && !draft?.blocked;
  const deny = () => { setProductionReceipt(undefined); revoked.current = true; readEpoch.current++; assetEpoch.current++; setLoading(false); setAssetLoading(false); setDenied(true); setCapabilities(undefined); setDocumentsReady(false); setDocuments([]); setReferences(undefined); setAssets(undefined); setAsset(undefined); setServerCandidate(undefined); setHistory(undefined); setRestoreVersion(undefined); setNotice(''); setPendingNavigation(undefined); setDiscardChecked(false); setError('当前身份或分支已失去访问权限。内容已锁定；请恢复授权后重新打开工作台。'); };
  useLayoutEffect(() => {
    if (!storyboardHost) return;
    const check = () => { if (!hostRef.current?.isCurrent()) { revoked.current = true; deny(); } };
    const offStudio = useStudio.subscribe(check), offHost = useLocalHostSession.subscribe(check);
    check();
    return () => { offStudio(); offHost(); };
  }, [!!storyboardHost]);
  useLayoutEffect(() => {
    if (!storyboardHost || admittedKey.current === requestKey) return;
    const requested = storyboardHost.prepared.request.requestId, target = currentDrafts.current.STORYBOARD;
    if (revoked.current || retiredRequests.current.has(requestKey!) || !storyboardHost.isCurrent() || mutationLock.current || target?.dirty || target?.blocked || productionDirty || directorBusy || busy || requested <= (admittedRequest.current ?? 0)) {
      setError('当前分镜有未保存输入或交接请求已失效，未替换文档。'); return;
    }
    try {
      checkedStoryboardCapabilities(storyboardHost.prepared.capabilities);
      const row = checkedStoryboardReceipt(storyboardHost.prepared.request, storyboardHost.prepared.receipt);
      admittedRequest.current = requested; admittedKey.current = requestKey;
      const next = { STORYBOARD: { value: documentInput(row), base: row, dirty: false } };
      currentDrafts.current = next; setDrafts(next); setDocuments([row]); setCapabilities(storyboardHost.prepared.capabilities); setDocumentsReady(true); setMode('STORYBOARD'); setError('');
      setHistory(undefined); setServerCandidate(undefined); setSceneId(undefined); setShotId(undefined);
    } catch { setError('分镜交接回执无效，未替换当前文档。'); }
  }, [requestKey]);
  useEffect(() => { if (!context.scope && !context.actor && hostOwner.current !== hostEpoch) deny(); }, [hostEpoch]);
  const describe = (value: unknown) => value instanceof ApiError ? `${value.message} (${value.problem.code})` : '请求未完成，请检查连接后重试。';
  const read = async (signal?: AbortSignal) => { if (storyboardHost) return; const ticket = ++readEpoch.current; setLoading(true); try { const caps = await client.capabilities(signal); if (!mounted.current || revoked.current || signal?.aborted || ticket !== readEpoch.current) return; setCapabilities(caps); if (!caps.enabled) { setDocumentsReady(false); setDocuments([]); return; } const rows = await client.list(signal); if (!mounted.current || revoked.current || signal?.aborted || ticket !== readEpoch.current) return; setDocuments(rows.items); setDocumentsReady(true); setError(''); } catch (value) { if (mounted.current && !revoked.current && !signal?.aborted && ticket === readEpoch.current) { setError(describe(value)); if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } } finally { if (mounted.current && !revoked.current && !signal?.aborted && ticket === readEpoch.current) setLoading(false); } };
  const readAssets = async (signal?: AbortSignal) => { if (revoked.current) return; const ticket = ++assetEpoch.current; setAssetLoading(true); const result = await Promise.allSettled([client.references(signal), client.assets(signal)]); if (!mounted.current || revoked.current || signal?.aborted || ticket !== assetEpoch.current) return; setReferences(result[0].status === 'fulfilled' ? result[0].value : undefined); setAssets(result[1].status === 'fulfilled' ? result[1].value : undefined); setAssetError(result.some(row => row.status === 'rejected')); setAssetLoading(false); };
  useEffect(() => { mounted.current = true; const controller = new AbortController(); void read(controller.signal); return () => { mounted.current = false; controller.abort(); readEpoch.current++; assetEpoch.current++; }; }, [client]);
  useEffect(() => { if (!capabilities?.enabled || denied) return; const controller = new AbortController(); void readAssets(controller.signal); return () => controller.abort(); }, [client, capabilities?.enabled, denied]);
  // A stage chosen during bootstrap must wait for a successful scoped list, not
  // mistake the initial empty array for an empty project. Existing drafts encode
  // user intent (including clean explicit-new drafts) and must never be replaced.
  useEffect(() => {
    if (storyboardHost || mode === 'NOVEL' || loading || !documentsReady || !capabilities?.enabled || denied || revoked.current) return;
    setDrafts(current => {
      if (revoked.current || current[mode]) return current;
      const existing = documents.find(row => modeForDocument(row.mode) === mode);
      return { ...current, [mode]: existing ? { value: documentInput(existing), base: existing, dirty: false } : { value: newDocument(mode, manuscriptReady ? chapter?.id : undefined), dirty: false } };
    });
  }, [mode, loading, documentsReady, capabilities?.enabled, denied, documents, manuscriptReady, chapter?.id]);
  useEffect(() => { if (!dirtyModes.length && !adaptationDraft && !productionDirty) return; const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; }; window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent); }, [dirtyModes.length, adaptationDraft, productionDirty]);
  const setDraft = (next: Draft, target: WorkspaceMode = mode) => { currentDrafts.current = { ...currentDrafts.current, [target]: next }; setDrafts(current => ({ ...current, [target]: next })); };
  const changeMode = (next: WorkspaceMode) => {
    if (storyboardHost || busy || directorBusy || productionDirty || denied || mutationLock.current) return;
    setMode(next); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); setSceneId(undefined); setShotId(undefined); setAsset(undefined); setNotice(''); setError('');
  };
  const change = (value: CreativeInput) => { if (!hostCurrent() || revoked.current || !canEdit || busy || directorBusy || productionDirty || mutationLock.current) return; setDraft({ ...draft, value, dirty: !draft?.base || !sameInput(value, draft.base) }); setNotice(''); };
  const navigate = (action: () => void) => { if (busy || directorBusy || productionDirty || mutationLock.current) return; if (revoked.current) { action(); return; } if (dirtyModes.length || adaptationDraft) { setPendingNavigation(() => action); setDiscardChecked(false); } else action(); };
  const openDocument = (row: CreativeDocument) => { if (storyboardHost || revoked.current) return; const target = modeForDocument(row.mode); if (currentDrafts.current[target]?.dirty) { setNotice(`“${row.title}”已保存在服务端。请先保存或处理${target}中的未保存草稿，再打开。`); return; } setMode(target); setDraft({ value: documentInput(row), base: row, dirty: false }, target); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); setSceneId(undefined); setShotId(undefined); setError(''); };
  const save = async () => {
    if (!hostCurrent() || revoked.current || !draft || !canEdit || productionDirty || mutationLock.current || !draft.dirty || creativeAuthoringProblems(draft.value).length || !draft.value.title.trim()) return;
    const originMode = mode, originDraft = draft; mutationLock.current = true; setOperation({ kind: 'SAVE', mode: originMode, draft: originDraft }); setError(''); setNotice('');
    try { const row = originDraft.base ? await client.update(originDraft.base.id, originDraft.base.version, originDraft.value) : await client.create(originDraft.value); if (!mounted.current || revoked.current || !hostCurrent()) return; setDocuments(rows => [...rows.filter(item => item.id !== row.id), row]); setDraft({ value: documentInput(row), base: row, dirty: false }, originMode); setNotice(`已保存“${row.title}” · v${row.version}`); }
    catch (value) { if (!mounted.current || revoked.current) return; setError(describe(value)); const uncertain = !(value instanceof ApiError) || value.status >= 500 || value.status === 409; if (uncertain) { setDraft({ ...originDraft, blocked: true }, originMode); setNotice('草稿已保留。版本冲突或写入回执不确定，继续写入前需核对服务端。'); } if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); }
    finally { mutationLock.current = false; if (mounted.current) setOperation(undefined); }
  };
  const checkServer = async () => { if (!draft || busy) return; const originMode = mode, originDraft = draft; const current = () => mounted.current && !revoked.current && currentMode.current === originMode && currentDrafts.current[originMode] === originDraft; setOperation({ kind: 'VERIFY', mode: originMode, draft: originDraft }); setError(''); try { if (originDraft.base) { const row = await client.get(originDraft.base.id); if (current()) { setServerCandidate(row); setDiscardChecked(false); } } else { await read(); if (current()) setNotice('已重新读取文档列表。请核对是否已经创建；导出本地草稿后再放弃此草稿，避免重复创建。'); } } catch (value) { if (mounted.current && !revoked.current) { if (current()) setError(describe(value)); if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } } finally { if (mounted.current) setOperation(undefined); } };
  const download = (value: unknown, name: string) => { const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url); };
  const exportDocument = async () => { if (!draft?.base || busy) return; try { const result = await client.export(draft.base.id); if (mounted.current && !revoked.current) download(result, `creative-${draft.base.id}.json`); } catch (value) { if (mounted.current && !revoked.current) { setError(describe(value)); if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } } };
  const readHistory = async () => { if (!draft?.base || busy) return; const id = draft.base.id; try { const result = await client.history(id); if (mounted.current && !revoked.current && currentMode.current === mode && currentDrafts.current[mode]?.base?.id === id) setHistory(result); } catch (value) { if (mounted.current && !revoked.current) { setError(describe(value)); if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } } };
  const derive = async (shotPolicy?: "DIRECTOR_NOTES", scriptBridge = false) => {
    if (!hostCurrent() || !mounted.current || revoked.current || !draft?.base || draft.dirty || !canEdit || busy || directorBusy || productionDirty || mutationLock.current || currentMode.current !== mode || currentDrafts.current[mode] !== draft) return;
    if (scriptBridge && (draft.value.mode !== 'SCRIPT' || !capabilities?.modes.includes('SCREENPLAY'))) return;
    const target = draft.value.mode === 'STORYBOARD' ? 'PRODUCTION' : 'STORYBOARD';
    mutationLock.current = true; setOperation({ kind: 'DERIVE', mode, draft }); setError('');
    try { const row = await (scriptBridge ? client.deriveScriptScreenplay(draft.base) : client.derive(draft.base, target, shotPolicy));
      if (scriptBridge && (row.mode !== 'SCREENPLAY' || row.status !== 'DRAFT' || row.version !== 1 || !row.id || row.id === draft.base.id || !Array.isArray(row.scenes) || row.scenes.map(scene => scene.action).join('') !== draft.base.script?.body || row.source_documents?.[draft.base.id]?.version !== draft.base.version || !/^[a-f0-9]{64}$/.test(row.source_documents?.[draft.base.id]?.digest || ''))) throw new Error('剧本底稿回执不匹配，请核对原文档目录，不自动重复创建。');
      if (scriptBridge && (!hostCurrent() || currentMode.current !== mode || currentDrafts.current[mode] !== draft)) return;
      if (mounted.current && !revoked.current) { setDocuments(rows => [...rows.filter(item => item.id !== row.id), row]); openDocument(row); setNotice(`已从当前已保存版本建立“${row.title}”。新文档保留来源绑定；没有调用模型或生成媒体。`); } }
    catch (value) { if (mounted.current && !revoked.current) { setError(describe(value)); if (!(value instanceof ApiError) || value.status >= 500 || value.status === 409) { setDraft({ ...draft, blocked: true }); setNotice('派生操作需核对服务端结果，请勿重复建立。'); } if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } }
    finally { mutationLock.current = false; if (mounted.current) setOperation(undefined); }
  };
  const scaffold = () => {
    if (!chapter || !manuscriptReady || mode !== 'SCREENPLAY' || !draft || draft.base || draft.value.scenes.length || chapter.content.length > 32000 || !canEdit) return;
    const scene = { ...newScene(1, chapter.id), heading: chapter.title, action: chapter.content };
    setDraft({ value: { ...draft.value, title: draft.value.title || `${chapter.title.slice(0, 220)} · 剧本底稿`, source_chapter_ids: [chapter.id], source_independent: false, scenes: [scene] }, dirty: true });
    setSceneId(scene.id); setNotice('已复制当前已保存章节到场景动作底稿。尚未进行剧本改编或调用模型，请自行拆分、编辑并保存。');
  };
  const restore = async () => {
    if (!hostCurrent() || revoked.current || !draft?.base || draft.dirty || !restoreVersion || !canEdit || mutationLock.current) return;
    mutationLock.current = true; setOperation({ kind: 'RESTORE', mode, draft }); setError('');
    try { const row = await client.restore(draft.base, restoreVersion); if (mounted.current && !revoked.current) { setDocuments(rows => rows.map(item => item.id === row.id ? row : item)); setDraft({ value: documentInput(row), base: row, dirty: false }); setHistory(undefined); setRestoreVersion(undefined); setNotice(`已将所选历史内容恢复为新版本 v${row.version}，其他历史版本仍保留。`); } }
    catch (value) { if (mounted.current && !revoked.current) { setError(describe(value)); if (!(value instanceof ApiError) || value.status >= 500 || value.status === 409) setDraft({ ...draft, blocked: true }); if (value instanceof ApiError && [401, 403].includes(value.status)) deny(); } }
    finally { mutationLock.current = false; if (mounted.current) setOperation(undefined); }
  };
  const usePreset = (preset: ScreenplayPreset) => {
    if (revoked.current || !mounted.current || mode !== 'SCREENPLAY' || !canEdit || !documentsReady || busy || directorBusy || mutationLock.current || currentDrafts.current.SCREENPLAY?.dirty || currentDrafts.current.SCREENPLAY?.blocked || !capabilities?.modes.includes('SCREENPLAY')) return;
    const next = { value: instantiateScreenplayPreset(preset), dirty: true };
    // Fence repeated clicks synchronously before React commits the next draft.
    currentDrafts.current = { ...currentDrafts.current, SCREENPLAY: next };
    setDraft(next, 'SCREENPLAY'); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); setSceneId(undefined); setShotId(undefined); setAsset(undefined); setError('');
    setNotice(`已从“${preset.title}”模板 v${preset.version} 建立未保存独立剧本。请替换写作提示并明确保存；原文档未修改。`);
  };
  const newDraft = () => { if (!storyboardHost && mode !== 'NOVEL' && !draft?.dirty && canEdit) { const kind = draft?.value.mode === 'SCRIPT' ? 'SCRIPT' : mode; setDraft({ value: kind === 'SCRIPT' ? { ...newDocument('SCRIPT'), source_independent: true } : newDocument(kind, manuscriptReady ? chapter?.id : undefined), dirty: false }); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); } };
  const productionCurrent = () => hostCurrent() && mounted.current && !revoked.current && (!!context.scope || !!context.actor || hostOwner.current === useLocalHostSession.getState().epoch) && ['DIRECTOR', 'STORYBOARD'].includes(currentMode.current);
  const productionWork = async <T,>(work: () => Promise<T>): Promise<T> => { if (!productionCurrent() || mutationLock.current) throw new ApiError({ status: 409, code: 'CREATIVE_OPERATION_BUSY', message: '当前操作尚未完成，请读取原回执。' }); mutationLock.current = true; setDirectorBusy(true); try { return await work(); } finally { mutationLock.current = false; if (mounted.current) setDirectorBusy(false); } };
  const stageLabel = WORKSPACE_MODES.find(item => item.id === mode)!.label;
  const baseLabel = draft?.base ? ` · 基于 v${draft.base.version}` : '';
  const operationCurrent = operation?.mode === mode && operation.draft === draft;
  const operationLabel = operation && { SAVE: '保存中…', VERIFY: '核对服务端版本中…', DERIVE: '建立派生文档中…', RESTORE: '恢复历史版本中…' }[operation.kind];
  const currentSaveState = denied ? '访问已锁定' : operationCurrent && operationLabel ? `${operationLabel}${baseLabel}` : loading ? '正在核对创作文档与权限…' : capabilities && !capabilities.enabled ? '创作 V2 未启用' : !documentsReady ? '文档与权限待核对' : !draft ? '正在准备草稿…' : draft.blocked ? `需核对保存结果 · 本地草稿保留${baseLabel}` : draft.dirty ? `未保存更改${draft.base ? baseLabel : ' · 仅本页内存'}` : draft.base ? `已保存 · v${draft.base.version}` : '新草稿 · 尚未保存到服务端';
  const otherDirtyLabels = WORKSPACE_MODES.filter(item => item.id !== mode && dirtyModes.includes(item.id)).map(item => item.label);
  const otherBlockedLabels = WORKSPACE_MODES.filter(item => item.id !== mode && drafts[item.id]?.blocked).map(item => item.label);
  const otherDraftStates = [operation && !operationCurrent ? `其他文档：${operationLabel}` : '', otherDirtyLabels.length ? `其他阶段未保存：${otherDirtyLabels.join('、')}（仅本页内存）` : '', otherBlockedLabels.length ? `其他阶段需核对：${otherBlockedLabels.join('、')}` : '', adaptationDraft ? '改编草稿未保存（仅本页内存）' : '', productionDirty ? '制作草稿待处理（仅本页内存）' : '', directorBusy ? '创作操作进行中…' : ''].filter(Boolean);
  const saveStatus = <>{mode === 'NOVEL' ? novelStatus : <><span role="status" aria-label="当前创作文档保存状态">当前{stageLabel}：{currentSaveState}</span>{commonStatus && <> · {commonStatus}</>}</>}<span> · V2 {mode}</span>{otherDraftStates.length > 0 && <span aria-label="其他创作草稿状态"> · {otherDraftStates.join('；')}</span>}{!capabilities?.can_mutate && <Badge tone="warning">{capabilities ? '只读' : '权限待核对'}</Badge>}</>;
  const content = <div className="creative-workspace"><ProjectTimeline allowedModes={storyboardHost ? ['STORYBOARD'] : undefined} mode={mode} onChange={changeMode} documents={denied ? [] : documents} chapterCount={chapterCount} dirtyModes={dirtyModes} />
    {storyboardHost && draft?.base && <p aria-label="原分镜精确文档">原分镜 {draft.base.id} · v{draft.base.version} · {storyboardHost.module}</p>}
    {pendingNavigation && <section className="creative-navigation-confirm" role="alert"><p>离开会关闭未保存的创作草稿。可以取消离开，先保存或导出。</p><Button onClick={() => { for (const [key, row] of Object.entries(drafts)) if (row?.dirty) download(row.value, `creative-unsaved-${key}.json`); if (adaptationDraft) download(adaptationDraft, 'adaptation-unsaved-draft.json'); }}>导出全部未保存草稿</Button><label><input type="checkbox" checked={discardChecked} onChange={e => setDiscardChecked(e.target.checked)} />确认放弃未保存草稿并离开</label><Button disabled={!discardChecked} onClick={() => { const action = pendingNavigation; setPendingNavigation(undefined); action(); }}>确认离开</Button><Button onClick={() => setPendingNavigation(undefined)}>继续编辑</Button></section>}
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="info">{notice}</StatusMessage>}
    {loading && <StatusMessage>正在核对创作文档与权限…</StatusMessage>}{!storyboardHost && !loading && !denied && (!capabilities || (capabilities.enabled && !documentsReady)) && <Button onClick={() => void read()}>重试读取工作台</Button>}
    {capabilities && !capabilities.enabled && <EmptyState title="服务端尚未启用创作 V2" detail="请由管理员启用 narrative_production_v2。当前工作台不会写入创作文档。" />}
    {!denied && mode === 'SCREENPLAY' && capabilities?.source_adaptation === 'HOST_SESSION_REQUIRED' && <StatusMessage tone="info">来源改编需要已验证的可信 Host 会话。普通手工创作仍可使用。</StatusMessage>}
    {!denied && capabilities?.source_adaptation === 'REVIEWED_LOCAL_MODEL' && <div className="creative-adaptation-slot" hidden={mode !== 'SCREENPLAY'}><SourceAdaptationPanel client={client} chapter={chapter} savedChapters={savedChapters} savedChaptersReady={savedChaptersReady} loadSavedChapter={loadSavedChapter} onRefreshSavedChapters={onRefreshSavedChapters} sourceReady={manuscriptReady} canMutate={capabilities.can_mutate && !busy && !mutationLock.current && !productionDirty} onBusyChange={setDirectorBusy} onDraftChange={keepAdaptationDraft} onDenied={deny} onDocument={row => { if (revoked.current) return; setDocuments(rows => [...rows.filter(item => item.id !== row.id), row]); openDocument(row); }} /></div>}
    {denied ? <EmptyState title="访问已锁定" detail="当前身份不可继续查看或写入创作文档。原正文的权限和草稿恢复仍由小说工作区管理。" /> : <><div id="creative-canvas-NOVEL" role="tabpanel" aria-labelledby="creative-stage-NOVEL" hidden={mode !== 'NOVEL'}>{novelMain}</div>{mode !== 'NOVEL' && <section id={`creative-canvas-${mode}`} role="tabpanel" aria-labelledby={`creative-stage-${mode}`}>
      {draft?.blocked && <section className="creative-conflict" role="alert"><strong>需要核对版本 · 本地草稿仍保留</strong><p>不会自动覆盖服务端，也不会自动重试不确定的写入。</p><Button disabled={busy} onClick={() => void checkServer()}>核对服务端版本</Button><Button onClick={() => download(draft.value, 'creative-unsaved-draft.json')}>导出保留草稿</Button>{!draft.base && <><label><input type="checkbox" checked={discardChecked} onChange={e => setDiscardChecked(e.target.checked)} />已核对文档列表，放弃本地未保存草稿</label><Button disabled={!discardChecked || busy} onClick={() => { setDraft({ value: newDocument(mode, manuscriptReady ? chapter?.id : undefined), dirty: false }); setNotice(''); setError(''); }}>放弃此草稿</Button></>}</section>}
      {serverCandidate && <section className="creative-conflict" aria-label="服务端版本核对"><h3>服务端 v{serverCandidate.version} · {serverCandidate.title}</h3><p>{serverCandidate.scenes.length} 场景 · {serverCandidate.shots.length} 镜头</p><details><summary>查看服务端完整内容</summary><pre>{JSON.stringify(documentInput(serverCandidate), null, 2)}</pre></details><label><input type="checkbox" checked={discardChecked} onChange={e => setDiscardChecked(e.target.checked)} />已核对并确认用服务端版本替换当前本地草稿</label><Button disabled={!discardChecked} onClick={() => { setDraft({ value: documentInput(serverCandidate), base: serverCandidate, dirty: false }); setServerCandidate(undefined); setHistory(undefined); setRestoreVersion(undefined); setError(''); setNotice('已采用核对后的服务端版本。'); }}>使用核对后的服务端版本</Button><Button onClick={() => setServerCandidate(undefined)}>保留本地草稿</Button></section>}
      {mode === 'SCREENPLAY' && capabilities?.modes.includes('SCRIPT') && <div className="creative-actions"><Button disabled={!canEdit || busy || directorBusy || !!draft?.dirty} onClick={() => { setDraft({ value: { ...newDocument('SCRIPT'), source_independent: true }, dirty: false }); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); setError(''); setNotice('已建立独立通用脚本草稿。填写标题与内容后保存。'); }}>新建独立通用脚本</Button>{draft?.value.mode === 'SCRIPT' && <Button disabled={!canEdit || busy || directorBusy || !!draft.dirty} onClick={() => { setDraft({ value: { ...newDocument('SCREENPLAY'), source_independent: true }, dirty: false }); setHistory(undefined); setRestoreVersion(undefined); setServerCandidate(undefined); setError(''); setNotice('已建立独立剧本草稿。'); }}>新建独立剧本</Button>}</div>}
      {mode === 'SCREENPLAY' && documentsReady && capabilities?.enabled && capabilities.modes.includes('SCREENPLAY') && <ScreenplayPresetPanel client={client} available={canEdit && !busy && !directorBusy && !draft?.dirty && !draft?.blocked} onUse={usePreset} onDenied={deny} />}
      {!storyboardHost && draft?.base && draft.value.mode === 'SCRIPT' && capabilities?.modes.includes('SCREENPLAY') && <ScriptScreenplayBridge source={draft.base} available={canEdit && !busy && !directorBusy && !productionDirty && !draft.dirty} isCurrent={() => hostCurrent() && !revoked.current && currentMode.current === mode && currentDrafts.current[mode] === draft} onCreate={() => void derive(undefined, true)} />}
      {draft?.base && mode === 'STORYBOARD' && <DirectorSheetExportPanel key={`${draft.base.id}:${draft.base.version}`} sheetKind="STORYBOARD"
        document={draft.base} available={!draft.dirty && !draft.blocked && !busy && !directorBusy && !denied && capabilities?.enabled === true}
        isCurrent={() => productionCurrent() && currentDrafts.current.STORYBOARD?.base === draft.base}
        request={client.storyboardSheetExport} onDenied={deny} />}
      {draft?.base && mode === 'SCREENPLAY' && <ScreenplayExportPanel key={`${draft.base.id}:${draft.base.version}`} client={client} document={draft.base} available={!draft.dirty && !draft.blocked && !busy && capabilities?.enabled === true} onDenied={deny} />}
      {draft?.base && draft.value.mode === "DIRECTOR" && draft.value.director_notes.length > 0 && <Button disabled={!canEdit || busy || directorBusy || draft.dirty || draft.blocked} onClick={() => void derive("DIRECTOR_NOTES")}>按已保存导演调度逐项建立分镜草稿</Button>}
      {draft && <CreativeCanvas allowNew={!storyboardHost} productionShots={productionReceipt && productionReceipt.document_snapshot.id === draft.base?.id && productionReceipt.document_snapshot.version === draft.base?.version && !draft.dirty ? productionReceipt.shots : undefined} productionApproved={productionReceipt?.approved} draft={draft.value} version={draft.base?.version} dirty={draft.dirty} saving={operation?.kind === 'SAVE' && operationCurrent} canEdit={canEdit && capabilities?.modes.includes(draft.value.mode) === true} busy={busy || directorBusy || productionDirty} selectedSceneId={sceneId} selectedShotId={shotId} onScene={setSceneId} onShot={setShotId} onChange={change} onSave={() => void save()} onNew={newDraft} onExport={draft.base ? () => void exportDocument() : undefined} onHistory={draft.base ? () => void readHistory() : undefined} onDerive={!storyboardHost && draft.base && ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD'].includes(draft.value.mode) ? () => void derive() : undefined} onScaffold={mode === 'SCREENPLAY' && !draft.base && !draft.value.scenes.length && manuscriptReady && chapter && chapter.content.length <= 32000 ? scaffold : undefined} sourceChapterTitle={draft.value.source_chapter_ids.includes(chapter?.id || '') ? chapter?.title : undefined} />}
      {history && <section className="creative-history" aria-label="创作文档历史"><h3>版本历史 · 当前 v{history.current_version}</h3><Button onClick={() => setHistory(undefined)}>关闭历史</Button>{history.items.map(row => <details key={row.version}><summary>v{row.version} · {row.title}</summary><pre>{JSON.stringify(documentInput(row), null, 2)}</pre><label className="creative-review-check"><input type="checkbox" disabled={busy || !canEdit || !!draft?.dirty || row.version === history.current_version} checked={restoreVersion === row.version} onChange={event => setRestoreVersion(event.target.checked ? row.version : undefined)} />已核对 v{row.version} 的完整内容；恢复会新建当前版本</label><Button disabled={busy || !canEdit || !!draft?.dirty || restoreVersion !== row.version} onClick={() => void restore()}>恢复 v{row.version} 为新版本</Button></details>)}</section>}
    </section>}<ProductionTimeline draft={mode === 'NOVEL' ? undefined : draft?.value} editable={canEdit && !busy} onChange={change} onShot={setShotId} /></>}
  </div>;
  return <AppShell module={storyboardHost?.module ?? "NOVEL"} onModuleChange={target => navigate(() => onModuleChange(target))} scope={scope} actor={actor} onGlobalSearch={onGlobalSearch} sidebar={<AssetBrowser returnLabel={storyboardHost?.returnLabel} mode={mode} documents={documents} draft={denied ? undefined : draft?.value} references={references} assets={assets} loading={assetLoading} error={assetError} selectedDocumentId={draft?.base?.id} onDocument={openDocument} onSelect={selected => { setAsset(selected); if (selected.kind === 'Scene') setSceneId(selected.id); if (selected.kind === 'Shot') setShotId(selected.id); }} onRetry={() => void readAssets()} novelSidebar={novelSidebar} onExit={() => navigate(onExit)} />} main={content} inspector={<>{!denied && draft?.base && ['DIRECTOR', 'STORYBOARD'].includes(mode) && <StoryboardProductionPanel key={draft.base.id} document={draft.base} client={client} studio={studio} production={production} active={!denied} editable={canEdit && !draft.dirty && !draft.blocked} busy={busy || directorBusy} isBusy={() => mutationLock.current} isCurrent={() => !!productionCurrent() && currentDrafts.current[mode]?.base?.id === draft.base?.id && !currentDrafts.current[mode]?.dirty && !currentDrafts.current[mode]?.blocked} perform={productionWork} onDocument={row => { if (!productionCurrent() || currentDrafts.current[mode]?.dirty) return; setDocuments(rows => rows.map(item => item.id === row.id ? row : item)); setDraft({ value: documentInput(row), base: row, dirty: false }, mode); }} onDenied={deny} onDirtyChange={setProductionDirty} onReceipt={setProductionReceipt} />}<Button onClick={() => setShotsOpen(true)} aria-expanded={shotsOpen}>按需打开镜头工作区</Button>{shotsOpen && <StoryboardWorkspacePanel projectId={novelId} transport={studioTransport({ ...context, scope: context.scope ? { ...context.scope } : undefined })} scope={context.scope} identity={`${novelId}|${draft?.base?.id ?? ''}`} active={!denied} denied={denied} writable={canEdit} onDocumentCommitted={(row, expectedTargetVersion) => { const current = currentDrafts.current[mode]; if (!productionCurrent() || current?.dirty || current?.blocked || current?.base?.id !== row.id || current.base.version !== expectedTargetVersion) throw new Error('当前文档或草稿已变化，请重新读取分镜。'); setDocuments(rows => rows.map(item => item.id === row.id ? row : item)); setDraft({ value: documentInput(row), base: row, dirty: false }, mode); }} busy={busy || directorBusy} isCurrent={() => !!productionCurrent() && currentDrafts.current[mode]?.base?.id === draft?.base?.id && !currentDrafts.current[mode]?.dirty && !currentDrafts.current[mode]?.blocked} read={async work => { if (revoked.current) throw new Error('身份或项目已改变，请重新打开工作区。'); return work(); }} mutate={async work => { if (revoked.current || !canEdit) throw new Error('当前身份不可修改分镜草稿。'); return productionWork(work); }} onUnavailable={deny} />}<div hidden={mode !== 'NOVEL'}>{novelInspector}</div><div hidden={mode === 'NOVEL' || !!storyboardHost}>{denied || !capabilities?.enabled ? <EmptyState title="导演协作暂不可用" detail="需要服务端启用 V2 并授权当前身份。" /> : !storyboardHost && <AIDirectorPanel client={client} documents={documents} canMutate={capabilities.can_mutate && !busy && !mutationLock.current && !productionDirty} onBusyChange={setDirectorBusy} onDenied={deny} asset={asset} environment={<AIEnvironmentSummary enabled={true} onboarding={{context, projectId: novelId}} onOpenModels={() => navigate(() => onModuleChange('CONTROL'))} />} onOpenModels={() => navigate(() => onModuleChange('CONTROL'))} onDocument={row => { if (revoked.current) return; setDocuments(rows => [...rows.filter(item => item.id !== row.id), row]); openDocument(row); }} />}</div></>} status={saveStatus} />;
}
