import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { CreativeField } from './CreativeCanvas';
import { STORYBOARD_SOURCE_CONTRACT, type CreativeClient, type DirectorModelRoute, type DirectorProposal, type DirectorProposalClient } from './client';
import type { CreativeDocument } from './types';
function ScreenplayModelControls({ client, proposal, disabled, run, onUpdate }: { client: Pick<CreativeClient, 'modelRoutes' | 'previewModel' | 'dispatchModel' | 'refreshModel' | 'cancelProposal'>; proposal: DirectorProposal; disabled: boolean; run: (action: () => Promise<void>) => Promise<void>; onUpdate: (proposal: DirectorProposal) => void }) {
  const [routes, setRoutes] = useState<DirectorModelRoute[]>([]), [routeId, setRouteId] = useState(''), [loading, setLoading] = useState(true), [error, setError] = useState(''), [reviewed, setReviewed] = useState(false), [unauthorized, setUnauthorized] = useState(false);
  const preview = proposal.model_preview, execution = proposal.model_execution;
  useEffect(() => { const controller = new AbortController(); setLoading(true); client.modelRoutes(controller.signal).then(value => { if (!controller.signal.aborted) { setRoutes(value.items); setError(''); } }).catch(value => { if (!controller.signal.aborted) { setError('本地模型路由尚不可用。可以继续审核规则辅助建议。'); if (value instanceof ApiError && [401, 403].includes(value.status)) { setUnauthorized(true); setRoutes([]); setReviewed(false); } } }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, [client]);
  useEffect(() => setReviewed(false), [proposal.version, preview?.preview_digest, routeId]);
  const execute = (operation: () => Promise<void>) => run(async () => {
    try { await operation(); } catch (value) {
      if (value instanceof ApiError && [401, 403].includes(value.status)) { setUnauthorized(true); setRoutes([]); setReviewed(false); setError('本地模型调用缺少主机授权。手动编辑和规则辅助建议仍可继续。'); return; }
      throw value;
    }
  });
  const route = routes.find(row => row.route_id === routeId) || routes.find(row => row.available && !row.synthetic);
  const terminal = ['APPROVED', 'CANCELLED'].includes(proposal.status);
  return <section className="creative-model-controls" aria-label="可选本地模型导演"><h3>可选：本地模型导演</h3><p>仅使用明确选择、价格已确认是零的本地文字模型。先预览输入，再确认调用；不自动重试或转云端。</p>{loading && <StatusMessage>读取本地模型路由…</StatusMessage>}{error && <StatusMessage tone="warning">{error}</StatusMessage>}{!loading && !error && !routes.some(row => row.available && !row.synthetic) && <StatusMessage tone="warning">尚无可用的本地模型路由。需要配置模型和路由价格，且启用模型路由、上下文预览能力。</StatusMessage>}
    {!unauthorized && !execution && !terminal && <><CreativeField label="本地导演模型"><select disabled={disabled || loading} value={route?.route_id || ''} onChange={event => setRouteId(event.target.value)}><option value="">选择本地模型</option>{routes.filter(row => !row.synthetic).map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.provider_id} / {row.model_id}{row.available ? '' : ` · 不可用 (${row.reasons.join(', ')})`}</option>)}</select></CreativeField><Button disabled={disabled || !route?.available || route.synthetic} onClick={() => route && void execute(async () => onUpdate(await client.previewModel(proposal, route.route_id)))}>预览模型输入</Button></>}
    {!unauthorized && preview && !execution && !terminal && <div className="creative-model-preview"><Badge tone="info">预览尚未调用模型</Badge><p>输入：当前已保存剧本的场景。最长 {preview.timeout_seconds}s。最高费用：0 USD。</p><p>路由：{preview.broker.chosen?.provider_id || '未选定'} / {preview.broker.chosen?.model_id || '未选定'}</p><details><summary>核对将发送的完整模型输入</summary><pre>{JSON.stringify(preview.request, null, 2)}</pre></details><label className="creative-review-check"><input disabled={disabled || !preview.execution_available} type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对输入和本地路由，允许调用一次</label><Button variant="primary" disabled={disabled || !reviewed || !preview.execution_available || route?.provider_id !== preview.broker.chosen?.provider_id || route?.model_id !== preview.broker.chosen?.model_id} onClick={() => void execute(async () => onUpdate(await client.dispatchModel(proposal)))}>确认调用本地模型</Button></div>}
    {!unauthorized && execution && <div><Badge tone={proposal.status === 'MODEL_UNAVAILABLE' ? 'warning' : 'info'}>{execution.status}</Badge><p>任务：{execution.job_id}</p><p>调用：{execution.model_called ? '已调用' : '尚未确认调用'} · 回执：{execution.receipt_state}</p>{execution.failure_code && <p>{execution.failure_code}</p>}{!terminal && <div className="creative-actions"><Button disabled={disabled} onClick={() => void execute(async () => onUpdate(await client.refreshModel(proposal)))}>核对模型结果</Button><Button disabled={disabled} onClick={() => void run(async () => onUpdate(await client.cancelProposal(proposal)))}>取消模型任务</Button></div>}</div>}
  </section>;
}


type ModelProps = { client: Pick<DirectorProposalClient, 'modelRoutes' | 'previewModel' | 'dispatchModel' | 'refreshModel' | 'cancelProposal' | 'modelCapabilities' | 'previewStoryboardModel' | 'dispatchStoryboardModel'>; proposal: DirectorProposal; source?: CreativeDocument; disabled: boolean; run: (action: () => Promise<void>) => Promise<void>; onUpdate: (proposal: DirectorProposal) => void };

// Keep the established SCREENPLAY owner and payloads intact. STORYBOARD is an
// additive, explicitly advertised contract, never a fallback into legacy calls.
export function DirectorModelControls(props: ModelProps) {
  if (props.source?.mode === 'STORYBOARD' && props.proposal.provenance?.source_mode !== 'STORYBOARD') return <StatusMessage tone="warning">来源类型记录不一致或缺失，模型操作已禁用。</StatusMessage>;
  return props.proposal.provenance?.source_mode === 'STORYBOARD'
    ? <StoryboardModelControls {...props} /> : <ScreenplayModelControls {...props} />;
}

const exact = (a: unknown, b: unknown): boolean => {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const left = Object.keys(a), right = Object.keys(b);
  return left.length === right.length && left.every(key => Object.prototype.hasOwnProperty.call(b, key) && exact((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
};
export function storyboardSourceMatches(proposal: DirectorProposal, source?: CreativeDocument) {
  if (!source || source.mode !== 'STORYBOARD' || proposal.provenance?.source_mode !== 'STORYBOARD'
    || !Number.isSafeInteger(proposal.version) || proposal.version < 1
    || source.id !== proposal.source_document_id || source.version !== proposal.source_version
    || !/^[a-f0-9]{64}$/.test(proposal.source_digest || '') || !source.shots.length) return false;
  const shots = [...source.shots].sort((a, b) => a.number - b.number), mappings = proposal.provenance.source_shots;
  const emptyTerminal = proposal.director_notes.length === 0 && (['CANCELLED', 'MODEL_UNAVAILABLE'].includes(proposal.status) || proposal.status === 'GENERATING' && proposal.model_execution?.source_contract === STORYBOARD_SOURCE_CONTRACT);
  return !!mappings && mappings.length === shots.length && (emptyTerminal || proposal.director_notes.length === shots.length)
    && new Set(shots.map(shot => shot.id)).size === shots.length
    && new Set(mappings.map(row => row.note_id)).size === shots.length
    && mappings.every((row, index) => row.source_shot_id === shots[index].id && row.source_number === shots[index].number
      && row.scene_id === shots[index].scene_id && exact(row.source_shot, shots[index])
      && (emptyTerminal || proposal.director_notes[index].id === row.note_id && proposal.director_notes[index].scene_id === row.scene_id
      && proposal.director_notes[index].number === row.source_number));
}
function storyboardPreviewMatches(proposal: DirectorProposal, source?: CreativeDocument) {
  const preview = proposal.model_preview;
  const instruction = preview?.author?.instruction;
  if (!source || typeof instruction !== 'string' || Array.from(instruction).length > 20000 || !instruction.startsWith(`${STORYBOARD_SOURCE_CONTRACT}\n`)
    || typeof preview?.request?.prompt !== 'string' || !preview.request.prompt.includes(instruction)) return false;
  try {
    const data = JSON.parse(instruction.slice(STORYBOARD_SOURCE_CONTRACT.length + 1));
    if (data.contract !== STORYBOARD_SOURCE_CONTRACT || data.source_document_id !== proposal.source_document_id
      || data.source_version !== proposal.source_version || data.source_digest !== proposal.source_digest
      || !exact(data.storyboard, { title: source.title, scenes: source.scenes, shots: [...source.shots].sort((a, b) => a.number - b.number) })
      || !exact(data.source_mapping, preview.source_mapping) || !exact(data.visual_target, proposal.visual_target ?? undefined)) return false;
  } catch { return false; }
  return storyboardSourceMatches(proposal, source) && !!preview
    && /^[a-f0-9]{64}$/.test(preview.preview_digest || '')
    && !!preview.broker && typeof preview.broker === 'object'
    && typeof preview.broker.chosen?.provider_id === 'string' && !!preview.broker.chosen.provider_id
    && typeof preview.broker.chosen?.model_id === 'string' && !!preview.broker.chosen.model_id
    && preview.broker.chosen.price?.reserve_microusd === 0
    && typeof preview.execution_available === 'boolean'
    && Number.isFinite(preview.timeout_seconds) && preview.timeout_seconds > 0 && preview.timeout_seconds <= 180
    && Number.isSafeInteger(preview.max_output_bytes) && preview.max_output_bytes! > 0 && preview.max_output_bytes! <= 128000
    && preview.source_contract === STORYBOARD_SOURCE_CONTRACT && preview.source_mode === 'STORYBOARD'
    && preview.source_strategy === 'EXACT_CREATIVE_STORYBOARD_SHOTS_AND_SCENES_NO_IMPLICIT_CONTEXT'
    && preview.source_document_id === proposal.source_document_id && preview.source_version === proposal.source_version
    && preview.input_digest === proposal.source_digest && preview.token_fit_guaranteed === false
    && preview.model_called === false && preview.allow_cloud_fallback === false && preview.automatic_retry === false
    && exact(preview.source_mapping, proposal.provenance.source_shots?.map(({ source_shot_id, note_id, scene_id, source_number }) => ({ source_shot_id, note_id, scene_id, source_number })));
}
function StoryboardModelControls({ client, proposal, source, disabled, run, onUpdate }: ModelProps) {
  const [routes, setRoutes] = useState<DirectorModelRoute[]>([]), [routeId, setRouteId] = useState('');
  const [supported, setSupported] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState(''), [reviewed, setReviewed] = useState(false);
  const live = useRef(true), locked = useRef(false), admission = useRef<symbol | null>(null), renderTicket = Symbol();
  // Only committed handlers own admission; a discarded/no-op render must not retire them.
  useLayoutEffect(() => { admission.current = renderTicket; });
  const identity = JSON.stringify([source, proposal.source_document_id, proposal.source_version, proposal.source_digest]);
  const origin = useRef({ client, identity, generation: 0 });
  if (origin.current.client !== client || origin.current.identity !== identity) origin.current = { client, identity, generation: origin.current.generation + 1 };
  const generation = origin.current.generation;
  const current = () => live.current && origin.current.generation === generation;
  const admitted = () => current() && admission.current === renderTicket && !locked.current && !disabled;
  useEffect(() => { live.current = true; return () => { live.current = false; admission.current = Symbol(); }; }, []);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setSupported(false); setRoutes([]); setReviewed(false); setError('');
    const read = async () => {
      try {
        if (!client.modelCapabilities || !client.previewStoryboardModel || !client.dispatchStoryboardModel) throw new Error('UNSUPPORTED');
        const support = await client.modelCapabilities(controller.signal);
        if (controller.signal.aborted) return;
        if (support.storyboard_source_contract !== STORYBOARD_SOURCE_CONTRACT || support.storyboard_preview_suffix !== 'storyboard-preview' || support.storyboard_dispatch_suffix !== 'storyboard-dispatch' || support.token_fit_guaranteed !== false) throw new Error('UNSUPPORTED');
        const result = await client.modelRoutes(controller.signal);
        if (!Array.isArray(result.items) || !result.items.every(row => row && typeof row.route_id === 'string' && typeof row.provider_id === 'string' && typeof row.model_id === 'string'
          && typeof row.available === 'boolean' && typeof row.synthetic === 'boolean' && Array.isArray(row.reasons) && row.reasons.every(reason => typeof reason === 'string'))) throw new Error('INVALID_ROUTE_CATALOG');
        if (!controller.signal.aborted) { setSupported(true); setRoutes(result.items); }
      } catch { if (!controller.signal.aborted) setError('STORYBOARD 当前仅支持 RULE_ASSISTED。模型上下文能力未获主机确认或端点不可用；不会回退到剧本调用。'); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    };
    void read(); return () => controller.abort();
  }, [client, generation]);
  useEffect(() => setReviewed(false), [proposal.version, proposal.model_preview?.preview_digest, routeId, disabled]);
  const sourceValid = storyboardSourceMatches(proposal, source);
  const anchored = !!source?.source_chapter_ids.length && source.source_chapter_ids.length <= 20;
  const preview = proposal.model_preview, execution = proposal.model_execution;
  const validPreview = storyboardPreviewMatches(proposal, source);
  const route = routes.find(row => row.route_id === routeId) || (!routeId && routes.find(row => row.available && !row.synthetic && row.provider_id === preview?.broker?.chosen?.provider_id && row.model_id === preview?.broker?.chosen?.model_id)) || routes.find(row => row.available && !row.synthetic);
  const terminal = ['APPROVED', 'CANCELLED'].includes(proposal.status);
  const enabled = supported && sourceValid && anchored && !terminal;
  const operate = (operation: () => Promise<DirectorProposal>, validatePreview = false) => {
    if (!admitted() || !enabled) return;
    locked.current = true; admission.current = Symbol(); setReviewed(false);
    void run(async () => {
      try {
        const row = await operation();
        if (!current()) return;
        if (row.version < proposal.version || row.id !== proposal.id || row.source_document_id !== proposal.source_document_id || row.source_version !== proposal.source_version || row.source_digest !== proposal.source_digest
          || !storyboardSourceMatches(row, source) || (row.model_execution && (row.model_execution.source_contract !== STORYBOARD_SOURCE_CONTRACT || row.model_execution.preview_digest !== (proposal.model_preview?.preview_digest ?? proposal.model_execution?.preview_digest))) || (validatePreview && !storyboardPreviewMatches(row, source))) {
          setSupported(false); setError('模型回执来源或契约不一致，已停止操作；请重新读取建议。'); throw new Error('STORYBOARD_MODEL_RECEIPT_MISMATCH');
        }
        onUpdate(row);
      } catch (value) {
        if (!current()) return;
        if (value instanceof ApiError && [401, 403, 404, 405, 422].includes(value.status)) {
          setSupported(false); setError('分镜模型端点未授权、不支持或输入不满足契约；未回退到其他端点。'); return;
        }
        throw value;
      } finally { locked.current = false; }
    });
  };
  if (loading) return <StatusMessage>核对分镜模型上下文能力…</StatusMessage>;
  if (!supported) return <StatusMessage tone="info">{error || 'STORYBOARD 当前仅支持 RULE_ASSISTED。模型上下文能力未获确认。'}</StatusMessage>;
  if (!sourceValid) return <StatusMessage tone="warning">来源标识、版本或逐镜头映射不一致，模型操作已禁用。</StatusMessage>;
  if (!anchored) return <StatusMessage tone="warning">分镜缺少章节锚点或超过 20 个章节；当前模型上下文不支持此来源，不会补造锚点。</StatusMessage>;
  return <section className="creative-model-controls" aria-label="可选本地分镜模型导演"><h3>可选：本地分镜模型导演</h3><p>仅使用价格已确认为零的本地文字模型。完整分镜与场景先预览，再明确允许调用一次；不自动重试或转云端。</p>{error && <StatusMessage tone="warning">{error}</StatusMessage>}{!routes.some(row => row.available && !row.synthetic) && <StatusMessage tone="warning">尚无可用的零费用本地模型路由。</StatusMessage>}
    {!execution && !terminal && <><CreativeField label="本地分镜导演模型"><select disabled={disabled} value={route?.route_id || ''} onChange={event => { if (!admitted()) return; admission.current = Symbol(); setReviewed(false); setRouteId(event.target.value); }}><option value="">选择本地模型</option>{routes.filter(row => !row.synthetic).map(row => <option key={row.route_id} value={row.route_id} disabled={!row.available}>{row.provider_id} / {row.model_id}{row.available ? '' : ` · 不可用 (${row.reasons.join(', ')})`}</option>)}</select></CreativeField><Button disabled={disabled || !route?.available || route.synthetic} onClick={() => { if (route?.available && !route.synthetic && client.previewStoryboardModel) operate(() => client.previewStoryboardModel!(proposal, route.route_id), true); }}>预览分镜模型输入</Button></>}
    {preview && !execution && !terminal && <div className="creative-model-preview">{validPreview && <><Badge tone="info">预览尚未调用模型</Badge><p>来源 {proposal.source_document_id} · v{proposal.source_version} · {proposal.source_digest} · {source!.shots.length} 个已写镜头，按原序号排列。</p><p>完整已写镜头、场景与固定映射均在输入中。证据只引用场景，不伪造镜头引用。章节最多 20 个，完整指令最多 20000 字符；不保证适合模型 token 窗口。最长 {preview.timeout_seconds}s。最高费用：0 USD。</p><p>路由：{preview.broker?.chosen?.provider_id || '未选定'} / {preview.broker?.chosen?.model_id || '未选定'}</p></>}<details><summary>核对将发送的完整分镜模型输入与固定映射</summary><pre>{JSON.stringify({ source_contract: preview.source_contract, source_mapping: preview.source_mapping, request: preview.request }, null, 2)}</pre></details>{!validPreview && <StatusMessage tone="warning">预览来源或契约不一致；必须重新预览，不能调用模型。</StatusMessage>}<label className="creative-review-check"><input type="checkbox" disabled={disabled || !validPreview || !preview.execution_available} checked={reviewed} onChange={event => { if (!admitted()) return; admission.current = Symbol(); setReviewed(event.target.checked); }} />已核对完整分镜输入和固定映射，允许本地调用一次</label><Button variant="primary" disabled={disabled || !reviewed || !validPreview || !preview.execution_available || !route?.available || route.synthetic || route.provider_id !== preview.broker?.chosen?.provider_id || route.model_id !== preview.broker?.chosen?.model_id} onClick={() => { if (reviewed && validPreview && preview.execution_available && route?.available && !route.synthetic && route.provider_id === preview.broker?.chosen?.provider_id && route.model_id === preview.broker?.chosen?.model_id && client.dispatchStoryboardModel) operate(() => client.dispatchStoryboardModel!(proposal)); }}>确认调用分镜本地模型</Button></div>}
    {execution && <div><Badge>{execution.status}</Badge><p>任务：{execution.job_id}</p><p>调用：{execution.model_called ? '已调用' : '尚未确认调用'} · 回执：{execution.receipt_state}</p>{execution.failure_code && <p>{execution.failure_code}</p>}{!terminal && <div className="creative-actions"><Button disabled={disabled} onClick={() => operate(() => client.refreshModel(proposal))}>核对模型结果</Button><Button disabled={disabled} onClick={() => operate(() => client.cancelProposal(proposal))}>取消模型任务</Button></div>}</div>}
  </section>;
}
