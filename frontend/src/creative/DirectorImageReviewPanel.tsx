import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import type { CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import type { StudioAsset } from './studioClient';
import type { DirectorImageClient, ImageAdoption, ImageAdvice, ImageCapabilities, ImagePending, ImagePreview, ImageReview, ImageStatus, ImageTarget } from './directorImageClient';

type Props = { client: DirectorImageClient; source: CreativeDocument; snapshot: PlanningSnapshot; selectionKey?: string;
  active: boolean; available: boolean; busy: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onPending: (value: boolean) => void; onAdopted: (receipt: ImageAdoption) => void; onDenied: () => void; onOpenModels?: () => void; onOpenBroker?: () => void };
type Session = { token: object; open: boolean; caps?: ImageCapabilities; assets: StudioAsset[]; proposals: ImageStatus[]; truncated?: boolean;
  assetId: string; routeKey: string; sceneId: string; instruction: string; proposalId: string; status?: ImageStatus;
  preview?: ImagePreview; pending?: ImagePending; review?: ImageReview; dispatchConsent: boolean; cancelConsent: boolean;
  amount: string; evidence: string; costConsent: boolean; selected: number[]; note: string; adoptionConsent: boolean;
  discardConsent?: boolean; working?: string; error?: string; notice?: string; uncertain?: string; adopted?: ImageAdoption };
const empty = (token: object): Session => ({ token, open: false, assets: [], proposals: [], assetId: '', routeKey: '', sceneId: '', instruction: '', proposalId: '',
  dispatchConsent: false, cancelConsent: false, amount: '', evidence: '', costConsent: false, selected: [], note: '', adoptionConsent: false,
  caps: undefined, truncated: undefined, status: undefined, preview: undefined, pending: undefined, review: undefined, working: undefined, error: undefined, notice: undefined, uncertain: undefined, adopted: undefined, discardConsent: false });
const routeKey = (r: { provider_id: string; model_id: string }) => JSON.stringify([r.provider_id, r.model_id]);
const completed = (s?: ImageStatus) => !!s && s.job_status === 'COMPLETED' && ['DISPATCHED', 'PENDING_REVIEW'].includes(s.status);
const imageAsset = (asset: StudioAsset) => asset.kind === 'image' && !asset.deleted_at && ['image/png', 'image/jpeg'].includes(asset.media_type)
  && asset.size > 0 && asset.size <= 4 * 1024 * 1024 && Number.isSafeInteger(asset.version) && asset.version > 0 && /^[a-f0-9]{64}$/.test(asset.sha256);

/** Every lifetime has private, in-memory evidence; A → B → A never revives it. */
export function DirectorImageReviewPanel(props: Props) {
  return <ImageSession key={JSON.stringify([props.source.id, props.source.version, props.snapshot, props.selectionKey])} {...props} />;
}
function ImageSession(props: Props) {
  const alive = useRef(true), live = useRef(props); live.current = props;
  const request = useRef<AbortController>(), consumedDispatch = useRef(new Set<string>());
  const authority = [props.client, props.active, props.available, props.source, props.snapshot.digest], owner = useRef({ authority, token: {} });
  if (authority.some((value, index) => !Object.is(value, owner.current.authority[index]))) { request.current?.abort(); request.current = undefined; owner.current = { authority, token: {} }; }
  const token = owner.current.token;
  const [stored, setStored] = useState<Session>(() => empty(token));
  const state = stored.token === token ? stored : empty(token), latest = useRef(state); latest.current = state;
  const current = () => alive.current && owner.current.token === token && live.current.active && live.current.available && live.current.isCurrent();
  function commit(next: Session) { if (!current()) return; latest.current = next; props.onPending(next.open && (!!next.working || !!next.instruction || !!next.assetId || !!next.sceneId || !!next.status || !!next.preview || !!next.uncertain)); setStored(next); }
  const hasIntent = state.open && (!!state.working || !!state.instruction || !!state.assetId || !!state.sceneId || !!state.status || !!state.preview || !!state.uncertain);
  useEffect(() => props.onPending(hasIntent), [hasIntent, props.onPending]);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; request.current?.abort(); props.onPending(false); }; }, []);
  const unsent = (s: Session) => !!s.amount || !!s.evidence || !!s.note || s.selected.length > 0;
  const hasUnsent = unsent(state);
  const writable = current() && !props.busy && !request.current;
  const canStart = () => writable && latest.current === state;
  const target = (): ImageTarget | undefined => {
    const s = latest.current;
    if (!props.source.scenes.some(scene => scene.id === s.sceneId) || props.source.mode !== 'DIRECTOR' || props.source.status !== 'DRAFT'
      || props.source.id !== props.snapshot.id || props.source.version !== props.snapshot.version) return undefined;
    return { document_id: props.snapshot.id, version: props.snapshot.version, digest: props.snapshot.digest, scene_id: s.sceneId };
  };
  function retire() {
    if (!current()) return;
    request.current?.abort(); request.current = undefined;
    owner.current = { ...owner.current, token: {} };
    latest.current = empty(owner.current.token); setStored(latest.current); props.onPending(false);
  }
  function change(patch: Partial<Session>, invalidate = false) {
    if (!current() || latest.current !== state || props.busy || request.current || invalidate && (latest.current.uncertain || unsent(latest.current))) return;
    const previous = latest.current;
    commit({ ...previous, ...patch, ...(invalidate ? { preview: undefined, pending: undefined, review: undefined, status: undefined, adopted: undefined,
      proposalId: '', dispatchConsent: false, cancelConsent: false, costConsent: false, adoptionConsent: false, selected: [], note: '', amount: '', evidence: '', uncertain: undefined, error: undefined, notice: undefined } : {}) });
  }
  async function run<T>(name: string, work: (signal: AbortSignal) => Promise<T>, done: (value: T, s: Session) => Session, write = false, patch: Partial<Session> = {}) {
    if (!current() || latest.current !== state || live.current.busy || request.current) return;
    const abort = new AbortController(); request.current = abort;
    commit({ ...latest.current, ...patch, working: name, error: undefined });
    try {
      const guarded = () => { if (!current() || abort.signal.aborted) throw new DOMException('已退回。', 'AbortError'); return work(abort.signal); };
      const result = await (write ? props.mutate(guarded) : props.read(guarded));
      if (current() && request.current === abort && !abort.signal.aborted) commit({ ...done(result, latest.current), working: undefined });
    } catch (reason) {
      if (!current() || request.current !== abort || abort.signal.aborted) return;
      if (reason instanceof ApiError && reason.problem.code === 'DIRECTOR_IMAGE_BROKER_ADMISSION_BLOCKED') commit({ ...latest.current, working: undefined, uncertain: undefined, dispatchConsent: false, notice: undefined, error: 'Broker 未准入本次请求：可能缺少有效成本估计或不满足现有预算规则。请在原“模型路由与评测”中核对项目预算、require_known_estimate 与价格来源。这里不会更改策略或自动重新发送。' });
      else if (reason instanceof ApiError && [401, 403].includes(reason.status)) { commit({ ...empty(token), error: '当前身份或分支已失去访问权限，请重新打开工作区。' }); props.onDenied(); }
      else commit({ ...latest.current, working: undefined, dispatchConsent: false, costConsent: false, adoptionConsent: false,
        error: name === '发送图像理解' ? '发送回执未确认。不会再次发送；请读取同一提案状态。'
          : name === '采纳导演备注' ? '采纳回执未确认。请读取同一提案状态核对是否已提交；不要重复采纳。'
            : name === '声明本地成本' ? '成本声明回执未确认。请明确读取人工审核内容核对声明；不要重复声明。'
              : '操作未完成，当前来源、目标版本或权限可能已变化。请核对原文档与素材后明确重开；不会自动重试。' });
    } finally { if (request.current === abort) request.current = undefined; }
  }
  function load() {
    if (!canStart() || unsent(latest.current)) return;
    void run('读取图像能力与素材', async signal => {
      const caps = await props.client.capabilities(signal);
      if (!current() || signal.aborted) throw new DOMException('已退回。', 'AbortError');
      const assets = await props.client.assets(signal);
      return { caps, assets: assets.items.filter(imageAsset) };
    }, (value, s) => ({ ...s, ...value, open: true }), false, { ...empty(token), open: true });
  }
  function preview() {
    const s = latest.current, wanted = target(), asset = s.assets.find(row => row.id === s.assetId), registration = s.caps?.registered_choices.find(r => routeKey(r) === s.routeKey);
    if (!canStart() || unsent(s) || !s.caps?.enabled || !wanted || !asset || !registration || !s.instruction.trim() || s.instruction.length > 2000) return;
    const input = { asset: { asset_id: asset.id, version: asset.version, sha256: asset.sha256 }, target: wanted, provider_id: registration.provider_id, model_id: registration.model_id, instruction: s.instruction };
    void run('预览图像请求', signal => props.client.preview(input, signal), (value, previous) => ({ ...previous, preview: value, proposalId: value.id,
      status: { id: value.id, version: value.version, status: 'PREVIEW', job_id: null, job_status: null, can_cancel: false, target_document_id: wanted.document_id, target_scene_id: wanted.scene_id },
      notice: '已保存请求预览，尚未调用模型。核对后另行确认发送。' }), true,
    { preview: undefined, pending: undefined, review: undefined, dispatchConsent: false, costConsent: false, adoptionConsent: false, adopted: undefined });
  }
  function dispatch() {
    const s = latest.current, p = s.preview;
    if (!canStart() || !p || !s.dispatchConsent || consumedDispatch.current.has(p.id)) return;
    consumedDispatch.current.add(p.id);
    void run('发送图像理解', signal => props.client.dispatch(p, signal), (value, previous) => ({ ...previous, status: value, uncertain: undefined,
      notice: '请求已发送。请手动读取状态；本地运行也可能产生资源成本，成本仍须独立声明。' }), true,
    { preview: undefined, dispatchConsent: false, uncertain: 'dispatch', notice: '发送只提交一次。回执中断时读取同一提案状态。' });
  }
  function readStatus(id: string) {
    if (!canStart() || !id || unsent(latest.current)) return;
    void run('读取同一提案状态', signal => props.client.status(id, signal), (value, previous) => ({ ...previous, status: value, proposalId: value.id, uncertain: undefined,
      notice: value.adoption_receipt ? `历史回执：已采纳至 v${value.adoption_receipt.target.version}。请在原文档明确核对当前版本。` : '仅核对任务元数据，未读取或恢复任何旧图像建议。' }), false,
    { preview: undefined, pending: undefined, review: undefined, dispatchConsent: false, cancelConsent: false, costConsent: false, adoptionConsent: false, selected: [], note: '', amount: '', evidence: '' });
  }
  function prepare() {
    const s = latest.current, wanted = target(); if (!canStart() || unsent(s) || !s.status || !completed(s.status) || !wanted) return;
    void run('准备成本审核', signal => props.client.prepare(s.status!, wanted, signal), (value, previous) => ({ ...previous, pending: value,
      status: previous.status ? { ...previous.status, version: value.version, status: 'PENDING_REVIEW' } : undefined, uncertain: undefined,
      notice: '下面的描述与建议来自模型，尚未核实。请单独填写并确认本地成本。' }), true,
    { pending: undefined, review: undefined, amount: '', evidence: '', costConsent: false, adoptionConsent: false, selected: [], note: '' });
  }
  function declareCost() {
    const s = latest.current, p = s.pending;
    if (!canStart() || !p || !s.costConsent || !/^\d+$/.test(s.amount) || !Number.isSafeInteger(Number(s.amount)) || Number(s.amount) > 10 ** 12 || !s.evidence.trim()) return;
    const input = { contract: 'DIRECTOR_IMAGE_COST_DECLARATION_V3' as const, request_id: crypto.randomUUID(), expected_version: p.accounting_version,
      reviewed_terminal_digest: p.terminal_digest, declared_microusd: Number(s.amount), evidence_note: s.evidence, confirmed_declaration: true as const };
    void run('声明本地成本', signal => props.client.declareCost(p.id, input, signal), (_, previous) => ({ ...previous, uncertain: undefined,
      notice: '已记录人工声明的本地成本。这不是实测用量或供应商账单。下一步明确读取人工审核内容。' }), true,
    { pending: undefined, costConsent: false, uncertain: 'cost', amount: '', evidence: '' });
  }
  function readReview() {
    const s = latest.current, wanted = target(); if (!canStart() || unsent(s) || !s.status || !completed(s.status) || !wanted) return;
    void run('读取人工审核内容', signal => props.client.review(s.status!.id, wanted, signal), (value, previous) => ({ ...previous, review: value, uncertain: undefined,
      notice: '已核对当前图像与目标版本。请逐项选择建议，并亲自填写要保存的导演备注。' }), false,
    { pending: undefined, review: undefined, selected: [], note: '', adoptionConsent: false, costConsent: false });
  }
  function adopt() {
    const s = latest.current, r = s.review;
    if (!canStart() || !r || !s.adoptionConsent || !s.selected.length || !s.note.trim() || s.note.length > 8000) return;
    const input = { contract: 'DIRECTOR_IMAGE_ADOPTION_INPUT_V1' as const, request_id: crypto.randomUUID(), expected_version: r.proposal_version, target: r.target,
      reviewed_terminal_digest: r.terminal_digest, reviewed_accounting_digest: r.accounting_digest, selected_suggestions: [...s.selected], note: s.note, human_review_confirmed: true as const };
    void run('采纳导演备注', signal => props.client.adopt(r.proposal_id, input, signal), (value, previous) => {
      props.onAdopted(value);
      return { ...previous, adopted: value, uncertain: undefined, notice: `已保存一条人工审核导演备注至 v${value.target.version}。请明确核对原文档；图绑定没有改变。` };
    }, true, { review: undefined, adoptionConsent: false, selected: [], note: '', uncertain: 'adopt' });
  }
  if (!props.active || !props.isCurrent()) return null;
  if (!props.available) return <StatusMessage>图像导演审核需要已保存、已核对摘要且无本地修改的 DIRECTOR DRAFT 文档。</StatusMessage>;
  const targetReady = !!target(), selectedAsset = state.assets.find(row => row.id === state.assetId), enabled = writable && state.caps?.enabled;
  return <section aria-label="图像导演审核"><h3>图像导演 · IMAGE V3</h3>
    <p>使用原素材库中的单张 PNG／JPEG 与 Model Center 已注册的 VISION 图像理解模型。只向已有场景追加人工审核备注。</p>
    {!state.open ? <Button disabled={!writable} onClick={load}>打开图像导演审核</Button> : <>
      <Button onClick={retire}>关闭图像审核并清除本页内容</Button>
      <p>关闭只清除本页内容，已发送任务继续由原任务管理；需要停止时另行请求取消。状态与重开不会自动发送、重试、刷新图绑定或恢复旧建议。</p>
      <Button disabled={!writable || hasUnsent} onClick={load}>重新读取图像能力与素材</Button>
      {state.caps && !state.caps.enabled && <StatusMessage tone="warning">图像执行能力尚未启用。仍可明确读取历史任务状态。</StatusMessage>}
      {state.caps && !state.caps.registered_choices.length && <EmptyState title="没有可用的 VISION 图像理解注册" detail="此路径不受支持；不会用 OCR 或文字模型替代。请到 Model Center 核对现有注册。" />}
      {props.onOpenModels && <Button disabled={!writable} onClick={() => { if (canStart()) props.onOpenModels?.(); }}>打开 Model Center 核对 VISION</Button>}
      {!state.assets.length && state.caps && <p>没有符合条件的已保存图片。请先在原素材库导入 PNG／JPEG；上限 4 MiB、4096 像素边长与 4194304 总像素。</p>}
      {props.onOpenBroker && <Button disabled={!writable} onClick={() => { if (canStart()) props.onOpenBroker?.(); }}>打开原 Broker 预算设置</Button>}
      {hasUnsent && <section aria-label="未提交的图像审核输入"><p>成本或备注输入尚未提交。先提交，或明确放弃输入后再刷新、重开或改变来源。</p>
        <label><input type="checkbox" checked={!!state.discardConsent} disabled={!writable} onChange={e => change({ discardConsent: e.target.checked })} />放弃尚未提交的成本与备注输入</label>
        <Button disabled={!writable || !state.discardConsent} onClick={() => { if (current() && !request.current && latest.current.discardConsent) change({ amount: '', evidence: '', note: '', selected: [], costConsent: false, adoptionConsent: false, discardConsent: false }); }}>清除未提交的审核输入</Button></section>}
      <fieldset disabled={!writable || hasUnsent || !!state.uncertain}><legend>明确选择请求来源与目标</legend>
        <label>图像理解原素材<select value={state.assetId} onChange={e => change({ assetId: e.target.value }, true)}><option value="">请选择已保存图片版本</option>
          {state.assets.map(a => <option key={a.id} value={a.id}>{a.filename} · v{a.version}</option>)}</select></label>
        {selectedAsset && <p>图片版本 v{selectedAsset.version} · SHA-256 {selectedAsset.sha256}</p>}
        <label>图像理解目标场景<select value={state.sceneId} onChange={e => change({ sceneId: e.target.value }, true)}><option value="">请选择已有场景</option>
          {props.source.scenes.map(s => <option key={s.id} value={s.id}>{s.sequence} · {s.heading}</option>)}</select></label>
        <p>目标文档 {props.source.title} · v{props.snapshot.version} · {props.snapshot.digest}</p>
        <label>VISION 注册模型<select value={state.routeKey} onChange={e => change({ routeKey: e.target.value }, true)}><option value="">请选择原 Model Center 注册</option>
          {state.caps?.registered_choices.map(r => <option key={routeKey(r)} value={routeKey(r)}>{r.display_name} · {r.provider_id} / {r.model_id}</option>)}</select></label>
        <label>图像导演指令<textarea value={state.instruction} maxLength={2000} onChange={e => change({ instruction: e.target.value }, true)} /></label>
      </fieldset>
      <Button disabled={!enabled || hasUnsent || !targetReady || !selectedAsset || !state.routeKey || !state.instruction.trim() || !!state.uncertain} onClick={preview}>预览图像理解请求</Button>
      {state.preview && <section aria-label="图像请求预览"><h4>请求预览 · 尚未调用模型</h4>
        <p>{state.preview.provider_id} / {state.preview.model_id} · 图片 {state.preview.asset.asset_id} v{state.preview.asset.version} · 场景 {state.preview.target.scene_id}</p>
        <p>输出上限 {state.preview.parameters.max_output_tokens} token · temperature {state.preview.parameters.temperature} · 仅本地，无自动重试或降级</p>
        <label>图像理解完整提示<textarea readOnly value={state.preview.prompt} /></label>
        <p>预览摘要 {state.preview.preview_digest}</p>
        <label><input type="checkbox" checked={state.dispatchConsent} disabled={!enabled} onChange={e => change({ dispatchConsent: e.target.checked })} />已核对图片、场景、模型和完整提示，同意发送一次本地图像理解请求</label>
        <Button disabled={!enabled || !state.dispatchConsent} onClick={dispatch}>确认发送图像理解</Button>
      </section>}
      <section aria-label="图像任务状态与重开"><h4>任务状态与重开</h4>
        <Button disabled={!writable} onClick={() => void run('读取图像提案目录', signal => props.client.list(signal), (value, s) => ({ ...s, proposals: value.items, truncated: value.truncated }), false)}>读取图像提案目录</Button>
        <label>已保存图像提案<select value={state.proposalId} disabled={!writable || hasUnsent} onChange={e => { if (unsent(latest.current)) return; change({ proposalId: e.target.value, status: undefined, preview: undefined, pending: undefined, review: undefined,
          dispatchConsent: false, costConsent: false, adoptionConsent: false, selected: [], note: '', amount: '', evidence: '', uncertain: undefined }); }}>
          <option value="">请选择同一提案</option>
          {state.proposalId && !state.proposals.some(p => p.id === state.proposalId) && <option value={state.proposalId}>{state.proposalId}</option>}
          {state.proposals.map(p => <option key={p.id} value={p.id}>{p.id} · {p.status} · {p.job_status ?? '尚未发送'}</option>)}
        </select></label>
        {state.truncated && <p>仅显示最近 30 条提案。</p>}
        <Button disabled={!writable || hasUnsent || !state.proposalId} onClick={() => readStatus(state.proposalId)}>读取同一提案状态</Button>
        {state.status && <><p>提案 {state.status.id} · v{state.status.version} · {state.status.status} · 任务 {state.status.job_status ?? '尚未发送'}</p>
          <p>状态仅为元数据，内容新鲜度未检查。目标：{state.status.target_document_id} / {state.status.target_scene_id}。</p>
          {state.status.recovery_state && <StatusMessage tone="warning">原执行器当前不可用，不能继续或重放这个任务。</StatusMessage>}
          {state.status.adoption_receipt && <p>历史采纳回执已提交至 v{state.status.adoption_receipt.target.version}；仍须重新读取原文档核对当前内容。</p>}
          {state.status.can_cancel && <><label><input type="checkbox" checked={state.cancelConsent} disabled={!writable} onChange={e => change({ cancelConsent: e.target.checked })} />请求取消同一图像任务，理解这不保证上游已停止</label>
            <Button disabled={!writable || !state.cancelConsent} onClick={() => { const s = latest.current; if (!s.status || !s.cancelConsent) return;
              void run('请求取消图像任务', signal => props.client.cancel(s.status!, signal), (_, previous) => ({ ...previous, cancelConsent: false, notice: '已请求取消；不代表上游已经停止。请手动核对任务状态。' }), true, { cancelConsent: false }); }}>请求取消图像任务</Button></>}
        </>}
      </section>
      {completed(state.status) && <section aria-label="图像成本与人工审核"><h4>独立成本声明与人工审核</h4>
        <p>请明确选择该提案的原目标场景。先准备成本审核；已声明成本或声明回执中断时，直接读取人工审核内容。</p>
        <Button disabled={!enabled || hasUnsent || !targetReady || state.uncertain === 'adopt'} onClick={prepare}>准备图像成本审核</Button>
        <Button disabled={!enabled || hasUnsent || !targetReady || state.uncertain === 'adopt'} onClick={readReview}>读取图像人工审核内容</Button>
        {state.pending && <><Advice value={state.pending.advice} /><p>结算状态 UNKNOWN_UPSTREAM。完成执行不代表成本为零。</p>
          <label>人工声明本地成本（microUSD，1 USD = 1000000）<input inputMode="numeric" value={state.amount} maxLength={13} disabled={!writable} onChange={e => change({ amount: e.target.value, costConsent: false })} /></label>
          <label>成本声明依据<textarea value={state.evidence} maxLength={500} disabled={!writable} onChange={e => change({ evidence: e.target.value, costConsent: false })} /></label>
          <label><input type="checkbox" checked={state.costConsent} disabled={!writable} onChange={e => change({ costConsent: e.target.checked })} />我明确声明此金额；这不是实测用量、免费证明或供应商验证账单</label>
          <Button disabled={!enabled || !state.costConsent || !/^\d+$/.test(state.amount) || Number(state.amount) > 10 ** 12 || !state.evidence.trim()} onClick={declareCost}>提交独立成本声明</Button>
        </>}
        {state.review && <><Advice value={state.review.advice} /><p>已声明 {state.review.declared_microusd} microUSD，measurement_verified=false。此金额是人工声明，不是模型观测或实测成本。</p>
          <fieldset disabled={!writable}><legend>选择人工采纳的建议</legend>{state.review.advice.suggestions.map((suggestion, index) => <label key={index}><input type="checkbox" checked={state.selected.includes(index)}
            onChange={e => change({ selected: e.target.checked ? [...latest.current.selected, index] : latest.current.selected.filter(i => i !== index), adoptionConsent: false })} />建议 {index + 1}：{suggestion}</label>)}</fieldset>
          <label>人工审核后的导演备注<textarea value={state.note} maxLength={8000} disabled={!writable} onChange={e => change({ note: e.target.value, adoptionConsent: false })} /></label>
          <label><input type="checkbox" checked={state.adoptionConsent} disabled={!writable} onChange={e => change({ adoptionConsent: e.target.checked })} />已人工核对所选建议与备注，确认追加到这个已有场景</label>
          <Button disabled={!enabled || !state.adoptionConsent || !state.selected.length || !state.note.trim()} onClick={adopt}>采纳为一条导演备注</Button>
        </>}
      </section>}
    </>}
    {state.working && <StatusMessage>正在{state.working}…</StatusMessage>}
    {state.notice && <StatusMessage>{state.notice}</StatusMessage>}{state.error && <StatusMessage tone="warning">{state.error}</StatusMessage>}
  </section>;
}
function Advice({ value }: { value: ImageAdvice }) {
  return <section aria-label="未经验证的图像模型建议"><h4>未经验证的模型描述与导演建议</h4>
    <p>observations_verified=false。单张图片不能证明人物身份、实测几何、动作、连续性或时长。</p>
    <p>模型描述：</p><ul>{value.observations.map((text, index) => <li key={index}>{text}</li>)}</ul>
    <p>假设性的导演建议：</p><ol>{value.suggestions.map((text, index) => <li key={index}>{text}</li>)}</ol><p>不确定性：{value.uncertainty}</p>
  </section>;
}
