import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient, Row, Rows } from './api';
import { segment } from './api';
import { Details, Field, Form, ids, ResourceState, useAction, useResource } from './shared';
import type { WorkspaceNavigation } from './uxClient';

type Link = { id?: string; label?: string; version?: number; digest?: string; state: string };
type Asset = { id: string; label: string; kind: string; version: number; digest: string; deleted: boolean; integrity: string; origin: string; license: { label: string; source: string; note: string }; operation: string; parents: Link[]; sources: Link[]; stale: boolean; source_task_id?: string; producer?: { declared_by?: string; provider_id?: string; model_id?: string }; generation?: { task_id: string; adapter_id: string; operation: string; candidate_count: number; input_digest: string } | null; declaration_history_versions?: number[]; impact?: Impact };
type Impact = { assets: { id: string; label: string; version: number; deleted: boolean }[]; usages: { kind: string; id: string; label: string; version: number }[]; other_dependencies: string };
type Manifest = Row & { task_id: string; task_version: number; created_at: string; operation: string; input_digest: string; manifest_digest: string; adapter_id: string; model_id: string | null; parameters: { candidate_count: number; seed?: number; width?: number; height?: number; steps?: number }; seed: { state?: string; value: number | null }; verification: string; environment: { app_version: string; runtime: { python: string; zlib: string }; adapter_version: string; adapter_digest: string; workflow_version: string; workflow_digest: string; model_digest: string | null; deterministic: boolean; registration?: { model_digest_source: string; runtime_version: string | null } } | null; outputs: { proposal_id: string; candidate_index: number; digest: string }[]; input_versions: (Link & { kind: string })[] };
type Preflight = { manifest_id: string; manifest_version: number; ready: boolean; blockers: string[]; preflight_digest: string; broker_decision_id: string | null; broker_decision_version: number | null; verification: string; cost: { state: string; currency: string; estimate_microusd: number | null }; states: { traceable: boolean; rebuildable: boolean; replayable: boolean; deterministic: boolean; byte_equal: boolean | null } };
type Replay = Row & { manifest_id: string; task_id: string; task_version: number; byte_equal: boolean | null; outputs: { proposal_id: string; candidate_index: number; digest: string; status: string }[]; recovery: string | null; recoverable: boolean; broker_required: boolean; reservation_id: string | null };
type Props = { client: ExperimentalClient; manifestsEnabled?: boolean; onNavigate?: (target: WorkspaceNavigation) => void };
const origins: Record<string, string> = { ORIGINAL_INPUT: '原创输入', GENERATED_RESULT: '生成结果', DERIVED_PROCESSING: '派生处理', EXTERNAL_IMPORT: '外部导入', MANUAL_EDIT: '手工修改', UNDECLARED: '尚未声明', DERIVATION_UNDECLARED: '已有衍生关系，尚未补充声明' };
const states: Record<string, string> = { CURRENT: '当前有效', STALE: '版本已变化', DELETED: '已删除，可恢复', UNAVAILABLE: '不可用或无权访问', UNVERIFIED: '缺少原始版本证据', VERIFIED: '内容摘要已校验', CONTENT_UNAVAILABLE: '内容缺失或摘要不符' };
const reasons: Record<string, string> = { MODEL_BROKER_FEATURE_REQUIRED: '已登记本地图像重放需要启用模型路由和费用预检。', ORIGIN_AUTHORITY_CHANGED: '选择性更新的原来源、锁或权限已变化，需要重新预检。', SOURCE_CHANGED_OR_UNAVAILABLE: '来源内容、版本或权限已变化，需要重新准备源任务。', SOURCE_TASK_CHANGED: '原任务记录已变化。', CURRENT_PRIVACY_CHANGED: '来源隐私声明已变化，请重新审核。', ADAPTER_OR_MODEL_CHANGED: 'Adapter 或模型已变化，不能冒充原版重放。', CONFIGURED_ADAPTER_REQUIRED: '没有已配置的可执行 Adapter。发现模型不等于已配置工作流。', FRESH_CLOUD_AUTHORIZATION_NOT_INTEGRATED: '此重放入口尚未接入新的云端外发授权，已阻止调用。', ORIGINAL_RUNTIME_EVIDENCE_MISSING: '历史任务没有记录原始运行环境，无法从当前环境推定。', RUNTIME_OR_IMPLEMENTATION_CHANGED: 'App、Runtime、工具或实现摘要与原任务不一致。', EXACT_MODEL_IDENTITY_REQUIRED: '缺少模型精确哈希，尚不能验证原环境。', ORIGINAL_OUTPUT_UNAVAILABLE: '原始输出不可用，无法比较摘要。', ORIGINAL_OUTPUT_CHANGED: '原始输出摘要不符。', MODEL_BROKER_NOT_CONFIGURED: '已要求模型路由和预算检查，但服务未配置。', MODEL_BROKER_NO_LEGAL_ROUTE: '当前路由、预算或权限不允许重放，请检查模型路由面板。' };
const stateLabels = { traceable: '输入可追溯', rebuildable: '环境可重建', replayable: '任务可重放', deterministic: '合成协议确定性', byte_equal: '输出逐字节一致' };
const newKey = () => globalThis.crypto?.randomUUID?.() || `replay-${Date.now()}-${Math.random().toString(16).slice(2)}`;

function LineageForm({ client, row, assets, saved }: { client: ExperimentalClient; row: Asset; assets: Asset[]; saved: () => void }) {
  const [origin, setOrigin] = useState(origins[row.origin] && !row.origin.includes('UNDECLARED') ? row.origin : row.parents.length ? 'DERIVED_PROCESSING' : 'EXTERNAL_IMPORT');
  const [parents, setParents] = useState(row.parents.flatMap(p => p.id ? [p.id] : []));
  const [chapters, setChapters] = useState(row.sources.flatMap(p => p.id ? [p.id] : []).join(', '));
  const [license, setLicense] = useState(row.license.label), [source, setSource] = useState(row.license.source || ''), [note, setNote] = useState(row.license.note || ''), [operation, setOperation] = useState(row.operation);
  const action = useAction(saved);
  const unavailable = row.deleted || row.integrity !== 'VERIFIED' || row.parents.some(p => !p.id || p.state === 'DELETED');
  return <Form onSubmit={() => action.run(() => client.put(`/production/assets/${segment(row.id)}/lineage`, { expected_version: row.version, origin, parent_asset_ids: parents, chapter_ids: ids(chapters), license: { label: license, source, note }, operation }), '来源声明已保存，未替换源文件。')}>
    <h3>补充来源声明 · 基于 v{row.version}</h3>{action.feedback}
    <StatusMessage>许可是作者提供的来源声明，不代表法律鉴定。已有父资产不能静默移除；替换应创建新资产并重新审核。</StatusMessage>
    {unavailable && <StatusMessage tone="warning">当前资产或父资产不可用，请先在资产库恢复并核对来源。</StatusMessage>}
    <div className="experimental-grid"><Field label="资产来源类型"><select value={origin} onChange={e => setOrigin(e.target.value)}>{Object.entries(origins).filter(([k]) => !k.includes('UNDECLARED')).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field><Field label="处理操作说明"><input value={operation} maxLength={160} onChange={e => setOperation(e.target.value)} /></Field></div>
    <fieldset disabled={action.busy || unavailable}><legend>父资产（使用现有资产 ID）</legend>{assets.filter(a => a.id !== row.id && !a.deleted).map(a => <label key={a.id} className="experimental-check"><input type="checkbox" checked={parents.includes(a.id)} disabled={row.parents.some(p => p.id === a.id)} onChange={e => setParents(p => e.target.checked ? [...p, a.id] : p.filter(id => id !== a.id))} />{a.label} · v{a.version}</label>)}{assets.filter(a => a.id !== row.id && !a.deleted).length === 0 && <p>没有其他可用资产。</p>}</fieldset>
    <Field label="来源章节 ID（逗号分隔，可留空）"><input value={chapters} onChange={e => setChapters(e.target.value)} /></Field>
    <div className="experimental-grid"><Field label="许可声明"><input required value={license} maxLength={160} onChange={e => setLicense(e.target.value)} /></Field><Field label="许可来源"><input value={source} maxLength={2000} onChange={e => setSource(e.target.value)} /></Field></div>
    <Field label="许可使用备注"><textarea value={note} maxLength={2000} onChange={e => setNote(e.target.value)} /></Field>
    <Button type="submit" disabled={action.busy || unavailable || !license.trim()}>保存来源声明</Button>
  </Form>;
}

function AssetDetail({ client, id, assets, onNavigate, choose }: Props & { id: string; assets: Asset[]; choose: (id: string) => void }) {
  const resource = useResource(signal => client.get<Asset>(`/production/assets/${segment(id)}`, signal), [client, id]);
  const [formRevision, setFormRevision] = useState(0);
  const row = resource.data;
  return <section aria-label="资产来源详情" className="experimental-section"><Button onClick={() => { setFormRevision(n => n + 1); resource.reload(); }} disabled={resource.loading}>重新读取资产详情</Button><ResourceState loading={resource.loading} error={resource.error} />
    {row && !resource.loading && !resource.error && <><h3>{row.label} · v{row.version}</h3><div className="experimental-actions"><Badge>{origins[row.origin] || row.origin}</Badge><Badge tone={row.stale ? 'warning' : 'success'}>{states[row.integrity] || row.integrity}</Badge></div><p>内容摘要：{row.digest}</p>{row.producer && <p>声明者：{row.producer.declared_by || '未指定'} · Provider：{row.producer.provider_id || '未指定'} · 模型：{row.producer.model_id || '未指定'}</p>}{row.generation && <p>继承现有媒体来源：{row.generation.operation} · {row.generation.candidate_count} 个候选 · 输入摘要 {row.generation.input_digest}</p>}{!!row.declaration_history_versions?.length && <p>保留的声明历史：{row.declaration_history_versions.map(v => `v${v}`).join('、')}</p>}
      <section aria-label="资产来源关系图"><h3>父资产 → 当前资产 → 衍生资产</h3><div className="experimental-grid"><div className="experimental-record"><h3>父资产</h3>{row.parents.length ? row.parents.map((p, index) => <div key={p.id || `unavailable-${index}`}><p>{p.label || '来源不可用或无权访问'} · {states[p.state]}</p>{p.id && <Button onClick={() => choose(p.id!)}>查看父资产 {p.label}</Button>}</div>) : <p>{row.origin === 'ORIGINAL_INPUT' ? '作者声明为原创输入。' : '未记录父资产，不代表原创或获得许可。'}</p>}</div><div className="experimental-record"><h3>当前资产</h3><p>{row.label}</p><p>{origins[row.origin] || row.origin}</p><p>{row.operation || '未声明处理操作'}</p></div><div className="experimental-record"><h3>受影响的衍生资产</h3>{row.impact?.assets.length ? row.impact.assets.map(a => <Button key={a.id} onClick={() => choose(a.id)}>{a.label} · v{a.version}{a.deleted ? ' · 已删除' : ''}</Button>) : <p>没有已记录的下游资产。</p>}</div></div></section>
      <section aria-label="资产替换影响"><h3>使用位置与替换影响</h3><StatusMessage>这里只列出实际记录的资产与媒体依赖，其他关系未知。替换不会自动重做或批准任何产物。</StatusMessage>{row.impact?.usages.length ? row.impact.usages.map(u => <p key={`${u.kind}:${u.id}`}>{u.kind === 'MEDIA_BRIEF' ? '媒体需求' : '媒体任务'} · {u.label} · v{u.version} · {u.id}</p>) : <p>没有已记录的媒体使用位置。</p>}{onNavigate && !!row.impact?.usages.length && <Button onClick={() => onNavigate({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' })}>查看媒体任务与审核</Button>}</section>
      {!!row.sources.length && <section><h3>引用章节</h3>{row.sources.map((s, i) => <p key={s.id || i}>{s.id || '来源不可用或无权访问'} · {states[s.state]}{s.version ? ` · v${s.version}` : ''}</p>)}</section>}
      <LineageForm key={`${row.id}:${row.version}:${formRevision}`} client={client} row={row} assets={assets} saved={resource.reload} />
    </>}
  </section>;
}

function ManifestDetail({ client, manifest, onReplay, onNavigate }: Props & { manifest: Manifest; onReplay: () => void }) {
  const [preflight, setPreflight] = useState<Preflight>(), [idempotencyKey, setKey] = useState('');
  const action = useAction(), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const exportManifest = () => action.run(async () => {
    const value = await client.get(`/production/manifests/${segment(manifest.id)}/export`);
    if (!alive.current) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'production-manifest-redacted.json';
    try { a.click(); } finally { URL.revokeObjectURL(url); }
  }, '已下载服务器生成的脱敏清单。');
  const check = () => action.run(async () => {
    setPreflight(undefined); setKey('');
    const result = await client.post<Preflight>(`/production/manifests/${segment(manifest.id)}/preflight`, { expected_version: manifest.version });
    if (alive.current) { setPreflight(result); setKey(newKey()); }
  }, '依赖、当前权限、隐私和预算已重新检查。');
  const replay = () => preflight && action.run(async () => {
    await client.post(`/production/manifests/${segment(manifest.id)}/replay`, { expected_version: manifest.version, preflight_digest: preflight.preflight_digest, idempotency_key: idempotencyKey, broker_decision_id: preflight.broker_decision_id, broker_decision_version: preflight.broker_decision_version });
    if (alive.current) { setPreflight(undefined); onReplay(); }
  }, '已创建新的媒体任务。请在下方明确执行；结果仍需审核。');
  return <section className="experimental-section" aria-label="生产清单详情"><h3>任务 {manifest.task_id} 的生产清单</h3>{action.feedback}
    <StatusMessage tone="warning">合成 PNG Adapter 仅验证生产协议与确定性，不代表真实图片模型质量。有 seed 也不保证真实模型逐字节一致。</StatusMessage>
    <section aria-label="生产复现证据级别"><p>可追溯表示已记录输入与输出；可重放需要当前预检。近似复现尚未评估；确定性只对合成协议成立。</p>{manifest.assurance && <Details label="独立复现证据级别" value={manifest.assurance} />}</section>
    <dl className="experimental-meta"><div><dt>Adapter / 模型</dt><dd>{manifest.adapter_id} / {manifest.model_id || '精确标识缺失'}</dd></div><div><dt>输入摘要</dt><dd>{manifest.input_digest}</dd></div><div><dt>清单摘要</dt><dd>{manifest.manifest_digest}</dd></div><div><dt>有界参数</dt><dd>{manifest.parameters.candidate_count} 个候选；seed：{manifest.seed?.value ?? '原任务未记录'}；{manifest.parameters.width ? `${manifest.parameters.width} × ${manifest.parameters.height}，${manifest.parameters.steps} 步` : '合成协议参数'}</dd></div><div><dt>App / Runtime</dt><dd>{manifest.environment ? `${manifest.environment.app_version} / Python ${manifest.environment.runtime.python} / zlib ${manifest.environment.runtime.zlib}` : '原任务未记录，不能补推'}</dd></div><div><dt>Workflow</dt><dd>{manifest.environment?.workflow_version || '缺失'}</dd></div></dl>
    <details><summary>输入版本、工具和结果摘要</summary><div className="experimental-section"><p>Adapter 实现：{manifest.environment?.adapter_digest || '缺失'}</p><p>Workflow 实现：{manifest.environment?.workflow_digest || '缺失'}</p><p>模型哈希：{manifest.environment?.model_digest || '缺少精确模型证据'}</p>{manifest.environment?.registration && <><p>哈希来源：{manifest.environment.registration.model_digest_source}。运行时报告不等于本机读取权重验证。</p><p>模型运行时版本：{manifest.environment.registration.runtime_version || '未报告，环境可重建性未知'}</p></>}{manifest.input_versions.map((v, i) => <p key={`${v.id || 'unavailable'}:${i}`}>{v.kind} · {v.id || '不可用或无权访问'}{v.version ? ` · v${v.version}` : ''} · {v.digest || '已隐藏'}</p>)}{manifest.outputs.map(o => <p key={o.proposal_id}>候选 {o.candidate_index + 1} · {o.digest}</p>)}</div></details>
    <div className="experimental-actions"><Button disabled={action.busy} onClick={check}>检查重放条件</Button><Button disabled={action.busy} onClick={exportManifest}>下载脱敏生产清单</Button>{onNavigate && <Button onClick={() => onNavigate({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' })}>打开原媒体审核</Button>}</div>
    {preflight && <section aria-label="重放预检" className="experimental-record"><h3>{preflight.ready ? '可以创建新的重放任务' : '重放条件未满足'}</h3><div className="experimental-actions">{Object.entries(stateLabels).map(([key, label]) => { const value = preflight.states[key as keyof typeof stateLabels]; return <Badge key={key} tone={value === true ? 'success' : value === null ? 'neutral' : 'warning'}>{label}：{value === null ? '尚未比较' : value ? '是' : '否'}</Badge>; })}</div>{preflight.blockers.map(code => <StatusMessage key={code} tone="warning">{reasons[code] || code}</StatusMessage>)}<p>费用：{preflight.cost.estimate_microusd === null ? '未知，不以零元代替' : `${preflight.cost.estimate_microusd / 1000000} ${preflight.cost.currency}`} · {preflight.cost.state}</p><p>原授权不会继承。创建与执行时还会重新检查当前权限、来源、隐私与预算。</p><Button disabled={action.busy || !preflight.ready} onClick={replay}>创建新的重放任务</Button></section>}
  </section>;
}

function ReplayCard({ client, row, refresh, onNavigate }: Props & { row: Replay; refresh: () => void }) {
  const action = useAction(refresh), cancellation = useAction(refresh);
  const cancel = () => cancellation.run(async () => {
    const latest = await client.get<{ items: Replay[] }>('/production/replays');
    const current = latest.items.find(item => item.id === row.id);
    if (!current) throw new Error('重放记录不可用');
    await client.post(`/production/replays/${segment(row.id)}/cancel`, { expected_task_version: current.task_version });
  }, '已取消本地结果接收。');
  return <article className="experimental-record" aria-label={`重放任务 ${row.task_id}`}><h3>新任务 {row.task_id}</h3><div className="experimental-actions"><Badge tone={row.status === 'SUCCEEDED' ? 'success' : row.status === 'FAILED' ? 'error' : 'neutral'}>{row.status} · v{row.task_version}</Badge><Badge tone={row.byte_equal === true ? 'success' : row.byte_equal === false ? 'warning' : 'neutral'}>输出逐字节一致：{row.byte_equal === null ? '尚未比较' : row.byte_equal ? '是' : '否'}</Badge></div>{action.feedback}{cancellation.feedback}
    {row.recovery && <StatusMessage tone="warning">任务结果需要重新核对。不会自动重试；请重新预检并创建新任务。</StatusMessage>}
    <p>{row.broker_required ? '执行前将重新校验共用预算预留。' : '当前只支持无外发的确定性合成协议。'}</p><div className="experimental-actions">{row.status === 'QUEUED' && <Button disabled={action.busy || cancellation.busy} onClick={() => action.run(() => client.post(`/production/replays/${segment(row.id)}/execute`, { expected_task_version: row.task_version }), '执行结束，结果保留在原媒体审核流程。')}>{row.synthetic === false ? '执行这次本地重放' : '执行这次合成重放'}</Button>}{['QUEUED', 'RUNNING'].includes(row.status || '') && <Button disabled={cancellation.busy} onClick={cancel}>取消重放</Button>}{!!row.outputs.length && onNavigate && <Button onClick={() => onNavigate({ kind: 'feature', id: 'cover_storyboard_generation', feature: 'cover_storyboard_generation' })}>审核重放产物</Button>}</div>
    {row.outputs.map(o => <p key={o.proposal_id}>候选 {o.candidate_index + 1} · {o.status} · {o.digest}</p>)}
  </article>;
}

function ManifestWorkspace(props: Props) {
  const { client } = props;
  const resource = useResource(async signal => { const [manifests, tasks, replays] = await Promise.all([client.get<{ items: Manifest[] }>('/production/manifests', signal), client.get<Rows>('/media/tasks', signal), client.get<{ items: Replay[] }>('/production/replays', signal)]); return { manifests: manifests.items, tasks: tasks.items, replays: replays.items }; }, [client]);
  const [taskId, setTaskId] = useState(''), [selected, setSelected] = useState('');
  const action = useAction(resource.reload), data = resource.data;
  const completed = data?.tasks.filter(t => t.status === 'SUCCEEDED' && !t.benchmark_run_id && !t.safe_batch_id) || [];
  const task = completed.find(t => t.id === taskId);
  const manifest = data?.manifests.find(m => m.id === selected);
  return <section className="experimental-section" aria-label="生产清单与重放"><div className="experimental-actions"><h3>生产清单与受控重放</h3><Button onClick={resource.reload} disabled={resource.loading || action.busy}>刷新清单与重放状态</Button></div>{action.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    {data && !resource.loading && !resource.error && <><Form onSubmit={() => task && action.run(async () => { const result = await client.post<Manifest>('/production/manifests', { task_id: task.id, expected_task_version: task.version }); setSelected(result.id); }, '生产清单已记录。')}><Field label="已完成的媒体任务"><select value={taskId} onChange={e => setTaskId(e.target.value)}><option value="">选择任务</option>{completed.map(t => <option key={t.id} value={t.id}>{t.operation} · {t.id} · v{t.version}</option>)}</select></Field><Button type="submit" disabled={action.busy || !task}>记录所选任务清单</Button></Form>
      {!completed.length && <EmptyState title="暂无可记录的完成任务" detail="先在封面与分镜中明确运行一个已配置的 Adapter。没有真实 Adapter 时，仅合成测试流程可用。" />}
      <div className="experimental-actions" aria-label="生产清单列表">{data.manifests.map(m => <Button key={m.id} aria-pressed={selected === m.id} onClick={() => setSelected(m.id)}>清单 {m.operation} · {m.created_at}</Button>)}</div>
      {manifest && <ManifestDetail key={manifest.id} {...props} manifest={manifest} onReplay={resource.reload} />}
      <section aria-label="重放历史" className="experimental-section"><h3>现有媒体任务中的重放记录</h3>{data.replays.length ? data.replays.map(r => <ReplayCard key={r.id} {...props} row={r} refresh={resource.reload} />) : <p>尚未创建重放任务。</p>}</section>
    </>}
  </section>;
}

function ProductionWorkspace(props: Props) {
  const { client, manifestsEnabled = false } = props;
  const resource = useResource(signal => client.get<{ items: Asset[] }>('/production/assets', signal), [client]);
  const [selected, setSelected] = useState('');
  return <Panel title="资产来源与生产复现"><StatusMessage>复用现有资产库和媒体任务。缺失来源会保留占位关系，不会被当成原创；重放不会自动批准产物。</StatusMessage><div className="experimental-actions"><h3>资产来源</h3><Button onClick={resource.reload} disabled={resource.loading}>刷新资产列表</Button></div><ResourceState loading={resource.loading} error={resource.error} empty={resource.data?.items.length === 0} />
    {resource.data && !resource.loading && !resource.error && <><div className="experimental-actions" aria-label="资产列表">{resource.data.items.map(a => <Button key={a.id} aria-pressed={selected === a.id} onClick={() => setSelected(a.id)}>{a.label} · v{a.version}{a.deleted ? ' · 已删除' : a.stale ? ' · 待核对' : ''}</Button>)}</div>{selected && <AssetDetail key={selected} {...props} id={selected} assets={resource.data.items} choose={setSelected} />}</>}
    {manifestsEnabled ? <ManifestWorkspace {...props} /> : <StatusMessage>生产清单与重放未启用，资产来源仍可单独使用。</StatusMessage>}
  </Panel>;
}

export function ProductionLineagePanel(props: Props) {
  // Remount all private local state immediately when the captured authority
  // changes. Late reads/actions belong to the old unmounted scope.
  const identity = useRef({ client: props.client, generation: 0 });
  if (identity.current.client !== props.client) identity.current = { client: props.client, generation: identity.current.generation + 1 };
  return <ProductionWorkspace key={identity.current.generation} {...props} />;
}
