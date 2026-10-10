import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { InteractiveStoryHistory } from './InteractiveStoryHistory';
import { InteractiveStoryPreview } from './InteractiveStoryPreview';
import { interactiveStoryClient, type InteractiveStory, type StoryAnalysis, type StoryCatalog, type StoryExportPreview, type StoryNode, type StoryReviewPreview, type StoryRefreshPreview, type StorySpec, type StoryVariable } from './interactiveStoryClient';
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
  {!story.stale && story.spec && catalog.data && <><StoryEditor key={`editor:${story.id}:${story.version}`} story={story} catalog={catalog.data} busy={action.busy} onDirty={setDirty} onSave={spec => perform(() => api.save(story, spec), '互动草稿已保存，需要重新审核。')} />
    {story.analysis && <Analysis analysis={story.analysis} />}
    <InteractiveStoryHistory key={`history:${story.id}:${story.version}`} api={api} story={story} blocked={dirty || action.busy} perform={perform} />
    <InteractiveStoryPreview api={api} story={story} blocked={dirty || action.busy} />
    <StoryApproval key={`approval:${story.id}:${story.version}`} api={api} story={story} blocked={dirty || action.busy} perform={perform} />
  </>}
  </>}
  </section>;
}
function Analysis({ analysis }: { analysis: StoryAnalysis }) {
  return <Panel title="路径与变量检查"><StatusMessage tone={analysis.can_review ? 'success' : 'warning'}>已检查 {analysis.states_checked} 个状态；发现 {analysis.endings.length} 个可达结局；步数上限 {analysis.max_steps}。{analysis.analysis_complete ? '有限状态搜索完成。' : '达到分析边界，不能据此批准导出。'}</StatusMessage>
    {analysis.issues.map((issue, i) => <p key={i}>需修复：{issue.code}{issue.node_id ? ` · 节点 ${issue.node_id}` : ''}</p>)}{analysis.warnings.map((issue, i) => <p key={i}>提醒：{issue.code} · {issue.node_id}</p>)}
    {analysis.endings.map(e => <p key={e.node_id}>可验证结局：{e.ending} · {e.choices.length} 次选择</p>)}<p>循环会被报告并受运行步数限制；这是有界检查，不是所有可能故事的无限证明。</p>
  </Panel>;
}
function StoryEditor({ story, catalog, busy, onDirty, onSave }: { story: InteractiveStory; catalog: StoryCatalog; busy: boolean; onDirty: (value: boolean) => void; onSave: (spec: StorySpec) => void }) {
  const [spec, setSpec] = useState<StorySpec>(() => structuredClone(story.spec!)), [index, setIndex] = useState(0), [dirty, setDirty] = useState(false);
  const [name, setName] = useState(''), [kind, setKind] = useState<'bool' | 'int'>('bool'), [initial, setInitial] = useState('false'), [minimum, setMinimum] = useState(0), [maximum, setMaximum] = useState(100);
  const node = spec.nodes[index]; const blocked = busy || story.status === 'ARCHIVED';
  useEffect(() => { if (!dirty) return; const guard = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard); }, [dirty]);
  const change = (value: StorySpec) => { setSpec(value); setDirty(true); onDirty(true); };
  const edit = (patch: Partial<StoryNode>) => change({ ...spec, nodes: spec.nodes.map((n, i) => i === index ? { ...n, ...patch } : n) });
  const variables = spec.variables;
  return <Panel title="互动节点编辑"><fieldset disabled={blocked}>
    <Field label="改编标题"><input value={spec.title} maxLength={160} onChange={e => change({ ...spec, title: e.target.value })} /></Field>
    <div className="experimental-grid"><Field label="故事入口节点"><select value={spec.entry_node_id} onChange={e => change({ ...spec, entry_node_id: e.target.value })}>{spec.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.title}</option>)}</select></Field><Field label="互动步数上限"><input type="number" min={1} max={128} value={spec.max_steps} onChange={e => change({ ...spec, max_steps: Number(e.target.value) })} /></Field></div>
    <Field label="当前编辑节点"><select value={index} onChange={e => setIndex(Number(e.target.value))}>{spec.nodes.map((n, i) => <option key={n.node_id} value={i}>{n.title}</option>)}</select></Field>
    <p>原节点 ID：{node.node_id} · v{node.node_version}</p>
    <Field label="互动节点标题"><input value={node.title} maxLength={240} onChange={e => edit({ title: e.target.value })} /></Field>
    <Field label="对白或叙述"><textarea value={node.dialogue} maxLength={8000} onChange={e => edit({ dialogue: e.target.value })} /></Field>
    <div className="experimental-grid"><Field label="对白角色"><select value={node.character_id || ''} onChange={e => edit({ character_id: e.target.value || null })}><option value="">旁白</option>{catalog.characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
    <Field label="背景资产引用"><select value={node.background_asset_id || ''} onChange={e => edit({ background_asset_id: e.target.value || null })}><option value="">无背景引用</option>{catalog.assets.filter(a => a.kind === 'image').map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></Field>
    <Field label="音乐资产引用"><select value={node.music_asset_id || ''} onChange={e => edit({ music_asset_id: e.target.value || null })}><option value="">无音乐引用</option>{catalog.assets.filter(a => a.kind === 'audio').map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></Field></div>
    <Field label="结局名称（留空表示非结局）"><input value={node.ending} disabled={node.choices.length > 0} maxLength={240} onChange={e => edit({ ending: e.target.value })} /></Field>
    {!!node.choices.length && <p>要改成结局，请先移除此节点的选择。</p>}
    {node.choices.map((choice, i) => <section className="experimental-record" key={choice.id} aria-label={`选择 ${i + 1}`}><Field label={`选择 ${i + 1} 文案`}><input value={choice.label} maxLength={240} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, label: e.target.value } : c) })} /></Field>
      <Field label={`选择 ${i + 1} 目标`}><select value={choice.target} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, target: e.target.value } : c) })}>{spec.nodes.map(n => <option key={n.node_id} value={n.node_id}>{n.title}</option>)}</select></Field>
      <Field label={`选择 ${i + 1} 条件`}><input value={choice.condition} maxLength={240} placeholder="例如 courage >= 2 and trusted" onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, condition: e.target.value } : c) })} /></Field>
      <p>仅允许 bool/int 变量、True/False、比较、and/or/not 和括号；不执行代码。留空为始终可选。</p>
      {variables.map(v => <div key={v.name}><label className="experimental-check"><input type="checkbox" checked={v.name in choice.assignments} onChange={e => { const assignments = { ...choice.assignments }; if (e.target.checked) assignments[v.name] = v.initial; else delete assignments[v.name]; edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments } : c) }); }} />选择后设置 {v.name}</label>
        {v.name in choice.assignments && <Field label={`选择 ${i + 1} 设置 ${v.name}`}>{v.type === 'bool' ? <select value={String(choice.assignments[v.name])} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments: { ...c.assignments, [v.name]: e.target.value === 'true' } } : c) })}><option value="false">false</option><option value="true">true</option></select> : <input type="number" min={v.minimum} max={v.maximum} value={Number(choice.assignments[v.name])} onChange={e => edit({ choices: node.choices.map((c, j) => j === i ? { ...c, assignments: { ...c.assignments, [v.name]: Number(e.target.value) } } : c) })} />}</Field>}
      </div>)}<Button onClick={() => edit({ choices: node.choices.filter((_, j) => i !== j) })}>移除选择 {i + 1}</Button>
    </section>)}
    <Button disabled={!!node.ending || node.choices.length >= 8} onClick={() => { let n = 1; while (node.choices.some(c => c.id === `choice_${n}`)) n++; edit({ choices: [...node.choices, { id: `choice_${n}`, label: `选择 ${n}`, target: spec.nodes.find(s => s.node_id !== node.node_id)?.node_id || node.node_id, condition: '', assignments: {} }] }); }}>添加互动选择</Button>
    <h3>有界变量</h3>{variables.map(v => <div className="experimental-actions" key={v.name}><p>{v.name} · {v.type} · 初始 {String(v.initial)}{v.type === 'int' ? ` · ${v.minimum} 至 ${v.maximum}` : ''}</p><Button onClick={() => change({ ...spec, variables: variables.filter(item => item.name !== v.name) })}>移除变量 {v.name}</Button></div>)}
    <div className="experimental-grid"><Field label="新变量名称"><input value={name} pattern="[a-z][a-z0-9_]{0,31}" maxLength={32} onChange={e => setName(e.target.value)} /></Field><Field label="变量类型"><select value={kind} onChange={e => { const value = e.target.value as 'bool' | 'int'; setKind(value); setInitial(value === 'bool' ? 'false' : '0'); }}><option value="bool">bool</option><option value="int">int</option></select></Field>
    <Field label="变量初始值">{kind === 'bool' ? <select value={initial} onChange={e => setInitial(e.target.value)}><option value="false">false</option><option value="true">true</option></select> : <input type="number" value={initial} min={minimum} max={maximum} onChange={e => setInitial(e.target.value)} />}</Field>
    {kind === 'int' && <><Field label="变量最小值"><input type="number" value={minimum} min={-10000} max={10000} onChange={e => setMinimum(Number(e.target.value))} /></Field><Field label="变量最大值"><input type="number" value={maximum} min={-10000} max={10000} onChange={e => setMaximum(Number(e.target.value))} /></Field></>}
    </div><Button disabled={!/^[a-z][a-z0-9_]{0,31}$/.test(name) || variables.some(v => v.name === name) || variables.length >= 16} onClick={() => { const variable: StoryVariable = { name, type: kind, initial: kind === 'bool' ? initial === 'true' : Number(initial), minimum, maximum }; change({ ...spec, variables: [...variables, variable] }); setName(''); }}>添加有界变量</Button>
    <fieldset><legend>关联已审核故事图谱记录（可选，不复制事实）</legend>{catalog.graph_records.map(r => <label className="experimental-check" key={r.id}><input type="checkbox" checked={spec.graph_record_ids.includes(r.id)} onChange={e => change({ ...spec, graph_record_ids: e.target.checked ? [...spec.graph_record_ids, r.id] : spec.graph_record_ids.filter(id => id !== r.id) })} />{r.title} · v{r.version}</label>)}</fieldset>
    <div className="experimental-actions"><Button disabled={!dirty} onClick={() => onSave(spec)}>保存互动草稿</Button><Button disabled={!dirty} onClick={() => { setSpec(structuredClone(story.spec!)); setDirty(false); onDirty(false); }}>还原未保存输入</Button></div>
    </fieldset></Panel>;
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
