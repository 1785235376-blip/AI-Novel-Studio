import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { changeImpactClient, type ImpactNode, type ImpactPreflight, type ImpactRefresh, type ImpactSource } from './changeImpactClient';
import type { WorkspaceNavigation } from './uxClient';

type Props = { client: ExperimentalClient; onNavigate?: (target: WorkspaceNavigation) => void; readOnly?: boolean };
const kinds: Record<string, string> = { CHAPTER: '章节', CHARACTER: '角色', WORLD_RECORD: '世界关系 / 知识', ASSET: '资产', PLANNING_NODE: '规划', PLANNING_PROPOSAL: '规划建议', MEDIA_BRIEF: '媒体需求', MEDIA_TASK: '媒体任务', AUDIO_PLAN: '配音计划', SUBTITLES: '字幕视图', EXPORT: '清单导出视图', SHOT: '镜头', SCREENPLAY_SCENE: '剧本场景', STORYBOARD_FRAME: '分镜卡片', MOTION_TASK: '视频任务', AUDIO_MIX: '混音候选' };
const reasons: Record<string, string> = { LOCKED_OUTCOME: '成果已锁定，请先明确解锁。', SOURCE_CURRENT: '现有来源仍有效，无需重做。', ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED: '请到原领域核对与更新；此处不替代它的审核流程。', ORIGINAL_TASK_NOT_TERMINAL: '原任务仍在排队或执行中。', REGISTERED_LOCAL_IMAGE_EXECUTOR_REQUIRED: '需要已启用的原本地图像 Adapter 或内置合成协议 Adapter。', MODEL_BROKER_FEATURE_REQUIRED: '真实本地图像需要启用模型路由，并配置当前费用估计。', ORIGINAL_ADAPTER_CHANGED: '原 Adapter 配置已改变，需要在原领域重新准备。', ORIGINAL_ADAPTER_UNAVAILABLE: '原 Adapter 未配置或已停用。请先在原媒体领域检查工作流，不会自动换模型。', CURRENT_INPUTS_UNAVAILABLE: '当前输入已删除、不可访问或不满足原执行器条件。', MODEL_BROKER_NOT_CONFIGURED: '路由与预算服务未配置。', MODEL_BROKER_NO_LEGAL_ROUTE: '当前路由、隐私或预算不允许执行。', MEDIA_FEATURE_DISABLED: '原媒体领域未启用。' };
const evidenceStates: Record<string, string> = { CURRENT: '原始快照仍有效', STALE: '来源版本已变化', UNVERIFIED: '已记录关联，缺少版本证据' };
const sourceVersion = (source?: ImpactSource) => source?.binding && typeof source.binding === 'object' && 'version' in source.binding ? String(source.binding.version) : '摘要绑定';
const newKey = () => globalThis.crypto?.randomUUID?.() || `refresh-${Date.now()}-${Math.random().toString(16).slice(2)}`;

function RefreshCard({ api, row, reload, onNavigate }: { api: ReturnType<typeof changeImpactClient>; row: ImpactRefresh; reload: () => void; onNavigate?: Props['onNavigate'] }) {
  const action = useAction(reload), cancelAction = useAction(reload);
  const cancel = () => cancelAction.run(async () => {
    const current = (await api.refreshes()).items.find(item => item.id === row.id);
    if (!current) throw new Error('refresh unavailable');
    await api.cancel(current);
  }, '已取消本地结果接收；原成果保留。');
  return <article className="experimental-record" aria-label={`选择性更新 ${row.task_id}`}>
    <h3>新任务 {row.task_id}</h3><div className="experimental-actions"><Badge>{row.status} · v{row.task_version}</Badge><Badge tone={row.source_current ? 'neutral' : 'warning'}>{row.source_current ? '新任务来源快照有效' : '新任务来源已变化'}</Badge></div>
    {action.feedback}{cancelAction.feedback}
    {row.recovery && <StatusMessage tone="warning">需要重新查看影响并预检。不会复用旧授权或自动重试。</StatusMessage>}
    <div className="experimental-actions">{row.status === 'QUEUED' && <Button disabled={action.busy || cancelAction.busy || !row.source_current} onClick={() => action.run(() => api.execute(row), '选中任务已执行，产物仍需在原媒体领域审核。')}>执行此选中任务</Button>}
      {['QUEUED', 'RUNNING'].includes(row.status) && <Button disabled={cancelAction.busy} onClick={cancel}>取消此次更新</Button>}
      {row.outputs.length > 0 && onNavigate && <Button onClick={() => onNavigate({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' })}>审核更新产物</Button>}
    </div>{row.outputs.map(output => <p key={output.id}>候选 {output.id} · {output.status}</p>)}
  </article>;
}

function ImpactSelection({ source, api, onPrepared, onNavigate }: { source: ImpactSource; api: ReturnType<typeof changeImpactClient>; onPrepared: () => void; onNavigate?: Props['onNavigate'] }) {
  const resource = useResource(() => api.query(source), [api, source.id, source.kind]);
  const [selected, setSelected] = useState<string[]>([]), [preflight, setPreflight] = useState<ImpactPreflight>(), [key, setKey] = useState('');
  const action = useAction(), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const invalidate = () => { setSelected([]); setPreflight(undefined); setKey(''); resource.reload(); };
  const lock = (node: ImpactNode) => action.run(async () => { await api.lock(node); if (alive.current) invalidate(); }, node.locked ? '已解锁。下次更新仍需重新预检。' : '已锁定满意成果，选择性更新会跳过它。');
  const check = () => action.run(async () => {
    setPreflight(undefined); setKey('');
    const result = await api.preflight(source, resource.data!.items.filter(node => selected.includes(node.key)));
    if (alive.current) { setPreflight(result); setKey(newKey()); }
  }, '已核对选中节点、当前来源、权限、隐私和可知费用。');
  const prepare = () => preflight && action.run(async () => {
    await api.prepare(preflight, key);
    if (alive.current) { setPreflight(undefined); setSelected([]); onPrepared(); resource.reload(); }
  }, '已建立新来源快照与原执行器任务。尚未运行，原成果保留。');
  return <section className="experimental-section" aria-label="修改影响清单">
    <div className="experimental-actions"><h3>{source.label} 的已记录依赖</h3><Button disabled={resource.loading || action.busy} onClick={invalidate}>重新读取影响与版本</Button></div>
    {action.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    {!!resource.error && <StatusMessage>读取需要作者编辑权限。功能关闭、范围改变或只读身份时，依赖内容不可用。</StatusMessage>}
    {resource.data && !resource.loading && !resource.error && <>
      {resource.data.items.length === 0 && <EmptyState title="没有已记录的下游依赖" detail="没有证据不代表没有影响。未记录的章节文字引用和外部导出仍未知。" />}
      <div className="experimental-section" aria-label="确切依赖">{resource.data.items.map(node => <article className="experimental-record" key={node.key}>
        <h3>{kinds[node.kind] || node.kind} · {node.label}</h3>
        <div className="experimental-actions"><Badge tone={node.stale ? 'warning' : 'neutral'}>{node.stale ? '待更新 / 待核对' : '未发现版本变化'}</Badge><Badge>v{node.version} · {node.status}</Badge>{node.locked && <Badge>满意成果已锁定</Badge>}</div>
        {node.refresh_reason && <p>{reasons[node.refresh_reason] || node.refresh_reason}</p>}
        <label className="experimental-check"><input type="checkbox" disabled={!node.refresh_candidate || action.busy || (selected.length >= 20 && !selected.includes(node.key))} checked={selected.includes(node.key)} onChange={event => { setPreflight(undefined); setKey(''); setSelected(value => event.target.checked ? [...value, node.key] : value.filter(item => item !== node.key)); }} />选择更新 {node.label} · {node.id}</label>
        <div className="experimental-actions"><Button disabled={action.busy} onClick={() => lock(node)}>{node.locked ? '解锁此成果' : '锁定满意成果'}</Button>{onNavigate && node.feature && <Button onClick={() => onNavigate({ kind: 'feature', id: node.feature!, feature: node.feature! })}>打开原领域核对</Button>}</div>
        <details><summary>确切关联与来源证据</summary>{node.evidence.map(edge => <p key={edge.key}>{edge.label} · {evidenceStates[edge.state] || edge.state}{edge.recorded_version != null && ` · 记录 v${edge.recorded_version}`}{edge.current_version != null && ` → 当前 v${edge.current_version}`}</p>)}</details>
      </article>)}</div>
      <StatusMessage>模型推断影响：未运行。未记录的关系：未知。角色改名仅跟随稳定 ID 显示；全文替换需要独立预览，此处不会改正文。</StatusMessage>
      <Button disabled={action.busy || selected.length === 0} onClick={check}>预检选中的 {selected.length} 项</Button>
      {preflight && <section className="experimental-record" aria-label="选择性更新预检"><h3>{preflight.ready ? '可准备新的选中任务' : '当前不能执行选中更新'}</h3>
        {preflight.items.map(item => <div key={item.key}><p>{item.label}</p>{item.blockers.map(code => <StatusMessage key={code} tone="warning">{reasons[code] || code}</StatusMessage>)}</div>)}
        <p>预检来源：{preflight.source_snapshot?.label || source.label} · 当前来源版本 {sourceVersion(preflight.source_snapshot)}</p><p>费用：{preflight.cost.estimate_microusd === null ? '未知，不以免费代替' : `${preflight.cost.estimate_microusd / 1000000} ${preflight.cost.currency}`} · 最多 {preflight.maximum_candidates} 个候选</p>
        <StatusMessage tone="warning">支持合成测试与已登记本地封面 / 分镜路线，真实模型效果未验。每次执行仍重新检查权限、来源、隐私和预算；不会批准产物或替换旧成果。</StatusMessage>
        <Button disabled={action.busy || !preflight.ready} onClick={prepare}>仅准备这些选中更新</Button>
      </section>}
    </>}
  </section>;
}

function ImpactWorkspace({ client, onNavigate }: Props) {
  const api = useMemo(() => changeImpactClient(client), [client]);
  const sources = useResource(signal => api.sources(signal), [api]);
  const refreshes = useResource(signal => api.refreshes(signal), [api]);
  const [sourceKey, setSourceKey] = useState('');
  const source = sources.data?.items.find(item => `${item.kind}:${item.id}` === sourceKey);
  return <Panel title="修改影响与选择性更新">
    <StatusMessage>显示现有故事图谱、规划、资产血缘和生产来源中实际记录的关联。缺失关系保持未知。原稿、Canon 和已满意成果不会自动改写。</StatusMessage>
    <div className="experimental-actions"><Button disabled={sources.loading} onClick={() => { setSourceKey(''); sources.reload(); }}>刷新可访问来源</Button><Button disabled={refreshes.loading} onClick={refreshes.reload}>刷新更新任务</Button></div>
    <ResourceState loading={sources.loading} error={sources.error} />
    {!!sources.error && <StatusMessage>当前范围没有作者编辑权限，或依赖功能未启用。请保留原稿并在有权限的范围重试。</StatusMessage>}
    {sources.data && !sources.loading && !sources.error && <Field label="发生修改的来源"><select value={sourceKey} onChange={event => setSourceKey(event.target.value)}><option value="">选择章节、角色、关系或资产</option>{sources.data.items.map(item => <option key={`${item.kind}:${item.id}`} value={`${item.kind}:${item.id}`}>{kinds[item.kind]} · {item.label}</option>)}</select></Field>}
    {source && !sources.loading && !sources.error && <ImpactSelection key={sourceKey} source={source} api={api} onPrepared={refreshes.reload} onNavigate={onNavigate} />}
    <section className="experimental-section" aria-label="选择性更新历史"><h3>可恢复的原执行器任务</h3><ResourceState loading={refreshes.loading} error={refreshes.error} />{refreshes.data && !refreshes.loading && !refreshes.error && <>{refreshes.data.items.length ? refreshes.data.items.map(row => <RefreshCard key={row.id} api={api} row={row} reload={refreshes.reload} onNavigate={onNavigate} />) : <p>尚未准备更新。预检不会自动开始任务。</p>}</>}</section>
  </Panel>;
}

export function ChangeImpactPanel(props: Props) {
  const identity = useRef({ client: props.client, generation: 0 });
  if (identity.current.client !== props.client) identity.current = { client: props.client, generation: identity.current.generation + 1 };
  if (props.readOnly) return <Panel title="修改影响与选择性更新"><StatusMessage>只读身份不能查看作者私密依赖或发起更新。请切换到有编辑权限的范围。</StatusMessage></Panel>;
  return <ImpactWorkspace key={identity.current.generation} {...props} />;
}
