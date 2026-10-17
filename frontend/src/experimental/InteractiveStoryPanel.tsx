import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { InteractiveStoryHistory } from './InteractiveStoryHistory';
import { InteractiveStoryPreview } from './InteractiveStoryPreview';
import { interactiveStoryClient, type InteractiveStory, type StoryCatalog, type StoryExportPreview, type StoryIssue, type StoryNode, type StoryReviewPreview, type StoryRefreshPreview, type StorySpec, type StoryVariable } from './interactiveStoryClient';
import { applyNodeRemoval, previewNodeRemoval, type NodeRemovalPreview } from './interactiveNodeRemoval';
import './interactiveStory.css';
let instance = 0;
export function InteractiveStoryPanel({ client }: { client: ExperimentalClient }) {
  const key = useMemo(() => ++instance, [client]); return <StoryBody key={key} client={client} />;
}
type StoryApi = ReturnType<typeof interactiveStoryClient>;
function StoryBody({ client }: { client: ExperimentalClient }) {
  const api = useMemo(() => interactiveStoryClient(client), [client]);
  const catalog = useResource(signal => api.catalog(signal), [api]), stories = useResource(signal => api.list(signal), [api]);
  const [title, setTitle] = useState(''), [graphId, setGraphId] = useState(''), [nodeIds, setNodeIds] = useState<string[]>([]);
  const [story, setStory] = useState<InteractiveStory>(), [dirty, setDirty] = useState(false), [refresh, setRefresh] = useState<StoryRefreshPreview>();
  const alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const updated = (value: InteractiveStory) => { if (alive.current) { epoch.current++; setStory(value); setDirty(false); setRefresh(undefined); stories.reload(); } };
  const perform = (fn: () => Promise<InteractiveStory>, message: string) => void action.run(async () => { const ticket = epoch.current; const value = await fn(); if (alive.current && ticket === epoch.current) updated(value); }, message);
  const graph = catalog.data?.graphs.find(g => g.id === graphId);
  const choose = (value: InteractiveStory) => { epoch.current++; setStory(value); setDirty(false); setRefresh(undefined); };
  return <section className="experimental-section interactive-story" aria-label="互动故事与导出"><Panel title="规划节点改编为互动故事"><p>复用原规划图和节点 ID，另存作者私有互动改编。剧情结局不是协作分支；不会改写原稿、Canon 或批准资产。</p><StatusMessage>本地确定性功能，无模型调用。Ren’Py 8.5.4 文本/菜单子集，目标软件运行验证：NOT_RUN。</StatusMessage>
    <ResourceState loading={catalog.loading} error={catalog.error} empty={!catalog.data?.graphs.length} />
    {!catalog.loading && !catalog.error && !catalog.data?.graphs.length && <p>请先在「分层规划」创建规划图和剧情节点。</p>}
    <Field label="互动故事名称"><input value={title} maxLength={160} disabled={action.busy || dirty} onChange={e => setTitle(e.target.value)} /></Field>
    <Field label="原规划图"><select disabled={action.busy || dirty} value={graphId} onChange={e => { setGraphId(e.target.value); setNodeIds([]); }}><option value="">选择原规划图</option>{catalog.data?.graphs.map(g => <option key={g.id} value={g.id}>{g.title} · v{g.version}</option>)}</select></Field>
    {graph && <fieldset><legend>选择要改编的原规划节点</legend>{graph.nodes.map(n => <label className="experimental-check" key={n.node_id}><input type="checkbox" disabled={action.busy || dirty} checked={nodeIds.includes(n.node_id)} onChange={e => setNodeIds(old => e.target.checked ? [...old, n.node_id] : old.filter(id => id !== n.node_id))} />{n.title}</label>)}{graph.truncated && <p>只列出前 100 个节点，请拆分较大的规划图。</p>}</fieldset>}
    <div className="experimental-actions"><Button disabled={action.busy || dirty || !title.trim() || !graph || !nodeIds.length} onClick={() => { if (!graph) return; perform(() => api.create({ title, graph_id: graph.id, graph_version: graph.version, entry_node_id: nodeIds[0], max_steps: 32, variables: [], graph_record_ids: [], nodes: nodeIds.map(id => graph.nodes.find(n => n.node_id === id)!).map(n => ({ ...n, dialogue: '', ending: '', character_id: null, background_asset_id: null, music_asset_id: null, choices: [] })) }), '互动改编已保存，原规划不变。'); }}>创建互动改编</Button><Button disabled={dirty || action.busy} onClick={catalog.reload}>刷新可用规划与资产</Button></div>
  </Panel>{action.feedback}
  {dirty && <StatusMessage tone="warning">有未保存的互动草稿。请保存或还原后再切换记录。保存冲突时输入会保留。</StatusMessage>}
  <Panel title="互动改编记录"><Button disabled={dirty || action.busy || stories.loading} onClick={stories.reload}>刷新互动记录</Button><ResourceState loading={stories.loading} error={stories.error} empty={!stories.data?.items.length} />
    {!stories.loading && !stories.error && stories.data?.items.map(row => <div className="experimental-actions" key={row.id}><Button disabled={dirty || action.busy} aria-pressed={story?.id === row.id} onClick={() => choose(row)}>{row.spec?.title || '来源变化的互动改编'} · v{row.version}</Button><Badge tone={row.stale ? 'warning' : 'neutral'}>{row.stale ? 'STALE' : row.status}</Badge></div>)}
  </Panel>
  {story && <><Panel title="当前改编状态"><Badge>{story.status} · v{story.version}</Badge><Button disabled={dirty || action.busy} onClick={() => perform(() => api.get(story), '已核对最新版本。')}>核对当前互动版本</Button>
    {story.stale && <StatusMessage tone="warning">规划、正文、图谱、角色或资源已改变。旧内容已停止展示和导出。可明确预览并重新绑定当前仍有权限的同一来源，再人工复核旧对白；缺失或撤权的引用必须先恢复权限，或另建改编。</StatusMessage>}
    {story.stale && <><Button disabled={action.busy} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.refreshPreview(story); if (alive.current && ticket === epoch.current) setRefresh(result); }, '已检查当前来源，尚未重新绑定。')}>预览互动来源重绑定</Button>
      {refresh && <section aria-label="互动来源重绑定"><p>保留 {refresh.retained_nodes} 个原规划节点；更新 {refresh.changed_source_count} 个章节来源。对白和选择保留为未审核草稿，不自动改写。</p><Button disabled={action.busy} onClick={() => perform(() => api.refresh(story, refresh), '已重新绑定当前来源，请人工复核后重新审核。')}>确认重绑定并重新审核</Button></section>}</>}
    <Button disabled={dirty || action.busy || story.status === 'ARCHIVED'} onClick={() => perform(() => api.review(story, 'archive'), '改编已归档，记录仍可恢复。')}>归档互动改编</Button>
    {story.status === 'ARCHIVED' && <Button disabled={action.busy || story.stale} onClick={() => perform(() => api.review(story, 'restore'), '改编恢复为待审草稿。')}>恢复互动改编</Button>}
  </Panel>
  {!story.stale && !story.content_withheld && story.spec && catalog.data && <><StoryEditor key={`editor:${story.id}:${story.version}`} story={story} catalog={catalog.data} catalogReady={!catalog.loading && !catalog.error} busy={action.busy} onDirty={setDirty} onSave={spec => perform(() => api.save(story, spec), '互动草稿已保存，需要重新审核。')} />
    <InteractiveStoryHistory key={`history:${story.id}:${story.version}`} api={api} story={story} blocked={dirty || action.busy} perform={perform} />
    <InteractiveStoryPreview api={api} story={story} blocked={dirty || action.busy} />
    <StoryApproval key={`approval:${story.id}:${story.version}`} api={api} story={story} blocked={dirty || action.busy} perform={perform} />
  </>}
  </>}
  </section>;
}
function issueNodeIndex(spec: StorySpec, issue: StoryIssue, removedChoices: ReadonlySet<string>, removedNodes: ReadonlySet<string>): number {
  if (typeof issue.node_id !== 'string' || !issue.node_id.trim() || removedNodes.has(issue.node_id)) return -1;
  const matches = spec.nodes.flatMap((node, index) => node.node_id === issue.node_id ? [index] : []);
  if (matches.length !== 1) return -1;
  if ('choice_id' in issue && (removedChoices.has(JSON.stringify([issue.node_id, issue.choice_id])) || typeof issue.choice_id !== 'string' || !issue.choice_id.trim() || spec.nodes[matches[0]].choices.filter(choice => choice.id === issue.choice_id).length !== 1)) return -1;
  return matches[0];
}
function Analysis({ story, spec, removedChoices, removedNodes, dirty, blocked, onLocate }: { story: InteractiveStory; spec: StorySpec; removedChoices: ReadonlySet<string>; removedNodes: ReadonlySet<string>; dirty: boolean; blocked: boolean; onLocate: (issue: StoryIssue) => void }) {
  const analysis = story.analysis!;
  const [page, setPage] = useState(0);
  const rows = [...analysis.issues.map(issue => ({ issue, label: '需修复' })), ...analysis.warnings.map(issue => ({ issue, label: '提醒' }))];
  const pages = Math.max(1, Math.ceil(rows.length / 20));
  return <Panel title="路径与变量检查"><p>检查来源：互动版本 v{story.version} · 原规划 {story.spec!.graph_id} v{story.spec!.graph_version}。定位只切换当前编辑节点，不保存或修改内容。</p>
    {dirty && <StatusMessage tone="warning">以下是已保存版本的检查结果，未包含当前未保存输入。请保存后重新核对；定位会保留输入。</StatusMessage>}
    <StatusMessage tone={analysis.can_review ? 'success' : 'warning'}>已检查 {analysis.states_checked} 个状态；发现 {analysis.endings.length} 个可达结局；步数上限 {analysis.max_steps}。{analysis.analysis_complete ? '有限状态搜索完成。' : '达到分析边界，不能据此批准导出。'}</StatusMessage>
    {rows.slice(page * 20, (page + 1) * 20).map(({ issue, label }, i) => {
      const available = issueNodeIndex(spec, issue, removedChoices, removedNodes) >= 0;
      return <div key={page * 20 + i} className="experimental-record"><p>{label}：{issue.code}{issue.node_id ? ` · 节点 ${issue.node_id}` : ''}{issue.choice_id ? ` · 选择 ${issue.choice_id}` : ''}</p>
        {issue.node_id && <><Button disabled={blocked || !available} onClick={() => onLocate(issue)} aria-label={`定位 ${issue.code} 节点 ${issue.node_id}${issue.choice_id ? ` 选择 ${issue.choice_id}` : ''}`}>定位原互动{issue.choice_id ? '选择' : '节点'}</Button>{!available && <p>当前草稿中没有唯一且未被替换的对应节点或选择，无法定位。</p>}</>}
      </div>;
    })}
    {pages > 1 && <div className="experimental-actions"><Button disabled={page === 0} onClick={() => setPage(p => p - 1)}>上一页路径问题</Button><span>路径问题第 {page + 1} / {pages} 页</span><Button disabled={page + 1 >= pages} onClick={() => setPage(p => p + 1)}>下一页路径问题</Button></div>}
    {analysis.endings.map(e => <p key={e.node_id}>可验证结局：{e.ending} · {e.choices.length} 次选择</p>)}<p>循环提醒不等于非法故事；无法到达结局或变量条件无出口需要修复。循环受运行步数限制；这是有界检查，不是所有可能故事的无限证明。</p>
  </Panel>;
}
function membershipGraph(spec: StorySpec, catalog: StoryCatalog) {
  const matches = catalog.graphs.filter(graph => graph.id === spec.graph_id);
  const graph = matches.length === 1 ? matches[0] : undefined;
  if (!graph || !Number.isSafeInteger(graph.version) || graph.version < 1 || graph.version !== spec.graph_version) return;
  const validText = (value: unknown, maximum: number) => typeof value === 'string' && [...value].length > 0 && [...value].length <= maximum && ![...value].some(char => { const code = char.codePointAt(0)!; return (code < 32 && !'\n\t\r'.includes(char)) || (code >= 0xd800 && code <= 0xdfff); });
  if (new Set(graph.nodes.map(node => node.node_id)).size !== graph.nodes.length || new Set(spec.nodes.map(node => node.node_id)).size !== spec.nodes.length) return;
  if (graph.nodes.some(node => !validText(node.node_id, 160) || !validText(node.title, 240) || !Number.isSafeInteger(node.node_version) || node.node_version < 1)) return;
  if (spec.nodes.some(node => !graph.nodes.some(source => source.node_id === node.node_id && source.node_version === node.node_version))) return;
  return graph;
}
function StoryEditor({ story, catalog, catalogReady, busy, onDirty, onSave }: { story: InteractiveStory; catalog: StoryCatalog; catalogReady: boolean; busy: boolean; onDirty: (value: boolean) => void; onSave: (spec: StorySpec) => void }) {
  const [spec, setSpec] = useState<StorySpec>(() => structuredClone(story.spec!)), [index, setIndex] = useState(0), [dirty, setDirty] = useState(false);
  const [name, setName] = useState(''), [kind, setKind] = useState<'bool' | 'int'>('bool'), [initial, setInitial] = useState('false'), [minimum, setMinimum] = useState(0), [maximum, setMaximum] = useState(100);
  const titleInput = useRef<HTMLInputElement>(null), choiceInputs = useRef(new Map<string, HTMLInputElement>());
  const [focusTarget, setFocusTarget] = useState<StoryIssue>();
  const removedChoices = useRef(new Set<string>()), removedNodes = useRef(new Set<string>());
  const [removal, setRemoval] = useState<{ preview: NodeRemovalPreview; generation: number; epoch: number }>();
  const removalEpoch = useRef(0);
  const invalidateRemoval = () => { removalEpoch.current++; setRemoval(undefined); };
  const composing = useRef(false); const [compositionActive, setCompositionActive] = useState(false);
  const membershipAlive = useRef(false);
  useEffect(() => { membershipAlive.current = true; return () => { membershipAlive.current = false; }; }, []);
  const sourceGeneration = useRef({ catalog, ready: catalogReady, generation: 0 });
  if (sourceGeneration.current.catalog !== catalog || sourceGeneration.current.ready !== catalogReady) sourceGeneration.current = { catalog, ready: catalogReady, generation: sourceGeneration.current.generation + 1 };
  const generation = sourceGeneration.current.generation;
  const [candidate, setCandidate] = useState<{ id: string; generation: number }>();
  const sourceGraph = catalogReady ? membershipGraph(spec, catalog) : undefined;
  const candidates = sourceGraph?.nodes.filter(source => !spec.nodes.some(node => node.node_id === source.node_id)) || [];
  const selectedCandidate = candidate?.generation === generation ? candidates.find(source => source.node_id === candidate.id) : undefined;
  // A retained callback must never revive after catalog/client A -> B -> A,
  // a save, a revert, or a newer local edit, even if IDs happen to match.
  const membershipTicket = {}; const currentMembershipTicket = useRef(membershipTicket); currentMembershipTicket.current = membershipTicket;
  const node = spec.nodes[index]; const blocked = busy || story.status === 'ARCHIVED';
  const currentEditor = () => membershipAlive.current && currentMembershipTicket.current === membershipTicket && !blocked;
  const removalAvailability = useRef(blocked);
  if (removalAvailability.current !== blocked) { removalAvailability.current = blocked; removalEpoch.current++; }
  const interactionEpoch = removalEpoch.current;
  useEffect(() => {
    if (!focusTarget || blocked || composing.current || node.node_id !== focusTarget.node_id) return;
    const input = focusTarget.choice_id ? choiceInputs.current.get(focusTarget.choice_id) : titleInput.current;
    input?.focus(); setFocusTarget(undefined);
  }, [focusTarget, index, blocked, node.node_id]);
  const liveEditor = useRef({ spec, blocked }); liveEditor.current = { spec, blocked };
  const locate = (issue: StoryIssue) => {
    const { spec: current, blocked: unavailable } = liveEditor.current;
    if (!membershipAlive.current || currentMembershipTicket.current !== membershipTicket || interactionEpoch !== removalEpoch.current || unavailable || composing.current) return;
    const targetIndex = issueNodeIndex(current, issue, removedChoices.current, removedNodes.current);
    if (targetIndex < 0) return;
    currentMembershipTicket.current = {}; invalidateRemoval(); setIndex(targetIndex); setFocusTarget({ ...issue });
  };
  useEffect(() => { if (!dirty) return; const guard = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard); }, [dirty]);
  const change = (value: StorySpec) => {
    if (!currentEditor()) return false;
    currentMembershipTicket.current = {}; invalidateRemoval();
    for (const oldNode of spec.nodes) if (!value.nodes.some(node => node.node_id === oldNode.node_id)) removedNodes.current.add(oldNode.node_id);
    // The original editor can reuse a removed choice ID. A saved issue must not
    // silently navigate to that replacement before save and owner reanalysis.
    for (const oldNode of spec.nodes) for (const choice of oldNode.choices) {
      if (!value.nodes.find(n => n.node_id === oldNode.node_id)?.choices.some(c => c.id === choice.id)) removedChoices.current.add(JSON.stringify([oldNode.node_id, choice.id]));
    }
    setSpec(value); setDirty(true); onDirty(true); return true; };
  const changePendingVariable = (update: () => void) => { if (!currentEditor()) return; currentMembershipTicket.current = {}; invalidateRemoval(); update(); };
  const edit = (patch: Partial<StoryNode>) => change({ ...spec, nodes: spec.nodes.map((n, i) => i === index ? { ...n, ...patch } : n) });
  const variables = spec.variables;
  const membershipBlocked = blocked || compositionActive || !sourceGraph || spec.nodes.length >= 100;
  const addNode = () => {
    if (!membershipAlive.current || currentMembershipTicket.current !== membershipTicket || interactionEpoch !== removalEpoch.current || composing.current || membershipBlocked || !selectedCandidate) return;
    const { node_id, node_version, title } = selectedCandidate;
    change({ ...spec, nodes: [...spec.nodes, { node_id, node_version, title, dialogue: '', ending: '', character_id: null, background_asset_id: null, music_asset_id: null, choices: [] }] });
    setIndex(spec.nodes.length); setFocusTarget(undefined); setCandidate(undefined);
  };
  const removalBlocked = blocked || compositionActive || !sourceGraph;
  const currentRemoval = removal && removal.preview.spec === spec && removal.generation === generation && removal.epoch === removalEpoch.current && !removalBlocked ? removal.preview : undefined;
  const previewRemoval = () => {
    if (!membershipAlive.current || currentMembershipTicket.current !== membershipTicket || interactionEpoch !== removalEpoch.current || composing.current || removalBlocked) return;
    currentMembershipTicket.current = {}; invalidateRemoval();
    setRemoval({ preview: previewNodeRemoval(spec, node.node_id), generation, epoch: removalEpoch.current });
  };
  const confirmRemoval = () => {
    if (!membershipAlive.current || currentMembershipTicket.current !== membershipTicket || composing.current || removalBlocked || !currentRemoval || removal?.epoch !== removalEpoch.current) return;
    const next = applyNodeRemoval(spec, currentRemoval); if (!next) return;
    change(next); setIndex(Math.min(index, next.nodes.length - 1)); setFocusTarget(undefined); setCandidate(undefined);
  };
  return <><Panel title="互动节点编辑"><fieldset disabled={blocked} onCompositionStartCapture={() => { if (!currentEditor()) return; invalidateRemoval(); composing.current = true; setCompositionActive(true); setFocusTarget(undefined); }} onCompositionEndCapture={() => { if (!currentEditor()) return; invalidateRemoval(); composing.current = false; setCompositionActive(false); }}>
    <Field label="改编标题"><input value={spec.title} maxLength={160} onChange={e => change({ ...spec, title: e.target.value })} /></Field>
    <fieldset><legend>添加原规划节点</legend><p>只添加当前原规划版本中尚未改编的节点。添加后请手动编写对白、结局和连接选择，再保存互动草稿。</p>
      <Field label="待添加原规划节点"><select value={selectedCandidate?.node_id || ''} disabled={membershipBlocked || !candidates.length} onChange={event => { if (!membershipAlive.current || currentMembershipTicket.current !== membershipTicket || interactionEpoch !== removalEpoch.current || composing.current || membershipBlocked) return; currentMembershipTicket.current = {}; invalidateRemoval(); setCandidate({ id: event.target.value, generation }); }}><option value="">选择尚未改编的原节点</option>{candidates.map(source => <option key={source.node_id} value={source.node_id}>{source.title} · {source.node_id} · v{source.node_version}</option>)}</select></Field>
      <Button disabled={membershipBlocked || !selectedCandidate} onClick={addNode}>添加所选原节点</Button>
      {!catalogReady ? <StatusMessage tone="warning">可用来源正在刷新或读取失败，暂不能添加节点。</StatusMessage> : !sourceGraph ? <StatusMessage tone="warning">原规划版本或节点来源无法精确匹配。请先保存或还原输入，再核对当前互动版本；来源变化时使用原有来源重绑定流程。</StatusMessage> : spec.nodes.length >= 100 ? <p>互动改编最多包含 100 个节点。</p> : !candidates.length ? <p>当前可用原节点均已加入改编。</p> : null}
      {sourceGraph?.truncated && <p>只列出前 100 个原规划节点，不会猜测未列出的来源。</p>}
    </fieldset>
    <div className="experimental-grid"><Field label="故事入口节点"><select value={spec.entry_node_id} onChange={e => change({ ...spec, entry_node_id: e.target.value })}>{spec.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.title} · {n.node_id} · v{n.node_version}</option>)}</select></Field><Field label="互动步数上限"><input type="number" min={1} max={128} value={spec.max_steps} onChange={e => change({ ...spec, max_steps: Number(e.target.value) })} /></Field></div>
    <Field label="当前编辑节点"><select value={index} onChange={e => { if (!currentEditor() || interactionEpoch !== removalEpoch.current || composing.current) return; const nextIndex = Number(e.target.value); if (!Number.isInteger(nextIndex) || nextIndex < 0 || nextIndex >= spec.nodes.length) return; currentMembershipTicket.current = {}; invalidateRemoval(); setFocusTarget(undefined); setIndex(nextIndex); }}>{spec.nodes.map((n, i) => <option key={n.node_id} value={i}>{n.title} · {n.node_id} · v{n.node_version}</option>)}</select></Field>
    <p>原节点 ID：{node.node_id} · v{node.node_version}</p>
    <fieldset><legend>移除当前互动节点</legend><p>先预览，再明确移除。仅影响此互动草稿；不会删除原规划节点。节点的对白、结局和出站选择将从草稿移除，重新添加时内容为空。入口和所有入站选择必须先用原有控件手动处理。</p>
      <Button disabled={removalBlocked} onClick={previewRemoval}>预览移除当前节点</Button>
      {removalBlocked && <p>来源未就绪、版本不匹配、归档、忙碌或输入法组合期间不能移除节点。</p>}
      {currentRemoval && <section aria-label="互动节点移除预览"><p>待移除：{currentRemoval.node?.title} · {currentRemoval.nodeId} · v{currentRemoval.node?.node_version}</p>
        {currentRemoval.blockers.map(reason => <StatusMessage key={reason} tone="warning">{reason}</StatusMessage>)}
        {currentRemoval.incoming.map((reference, i) => <p key={i}>入站引用：节点 {reference.nodeId} · 选择 {reference.choiceId}</p>)}
        {!currentRemoval.blockers.length && <p>将只移除这个节点；保留其余节点、变量、入口、来源 ID 与版本。此操作尚未保存。</p>}
        <Button disabled={!!currentRemoval.blockers.length} onClick={confirmRemoval}>确认移除所选节点</Button>
        <Button onClick={() => { if (!currentEditor() || interactionEpoch !== removalEpoch.current || composing.current) return; currentMembershipTicket.current = {}; invalidateRemoval(); }}>取消移除节点</Button>
      </section>}
    </fieldset>
    <Field label="互动节点标题"><input ref={titleInput} value={node.title} maxLength={240} onChange={e => edit({ title: e.target.value })} /></Field>
    <Field label="对白或叙述"><textarea value={node.dialogue} maxLength={8000} onChange={e => edit({ dialogue: e.target.value })} /></Field>
    <div className="experimental-grid"><Field label="对白角色"><select value={node.character_id || ''} onChange={e => edit({ character_id: e.target.value || null })}><option value="">旁白</option>{catalog.characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="背景资产引用"><select value={node.background_asset_id || ''} onChange={e => edit({ background_asset_id: e.target.value || null })}><option value="">无背景引用</option>{catalog.assets.filter(a => a.kind === 'image').map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></Field>
    <Field label="音乐资产引用"><select value={node.music_asset_id || ''} onChange={e => edit({ music_asset_id: e.target.value || null })}><option value="">无音乐引用</option>{catalog.assets.filter(a => a.kind === 'audio').map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></Field></div>
    <Field label="结局名称（留空表示非结局）"><input value={node.ending} disabled={node.choices.length > 0} maxLength={240} onChange={e => edit({ ending: e.target.value })} /></Field>
    {!!node.choices.length && <p>要改成结局，请先移除此节点的选择。</p>}
    {node.choices.map((choice, i) => <section className="experimental-record" key={choice.id} aria-label={`选择 ${i + 1}`}><Field label={`选择 ${i + 1} 文案`}><input value={choice.label} maxLength={240} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, label: e.target.value } : c) })} /></Field>
      <Field label={`选择 ${i + 1} 目标`}><select value={choice.target} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, target: e.target.value } : c) })}>{spec.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.title} · {n.node_id} · v{n.node_version}</option>)}</select></Field>
      <Field label={`选择 ${i + 1} 条件`}><input ref={element => { if (element) choiceInputs.current.set(choice.id, element); else choiceInputs.current.delete(choice.id); }} value={choice.condition} maxLength={240} placeholder="例如 courage >= 2 and trusted" onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, condition: e.target.value } : c) })} /></Field>
      <p>仅允许 bool/int 变量、True/False、比较、and/or/not 和括号；不执行代码。留空为始终可选。</p>
      {variables.map(v => <div key={v.name}><label className="experimental-check"><input type="checkbox" checked={v.name in choice.assignments} onChange={e => { const assignments = { ...choice.assignments }; if (e.target.checked) assignments[v.name] = v.initial; else delete assignments[v.name]; edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments } : c) }); }} />选择后设置 {v.name}</label>
        {v.name in choice.assignments && <Field label={`选择 ${i + 1} 设置 ${v.name}`}>{v.type === 'bool' ? <select value={String(choice.assignments[v.name])} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments: { ...c.assignments, [v.name]: e.target.value === 'true' } } : c) })}><option value="false">false</option><option value="true">true</option></select> : <input type="number" min={v.minimum} max={v.maximum} value={Number(choice.assignments[v.name])} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments: { ...c.assignments, [v.name]: Number(e.target.value) } } : c) })} />}</Field>}
      </div>)}<Button onClick={() => edit({ choices: node.choices.filter((_, j) => i !== j) })}>移除选择 {i + 1}</Button>
    </section>)}
    <Button disabled={!!node.ending || node.choices.length >= 8} onClick={() => { let n = 1; while (node.choices.some(c => c.id === `choice_${n}`)) n++; edit({ choices: [...node.choices, { id: `choice_${n}`, label: `选择 ${n}`, target: spec.nodes.find(s => s.node_id !== node.node_id)?.node_id || node.node_id, condition: '', assignments: {} }] }); }}>添加互动选择</Button>
    <h3>有界变量</h3>{variables.map(v => <div className="experimental-actions" key={v.name}><p>{v.name} · {v.type} · 初始 {String(v.initial)}{v.type === 'int' ? ` · ${v.minimum} 至 ${v.maximum}` : ''}</p><Button onClick={() => change({ ...spec, variables: variables.filter(item => item.name !== v.name) })}>移除变量 {v.name}</Button></div>)}
    <div className="experimental-grid"><Field label="新变量名称"><input value={name} pattern="[a-z][a-z0-9_]{0,31}" maxLength={32} onChange={e => changePendingVariable(() => setName(e.target.value))} /></Field><Field label="变量类型"><select value={kind} onChange={e => changePendingVariable(() => { const value = e.target.value as 'bool' | 'int'; setKind(value); setInitial(value === 'bool' ? 'false' : '0'); })}><option value="bool">bool</option><option value="int">int</option></select></Field>
    <Field label="变量初始值">{kind === 'bool' ? <select value={initial} onChange={e => changePendingVariable(() => setInitial(e.target.value))}><option value="false">false</option><option value="true">true</option></select> : <input type="number" value={initial} min={minimum} max={maximum} onChange={e => changePendingVariable(() => setInitial(e.target.value))} />}</Field>
    {kind === 'int' && <><Field label="变量最小值"><input type="number" value={minimum} min={-10000} max={10000} onChange={e => changePendingVariable(() => setMinimum(Number(e.target.value)))} /></Field><Field label="变量最大值"><input type="number" value={maximum} min={-10000} max={10000} onChange={e => changePendingVariable(() => setMaximum(Number(e.target.value)))} /></Field></>}
    </div><Button disabled={!/^[a-z][a-z0-9_]{0,31}$/.test(name) || variables.some(v => v.name === name) || variables.length >= 16} onClick={() => { const variable: StoryVariable = { name, type: kind, initial: kind === 'bool' ? initial === 'true' : Number(initial), minimum, maximum }; if (change({ ...spec, variables: [...variables, variable] })) setName(''); }}>添加有界变量</Button>
    <fieldset><legend>关联已审核故事图谱记录（可选，不复制事实）</legend>{catalog.graph_records.map(r => <label className="experimental-check" key={r.id}><input type="checkbox" checked={spec.graph_record_ids.includes(r.id)} onChange={e => change({ ...spec, graph_record_ids: e.target.checked ? [...spec.graph_record_ids, r.id] : spec.graph_record_ids.filter(id => id !== r.id) })} />{r.title} · v{r.version}</label>)}</fieldset>
    <div className="experimental-actions"><Button disabled={!dirty} onClick={() => { if (!currentEditor() || interactionEpoch !== removalEpoch.current || composing.current || !dirty) return; currentMembershipTicket.current = {}; invalidateRemoval(); onSave(spec); }}>保存互动草稿</Button><Button disabled={!dirty} onClick={() => { if (!currentEditor() || interactionEpoch !== removalEpoch.current || composing.current || !dirty) return; removedChoices.current.clear(); removedNodes.current.clear(); invalidateRemoval(); setIndex(0); setFocusTarget(undefined); setCandidate(undefined); currentMembershipTicket.current = {}; setSpec(structuredClone(story.spec!)); setDirty(false); onDirty(false); }}>还原未保存输入</Button></div>
    </fieldset></Panel>{story.analysis && <Analysis story={story} spec={spec} removedChoices={removedChoices.current} removedNodes={removedNodes.current} dirty={dirty} blocked={blocked || compositionActive} onLocate={locate} />}</>;
}
function StoryApproval({ api, story, blocked, perform }: { api: StoryApi; story: InteractiveStory; blocked: boolean; perform: (fn: () => Promise<InteractiveStory>, message: string) => void }) {
  const [review, setReview] = useState<StoryReviewPreview>(), [preview, setPreview] = useState<StoryExportPreview>(), [confirmed, setConfirmed] = useState(false);
  const [artifact, setArtifact] = useState<{ url: string; filename: string }>(); const url = useRef<string>(), alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; if (url.current) URL.revokeObjectURL(url.current); }; }, []);
  useEffect(() => { epoch.current++; setReview(undefined); setPreview(undefined); setConfirmed(false); if (url.current) URL.revokeObjectURL(url.current); url.current = undefined; setArtifact(undefined); }, [blocked]);
  const busy = blocked || action.busy;
  return <Panel title="审核与独立导出"><p>审核只批准此互动改编；导出为新的独立 ZIP 下载。包含版本化 story.json、生成的 Ren’Py 文本/菜单脚本、资源清单、缺失项、损失报告与校验和。媒体字节不随包导出。</p>
    <div className="experimental-actions"><Button disabled={busy || story.status !== 'DRAFT'} onClick={() => perform(() => api.review(story, 'submit'), '改编已提交审核。')}>提交互动审核</Button><Button disabled={busy || story.status !== 'REVIEW'} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.reviewPreview(story); if (alive.current && ticket === epoch.current) setReview(result); }, '审核预览已核对。')}>预览互动审核</Button>
      {review && <Button disabled={busy || !review.can_approve} onClick={() => perform(() => api.review(story, 'approve', review), '此版本互动改编已批准。')}>批准此互动版本</Button>}
      <Button disabled={busy || !['REVIEW', 'APPROVED'].includes(story.status)} onClick={() => perform(() => api.review(story, 'reopen'), '批准已撤销，重新开放为草稿。')}>撤销批准并重开</Button>
    </div>
    <Button disabled={busy || story.status !== 'APPROVED'} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.exportPreview(story); if (alive.current && ticket === epoch.current) { setPreview(result); setConfirmed(false); } }, '独立导出预检完成。')}>预检互动导出</Button>
    {preview && <section aria-label="互动导出预检"><p>目标运行：{preview.target_runtime}。缺失资源 {preview.media_manifest.filter(m => m.missing).length} 项；引用资源 {preview.media_manifest.length} 项。</p>{preview.losses.map(loss => <p key={loss}>{loss}</p>)}
      <label className="experimental-check"><input type="checkbox" checked={confirmed} disabled={busy || !preview.can_export} onChange={e => setConfirmed(e.target.checked)} />已核对缺失项与兼容性损失，确认生成独立下载</label>
      <Button disabled={busy || !confirmed || !preview.can_export} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await api.export(story, preview); if (alive.current && ticket === epoch.current) { const bytes = Uint8Array.from(atob(result.content_base64), c => c.charCodeAt(0)); if (url.current) URL.revokeObjectURL(url.current); url.current = URL.createObjectURL(new Blob([bytes], { type: result.mime })); setArtifact({ url: url.current, filename: result.filename }); } }, '独立互动故事包已准备好。')}>生成互动故事包</Button>
    </section>}{artifact && <a href={artifact.url} download={artifact.filename}>下载 {artifact.filename}</a>}{action.feedback}
  </Panel>;
}
