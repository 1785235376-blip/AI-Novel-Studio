import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ApiError, type Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { enabled, type ExperimentalClient, type ExperimentalFlags } from './api';
import { WorkspaceSearch } from './WorkspaceSearch';
import { NoticeCenterAddon } from './WritingSessionPanel';
import { ErrorMessage, Field, ResourceState, useAction, useResource } from './shared';
import { defaultLayout, defaultWorkspaceView, workspaceClient, type WorkspaceAnchor, type WorkspaceNavigation, type WorkspaceLayout, type WorkspaceView, type ResumeItem, type DiagnosticOptions, type DiagnosticResult } from './uxClient';

export type WorkspaceToolsProps = { focusActive?: boolean; saveFailure?: boolean; client: ExperimentalClient; chapter?: Chapter; flags?: ExperimentalFlags; currentAnchor?: WorkspaceAnchor; initialSection?: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; onNavigate?: (target: WorkspaceNavigation) => void; workspaceView?: WorkspaceView; onWorkspaceViewChange?: (view: WorkspaceView) => void; onWorkspaceSaved?: () => void };
const commands = [
  { id: 'editor', label: '继续纯写作', detail: '回到当前章节；手工写作不需要模型。', words: '写作 编辑 章节 保存 novel' },
  { id: 'knowledge', label: '导入与知识审核', detail: '打开既有导入工具，先预览资料。', words: '导入 长篇 import' },
  { id: 'screenplay', label: '剧本与镜头', detail: '打开既有剧本工具，选择作品后逐步制作。', words: '影视 剧本 分镜 screenplay' },
  { id: 'audiobook_v2', label: '准备有声书', detail: '打开已启用的有声书工具；生成仍需单独配置。', words: '声音 配音 音频 audiobook', flag: 'audiobook_v2' },
  { id: 'diagnostics', label: '检查本地模型', detail: '查看当前运行时状态与缺少的配置。', words: '本地 模型 诊断 local model' },
  { id: 'history', label: '查看版本历史', detail: '返回现有章节版本与恢复界面。', words: '历史 恢复 版本 history' },
  { id: 'exports', label: '打开导出中心', detail: '选择既有导出方式并查看任务。', words: '导出 发布 下载 export' },
] as const;
let scopeSequence = 0;

export function WorkspaceToolsPanel(props: WorkspaceToolsProps) {
  // A captured-client change unmounts all old responses, selections and notes.
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <WorkspaceToolsBody key={identity} {...props} />;
}

function WorkspaceToolsBody({ client, chapter, flags, currentAnchor, initialSection, onNavigate, focusActive, saveFailure, workspaceView, onWorkspaceViewChange, onWorkspaceSaved }: WorkspaceToolsProps) {
  const api = useMemo(() => workspaceClient(client), [client]);
  const resume = useResource(signal => api.resume(signal), [api]);
  const [section, setSection] = useState<string>(initialSection || 'resume');
  const sectionTouched = useRef(false), navigationEpoch = useRef(0);
  const sectionRef = useRef(section); sectionRef.current = section;
  const invalidateNavigation = () => { navigationEpoch.current += 1; stopLookup(); };
  const selectSection = (value: string) => { invalidateNavigation(); sectionTouched.current = true; setSection(value); };
  useEffect(() => { if (initialSection) selectSection(initialSection); }, [initialSection]);
  const [note, setNote] = useState('');
  const [density, setDensity] = useState<'normal' | 'advanced'>('normal');
  const [filters, setFilters] = useState(defaultLayout);
  const filtersTouched = useRef(false);
  const updateFilters = (patch: Partial<WorkspaceLayout>) => { invalidateNavigation(); filtersTouched.current = true; setFilters(value => ({ ...value, ...patch })); };
  const [recent, setRecent] = useState<string[]>([]);
  const [initialized, setInitialized] = useState(false);
  const noteTouched = useRef(false);
  const [saved, setSaved] = useState<ResumeItem | null>(null);
  const [notice, setNotice] = useState('');
  const action = useAction(resume.reload);
  const alive = useRef(true);
  const lookup = useRef<AbortController>();
  const stopLookup = () => { lookup.current?.abort(); lookup.current = undefined; };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => { navigationEpoch.current++; return stopLookup; }, [chapter?.id, chapter?.version, section]);
  useEffect(() => {
    if (resume.data) {
      setSaved(resume.data.item);
      if (!initialized) {
        if (!noteTouched.current) setNote(resume.data.item?.stopping_note || '');
        setDensity(resume.data.item?.layout.density || 'normal');
        if (!filtersTouched.current) setFilters({ ...defaultLayout, ...resume.data.item?.layout });
        if (!sectionTouched.current && !initialSection) setSection(resume.data.item?.layout.section || 'resume');
        setRecent(resume.data.item?.recent_commands || []);
        setInitialized(true);
      }
    }
  }, [resume.data, initialized]);
  const availableCommands = commands.filter(command => !('flag' in command) || enabled(flags, command.flag));
  const navigate = (target: WorkspaceNavigation) => {
    if (!alive.current || !onNavigate) return;
    navigationEpoch.current += 1;
    if (target.kind === 'feature') setRecent(values => [target.feature || target.id, ...values.filter(v => v !== (target.feature || target.id))].slice(0, 12));
    onNavigate(target);
  };
  const restore = (version: number, current = false) => {
    return action.run(async () => {
      const ticket = ++navigationEpoch.current;
      stopLookup(); lookup.current = new AbortController();
      const signal = lookup.current.signal;
      const target = await api.restore(version, current);
      if (alive.current && !signal.aborted && ticket === navigationEpoch.current && sectionRef.current === 'resume') navigate(target.workspace ? { ...target, signal } : target);
    }, '');
  };
  const save = (dismissGuide = saved?.guide_dismissed || false) => action.run(async () => {
    const selected = chapter || undefined;
    const result = await api.save({ expected_version: saved?.version || 0, chapter_id: selected?.id || null, chapter_version: selected?.version || null,
      anchor: selected ? currentAnchor || { offset: 0, scroll: 0 } : { offset: 0, scroll: 0 },
      layout: { ...filters, density, section }, view: workspaceView || { ...defaultWorkspaceView, focus_active: Boolean(focusActive) }, stopping_note: note, pinned_chapter_ids: [], recent_commands: recent, guide_dismissed: dismissGuide });
    if (alive.current) { setSaved(result.item); onWorkspaceSaved?.(); }
  }, '工作现场已保存。正文仍由编辑器保存。');
  return <section className="experimental-section" aria-label="工作现场工具">
    <div className="experimental-actions"><h3>工作现场</h3><Badge>本地确定性工具 · 不调用模型</Badge></div>
    <nav className="experimental-tabs" aria-label="工作现场工具分类">{[['resume', '继续工作'], ['search', '搜索与命令'], ['tasks', '任务中心'], ['diagnostics', '诊断包'], ['guide', '使用指引']].map(([id, label]) => <Button key={id} aria-pressed={section === id} onClick={() => selectSection(id)}>{label}</Button>)}</nav>
    {(section === 'search' || section === 'tasks') && <div className="experimental-actions"><Button disabled={resume.loading || !!resume.error || action.busy} onClick={() => save()}>保存筛选到工作现场</Button>{action.feedback}</div>}
    {!onNavigate && <StatusMessage tone="warning">当前宿主未接入跳转；可以保存工作现场、搜索与查看任务。</StatusMessage>}
    {section === 'resume' && <Panel title="继续上次工作">
      <ResourceState loading={resume.loading} error={resume.error} />
      {!!resume.error && <Button onClick={resume.reload}>重新读取工作现场</Button>}
      {!resume.loading && !resume.error && !saved && <EmptyState title="还没有保存工作现场" detail="选择一个章节，写下停止点，再保存工作现场。不会复制正文或凭据。" />}
      {saved && <>
        <div className="experimental-actions"><strong>{saved.chapter_title || '没有固定章节'}</strong><Badge>现场 v{saved.version}</Badge>{saved.chapter_version && <Badge>章节 v{saved.chapter_version}</Badge>}</div>
        <p>最后保存：{saved.updated_at}</p>
        {resume.data?.availability === 'STALE' && <StatusMessage tone="warning">原章节版本已变化。旧光标不会自动套用；可以打开当前版本，从章首重新定位。</StatusMessage>}
        {resume.data?.availability === 'UNAVAILABLE' && <StatusMessage tone="warning">原章节已删除、归档或当前无权访问。停止点仍保留，请另选章节。</StatusMessage>}
        {saved.layout_recovery_required && <StatusMessage tone="warning">布局记录损坏，已使用默认布局。可单独重置布局，正文与停止点不受影响。</StatusMessage>}
        {saved.focus_state === 'CHANGED' && <StatusMessage tone="warning">固定参考或阅读偏好已在原工具中变化。恢复章节时保留当前设置；请核对后重新保存现场。</StatusMessage>}
        {saved.focus_state === 'UNAVAILABLE' && <StatusMessage>原阅读与参考服务当前不可用；仍可恢复章节和筛选。</StatusMessage>}
        {saved.reference_recovery_required && <StatusMessage tone="warning">部分固定参考已过期或不可读。分屏会显示恢复提示，不会展示旧内容。</StatusMessage>}
        <div className="experimental-actions">
          <Button disabled={!onNavigate || action.busy || !saved.chapter_id || resume.data?.availability !== 'READY'} onClick={() => restore(saved.version)}>恢复章节位置</Button>
          {resume.data?.availability === 'STALE' && <Button disabled={!onNavigate || action.busy} onClick={() => restore(saved.version, true)}>打开当前版本（章首）</Button>}
          <Button disabled={action.busy} onClick={() => action.run(async () => { const ticket = ++navigationEpoch.current; stopLookup(); const result = await api.reset(saved.version); if (!alive.current) return; setSaved(result.item); if (ticket === navigationEpoch.current) { setDensity('normal'); setFilters(defaultLayout); onWorkspaceViewChange?.(defaultWorkspaceView); } onWorkspaceSaved?.(); }, '布局已重置，作品未改变')}>重置布局</Button>
        </div>
        <section aria-label="上次未决任务"><h4>上次未决任务 · 当前状态</h4><p>仅核对原任务 ID，不会重新提交或取消任务。</p>
          {!saved.pending_tasks?.length && <p>本次没有可展示的原任务。</p>}
          {saved.pending_tasks?.map(task => <article className="experimental-record" key={`${task.authority}:${task.id}`}><strong>{task.label}</strong><Badge>{task.stage_label}</Badge><p>任务 ID：{task.id}</p><Button disabled={!onNavigate} onClick={() => { stopLookup(); lookup.current = new AbortController(); navigate({ ...(task.source || { kind: 'feature', id: task.id, feature: task.feature }), signal: lookup.current.signal }); }}>{task.source?.kind === 'generation' ? '恢复原生成草稿' : '查看原任务工具'}</Button></article>)}
          {saved.tasks_recovery_required && <StatusMessage tone="warning">部分原任务当前不可核对，可能已移除、权限变化或不在近期读取范围。可在任务中心重新检查。</StatusMessage>}
          {saved.tasks_capture_partial && <StatusMessage>任务快照有界且不完整，更多记录请查看原任务工具。</StatusMessage>}
        </section>
      </>}
      <Field label="停止点与下次要做的事"><textarea maxLength={2000} value={note} onChange={e => { invalidateNavigation(); noteTouched.current = true; setNote(e.target.value); }} placeholder="例如：明天先检查第三章的伏笔" /></Field>
      <Field label="信息密度"><select value={density} onChange={e => { invalidateNavigation(); setDensity(e.target.value as 'normal' | 'advanced'); }}><option value="normal">普通</option><option value="advanced">高级（显示历史与稳定 ID）</option></select></Field>
      {enabled(flags, 'writing_focus_v2') && <label className="experimental-check"><input type="checkbox" checked={workspaceView?.references_visible ?? true} disabled={!onWorkspaceViewChange} onChange={e => { invalidateNavigation(); onWorkspaceViewChange?.({ ...(workspaceView || defaultWorkspaceView), references_visible: e.target.checked }); }} />显示固定参考分屏</label>}
      <p>固定参考和阅读偏好沿用“专注写作”的已保存版本；现场只记录该版本与分屏状态。</p>
      <p>{chapter ? `将保存当前章节「${chapter.title}」v${chapter.version}` : '当前没有选中章节；仍可保存停止点。'}{chapter && !currentAnchor ? ' 宿主未提供可靠光标，恢复时从章首开始。' : ''}</p>
      <div className="experimental-actions"><Button disabled={resume.loading || !!resume.error || action.busy} onClick={() => save()}>保存工作现场</Button><Button disabled={resume.loading || action.busy} onClick={resume.reload}>核对服务器现场（保留当前笔记）</Button></div>
      {action.feedback}
      {density === 'advanced' && <ResumeHistory api={api} revision={saved?.version} />}
    </Panel>}
    {section === 'search' && <WorkspaceSearch api={api} chapter={chapter} commands={availableCommands} navigate={onNavigate ? navigate : undefined} recent={recent} filters={filters} updateFilters={updateFilters} />}
    {section === 'tasks' && <><WorkspaceTasks api={api} navigate={onNavigate ? navigate : undefined} advanced={density === 'advanced'} filters={filters} updateFilters={updateFilters} />{enabled(flags, 'writing_sessions_v2') && <NoticeCenterAddon client={client} onNavigate={onNavigate} focusActive={focusActive} saveFailure={saveFailure} />}</>}
    {section === 'diagnostics' && <WorkspaceDiagnostics api={api} />}
    {section === 'guide' && <Panel title="从一个真实任务开始">
      <p>这些入口只打开已有工具。生成、接受修改、导出和外发仍各自确认；没有模型也可以手工写作。</p>
      <div className="experimental-grid">{availableCommands.slice(0, 5).map(command => <article className="experimental-record" key={command.id}><h3>{command.label}</h3><p>{command.detail}</p><Button disabled={!onNavigate} onClick={() => navigate({ kind: 'feature', id: command.id, feature: command.id })}>打开{command.label}</Button></article>)}</div>
      {!enabled(flags, 'audiobook_v2') && <StatusMessage>有声书实验入口未启用。引导不会开启服务端开关。</StatusMessage>}
      <Button disabled={action.busy || resume.loading || !!resume.error} onClick={async () => { const ticket = navigationEpoch.current; await save(true); if (alive.current && ticket === navigationEpoch.current && sectionRef.current === 'guide') { selectSection('resume'); setNotice('可随时从“使用指引”重新打开。'); } }}>跳过并保存当前现场</Button>
      {action.feedback}
    </Panel>}
    {notice && <StatusMessage>{notice}</StatusMessage>}
  </section>;
}

function ResumeHistory({ api, revision }: { api: ReturnType<typeof workspaceClient>; revision?: number }) {
  const result = useResource(signal => api.history(signal), [api, revision]);
  return <details><summary>工作现场历史（最多 20 次）</summary><ResourceState loading={result.loading} error={result.error} empty={!result.data?.items.length} /><ol>{result.data?.items.map(row => <li key={row.version}>现场 v{row.version} · 章节 v{row.chapter_version || '—'} · {row.stopping_note || '无停止点'}</li>)}</ol></details>;
}

function WorkspaceTasks({ api, navigate, advanced, filters, updateFilters }: { api: ReturnType<typeof workspaceClient>; navigate?: (target: WorkspaceNavigation) => void; advanced: boolean; filters: WorkspaceLayout; updateFilters: (patch: Partial<WorkspaceLayout>) => void }) {
  const query = filters.task_query, failed = filters.show_failed_only;
  const setQuery = (value: string) => updateFilters({ task_query: value });
  const setFailed = (value: boolean) => updateFilters({ show_failed_only: value });
  const tasks = useResource(signal => api.tasks(query, failed, signal), [api, query, failed]);
  const action = useAction();
  const lookup = useRef<AbortController>();
  const stopLookup = () => { lookup.current?.abort(); lookup.current = undefined; };
  useLayoutEffect(() => () => stopLookup(), [api, query, failed]);
  const openSource = (source: WorkspaceNavigation) => {
    stopLookup();
    if (source.kind !== 'generation') { navigate?.(source); return; }
    lookup.current = new AbortController();
    // This cancels navigation only. It never cancels or resubmits the source job.
    navigate?.({ ...source, signal: lookup.current.signal });
  };
  return <Panel title="任务中心 · 原服务实时读取" aria-label="任务中心 · 原服务实时读取">
    <div className="experimental-actions"><Field label="按任务 ID、类型或阶段搜索"><input maxLength={160} value={query} onChange={e => { stopLookup(); setQuery(e.target.value); }} /></Field><label className="experimental-check"><input type="checkbox" checked={failed} onChange={e => { stopLookup(); setFailed(e.target.checked); }} />只看失败或结果未知</label><Button disabled={tasks.loading} onClick={() => { stopLookup(); tasks.reload(); }}>刷新任务</Button></div>
    <p>费用未知时不显示免费。这里不会执行或重试任务；请进入原工具核对权限、输入和费用后处理。正文生成只显示近期可读记录，更早记录可能不在本次读取范围。</p>
    <ResourceState loading={tasks.loading} error={tasks.error} empty={!tasks.data?.items.length} />
    {tasks.data?.unavailable.map(source => <StatusMessage tone="warning" key={source.authority}>{source.label}暂时不可读，其他来源仍可使用。</StatusMessage>)}
    {tasks.data?.truncated && <StatusMessage tone="warning">显示范围达到上限；更早的记录请进入原任务工具查找。</StatusMessage>}
    {!tasks.loading && !tasks.error && <div className="experimental-list">{tasks.data?.items.map(task => <article key={`${task.authority}:${task.id}`} className="experimental-record"><div className="experimental-actions"><h3>{task.label}</h3><Badge tone={task.status === 'FAILED' || task.status === 'UNKNOWN' ? 'warning' : 'neutral'}>{task.stage_label}</Badge>{task.stale && <Badge tone="warning">来源已变化</Badge>}</div><p>任务 ID：{task.id}</p><p>{task.progress ? `${task.progress.completed} / ${task.progress.total} ${task.progress.unit}` : '原服务未报告可量化进度，仅显示阶段。'} · 预估费用：未知 · 实际费用：未知</p><p>{task.lifecycle}</p>{advanced && <details><summary>原任务状态历史</summary>{task.history.length ? <ol>{task.history.map((entry, index) => <li key={index}>v{entry.version ?? '—'} · {entry.status}</li>)}</ol> : <p>来源没有提供历史。</p>}</details>}<div className="experimental-actions"><Button disabled={!navigate} onClick={() => openSource(task.source?.kind === 'generation' ? task.source : { kind: 'feature', id: task.id, feature: task.feature })}>{task.source?.kind === 'generation' ? '打开原生成草稿' : '打开来源工具'}</Button><Button disabled={action.busy || !navigator.clipboard?.writeText} title={!navigator.clipboard?.writeText ? '当前浏览器不支持剪贴板写入，可在诊断包中导出安全信息。' : undefined} onClick={() => action.run(() => navigator.clipboard.writeText(JSON.stringify({ component: 'workspace_tools_v2', authority: task.authority, status: task.status, error_code: task.error_code, cost_state: 'UNKNOWN' }, null, 2)), '已复制脱敏状态，不含正文、任务 ID 或密钥')}>复制脱敏状态</Button></div></article>)}</div>}
    {action.feedback}
  </Panel>;
}

function WorkspaceDiagnostics({ api }: { api: ReturnType<typeof workspaceClient> }) {
  const alive = useRef(true);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [options, setOptions] = useState<DiagnosticOptions>({ include_environment: true, include_task_states: true, include_error_codes: true });
  const [preview, setPreview] = useState<DiagnosticResult>();
  const action = useAction();
  const select = (key: keyof DiagnosticOptions, checked: boolean) => { setOptions(value => ({ ...value, [key]: checked })); setPreview(undefined); };
  return <Panel title="隐私友好诊断包">
    <p>只收集允许的组件信息、任务阶段和已登记错误码。不读取正文、原始提示词、运行日志、路径、密钥、Cookie 或设备标识。不会自动上传。</p>
    {([['include_environment', '组件与存储类型'], ['include_task_states', '任务阶段（不含标题与 ID）'], ['include_error_codes', '安全错误码']] as const).map(([key, label]) => <label className="experimental-check" key={key}><input type="checkbox" checked={options[key]} disabled={action.busy} onChange={e => select(key, e.target.checked)} />{label}</label>)}
    <div className="experimental-actions"><Button disabled={action.busy} onClick={() => action.run(async () => { const result = await api.preview(options); if (alive.current) setPreview(result); }, '诊断预览已生成，请检查后导出')}>生成诊断预览</Button><Button disabled={!preview || action.busy} onClick={() => action.run(async () => { let data: DiagnosticResult; try { data = await api.export(options, preview!.preview_digest); } catch (error) { if (alive.current && error instanceof ApiError && error.status === 409) setPreview(undefined); throw error; } if (!alive.current) return; const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const link = document.createElement('a'); link.href = url; link.download = 'workspace-diagnostics.json'; link.click(); URL.revokeObjectURL(url); }, '已请求下载诊断包，未上传')}>导出已选诊断项</Button></div>
    {preview && <section className="experimental-record" aria-label="诊断预览"><h3>将包含的诊断信息</h3>{preview.sections.environment && <p>组件：{preview.sections.environment.component}；存储：{preview.sections.environment.storage}；范围：{preview.sections.environment.scope_mode}</p>}{preview.sections.task_states && <><h3>任务阶段</h3>{preview.sections.task_states.length ? <ul>{preview.sections.task_states.map((task, index) => <li key={index}>{task.authority} · {task.status} · 费用未知</li>)}</ul> : <p>没有可提供的任务记录。</p>}</>}{preview.sections.error_codes && <p>错误码：{preview.sections.error_codes.join('、') || '没有已报告的错误码'}</p>}<p>原始日志：不包含。上传：否。</p></section>}
    {action.feedback}
  </Panel>;
}
