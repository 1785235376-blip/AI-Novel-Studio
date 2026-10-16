import { useEffect, useRef, useState } from 'react';
import type { Chapter } from '../api';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { type ExperimentalClient, type Row, type Rows, segment } from './api';
import { Details, Field, Form, RecordStatus, Refresh, ResourceState, ids, useAction, useResource } from './shared';
import { hasPromotionIntent, PromotionRecovery } from './PromotionRecovery';

export function RegistryPanel({ client }: { client: ExperimentalClient }) {
  const resource = useResource(signal => client.get('/media/adapters', signal), [client]);
  return <Panel title="Media Workflow Adapter Registry" actions={<Refresh reload={resource.reload} />}><StatusMessage>模型发现与可运行 Workflow 分离。ADAPTER_REQUIRED 不可运行；Mock 仅验证任务与审核契约。</StatusMessage><ResourceState loading={resource.loading} error={resource.error} /><Details label="IMAGE / VIDEO / AUDIO 操作契约" value={resource.data?.operations} /><div className="experimental-list">{resource.data?.items?.map((row: Row) => <article className="experimental-record" key={row.adapter_id}><h3>{row.family}</h3><div className="experimental-actions"><Badge>{row.modality}</Badge><Badge tone={row.runnable ? 'info' : 'warning'}>{row.state}</Badge><span>{row.runnable ? '具备可运行实现' : '尚无可运行实现'}</span></div><p>{row.operations.join(' · ')}</p><Details label="Adapter 身份与限制" value={row} /></article>)}</div></Panel>;
}
function ProposalImage({ client, row }: { client: ExperimentalClient; row: Row }) {
  const [url, setUrl] = useState(''), [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let objectUrl = '';
    client.blob(`/media/proposals/${segment(row.id)}/preview`, controller.signal).then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [client, row.id]);
  return url ? <img className="experimental-preview" src={url} alt={`${row.kind} ${row.verification || '待审核'} 候选 ${(row.candidate_index ?? 0) + 1}`} /> : failed ? <StatusMessage tone="error">预览暂不可读</StatusMessage> : <p>正在读取候选预览…</p>;
}
function RegisteredMediaTask({ client, row, reload }: { client: ExperimentalClient; row: Row; reload: () => void }) {
  const [quote, setQuote] = useState<Row>(), alive = useRef(true), epoch = useRef(0);
  const action = useAction(reload), cancel = useAction(reload);
  useEffect(() => { alive.current = true; epoch.current++; setQuote(undefined); return () => { alive.current = false; epoch.current++; }; }, [client, row.id, row.version]);
  const owned = !!(row.production_replay_id || row.change_impact_refresh_id || row.benchmark_run_id || row.safe_batch_id);
  if (owned) return <StatusMessage>此任务由评测、重放或选择性更新入口控制。请回到原入口执行或取消。</StatusMessage>;
  return <section className="experimental-section" aria-label="已登记本地图像执行">
    {row.status === 'QUEUED' && <><Button disabled={action.busy} onClick={() => void action.run(async () => { setQuote(undefined); const ticket = epoch.current; const value = await client.post<Row>(`/media/tasks/${segment(row.id)}/preflight`, { expected_version: row.version }); if (alive.current && ticket === epoch.current) setQuote(value); }, '当前路线、来源与费用已检查，尚未生成。')}>检查本地图像路线与费用</Button>
      {quote && <><p>费用估计：{quote.cost?.estimate_microusd == null ? '未知' : `${quote.cost.estimate_microusd} µUSD`} · {quote.cost?.state}</p><Details value={quote.parameters} label="本次图像尺寸、步数与 seed" />{quote.blockers?.map((reason: string) => <StatusMessage key={reason} tone="warning">{reason}；请在模型路由中检查当前路线和费用估计。</StatusMessage>)}<Button disabled={action.busy || !quote.ready} onClick={() => void action.run(() => client.post(`/media/tasks/${segment(row.id)}/execute`, { expected_version: row.version, broker_decision_id: quote.broker_decision_id, broker_decision_version: quote.broker_decision_version }), '图像执行已返回，产物仍待审核。')}>按预检执行本地图像任务</Button></>}
    </>}
    {['QUEUED', 'RUNNING'].includes(row.status || '') && <Button disabled={cancel.busy} onClick={() => void cancel.run(async () => { const latest = (await client.get<Rows>('/media/tasks')).items.find(item => item.id === row.id); if (latest) await client.post(`/media/tasks/${segment(row.id)}/cancel`, { expected_version: latest.version }); setQuote(undefined); }, '已取消结果接收。已发送的计算不能撤回。')}>取消本地图像任务</Button>}
    {['FAILED', 'CANCELLED'].includes(row.status || '') && <StatusMessage>恢复需要从当前 Brief 建立新任务并重新预检，旧任务不会重发。</StatusMessage>}
    {row.status === 'SUCCEEDED' && <StatusMessage>产物待审核。运行时未报告实际费用；请在模型路由核对并结算未知账目，再开始下一次生成。</StatusMessage>}
    {action.feedback}{cancel.feedback}
  </section>;
}
type MediaCatalog = { screenplays?: (Row & { shots: Row[] })[]; characters?: { id: string; name: string }[] };
function MockMediaTask({ client, row, reload }: { client: ExperimentalClient; row: Row; reload: () => void }) {
  const execution = useAction(reload), cancellation = useAction(reload);
  const owned = row.production_replay_id || row.change_impact_refresh_id || row.safe_batch_id || row.benchmark_run_id;
  if (owned) return <StatusMessage>此任务由原预检入口控制，请回到原入口执行或取消。</StatusMessage>;
  const transition = (operation: string) => execution.run(() => client.post(`/media/tasks/${segment(row.id)}/${operation}`, { expected_version: row.version }), '媒体任务状态已更新');
  return <>{execution.feedback}{cancellation.feedback}<div className="experimental-actions">
    {row.status === 'QUEUED' && <Button disabled={execution.busy || cancellation.busy} onClick={() => transition('execute')}>执行 Mock 图像任务</Button>}
    {['QUEUED', 'RUNNING'].includes(row.status || '') && <Button disabled={cancellation.busy} onClick={() => cancellation.run(async () => {
      const latest = (await client.get<Rows>('/media/tasks')).items.find(item => item.id === row.id);
      if (!latest) throw new Error('媒体任务不可用');
      await client.post(`/media/tasks/${segment(row.id)}/cancel`, { expected_version: latest.version });
    }, '已取消结果接收；较晚返回的结果不会进入审核。')}>取消媒体任务</Button>}
    {(['FAILED', 'CANCELLED'].includes(row.status || '') || row.recoverable) && <Button disabled={execution.busy || cancellation.busy} onClick={() => transition('retry')}>重试媒体任务</Button>}
  </div></>;
}
function CoverBriefEditor({ client, brief, reload }: { client: ExperimentalClient; brief: Row; reload: () => void }) {
  const [prompt, setPrompt] = useState(brief.prompt || ''), [typography, setTypography] = useState(brief.typography_intent || '');
  const action = useAction(reload);
  return <Form onSubmit={() => action.run(() => {
    const fields = ['title', 'subtitle', 'genre', 'character_ids', 'palette', 'composition', 'safe_area', 'chapter_ids', 'reference_asset_ids', 'privacy_level'];
    const body = Object.fromEntries(fields.filter(key => brief[key] !== undefined).map(key => [key, brief[key]]));
    return client.put(`/media/cover-briefs/${segment(brief.id)}?expected_version=${brief.version}`, { ...body, prompt, typography_intent: typography });
  }, '封面 Brief 已新增修订，旧任务和候选需重新核对。')}>
    <h3>修订已选封面 Brief · v{brief.version}</h3>{action.feedback}<p>沿用已保存的标题、人物和构图；保存会重新绑定当前来源版本。</p>
    <Field label="修订封面图像说明"><textarea maxLength={12000} value={prompt} onChange={e => setPrompt(e.target.value)} /></Field>
    <Field label="修订封面排版意图"><textarea maxLength={2000} value={typography} onChange={e => setTypography(e.target.value)} /></Field>
    <Button type="submit" disabled={action.busy || !!brief.change_impact_refresh_id || !!brief.safe_batch_id}>保存封面 Brief 修订</Button>
  </Form>;
}
function StoryboardBriefEditor({ client, brief, catalog, reload }: { client: ExperimentalClient; brief: Row; catalog?: MediaCatalog; reload: () => void }) {
  const [prompt, setPrompt] = useState(brief.prompt || '');
  const action = useAction(reload);
  const source = catalog?.screenplays?.find(row => row.id === brief.screenplay_id && row.shots.some(shot => shot.id === brief.shot_id));
  return <Form onSubmit={() => source && action.run(() => client.put(`/media/storyboard-briefs/${segment(brief.id)}?expected_version=${brief.version}`, {
    screenplay_id: brief.screenplay_id, shot_id: brief.shot_id, expected_screenplay_version: source.edit_version, prompt,
    reference_asset_ids: brief.reference_asset_ids || [], privacy_level: brief.privacy_level,
  }), '分镜 Brief 已新增修订，旧候选不能覆盖新修订。')}>
    <h3>修订已选分镜 Brief · v{brief.version}</h3>{action.feedback}
    <p>沿用原 Shot。保存将绑定当前剧本 v{source?.edit_version ?? '不可用'}，历史仍保留。旧候选需重新生成并审核。</p>
    <Field label="修订分镜图像说明"><textarea value={prompt} maxLength={12000} onChange={e => setPrompt(e.target.value)} /></Field>
    <Button type="submit" disabled={action.busy || !source || !!brief.change_impact_refresh_id || !!brief.safe_batch_id}>保存分镜 Brief 修订</Button>
  </Form>;
}
export function MediaPanel(props: { client: ExperimentalClient; chapter?: Chapter; requestedTaskId?: string }) {
  const identity = useRef({ client: props.client, generation: 0 });
  if (identity.current.client !== props.client) identity.current = { client: props.client, generation: identity.current.generation + 1 };
  return <MediaContent key={identity.current.generation} {...props} />;
}
function MediaContent({ client, chapter, requestedTaskId }: { client: ExperimentalClient; chapter?: Chapter; requestedTaskId?: string }) {
  const resource = useResource(async signal => { const [covers, storyboards, tasks, proposals] = await Promise.all([client.get<Rows>('/media/cover-briefs', signal), client.get<Rows>('/media/storyboard-briefs', signal), client.get<Rows>('/media/tasks', signal), client.get<Rows>('/media/proposals', signal)]); return { briefs: [...covers.items, ...storyboards.items], tasks: tasks.items, proposals: proposals.items }; }, [client]);
  const catalog = useResource(signal => client.get<MediaCatalog>('/media/catalog', signal), [client]);
  const adapters = useResource(signal => client.get<Rows>('/media/adapters', signal), [client]);
  const [adapterId, setAdapterId] = useState('mock-image-v1'), [seed, setSeed] = useState(0);
  const registered = adapterId !== 'mock-image-v1';
  const action = useAction(resource.reload);
  const [title, setTitle] = useState(''), [subtitle, setSubtitle] = useState(''), [genre, setGenre] = useState(''), [characters, setCharacters] = useState(''), [palette, setPalette] = useState(''), [composition, setComposition] = useState(''), [typography, setTypography] = useState(''), [prompt, setPrompt] = useState(''), [safeArea, setSafeArea] = useState(.08);
  const [screenplay, setScreenplay] = useState(''), [shot, setShot] = useState(''), [screenplayVersion, setScreenplayVersion] = useState(1);
  const [briefId, setBriefId] = useState(''), [selected, setSelected] = useState<string[]>([]), [comparison, setComparison] = useState<any>();
  const requestedTask = !resource.loading && !resource.error ? resource.data?.tasks.find(row => row.id === requestedTaskId) : undefined;
  const taskAnchor = useRef<HTMLElement>(null), located = useRef<string>();
  useEffect(() => { if (requestedTask && requestedTask.id !== located.current) { located.current = requestedTask.id; setBriefId(requestedTask.brief_id || ''); taskAnchor.current?.scrollIntoView?.({ block: 'nearest' }); taskAnchor.current?.focus(); } }, [requestedTask]);
  const compareEpoch = useRef(0), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; compareEpoch.current++; }; }, []);
  const clearComparison = () => { compareEpoch.current++; setComparison(undefined); };
  const brief = resource.data?.briefs.find(row => row.id === briefId);
  useEffect(() => { if (!briefId && resource.data?.briefs[0]) setBriefId(resource.data.briefs[0].id); }, [briefId, resource.data]);
  const transition = (row: Row, operation: string, collection = 'tasks') => action.run(async () => {
    try { return await client.post(`/media/${collection}/${segment(row.id)}/${operation}`, { expected_version: row.version }); }
    catch (error) { if (collection === 'proposals' && operation === 'approve') resource.reload(); throw error; }
  }, '媒体状态已更新');
  const busy = action.busy || resource.loading;
  const safeComparison = !resource.loading && !resource.error && comparison?.items.every((item: Row) => resource.data?.proposals.some(row => row.id === item.id && row.version === item.version && row.stale === item.stale)) ? comparison : undefined;
  const refresh = () => { clearComparison(); resource.reload(); catalog.reload(); };
  return <Panel title="封面与分镜生成工作流" actions={<Refresh reload={refresh} busy={busy} />}>
    <StatusMessage>可显式选择合成测试或已验证启用的原 ComfyUI / A1111 本地图像路线。真实路线每任务一张，先检查费用与来源；不支持参考图条件输入。只有批准后才生成正式资产与 lineage。实际模型质量尚未验证。</StatusMessage>{action.feedback}<ResourceState loading={resource.loading} error={resource.error} />
    <Form onSubmit={() => action.run(async () => { const value = await client.post<Row>('/media/cover-briefs', { title, subtitle, genre, character_ids: ids(characters), palette: ids(palette), composition, typography_intent: typography, prompt, safe_area: { left: safeArea, right: safeArea, top: safeArea, bottom: safeArea, units: 'FRACTION' }, chapter_ids: chapter ? [chapter.id] : [], privacy_level: 'LOCAL_ONLY' }); setBriefId(value.id); }, '封面 Brief 已保存')}>
      <h3>Cover Brief</h3><Field label="封面标题"><input required value={title} onChange={event => setTitle(event.target.value)} /></Field><Field label="封面副标题"><input value={subtitle} onChange={event => setSubtitle(event.target.value)} /></Field><Field label="封面类型"><input value={genre} onChange={event => setGenre(event.target.value)} /></Field>{!!catalog.data?.characters?.length && <fieldset><legend>封面人物（原项目）</legend>{catalog.data.characters.map(row => <label key={row.id} className="experimental-check"><input type="checkbox" checked={ids(characters).includes(row.id)} onChange={e => setCharacters(e.target.checked ? [...ids(characters), row.id].join(', ') : ids(characters).filter(id => id !== row.id).join(', '))} />{row.name}</label>)}</fieldset>}<Field label="封面关键人物 ID"><input value={characters} onChange={event => setCharacters(event.target.value)} /></Field><Field label="封面调色板（逗号分隔）"><input value={palette} onChange={event => setPalette(event.target.value)} /></Field><Field label="封面构图"><textarea value={composition} onChange={event => setComposition(event.target.value)} /></Field><Field label="封面排版意图"><textarea maxLength={2000} value={typography} onChange={event => setTypography(event.target.value)} /></Field><Field label="安全边距比例"><input type="number" min={0} max={.49} step={.01} value={safeArea} onChange={event => setSafeArea(Number(event.target.value))} /></Field><Field label="媒体生成说明"><textarea value={prompt} onChange={event => setPrompt(event.target.value)} /></Field><Button type="submit" disabled={busy || !title.trim()}>保存封面 Brief</Button>
    </Form>
    <Form onSubmit={() => action.run(async () => { const value = await client.post<Row>('/media/storyboard-briefs', { screenplay_id: screenplay, shot_id: shot, expected_screenplay_version: screenplayVersion, prompt, privacy_level: 'LOCAL_ONLY' }); setBriefId(value.id); }, '分镜 Brief 已保存')}><h3>Shot → Storyboard Brief</h3><ResourceState loading={catalog.loading} error={catalog.error} />
    <Field label="从原剧本选择分镜来源"><select value={screenplay} disabled={busy || catalog.loading || !!catalog.error} onChange={e => { const row = catalog.data?.screenplays?.find(item => item.id === e.target.value); setScreenplay(row?.id || ''); setScreenplayVersion(row?.edit_version || 1); setShot(''); }}><option value="">选择已有镜头的当前剧本</option>{catalog.data?.screenplays?.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.edit_version}</option>)}</select></Field>
    <Field label="从原 Shot 选择分镜镜头"><select value={shot} disabled={busy || !screenplay || catalog.loading || !!catalog.error} onChange={e => setShot(e.target.value)}><option value="">选择镜头</option>{catalog.data?.screenplays?.find(row => row.id === screenplay)?.shots.map(row => <option key={row.id} value={row.id}>Shot {row.number} · {row.shot_size}</option>)}</select></Field><Field label="分镜剧本 ID"><input required value={screenplay} onChange={event => setScreenplay(event.target.value)} /></Field><Field label="分镜 Shot ID"><input required value={shot} onChange={event => setShot(event.target.value)} /></Field><Field label="剧本当前编辑版本"><input type="number" min={1} value={screenplayVersion} onChange={event => setScreenplayVersion(Number(event.target.value))} /></Field><Button type="submit" disabled={busy || !screenplay || !shot}>从 Shot 创建分镜 Brief</Button></Form>
    <section className="experimental-section"><Field label="待生成媒体 Brief"><select value={briefId} onChange={event => setBriefId(event.target.value)}><option value="">选择 Brief</option>{resource.data?.briefs.map(row => <option key={row.id} value={row.id}>{row.kind} · {row.title || row.shot_id} · v{row.version}</option>)}</select></Field>{brief && <><Details value={brief} label="Brief 与来源版本" />{brief.stale && <StatusMessage tone="warning">来源版本已变化，请修订 Brief 后创建新任务。</StatusMessage>}{brief.kind === 'COVER' && <CoverBriefEditor key={`${brief.id}:${brief.version}`} client={client} brief={brief} reload={resource.reload} />}{brief.kind === 'STORYBOARD' && <StoryboardBriefEditor key={`${brief.id}:${brief.version}`} client={client} brief={brief} catalog={!catalog.error && !catalog.loading ? catalog.data : undefined} reload={resource.reload} />}</>}<Field label="图像工作流路线"><select value={adapterId} onChange={event => setAdapterId(event.target.value)}><option value="mock-image-v1">内置 Mock 合成协议测试</option>{adapters.data?.items?.filter(row => row.runnable && row.adapter_id.startsWith('registered-image:')).map(row => <option key={row.adapter_id} value={row.adapter_id}>{row.family}</option>)}</select></Field>{registered && <><Field label="本地图像 seed"><input type="number" min={0} max={2147483647} value={seed} onChange={event => setSeed(Number(event.target.value))} /></Field><p>512 × 512，20 步，每任务一张。seed 保留在生产记录中，不保证输出逐字节一致。</p></>}<Button disabled={busy || !!resource.error || !brief || brief.stale || (registered && !adapters.data?.items?.some(row => row.adapter_id === adapterId && row.runnable))} onClick={() => action.run(() => client.post('/media/tasks', { brief_id: brief!.id, expected_brief_version: brief!.version, adapter_id: adapterId, candidate_count: registered ? 1 : 2, ...(registered ? { parameters: { seed } } : {}) }), '媒体任务已排队，尚未生成。')}>{registered ? '创建本地图像任务' : '创建 Mock 图像任务'}</Button></section>
    {requestedTaskId && !resource.loading && !resource.error && !requestedTask && <StatusMessage tone="warning">请求的媒体任务在当前项目、分支或权限下不可用。</StatusMessage>}
    <div className="experimental-list">{resource.data?.tasks.map(row => <article className="experimental-record" key={row.id} aria-label="媒体任务" aria-current={row.id === requestedTask?.id ? true : undefined} tabIndex={-1} ref={row.id === requestedTask?.id ? taskAnchor : undefined}>{row.id === requestedTask?.id && <StatusMessage>已定位任务中心请求的原媒体任务。</StatusMessage>}<h3>{row.operation}</h3><RecordStatus row={row} /><Badge>{row.adapter_definition?.state}</Badge>{!row.registration_identity && <MockMediaTask client={client} row={row} reload={resource.reload} />}{row.registration_identity && <RegisteredMediaTask client={client} row={row} reload={resource.reload} />}<Details value={row} label="任务契约与来源" /></article>)}</div>
    <Button disabled={busy || selected.length < 2} onClick={() => action.run(async () => { const ticket = ++compareEpoch.current; const result = await client.post('/media/proposals/compare', { proposal_ids: selected }); if (alive.current && ticket === compareEpoch.current) setComparison(result); }, '媒体比较已更新')}>比较已选媒体候选</Button>
    {safeComparison && <section className="experimental-record" aria-label="媒体候选比较"><h3>媒体候选比较 · 未执行质量评分</h3>{safeComparison.same_source_version === false && <StatusMessage tone="warning">候选来自不同 Brief 修订。对比保留历史证据；仅当前来源的候选可批准。</StatusMessage>}<div className="experimental-grid">{safeComparison.items.map((row: Row) => <div key={row.id}><ProposalImage client={client} row={row} /><Details value={row} label={`候选 ${row.candidate_index + 1} 的模型 / digest / lineage`} /></div>)}</div></section>}
    <div className="experimental-list">{resource.data?.proposals.map(row => <article className="experimental-record" key={row.id} aria-label={`媒体候选 ${row.candidate_index + 1}`}><label className="experimental-check"><input type="checkbox" checked={selected.includes(row.id)} disabled={busy || (!selected.includes(row.id) && selected.length >= 8)} onChange={event => { clearComparison(); setSelected(current => event.target.checked ? [...current, row.id] : current.filter(id => id !== row.id)); }} />{row.kind} 候选 {row.candidate_index + 1}</label><RecordStatus row={row} /><Badge>{row.verification}</Badge><ProposalImage client={client} row={row} /><Details value={{ source_digest: row.source_digest, sources: row.sources, asset_id: row.asset_id, lineage: row.lineage, promotion_asset_id: row.promotion_asset_id, promotion_asset_digest: row.promotion_asset_digest, promotion_state: row.promotion_state, recovery_state: row.recovery_state }} label="来源与正式资产血缘" /><PromotionRecovery row={row} busy={busy} sourceUnavailable={!!resource.error} onResume={() => transition(row, 'approve', 'proposals')} /><div className="experimental-actions">{row.status === 'PENDING_REVIEW' && !hasPromotionIntent(row) && <><Button disabled={busy || !!resource.error || row.stale} onClick={() => transition(row, 'approve', 'proposals')}>批准媒体为资产</Button><Button disabled={busy} onClick={() => transition(row, 'reject', 'proposals')}>驳回媒体候选</Button></>}{row.status === 'REJECTED' && !hasPromotionIntent(row) && <Button disabled={busy} onClick={() => transition(row, 'reopen', 'proposals')}>重开媒体审核</Button>}</div></article>)}</div>
  </Panel>;
}
