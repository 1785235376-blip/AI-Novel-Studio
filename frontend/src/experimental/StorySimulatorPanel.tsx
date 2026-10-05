import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { ErrorMessage, Field, ResourceState, useResource } from './shared';
import { useReviewAction } from './styleReviewClient';
import { storySimulatorClient, type SimulatorModelRoute, type SimulatorContext, type SimulatorEvent, type SimulatorInput, type SimulatorKnowledge, type SimulatorRoute, type SimulatorRouteInput, type SimulatorRun } from './storySimulatorClient';
import type { WorkspaceNavigation } from './uxClient';

type Props = { client: ExperimentalClient; chapter?: Chapter; onNavigate?: (target: WorkspaceNavigation) => void };
type Amount = { key: string; value: string };
type EventDraft = Omit<SimulatorEvent, 'resource_delta'> & { resource_delta: Amount[] };
type RouteDraft = Omit<SimulatorRouteInput, 'events'> & { events: EventDraft[] };
const lines = (value: string) => value.split('\n').map(text => text.trim()).filter(Boolean);
const amountsValid = (rows: Amount[], signed = false) => rows.every(row => row.key.trim() && /^-?\d+$/.test(row.value) && Number.isSafeInteger(Number(row.value)) && (signed || Number(row.value) >= 0)) && new Set(rows.map(row => row.key.trim())).size === rows.length;
const amounts = (rows: Amount[]) => Object.fromEntries(rows.map(row => [row.key.trim(), Number(row.value)]));
const statuses = { READY: '等待手动推进', RUNNING: '推演进行中', COMPLETED: '推演已结束', CANCELLED: '已取消' };
let scopeSequence = 0;
export function StorySimulatorPanel(props: Props) {
  const identity = useMemo(() => ++scopeSequence, [props.client]);
  return <StorySimulatorBody key={identity} {...props} />;
}
function StorySimulatorBody({ client, chapter, onNavigate }: Props) {
  const api = useMemo(() => storySimulatorClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]);
  const runs = useResource(signal => api.runs(signal), [api]);
  const [runId, setRunId] = useState('');
  const detail = useResource(signal => runId ? api.run(runId, signal) : Promise.resolve(undefined), [api, runId]);
  const action = useReviewAction(), epoch = useRef(0), sequence = useRef(2);
  const [sourceVersions, setSourceVersions] = useState<Record<string, number>>(chapter ? { [chapter.id]: chapter.version } : {});
  const [chapterId, setChapterId] = useState(chapter?.id || ''), [characterId, setCharacterId] = useState(''), [worldTime, setWorldTime] = useState('');
  const [target, setTarget] = useState<{ id: string; version: number }>();
  const [receipt, setReceipt] = useState<{ value: SimulatorContext; binding: string }>();
  const [assumptions, setAssumptions] = useState(''), [goal, setGoal] = useState(''), [motivation, setMotivation] = useState(''), [knowledgeIds, setKnowledgeIds] = useState<string[]>([]);
  const [resources, setResources] = useState<Amount[]>([]), [caps, setCaps] = useState<Amount[]>([]), [forbidden, setForbidden] = useState(''), [required, setRequired] = useState('');
  const [maxSteps, setMaxSteps] = useState('4'), [maxBranches, setMaxBranches] = useState('2');
  const [routes, setRoutes] = useState<RouteDraft[]>(() => [newRoute(1), newRoute(2)]);
  const [chosen, setChosen] = useState(''), [reviewed, setReviewed] = useState(false), [needsRefresh, setNeedsRefresh] = useState(false), [savedProposal, setSavedProposal] = useState('');
  useLayoutEffect(() => { epoch.current++; setReceipt(undefined); setReviewed(false); if (runId) detail.reload(); }, [chapter?.id, chapter?.version]);
  const ready = !catalog.loading && !catalog.error && !!catalog.data;
  const sources = ready ? catalog.data!.chapters.filter(row => row.id in sourceVersions) : [];
  const localSourceChanged = !!chapter && chapter.id in sourceVersions && chapter.version > sourceVersions[chapter.id];
  const sourcesMatch = ready && !!sources.length && sources.length === Object.keys(sourceVersions).length && sources.every(row => row.version === sourceVersions[row.id]) && !localSourceChanged;
  const node = ready ? catalog.data!.planning_nodes.find(row => row.id === target?.id) : undefined;
  const targetMatches = !!node && node.version === target?.version;
  const targetSourcesMatch = !!node && node.chapter_ids.every(id => id in sourceVersions);
  const timeValid = !worldTime || /^-?\d+$/.test(worldTime) && Number.isSafeInteger(Number(worldTime));
  const contextBinding = JSON.stringify([chapterId, sourceVersions[chapterId], characterId, worldTime]);
  const context = ready && sourcesMatch && receipt?.binding === contextBinding ? receipt.value : undefined;
  const fresh = ready && !runs.loading && !runs.error && !detail.loading && !detail.error && !needsRefresh && !localSourceChanged;
  const run = fresh && detail.data?.id === runId ? detail.data : undefined;
  const activeRun = run && !run.stale ? run : undefined;
  const selectedRoute = activeRun?.routes?.find(row => row.id === chosen);
  const branchLimit = catalog.data?.limits.max_branches || 8, stepLimit = catalog.data?.limits.max_steps || 32;
  const limitsValid = /^\d+$/.test(maxSteps) && Number(maxSteps) >= 1 && Number(maxSteps) <= stepLimit && /^\d+$/.test(maxBranches) && Number(maxBranches) >= 1 && Number(maxBranches) <= branchLimit && routes.length <= Number(maxBranches);
  const routeValid = routes.length > 0 && routes.every(route => route.title.trim() && route.events.length > 0 && route.events.length <= stepLimit && route.events.every(event => event.title.trim() && Number.isSafeInteger(event.at) && amountsValid(event.resource_delta, true) && event.requires_knowledge.every(id => context?.knowledge.some(item => item.id === id) && knowledgeIds.includes(id))));
  const canCreate = ready && sourcesMatch && targetMatches && targetSourcesMatch && !!context && limitsValid && routeValid && amountsValid(resources) && amountsValid(caps) && !action.busy && !needsRefresh;
  const invalidateContext = () => { epoch.current++; setReceipt(undefined); setKnowledgeIds([]); };
  const refresh = () => { epoch.current++; setReceipt(undefined); setReviewed(false); setNeedsRefresh(false); catalog.reload(); runs.reload(); detail.reload(); action.clear(); };
  const changeRoute = (id: string, update: (route: RouteDraft) => RouteDraft) => setRoutes(current => current.map(route => route.id === id ? update(route) : route));
  const runWrite = (operation: (current: () => boolean) => Promise<unknown>, message: string) => action.run(async isCurrent => {
    const ticket = ++epoch.current;
    try { await operation(() => isCurrent() && ticket === epoch.current); if (isCurrent() && ticket === epoch.current) { setReviewed(false); detail.reload(); runs.reload(); } }
    catch (error) { if (isCurrent() && ticket === epoch.current) setNeedsRefresh(true); throw error; }
  }, message);
  const loadContext = () => action.run(async isCurrent => {
    const ticket = ++epoch.current, binding = contextBinding;
    setReceipt(undefined); setKnowledgeIds([]);
    try { const value = await api.context({ chapter_id: chapterId, expected_version: sourceVersions[chapterId], character_id: characterId, world_time: worldTime ? Number(worldTime) : null, calendar: 'story' }); if (isCurrent() && ticket === epoch.current) setReceipt({ value, binding }); }
    catch (error) { if (isCurrent() && ticket === epoch.current) setNeedsRefresh(true); throw error; }
  }, '人物视角已读取。请核对已知信息并明确选择；动机仍由作者填写为假设。');
  const recoverInput = (input: SimulatorInput) => {
    invalidateContext(); setSourceVersions(input.expected_versions); setChapterId(input.chapter_id); setCharacterId(input.character_id);
    setWorldTime(input.world_time === null ? '' : String(input.world_time)); setTarget({ id: input.node_id, version: input.expected_node_version });
    setAssumptions(input.assumptions.join('\n')); setGoal(input.character_goal); setMotivation(input.motivation_hypothesis);
    setResources(Object.entries(input.resources).map(([key, value]) => ({ key, value: String(value) })));
    setCaps(Object.entries(input.hard_constraints.resource_caps).map(([key, value]) => ({ key, value: String(value) })));
    setForbidden(input.hard_constraints.forbidden_facts.join('\n')); setRequired(input.hard_constraints.required_final_facts.join('\n'));
    setMaxSteps(String(input.max_steps)); setMaxBranches(String(input.max_branches));
    setRoutes(input.routes.map(route => ({ ...route, events: route.events.map(event => ({ ...event, resource_delta: Object.entries(event.resource_delta).map(([key, value]) => ({ key, value: String(value) })) })) })));
    sequence.current += input.routes.length * 32 + 256; setReviewed(false); setSavedProposal('');
  };
  const create = () => action.run(async isCurrent => {
    if (!canCreate || !context || !target) return;
    const ticket = ++epoch.current;
    const input: SimulatorInput = { chapter_ids: sources.map(row => row.id), expected_versions: { ...sourceVersions }, chapter_id: chapterId, character_id: characterId, world_time: worldTime ? Number(worldTime) : null, calendar: 'story', node_id: target.id, expected_node_version: target.version, context_digest: context.context_digest, assumptions: lines(assumptions), character_goal: goal.trim(), motivation_hypothesis: motivation.trim(), knowledge_ids: knowledgeIds, resources: amounts(resources), hard_constraints: { forbidden_facts: lines(forbidden), resource_caps: amounts(caps), required_final_facts: lines(required) }, max_steps: Number(maxSteps), max_branches: Number(maxBranches), model_id: null, model_budget: 0, routes: routes.map(route => ({ ...route, title: route.title.trim(), events: route.events.map(event => ({ ...event, title: event.title.trim(), requires: lines(event.requires.join('\n')), adds: lines(event.adds.join('\n')), removes: lines(event.removes.join('\n')), foreshadowing_links: lines(event.foreshadowing_links.join('\n')), resource_delta: amounts(event.resource_delta) })) })) };
    try { const result = await api.create(input); if (isCurrent() && ticket === epoch.current) { setRunId(result.id); setChosen(''); setReviewed(false); setSavedProposal(''); runs.reload(); detail.reload(); } }
    catch (error) { if (isCurrent() && ticket === epoch.current) setNeedsRefresh(true); throw error; }
  }, '已保存推演输入。尚未执行任何步骤；点击“推进一步”才检查下一事件。');
  return <section className="experimental-section" aria-label="有界剧情推演">
    <div className="experimental-actions"><h3>剧情推演</h3><Badge>手动确定性检查</Badge><Button disabled={action.busy || catalog.loading || runs.loading || detail.loading} onClick={refresh}>刷新推演与来源（保留输入）</Button></div>
    <p>用作者提供的有限事件比较候选路线，每次只推进一步。手工检查不调用模型。检查结束后可另行预览已配置的本地模型候选；文学质量、动机与因果关系仍由作者判断。</p>
    <StatusMessage>路线选择只会另存为待审规划。正文、Canon、分支和发布状态不会自动改变。</StatusMessage>
    <ResourceState loading={catalog.loading} error={catalog.error} />
    {!!action.error && <ErrorMessage error={action.error} />}{action.notice && <StatusMessage tone="success">{action.notice}</StatusMessage>}
    {(!!catalog.error || !!runs.error || !!detail.error || needsRefresh) && <StatusMessage tone="warning">请核对本机会话、分支权限、功能开关和来源版本，再刷新重试。表单输入保留；旧结果不能继续推进或保存，不会自动重发请求。</StatusMessage>}
    <Panel title="1. 来源与人物视角">
      <fieldset className="experimental-form" disabled={!ready || action.busy}><legend>已保存的来源章节</legend>{ready && catalog.data!.chapters.map(row => <label key={row.id} className="experimental-check"><input type="checkbox" checked={row.id in sourceVersions} disabled={!(row.id in sourceVersions) && Object.keys(sourceVersions).length >= 20} onChange={event => { invalidateContext(); setSourceVersions(current => { const next = { ...current }; if (event.target.checked) next[row.id] = row.version; else delete next[row.id]; return next; }); if (row.id === chapterId && !event.target.checked) setChapterId(''); }} />推演来源：{row.title} · v{row.version}</label>)}</fieldset>
      {ready && !catalog.data!.chapters.length && <EmptyState title="没有可用的已保存章节" detail="先保存正文，再返回刷新。不会读取其他分支作为替代。" />}
      {ready && !!Object.keys(sourceVersions).length && !sourcesMatch && <StatusMessage tone="warning">所选来源已变化或不可用。请核对最新章节后明确更新来源基线；输入不会被覆盖。<Button disabled={action.busy || localSourceChanged && sources.some(row => row.id === chapter?.id && row.version < chapter.version)} onClick={() => { invalidateContext(); setSourceVersions(Object.fromEntries(sources.map(row => [row.id, row.version]))); if (!sources.some(row => row.id === chapterId)) setChapterId(''); }}>已核对，更新来源版本（保留输入）</Button></StatusMessage>}
      <div className="experimental-grid">
        <Field label="人物视角所在章节"><select disabled={!ready || action.busy} value={chapterId} onChange={event => { invalidateContext(); setChapterId(event.target.value); }}><option value="">选择所选来源中的章节</option>{sources.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></Field>
        <Field label="推演人物"><select disabled={!ready || action.busy} value={characterId} onChange={event => { invalidateContext(); setCharacterId(event.target.value); }}><option value="">选择虚构人物</option>{ready && catalog.data!.characters.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
        <Field label="起始世界时间（整数，留空仅按章节）"><input type="number" step="1" disabled={action.busy} value={worldTime} onChange={event => { invalidateContext(); setWorldTime(event.target.value); }} /></Field>
        <Field label="待审规划的目标节点"><select disabled={!ready || action.busy} value={target?.id || ''} onChange={event => { const row = catalog.data?.planning_nodes.find(value => value.id === event.target.value); setTarget(row ? { id: row.id, version: row.version } : undefined); }}><option value="">选择现有规划节点</option>{ready && catalog.data!.planning_nodes.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}</select></Field>
      </div>
      {ready && !catalog.data!.characters.length && <EmptyState title="还没有可选择的人物" detail="在人物资料中创建虚构人物，再刷新此页。" />}
      {ready && !catalog.data!.planning_nodes.length && <EmptyState title="还没有可用的规划节点" detail="先在分层规划创建目标节点，再返回刷新。" />}
      {node && !targetSourcesMatch && <StatusMessage tone="warning">此规划节点还有未选的来源章节。请先选择该节点绑定的全部章节：{node.chapter_ids.filter(id => !(id in sourceVersions)).map(id => catalog.data?.chapters.find(row => row.id === id)?.title || id).join('、')}。</StatusMessage>}
      {ready && target && !targetMatches && <StatusMessage tone="warning">目标规划节点已变化或不可用。核对最新节点后再继续。{node && <Button disabled={action.busy} onClick={() => setTarget({ id: node.id, version: node.version })}>已核对，更新目标规划版本</Button>}</StatusMessage>}
      <Button disabled={!sourcesMatch || !chapterId || !characterId || !timeValid || action.busy || needsRefresh} onClick={() => void loadContext()}>读取并核对人物已知信息</Button>
      {!context && <p>选择来源、人物或时间后，需要重新读取视角。页面不会自动推断人物知道哪些秘密。</p>}
      {context && <section className="experimental-section" aria-label="人物已知信息"><h4>本次人物视角</h4><KnowledgeChoices knowledge={context.knowledge} selected={knowledgeIds} disabled={action.busy} label="使用已知信息" onChange={setKnowledgeIds} />{!context.knowledge.length && <EmptyState title="此视角没有可选的已知事实或秘密" detail="可继续填写作者假设，但不能把未知秘密当作人物知识。" />}{!!context.goals.length && <><h4>已有目标（仅供核对）</h4><ul>{context.goals.map(row => <li key={row.id}>{row.text} · v{row.version}</li>)}</ul></>}{!!context.graph_links?.length && <><h4>可引用的已审核图谱记录</h4><ul>{context.graph_links.map(row => <li key={row.id}>{row.text} · ID：{row.id} · v{row.version}</li>)}</ul></>}</section>}
      <Field label="人物目标"><textarea disabled={action.busy} maxLength={2000} value={goal} onChange={event => setGoal(event.target.value)} /></Field>
      <Field label="人物动机假设（不作为已证实事实）"><textarea disabled={action.busy} maxLength={2000} value={motivation} onChange={event => setMotivation(event.target.value)} /></Field>
      <Field label="起始事实与作者假设（每行一条）"><textarea disabled={action.busy} value={assumptions} onChange={event => setAssumptions(event.target.value)} placeholder="例如：门已关闭。标签需与事件的前提和变化完全一致。" /></Field>
    </Panel>
    <Panel title="2. 规则、资源与执行边界">
      <p>事实标签按完整文字匹配。规则只检查你明确填写的前提、资源数量和时间顺序，不理解未填写的世界法则。</p>
      <div className="experimental-grid"><AmountEditor label="初始资源" rows={resources} onChange={setResources} disabled={action.busy} /><AmountEditor label="资源上限" rows={caps} onChange={setCaps} disabled={action.busy} /></div>
      <div className="experimental-grid"><Field label="禁止出现的事实（每行一条）"><textarea disabled={action.busy} value={forbidden} onChange={event => setForbidden(event.target.value)} /></Field><Field label="结束时必须成立的事实（每行一条）"><textarea disabled={action.busy} value={required} onChange={event => setRequired(event.target.value)} /></Field><Field label="每条路线最大步数"><input type="number" min={1} max={stepLimit} step={1} disabled={action.busy} value={maxSteps} onChange={event => setMaxSteps(event.target.value)} /></Field><Field label="最大候选路线数"><input type="number" min={1} max={branchLimit} step={1} disabled={action.busy} value={maxBranches} onChange={event => setMaxBranches(event.target.value)} /></Field></div>
      <p>最多 {stepLimit} 步、{branchLimit} 条候选路线、{catalog.data?.limits.max_expansions || 256} 次事件检查。模型预算为 0，未配置模型执行。</p>
      {(!limitsValid || !amountsValid(resources) || !amountsValid(caps)) && <StatusMessage tone="warning">请输入边界内的整数；资源名称不能为空或重复，初始数量和上限不能为负数。候选数不得超过所设上限。</StatusMessage>}
    </Panel>
    <Panel title="3. 编辑有限候选路线">
      <p>路线按表单顺序逐步检查。执行后修改这里的输入只用于创建新记录，不会改变已保存的推演。</p>
      <div className="experimental-list">{routes.map((route, routeIndex) => <section className="experimental-record" key={route.id} aria-label={`候选路线 ${routeIndex + 1}`}>
        <div className="experimental-actions"><h4>路线 {routeIndex + 1}</h4><Button disabled={action.busy || routes.length <= 1} onClick={() => setRoutes(current => current.filter(row => row.id !== route.id))}>删除路线 {routeIndex + 1}</Button></div>
        <Field label={`路线 ${routeIndex + 1} 名称`}><input maxLength={240} disabled={action.busy} value={route.title} onChange={event => changeRoute(route.id, current => ({ ...current, title: event.target.value }))} /></Field>
        <Field label={`路线 ${routeIndex + 1} 动机假设（留空沿用上方）`}><textarea maxLength={2000} disabled={action.busy} value={route.motivation_hypothesis || ''} onChange={event => changeRoute(route.id, current => ({ ...current, motivation_hypothesis: event.target.value }))} /></Field>
        {route.events.map((event, eventIndex) => <EventEditor key={event.id} prefix={`路线 ${routeIndex + 1} 事件 ${eventIndex + 1}`} event={event} knowledge={context?.knowledge.filter(row => knowledgeIds.includes(row.id)) || []} disabled={action.busy} onChange={next => changeRoute(route.id, current => ({ ...current, events: current.events.map(row => row.id === event.id ? next : row) }))} onRemove={route.events.length <= 1 ? undefined : () => changeRoute(route.id, current => ({ ...current, events: current.events.filter(row => row.id !== event.id) }))} />)}
        <Button disabled={action.busy || route.events.length >= stepLimit} onClick={() => { const next = ++sequence.current; changeRoute(route.id, current => ({ ...current, events: [...current.events, newEvent(`${route.id}-event-${next}`, (current.events.at(-1)?.at || 0) + 1)] })); }}>为路线 {routeIndex + 1} 添加事件</Button>
      </section>)}</div>
      <Button disabled={action.busy || routes.length >= branchLimit || routes.length >= Number(maxBranches)} onClick={() => { const next = ++sequence.current; setRoutes(current => [...current, newRoute(next, Number(worldTime) || 0)]); }}>添加候选路线</Button>
      {context && routes.some(route => route.events.some(event => event.requires_knowledge.some(id => !knowledgeIds.includes(id) || !context.knowledge.some(row => row.id === id)))) && <StatusMessage tone="warning">事件引用的知识已不在本次人物视角选择中。请在事件内清除不可用的知识要求，或重新选择可用信息。</StatusMessage>}
      <Button variant="primary" disabled={!canCreate} onClick={() => void create()}>保存输入并创建推演</Button>
      {!canCreate && !action.busy && <p>创建前请核对来源、人物视角和目标规划，填写路线及事件名称，并检查资源与执行边界。</p>}
    </Panel>
    <Panel title="4. 手动推进与候选比较">
      <ResourceState loading={runs.loading} error={runs.error} />
      {!runs.loading && !runs.error && !runs.data?.items.length && <EmptyState title="还没有剧情推演记录" detail="保存输入只创建等待中的记录，不会自动执行或调用模型。" />}
      <Field label="查看剧情推演记录"><select value={runId} disabled={!ready || runs.loading || !!runs.error || action.busy} onChange={event => { epoch.current++; setRunId(event.target.value); setChosen(''); setReviewed(false); setSavedProposal(''); }}><option value="">选择一次推演</option>{ready && !runs.loading && !runs.error && runs.data?.items.map((row, index) => <option key={row.id} value={row.id}>推演 {index + 1} · {statuses[row.status]}{row.stale ? ' · 来源已变化' : ''} · {row.created_at || row.id.slice(0, 12)}</option>)}</select></Field>
      {runId && <ResourceState loading={detail.loading} error={detail.error} />}
      {runId && localSourceChanged && <StatusMessage tone="warning">当前章节版本已变化。旧结果已隐藏，请刷新并核对来源。</StatusMessage>}
      {run && <><div className="experimental-actions"><Badge tone={run.stale ? 'warning' : run.status === 'COMPLETED' ? 'success' : 'neutral'}>{run.stale ? '来源已变化' : statuses[run.status]}</Badge><span>v{run.version}</span></div>{run.stale ? <StatusMessage tone="warning">旧来源的路线与证据已隐藏，不能继续推进或另存规划。请核对最新来源并重新读取人物视角，再创建新的推演；历史记录保留。</StatusMessage> : <>
        <p>已检查 {run.expansions || 0} 个事件 · 每路线最多 {run.limits?.max_steps} 步 · 最多 {run.limits?.max_branches} 条路线 · {run.model_called ? '含模型候选（质量未验证）' : '未调用模型'}</p>
        <div className="experimental-actions">{run.input && <Button disabled={action.busy} onClick={() => recoverInput(run.input!)}>用此记录恢复输入（覆盖当前表单）</Button>}<Button disabled={action.busy || !['READY', 'RUNNING'].includes(run.status)} onClick={() => void runWrite(() => api.step(run), '已检查每条未结束路线的下一个事件。不会自动继续。')}>推进一步</Button><Button disabled={action.busy || !['READY', 'RUNNING'].includes(run.status)} onClick={() => void runWrite(() => api.cancel(run), '推演已取消。已记录的检查保留，不会继续执行。')}>取消本次推演</Button>{run.chapter_id && <Button disabled={action.busy || !onNavigate} onClick={() => onNavigate?.({ kind: 'chapter', id: run.chapter_id!, version: run.source_version })}>打开推演来源章节</Button>}</div>
        {run.status === 'CANCELLED' && <StatusMessage>取消后的记录不能继续或另存规划。上方输入仍可用于明确创建新推演。</StatusMessage>}
        {!run.routes?.length && <EmptyState title="本次记录没有可比较的路线" detail="请核对来源和输入，再创建新推演。" />}
        <div className="experimental-grid" aria-label="候选路线比较">{run.routes?.map(route => <RouteResult key={`${run.id}:${route.id}`} route={route} selected={chosen === route.id} disabled={action.busy || run.status !== 'COMPLETED' || route.status === 'PENDING' || !!route.saved_proposal_id} onSelect={() => { setChosen(route.id); setReviewed(false); setSavedProposal(''); }} />)}</div>
        <label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={action.busy || !selectedRoute || run.status !== 'COMPLETED' || !!selectedRoute.saved_proposal_id} onChange={event => setReviewed(event.target.checked)} />已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划</label>
        <Button disabled={action.busy || !reviewed || !selectedRoute || selectedRoute.status === 'PENDING' || !!selectedRoute.saved_proposal_id || run.status !== 'COMPLETED'} onClick={() => void runWrite(async current => { const result = await api.save(run, chosen); if (current()) setSavedProposal(result.proposal_id); }, '所选路线已另存为待审规划，仍需在分层规划中人工审核。')}>将所选路线另存为待审规划</Button>
        {savedProposal && <StatusMessage tone="success">待审规划已创建：{savedProposal}<Button disabled={!onNavigate || action.busy} onClick={() => onNavigate?.({ kind: 'feature', id: savedProposal, feature: 'advanced_planning_v2' })}>前往分层规划审核</Button></StatusMessage>}
        {run.provenance && <details className="experimental-details"><summary>执行来源与检查凭据</summary><p>方式：{run.provenance.execution === 'MODEL_CANDIDATE_MANUAL_SELECTION' ? '人工选用模型假设，规则仍为确定性检查' : '手动确定性检查'} · {run.provenance.method}</p><ul>{Object.entries(run.provenance.source_versions).map(([id, version]) => <li key={id}>来源 {id} · v{version.version}</li>)}</ul><p>输入凭据：{run.request_digest || run.provenance.input_digest}</p><p>结果凭据：{run.result_digest || '尚未执行'}</p></details>}
      </>}{!!run.limitations?.length && <section aria-label="推演判断边界"><h4>判断边界</h4><ul>{run.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></section>}</>}
    </Panel>
    {activeRun && <ModelCandidatesPanel key={activeRun.id} run={activeRun} routes={catalog.data?.model_routes || []} api={api} busy={action.busy} write={runWrite} onAdopt={row => { setRunId(row.id); setChosen(''); setReviewed(false); setSavedProposal(''); }} />}
  </section>;
}
type SimulatorApi = ReturnType<typeof storySimulatorClient>;
type SimulatorWrite = (operation: (current: () => boolean) => Promise<unknown>, message: string) => Promise<unknown>;
function ModelCandidatesPanel({ run, routes, api, busy, write, onAdopt }: { run: SimulatorRun; routes: SimulatorModelRoute[]; api: SimulatorApi; busy: boolean; write: SimulatorWrite; onAdopt: (row: SimulatorRun) => void }) {
  const [routeId, setRouteId] = useState(run.model_preview?.broker.chosen?.route_id || ''), [consent, setConsent] = useState(false), [candidateId, setCandidateId] = useState(''), [reviewed, setReviewed] = useState(false);
  const preview = run.model_preview, execution = run.model_execution;
  useLayoutEffect(() => { setConsent(false); setReviewed(false); }, [preview?.preview_digest, run.model_candidates_digest, run.version]);
  const modelAvailable = routes.some(route => route.available);
  const canPreview = !busy && run.status === 'COMPLETED' && !run.model_adoption && !execution && routes.some(route => route.route_id === routeId && route.available);
  const candidate = run.model_candidates?.find(row => row.id === candidateId);
  const previewMatchesRoute = preview?.broker.chosen?.route_id === routeId;
  const chosenRoute = routes.find(route => route.route_id === routeId);
  const terminal = !!execution && ['CANDIDATES', 'CANCELLED', 'UNKNOWN', 'DISCARDED'].includes(execution.status);
  return <Panel title="5. 可选本地模型候选">
    <p>先完成手工规则检查，再明确预览并发送一次。只发送本次已保存推演中角色可知的已审核人物上下文、所选证据与作者假设，不发送正文或作者全知资料。每次最多 {run.limits?.max_branches} 条路线、每条 {run.limits?.max_steps} 步。</p>
    <StatusMessage>模型输出仍是待审假设，质量验证 NOT_RUN。不会自动续跑、重试、选择路线或写入正文与 Canon。</StatusMessage>
    {run.model_adoption ? <StatusMessage>此记录由人工选用模型候选创建。请使用上方“推进一步”完成规则检查，再另存为待审规划。</StatusMessage> : <>
      {run.status !== 'COMPLETED' && <p>完成上方确定性检查后，才可预览模型请求。手工模式始终可用。</p>}
      {!modelAvailable && <EmptyState title="没有可用的已知零费用本地路线" detail="请在模型中心与模型调度配置当前可用路线和价格。未配置、未授权或关闭功能时，仍可继续手工推演。" />}
      <Field label="推演候选本地模型"><select value={routeId} disabled={busy || !!execution || run.status !== 'COMPLETED'} onChange={event => { setRouteId(event.target.value); setConsent(false); }}><option value="">明确选择一条已配置路线</option>{routes.map(route => <option key={route.route_id} value={route.route_id} disabled={!route.available}>{route.provider_id} / {route.model_id}{route.synthetic ? ' · 合成协议测试，非真实推理' : ''}{route.available ? '' : ` · ${route.reasons.join('、')}`}</option>)}</select></Field>
      {chosenRoute?.synthetic && <p>此路线是明确标注的合成协议测试，不代表真实模型推理或质量。</p>}
      <Button disabled={!canPreview} onClick={() => void write(() => api.modelPreview(run, routeId), '模型发送内容与费用预览已准备。尚未发送；请逐项核对。')}>预览模型候选请求（不发送）</Button>
      {run.model_unavailable && <StatusMessage tone="warning">模型来源、路线、费用、授权或会话已变化，旧模型预览和候选已隐藏。不会自动重发；手工结果仍可检查。</StatusMessage>}
      {preview && <section aria-label="模型候选发送预览"><h4>本次确切发送预览</h4><p>范围：{preview.source_strategy} · 输出上限 {preview.max_output_bytes} 字节 · 超时 {preview.timeout_seconds} 秒 · LOCAL_ONLY</p>
        {preview.broker.chosen ? <p>路线：{preview.broker.chosen.provider_id} / {preview.broker.chosen.model_id} · 本次提供商费用上限 0 USD · {preview.broker.chosen.synthetic ? '合成协议测试' : '已配置零费率'}。价格来源：{preview.broker.chosen.price.source}{preview.broker.chosen.price.as_of && ` · ${preview.broker.chosen.price.as_of}`}{preview.broker.chosen.price.expires_at && ` · 有效至 ${preview.broker.chosen.price.expires_at}`}。不包含本机设备与电力成本。</p> : <StatusMessage tone="warning">当前没有满足约束的路线：{preview.broker.candidates.flatMap(row => row.reasons).join('、')}</StatusMessage>}
        <details className="experimental-details"><summary>核对完整发送指令与角色上下文</summary><pre>{JSON.stringify(preview.request, null, 2)}</pre></details>
        {!previewMatchesRoute && <StatusMessage tone="warning">模型选择已变化。请重新预览所选路线后再确认发送。</StatusMessage>}
        <label className="experimental-check"><input type="checkbox" checked={consent} disabled={busy || !!execution || !preview.execution_available || !previewMatchesRoute} onChange={event => setConsent(event.target.checked)} />我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求</label>
        <Button disabled={busy || !!execution || !consent || !preview.execution_available || !previewMatchesRoute} onClick={() => void write(() => api.modelDispatch(run), '本次请求已登记；不会自动重试。可手动检查结果或取消。')}>发送这一次模型候选请求</Button>
      </section>}
      {execution && <section aria-label="模型候选执行状态"><p>状态：{execution.status} · 回执：{execution.receipt_state} · 质量验证：NOT_RUN</p>{execution.accounting && <p>费用账本：{execution.accounting.status} · {execution.accounting.actual_microusd === null ? '实际费用未知' : `实际 ${execution.accounting.actual_microusd} 微美元`}</p>}{execution.failure_code && <StatusMessage tone="warning">{execution.failure_code}</StatusMessage>}
        <Button disabled={busy || terminal} onClick={() => void write(() => api.modelRefresh(run), '已检查原任务回执，不会启动新请求。')}>检查原模型请求结果</Button>
        <Button disabled={busy || execution.status === 'CANCELLED' || !!run.model_adopted_run_id} onClick={() => void write(() => api.modelCancel(run), '模型候选已取消并丢弃。迟到结果不会加入，原请求不会重试。')}>取消模型候选并丢弃结果</Button>
        {['UNKNOWN', 'CANCELLED', 'DISCARDED'].includes(execution.status) && <StatusMessage tone="warning">此次请求不会再发送或追加结果。可保留上方手工推演；新请求必须另建明确的推演记录。</StatusMessage>}
      </section>}
      {!!run.model_candidates?.length && <section aria-label="模型假设候选比较"><h4>模型假设与原规则检查</h4>{run.model_candidates.map(row => <div key={row.id}><RouteResult route={row.rules} selected={candidateId === row.id} disabled={busy || !!run.model_adopted_run_id} onSelect={() => { setCandidateId(row.id); setReviewed(false); }} selectionLabel={`选用模型候选 ${row.rules.title} 创建独立推演`} /><p>证据引用：{row.evidence_ids.length ? row.evidence_ids.join('、') : '无，明确标为推测假设'}</p></div>)}
        <label className="experimental-check"><input type="checkbox" checked={reviewed} disabled={busy || !candidate || !!run.model_adopted_run_id} onChange={event => setReviewed(event.target.checked)} />已核对所选模型假设、证据与违规，只创建待手动推进的独立推演</label>
        <Button disabled={busy || !candidate || !reviewed || !!run.model_adopted_run_id} onClick={() => void write(async current => { const adopted = await api.modelSelect(run, candidateId); if (current()) onAdopt(adopted); }, '所选候选已创建独立推演。请手动推进检查，再通过原有待审规划流程审核。')}>将选中模型候选创建为独立推演</Button>
        {run.model_adopted_run_id && <StatusMessage>已选用为独立推演：{run.model_adopted_run_id}。不会重复创建或自动接受规划。</StatusMessage>}
      </section>}
    </>}
  </Panel>;
}
function newEvent(id: string, at = 0): EventDraft { return { id, title: '', at, requires: [], adds: [], removes: [], requires_knowledge: [], resource_delta: [], foreshadowing_links: [], question: '' }; }
function newRoute(index: number, at = 0): RouteDraft { return { id: `route-${index}`, title: '', events: [newEvent(`route-${index}-event-1`, at)] }; }
function AmountEditor({ label, rows, onChange, disabled, signed = false }: { label: string; rows: Amount[]; onChange: (rows: Amount[]) => void; disabled: boolean; signed?: boolean }) {
  return <fieldset className="experimental-form" disabled={disabled}><legend>{label}</legend>{rows.map((row, index) => <div className="experimental-grid" key={index}><Field label={`${label} ${index + 1} 名称`}><input maxLength={120} value={row.key} onChange={event => onChange(rows.map((item, at) => at === index ? { ...item, key: event.target.value } : item))} /></Field><Field label={`${label} ${index + 1} 数量`}><input type="number" min={signed ? undefined : 0} step={1} value={row.value} onChange={event => onChange(rows.map((item, at) => at === index ? { ...item, value: event.target.value } : item))} /></Field><Button type="button" onClick={() => onChange(rows.filter((_, at) => at !== index))}>删除{label} {index + 1}</Button></div>)}<Button type="button" disabled={rows.length >= 32} onClick={() => onChange([...rows, { key: '', value: '0' }])}>添加{label}</Button></fieldset>;
}
function KnowledgeChoices({ knowledge, selected, disabled, label, onChange }: { knowledge: SimulatorKnowledge[]; selected: string[]; disabled: boolean; label: string; onChange: (values: string[]) => void }) {
  return <>{knowledge.map(row => <label key={row.id} className="experimental-check"><input type="checkbox" disabled={disabled} checked={selected.includes(row.id)} onChange={() => onChange(selected.includes(row.id) ? selected.filter(id => id !== row.id) : [...selected, row.id])} />{label}：{row.text} · v{row.version}</label>)}</>;
}
function EventEditor({ prefix, event, knowledge, disabled, onChange, onRemove }: { prefix: string; event: EventDraft; knowledge: SimulatorKnowledge[]; disabled: boolean; onChange: (event: EventDraft) => void; onRemove?: () => void }) {
  const lists = { requires: '前提事实', adds: '新增事实', removes: '移除事实', foreshadowing_links: '伏笔关联提示' } as const;
  return <fieldset className="experimental-form" disabled={disabled}><legend>{prefix}</legend><div className="experimental-grid"><Field label={`${prefix} 名称`}><input maxLength={240} value={event.title} onChange={value => onChange({ ...event, title: value.target.value })} /></Field><Field label={`${prefix} 世界时间`}><input type="number" step={1} value={Number.isNaN(event.at) ? '' : event.at} onChange={value => onChange({ ...event, at: value.target.value === '' ? NaN : Number(value.target.value) })} /></Field></div><details className="experimental-details"><summary>{prefix} 前提、变化与未决问题</summary><div className="experimental-grid">{Object.entries(lists).map(([key, label]) => <Field key={key} label={`${prefix} ${label}（每行一条）`}><textarea value={event[key as keyof typeof lists].join('\n')} onChange={value => onChange({ ...event, [key]: value.target.value.split('\n') })} /></Field>)}</div><p>伏笔关联填写下方角色可见图谱的记录 ID；只能确认引用可用，不能证明伏笔已回收。</p><KnowledgeChoices knowledge={knowledge} selected={event.requires_knowledge} disabled={disabled} label={`${prefix} 需要已知信息`} onChange={values => onChange({ ...event, requires_knowledge: values })} />{event.requires_knowledge.some(id => !knowledge.some(row => row.id === id)) && <Button type="button" onClick={() => onChange({ ...event, requires_knowledge: event.requires_knowledge.filter(id => knowledge.some(row => row.id === id)) })}>清除{prefix} 不可用的知识要求</Button>}<AmountEditor label={`${prefix} 资源变化`} rows={event.resource_delta} signed disabled={disabled} onChange={rows => onChange({ ...event, resource_delta: rows })} /><Field label={`${prefix} 未决问题`}><textarea maxLength={1000} value={event.question} onChange={value => onChange({ ...event, question: value.target.value })} /></Field></details>{onRemove && <Button type="button" onClick={onRemove}>删除{prefix}</Button>}</fieldset>;
}
function RouteResult({ route, selected, disabled, onSelect, selectionLabel }: { route: SimulatorRoute; selected: boolean; disabled: boolean; onSelect: () => void; selectionLabel?: string }) {
  return <article className={`experimental-record${selected ? ' is-selected' : ''}`} aria-label={`比较路线 ${route.title}`}><div className="experimental-actions"><h4>{route.title}</h4><Badge tone={route.violations.length ? 'warning' : 'neutral'}>{{ PENDING: '尚未结束', COMPLETED: '已结束', LIMIT_REACHED: '达到步数上限' }[route.status]}</Badge></div><p>已检查 {route.cursor} 步 · {route.violations.length} 条规则违规 · {route.unresolved_questions.length} 个未决问题</p><p>人物目标：{route.character_goal || '未填写'}</p><p>动机假设：{route.motivation_hypothesis || '未填写，不能推断'}</p>{!route.steps.length && <p>尚未检查事件。</p>}<ol>{route.steps.map(step => <li key={step.event_id}><strong>{step.title}</strong> · 时间 {step.at} · {step.applied ? '状态变化已应用' : '未应用状态变化'}{step.violations.length > 0 && <ul>{step.violations.map((item, index) => <li key={index}>{item.message}（{item.code}）</li>)}</ul>}{step.question && <p>未决问题：{step.question}</p>}{step.foreshadowing_links.length > 0 && <p>伏笔提示：{step.foreshadowing_links.join('、')}</p>}</li>)}</ol>{route.violations.length > 0 && <section aria-label={`${route.title} 规则违规`}><h5>规则违规</h5><ul>{route.violations.map((item, index) => <li key={index}>{item.message}（{item.code}）</li>)}</ul></section>}{!!route.unresolved_questions.length && <section aria-label={`${route.title} 未决问题`}><h5>仍需作者判断</h5><ul>{route.unresolved_questions.map((text, index) => <li key={index}>{text}</li>)}</ul></section>}{route.status === 'COMPLETED' && !route.violations.length && <p>所填规则未发现违规，不代表动机、因果或文学质量已通过。</p>}{route.saved_proposal_id ? <StatusMessage>已另存待审规划：{route.saved_proposal_id}</StatusMessage> : <label className="experimental-check"><input type="radio" name={selectionLabel ? 'simulator-model-candidate' : 'simulator-chosen-route'} checked={selected} disabled={disabled} onChange={onSelect} />{selectionLabel || `选择路线 ${route.title} 另存待审规划`}</label>}</article>;
}
