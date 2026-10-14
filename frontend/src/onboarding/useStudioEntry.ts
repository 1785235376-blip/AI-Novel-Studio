import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api';
import {
  STUDIO_ENTRY_CONTRACT, STUDIO_ENTRY_ERROR_CODES, STUDIO_INTENT_CATALOG, STUDIO_INTENT_CUSTOM_ID,
  STUDIO_INTENT_LABELS, STUDIO_INTENT_IDS, type ProductionWorkflowIntentValueInput, type ProductionWorkflowModuleId,
  type ProductionWorkflowPreset, type StudioEntryClient, type StudioEntryIntent, type StudioEntryProject,
  type StudioEntryProblem, type StudioEntryState, type StudioIntentDraft, type StudioProjectCreation,
  type StudioSuggestionPlan,
} from './studioEntryTypes';
import { studioBlankIntentValues, studioIntentIsSavable } from './studioEntryClient';

/**
 * Deterministic recommendations: the same selected intents always produce the same
 * layout, module list and node list. Everything here is advisory text — adopting it
 * writes the preference and nothing else.
 */
const MODULE_ORDER: readonly ProductionWorkflowModuleId[] = ['director', 'storyboard', 'image', 'video', 'audio', 'timeline', 'asset'];
const LAYOUTS: Readonly<Record<string, { layout: string; modules: readonly ProductionWorkflowModuleId[]; nodes: readonly string[]; preset: ProductionWorkflowPreset }>> = {
  blank: { layout: '空白画布：一个自由布局的工作区', modules: ['asset'], nodes: ['text_input'], preset: 'BLANK' },
  novel_writing: { layout: '以文本为中心的写作布局', modules: ['director', 'asset'], nodes: ['text_input', 'director_note'], preset: 'TEXT' },
  novel_adaptation: { layout: '改编布局：文本对照 + 分镜', modules: ['director', 'storyboard', 'asset'], nodes: ['text_input', 'director_note', 'human_review'], preset: 'TEXT' },
  ai_short_film: { layout: '短片布局：剧本 → 分镜 → 图像 → 视频', modules: ['director', 'storyboard', 'image', 'video', 'timeline', 'asset'], nodes: ['text_input', 'director_note', 'storyboard_shot', 'image_generate', 'video_generate'], preset: 'VIDEO' },
  commercial_cg: { layout: '商业 CG 布局：图像与视频并重', modules: ['storyboard', 'image', 'video', 'timeline', 'asset'], nodes: ['image_prompt', 'image_generate', 'video_generate'], preset: 'IMAGE' },
  advertisement: { layout: '广告布局：素材与剪辑优先', modules: ['image', 'video', 'timeline', 'asset'], nodes: ['image_generate', 'video_generate', 'timeline_export'], preset: 'MIXED' },
  music_video: { layout: 'MV 布局：音频与剪辑对齐', modules: ['audio', 'video', 'timeline', 'asset'], nodes: ['text_input', 'timeline_export'], preset: 'AUDIO' },
  game_previs: { layout: '预演布局：分镜与图像迭代', modules: ['director', 'storyboard', 'image', 'asset'], nodes: ['storyboard_shot', 'image_generate'], preset: 'IMAGE' },
  image_design: { layout: '图片设计布局：参考与生成并排', modules: ['image', 'asset'], nodes: ['image_reference', 'image_prompt', 'image_generate'], preset: 'IMAGE' },
  podcast_voice: { layout: '播客 / 配音布局：文本与音频', modules: ['audio', 'asset'], nodes: ['text_input'], preset: 'AUDIO' },
  custom: { layout: '自定义布局：保留手动编辑与导入', modules: ['asset'], nodes: ['text_input', 'manual_transform'], preset: 'BLANK' },
};
const MIXED_PLAN = {
  layout: '混合布局：七个模块都在，按需进入', preset: 'MIXED' as ProductionWorkflowPreset,
  modules: MODULE_ORDER as readonly ProductionWorkflowModuleId[],
  nodes: ['text_input', 'director_note', 'storyboard_shot', 'image_generate', 'timeline_export'] as readonly string[],
};

export type StudioEntryControllerConfig = {
  /** The injected owner seam. A new identity always re-reads. */
  client: StudioEntryClient;
  /** Stable identity of the entry session; a change discards every previously read value. */
  identity: string;
  /** The entry is on screen. A closed entry never reads. */
  active?: boolean;
  /** A resume/reopen target. Its intent is read; a failure is reported, never silently replaced. */
  projectId?: string | null;
  /** Title offered for a newly created project. */
  defaultTitle?: string;
  /** Navigation is supplied by the mounting workspace. */
  onOpenProject?: (projectId: string) => void;
  /** The author explicitly left the intent step (saved or skipped). */
  onIntentHandled?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
};

export type StudioCreateResult = {
  status: 'created' | 'failed' | 'intent_failed';
  project?: StudioProjectCreation;
  problem?: StudioEntryProblem;
};

function problemOf(reason: unknown, fallback: string, code: string): StudioEntryProblem {
  // Only the transport's own bounded ApiError text is surfaced; an unexpected local
  // failure is never echoed verbatim.
  return reason instanceof ApiError ? { code: reason.problem.code, message: reason.message } : { code, message: fallback };
}
const selectedIds = (values: ProductionWorkflowIntentValueInput[]): string[] =>
  values.filter(item => item.selected).map(item => item.intent_id).sort();
const sameValues = (left: ProductionWorkflowIntentValueInput[], right: ProductionWorkflowIntentValueInput[]): boolean =>
  left.length === right.length && left.every((item, index) => item.intent_id === right[index].intent_id
    && item.label === right[index].label && item.selected === right[index].selected);
const editableValues = (intent: StudioEntryIntent): ProductionWorkflowIntentValueInput[] =>
  intent.values.map(({ intent_id, label, selected }) => ({ intent_id, label, selected }));
/** Deterministic, content-addressed plan ids so an adopted id can be checked against the plan list. */
function planId(ids: string[]): string {
  return `plan:${ids.length ? ids.join('+') : 'blank'}`;
}
function planFor(ids: string[], fallbackId: string): StudioSuggestionPlan {
  const shape = ids.length === 1 ? LAYOUTS[ids[0]] : undefined;
  const layout = shape?.layout ?? (ids.length ? MIXED_PLAN.layout : LAYOUTS[fallbackId]?.layout ?? MIXED_PLAN.layout);
  const modules = [...(shape?.modules ?? (ids.length ? MIXED_PLAN.modules : LAYOUTS[fallbackId]?.modules ?? MIXED_PLAN.modules))]
    .sort((a, b) => MODULE_ORDER.indexOf(a) - MODULE_ORDER.indexOf(b));
  const nodes = [...(shape?.nodes ?? (ids.length ? MIXED_PLAN.nodes : LAYOUTS[fallbackId]?.nodes ?? MIXED_PLAN.nodes))];
  const preset = shape?.preset ?? (ids.length ? MIXED_PLAN.preset : LAYOUTS[fallbackId]?.preset ?? 'BLANK');
  const names = ids.map(id => STUDIO_INTENT_LABELS[id] ?? id).join('、');
  return {
    plan_id: planId(ids), title: ids.length ? `推荐方案：${names}` : '推荐方案：空白起步',
    intent_ids: ids, layout, modules, nodes, preset,
    note: `${STUDIO_ENTRY_CONTRACT.notices.adopt_scope}推荐只影响布局与提示，不会限制模块、权限，也不会生成内容。`,
  };
}
/** The permanent baseline recommendation, so the picker always offers something to adopt. */
export function studioBaselineSuggestion(): StudioSuggestionPlan {
  return planFor([], 'blank');
}
/** Recommendations computed only from the selected intents. */
export function studioSuggestions(ids: string[]): StudioSuggestionPlan[] {
  const known = [...new Set(ids)].filter(id => STUDIO_INTENT_IDS.includes(id));
  const singular = known.filter(id => id !== STUDIO_INTENT_CUSTOM_ID);
  const plans: StudioSuggestionPlan[] = [];
  if (singular.length) plans.push(...singular.sort().map(id => planFor([id], id)));
  if (known.includes(STUDIO_INTENT_CUSTOM_ID)) plans.push(planFor([STUDIO_INTENT_CUSTOM_ID], STUDIO_INTENT_CUSTOM_ID));
  if (known.length > 1) plans.push(planFor(known.sort(), known[0]));
  plans.push(studioBaselineSuggestion());
  const seen = new Set<string>();
  return plans.filter(plan => (seen.has(plan.plan_id) ? false : (seen.add(plan.plan_id), true)));
}

/**
 * The project entry controller: one project list read, at most one intent read, one blank
 * creation and one versioned intent replacement. It owns no authority, writes no storage
 * and never collapses a read failure into an empty list.
 */
export function useStudioEntry(config: StudioEntryControllerConfig) {
  const [projects, setProjects] = useState<StudioEntryProject[]>([]);
  const [state, setState] = useState<StudioEntryState>('idle');
  const [problem, setProblem] = useState<StudioEntryProblem>();
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState<string>(() => config.projectId ?? '');
  const [intent, setIntent] = useState<StudioEntryIntent>();
  const [draft, setDraft] = useState<StudioIntentDraft>();
  const [conflict, setConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState(config.defaultTitle ?? '');
  const [adoptedPlanId, setAdoptedPlanId] = useState('');
  const [intentHandled, setIntentHandled] = useState(false);

  const alive = useRef(true), epoch = useRef(0), abort = useRef<AbortController>();
  const readEpoch = useRef(0), saveLock = useRef(false), revoked = useRef(false);
  const latest = useRef(config), identity = useRef(config.identity), selected = useRef(selectedId);
  const intentRef = useRef(intent), draftRef = useRef(draft), projectsRef = useRef(projects);
  latest.current = config; identity.current = config.identity; selected.current = selectedId;
  intentRef.current = intent; draftRef.current = draft; projectsRef.current = projects;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const readClient = latest.current.client;
  const admit = useCallback(() => alive.current && !revoked.current && identity.current === latest.current.identity, []);

  const blankDraft = useCallback((): StudioIntentDraft => ({
    expected_version: intentRef.current?.version ?? 0,
    values: intentRef.current ? editableValues(intentRef.current) : studioBlankIntentValues(),
    ...(intentRef.current?.preset ? { preset: intentRef.current.preset } : {}),
  }), []);

  const loadIntent = useCallback(async (projectId: string, controller: AbortController) => {
    const request = ++readEpoch.current;
    try {
      const value = await latest.current.client.readIntent(projectId, controller.signal);
      if (!admit() || request !== readEpoch.current || controller.signal.aborted) return;
      setIntent(value); setDraft(undefined); setConflict(false); setProblem(undefined);
      // A resume target that is absent from the list is reported as an extra row, never
      // written back to the owner and never replaced by a new project.
      if (!projectsRef.current.some(row => row.id === projectId)) {
        setProjects(previous => previous.some(row => row.id === projectId) ? previous
          : [...previous, { id: projectId, title: projectId, updated_at: null, entry_kind: null, genre: null, status: null }]);
      }
      setState(previous => (previous === 'empty' ? 'ready' : previous));
    } catch (reason) {
      if (!admit() || request !== readEpoch.current || controller.signal.aborted) return;
      setIntent(undefined); setDraft(undefined); setConflict(false);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        revoked.current = true;
        setProblem({ code: STUDIO_ENTRY_ERROR_CODES.authorityInvalid, message: STUDIO_ENTRY_CONTRACT.messages.denied });
        setState('denied');
      } else if (reason instanceof ApiError && (reason.status === 404 || reason.problem.code === STUDIO_ENTRY_ERROR_CODES.projectMissing)) {
        // A failed reopen of a saved id is reported as invalid; no replacement is created.
        setProblem({ code: STUDIO_ENTRY_ERROR_CODES.projectMissing, message: STUDIO_ENTRY_CONTRACT.messages.project_missing });
        setState('missing');
      } else {
        setProblem(problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.read_failed, STUDIO_ENTRY_ERROR_CODES.readFailed));
        setState('failed');
      }
    }
  }, [admit]);

  const reload = useCallback(async () => {
    if (!alive.current || revoked.current) return;
    const requestIdentity = identity.current;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    setProblem(undefined); setNotice(''); setConflict(false); setState('loading');
    try {
      const rows = await readClient.listProjects(controller.signal);
      if (!alive.current || request !== epoch.current || identity.current !== requestIdentity || controller.signal.aborted) return;
      setProjects(rows);
      const wanted = latest.current.projectId || selected.current || '';
      if (!wanted) { setState(rows.length ? 'ready' : 'empty'); return; }
      setState('ready');
      setSelectedId(wanted);
      await loadIntent(wanted, controller);
    } catch (reason) {
      if (!alive.current || request !== epoch.current || identity.current !== requestIdentity || controller.signal.aborted) return;
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        revoked.current = true; setProjects([]); setIntent(undefined); setDraft(undefined);
        setProblem(problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.denied, STUDIO_ENTRY_ERROR_CODES.readFailed));
        setState('denied');
      } else {
        // A failed read is never an empty project list.
        setProjects([]); setProblem(problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.read_failed, STUDIO_ENTRY_ERROR_CODES.readFailed));
        setState('failed');
      }
    }
  }, [loadIntent, readClient]);

  useEffect(() => {
    epoch.current++; readEpoch.current++; abort.current?.abort(); saveLock.current = false;
    revoked.current = false;
    setProjects([]); setIntent(undefined); setDraft(undefined); setProblem(undefined); setNotice('');
    setConflict(false); setSaving(false); setCreating(false); setState('idle'); setAdoptedPlanId(''); setIntentHandled(false);
    setSelectedId(config.projectId ?? '');
    setTitle(config.defaultTitle ?? '');
    identity.current = config.identity;
  }, [config.identity, config.projectId, config.defaultTitle]);
  useEffect(() => { if (config.active !== false) void reload(); }, [config.active, config.identity, reload]);

  const values = useMemo(
    () => draft?.values ?? (intent ? editableValues(intent) : studioBlankIntentValues()),
    [draft, intent],
  );
  const dirty = useMemo(() => {
    if (intent) return !sameValues(values, editableValues(intent));
    return values.some(item => item.selected);
  }, [intent, values]);
  const customId = STUDIO_INTENT_CUSTOM_ID;
  const customValue = values.find(item => item.intent_id === customId);
  const customPending = !!customValue?.selected && !customValue.label.trim();
  const selectedIntentIds = useMemo(() => selectedIds(values), [values]);
  const suggestions = useMemo(() => studioSuggestions(selectedIntentIds), [selectedIntentIds]);
  const savable = studioIntentIsSavable(values, customId) && !customPending;
  const canSave = !!intent && savable && dirty && !saving && !conflict && state !== 'denied' && state !== 'missing';
  const ready = state === 'ready' || state === 'empty';
  const canCreate = ready && !creating && !saving && !!title.trim() && title.trim().length <= STUDIO_ENTRY_CONTRACT.bounds.title;

  const report = useCallback((value: boolean) => { latest.current.onDirtyChange?.(value); setIntentHandled(value); }, []);

  const edit = useCallback((next: ProductionWorkflowIntentValueInput[], patch: Partial<StudioIntentDraft> = {}) => {
    setDraft(previous => {
      const base = previous ?? blankDraft();
      return { ...base, values: next, ...patch };
    });
    setConflict(false); setProblem(undefined); setNotice('');
    report(true);
  }, [blankDraft, report]);

  const toggleIntent = useCallback((intentId: string) => {
    if (!admit() || saving || revoked.current) return;
    if (typeof intentId !== 'string' || !STUDIO_INTENT_IDS.includes(intentId)) return;
    const current = draftRef.current?.values ?? (intentRef.current ? editableValues(intentRef.current) : studioBlankIntentValues());
    if (current.filter(item => item.selected).length >= STUDIO_INTENT_CATALOG.length && !current.some(item => item.intent_id === intentId && item.selected)) return;
    edit(current.map(item => item.intent_id === intentId ? { ...item, selected: !item.selected } : item));
  }, [admit, edit, saving]);

  const setCustomLabel = useCallback((value: string) => {
    if (!admit() || saving || revoked.current || typeof value !== 'string') return;
    const label = value.replace(/[\u0000-\u001f\u007f]/g, '').slice(0, STUDIO_ENTRY_CONTRACT.bounds.label);
    const current = draftRef.current?.values ?? (intentRef.current ? editableValues(intentRef.current) : studioBlankIntentValues());
    edit(current.map(item => item.intent_id === customId ? { ...item, label } : item));
  }, [admit, edit, saving]);

  /** "Skip intent" is a first-class action: nothing is written and the step is left clean. */
  const skipIntent = useCallback(() => {
    if (!alive.current || revoked.current) return;
    setDraft(undefined); setConflict(false); setProblem(undefined); setAdoptedPlanId('');
    setNotice(STUDIO_ENTRY_CONTRACT.messages.skipped);
    setIntentHandled(true);
    latest.current.onDirtyChange?.(false);
    latest.current.onIntentHandled?.();
  }, []);

  const saveIntent = useCallback(async (): Promise<StudioEntryProblem | undefined> => {
    const projectId = selected.current || latest.current.projectId || '';
    const pending = draftRef.current;
    const captured = latest.current;
    if (!projectId || revoked.current || saveLock.current || !captured.client) return undefined;
    if (!pending || !studioIntentIsSavable(pending.values, customId)) {
      const local: StudioEntryProblem = { code: STUDIO_ENTRY_ERROR_CODES.localInvalid, message: STUDIO_ENTRY_CONTRACT.messages.custom_incomplete };
      setProblem(local);
      return local;
    }
    saveLock.current = true; setSaving(true); setProblem(undefined); setConflict(false); setNotice('');
    try {
      const value = await captured.client.saveIntent(projectId, { expected_version: pending.expected_version, values: pending.values, ...(pending.preset ? { preset: pending.preset } : {}) });
      if (!alive.current || revoked.current) return undefined;
      setIntent(value); setDraft(undefined); setState(previous => (previous === 'empty' ? 'ready' : previous));
      setNotice(`创作意图已保存 · v${value.version}。`);
      report(false);
      captured.onIntentHandled?.();
      return undefined;
    } catch (reason) {
      if (!alive.current || revoked.current) return undefined;
      const problem = problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.save_failed, STUDIO_ENTRY_ERROR_CODES.readFailed);
      setProblem(problem);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        revoked.current = true; setIntent(undefined); setDraft(undefined); setState('denied');
        report(false);
      } else if (reason instanceof ApiError && (reason.status === 409 || reason.problem.code === STUDIO_ENTRY_ERROR_CODES.conflict)) {
        // The local input is kept; only the expected version is re-read from the owner.
        setConflict(true); setNotice(STUDIO_ENTRY_CONTRACT.messages.conflict_reread);
        const controller = new AbortController();
        try {
          const served = await captured.client.readIntent(projectId, controller.signal);
          if (alive.current) {
            setIntent(served);
            setDraft(previous => previous ? { ...previous, expected_version: served.version } : previous);
          }
        } catch { /* The original message stays; a failed re-read never clears the draft. */ }
      }
      return problem;
    } finally {
      saveLock.current = false;
      if (alive.current) setSaving(false);
    }
  }, [customId, report]);

  const acknowledgeConflict = useCallback(() => {
    if (!alive.current || revoked.current) return;
    // The acknowledged conflict notice is cleared; the local selection is not.
    setConflict(false); setProblem(undefined); setNotice('已核对服务端最新版本；本地选择仍保留，可重新提交。');
  }, []);

  const adoptPlan = useCallback(async (id: string): Promise<StudioEntryProblem | undefined> => {
    if (!admit() || saving) return undefined;
    const plan = suggestions.find(item => item.plan_id === id);
    if (!plan) return undefined;
    const current = draftRef.current?.values ?? (intentRef.current ? editableValues(intentRef.current) : studioBlankIntentValues());
    const wanted = new Set(plan.intent_ids);
    const next = current.map(item => ({ ...item, selected: wanted.has(item.intent_id) }));
    // Adopting only writes the preference: the preset is a stored hint, never a grant.
    edit(next, { preset: plan.preset });
    setAdoptedPlanId(plan.plan_id);
    if (!intentRef.current) { setNotice(STUDIO_ENTRY_CONTRACT.messages.adopted); return undefined; }
    const failed = await saveIntent();
    if (alive.current) setNotice(failed ? STUDIO_ENTRY_CONTRACT.messages.save_failed : STUDIO_ENTRY_CONTRACT.messages.adopted);
    return failed;
  }, [admit, edit, saveIntent, saving, suggestions]);

  const create = useCallback(async (kind: 'blank' | 'intent'): Promise<StudioCreateResult> => {
    const captured = latest.current;
    const projectTitle = title.trim();
    if (revoked.current || creating || !projectTitle || projectTitle.length > STUDIO_ENTRY_CONTRACT.bounds.title) {
      return { status: 'failed', problem: { code: STUDIO_ENTRY_ERROR_CODES.localInvalid, message: '项目名称需要 1–200 个字符。' } };
    }
    setCreating(true); setProblem(undefined); setNotice(''); setConflict(false);
    try {
      const project = await captured.client.createBlankProject({ title: projectTitle });
      if (!alive.current) return { status: 'failed' };
      setProjects(previous => previous.some(row => row.id === project.id) ? previous : [{ id: project.id, title: project.title, updated_at: null, entry_kind: null, genre: null, status: null }, ...previous]);
      setSelectedId(project.id);
      setIntent(undefined); setDraft(undefined); setState('ready');
      if (kind === 'blank') { setNotice('项目已创建。'); return { status: 'created', project }; }
      const draftValues = draftRef.current?.values ?? studioBlankIntentValues();
      if (!studioIntentIsSavable(draftValues, customId)) {
        const problem: StudioEntryProblem = { code: STUDIO_ENTRY_ERROR_CODES.localInvalid, message: STUDIO_ENTRY_CONTRACT.messages.custom_incomplete };
        setProblem(problem);
        return { status: 'intent_failed', project, problem };
      }
      const served = await captured.client.readIntent(project.id).catch(() => undefined);
      if (!alive.current) return { status: 'failed' };
      setIntent(served); setDraft(undefined);
      const pending: StudioIntentDraft = { expected_version: served?.version ?? 0, values: draftValues, ...(draftRef.current?.preset ? { preset: draftRef.current.preset } : {}) };
      try {
        const saved = await captured.client.saveIntent(project.id, pending);
        if (!alive.current) return { status: 'failed' };
        setIntent(saved); setNotice(`项目已创建，创作意图已保存 · v${saved.version}。`);
        report(false); captured.onIntentHandled?.();
        return { status: 'created', project };
      } catch (reason) {
        // The project exists; the intent step failed and the draft is kept for a retry.
        if (!alive.current) return { status: 'failed' };
        const problem = problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.save_failed, STUDIO_ENTRY_ERROR_CODES.readFailed);
        setDraft({ ...pending, expected_version: intentRef.current?.version ?? pending.expected_version });
        setProblem(problem);
        return { status: 'intent_failed', project, problem };
      }
    } catch (reason) {
      if (!alive.current) return { status: 'failed' };
      const problem = problemOf(reason, STUDIO_ENTRY_CONTRACT.messages.create_failed, STUDIO_ENTRY_ERROR_CODES.readFailed);
      setProblem(problem);
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoked.current = true; setState('denied'); }
      return { status: 'failed', problem };
    } finally {
      if (alive.current) setCreating(false);
    }
  }, [creating, customId, report, title]);

  const selectProject = useCallback((projectId: string) => {
    if (!alive.current || revoked.current || typeof projectId !== 'string' || !projectId) return;
    setSelectedId(projectId); setIntent(undefined); setDraft(undefined); setConflict(false); setProblem(undefined); setNotice('');
    setState(previous => (previous === 'empty' ? 'empty' : previous));
    const controller = abort.current ?? new AbortController();
    void loadIntent(projectId, controller);
  }, [loadIntent]);

  const openProject = useCallback(() => {
    const projectId = selected.current || latest.current.projectId || '';
    if (!projectId || !intentRef.current || revoked.current || conflict) return;
    latest.current.onOpenProject?.(projectId);
  }, [conflict]);

  return {
    state, problem, notice, projects, selectedId, intent, draft, values, customId, customPending,
    selectedIntentIds, suggestions, adoptedPlanId, conflict, saving, creating, title, dirty, savable,
    canSave, canCreate, canOpen: !!selectedId && !!intent && !conflict && !revoked.current, intentHandled,
    baseline: studioBaselineSuggestion(),
    setTitle, reload, selectProject, openProject, toggleIntent, setCustomLabel, skipIntent, saveIntent,
    acknowledgeConflict, adoptPlan, create,
  };
}

export type StudioEntryController = ReturnType<typeof useStudioEntry>;
