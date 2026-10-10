import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import type { StudioProviderClient } from './studioProviderClient';
import type { StudioGraphModelCapabilities } from './studioGraphTypes';
import type { StudioProviderCatalog, StudioProviderFamily, StudioTaskMatchResult, StudioTaskRequirement, StudioTaskType } from './studioProviderTypes';

const taskLabels: Record<StudioTaskType, string> = { TEXT_GENERATION: '文字 · TEXT', IMAGE_GENERATION: '图片 · IMAGE', VIDEO_GENERATION: '视频 · VIDEO' };
const familyLabels: Record<StudioProviderFamily, string> = { LOCAL_OLLAMA: 'Ollama', LM_STUDIO: 'LM Studio', COMFYUI: 'ComfyUI', LLAMA_CPP: 'llama.cpp', API: '云端 API' };
const statusLabels = { REGISTERED: '已注册适配器', UNAVAILABLE: '不可用', RESERVED: '预留' };
const hardwareLabels = { NOT_REQUESTED: '未设置内存要求', UNKNOWN: '主机容量未知', INSUFFICIENT: '主机总容量不足', TOTAL_CAPACITY_ONLY: '仅主机总容量符合' };
type Props = {
  client: StudioProviderClient; routes?: StudioGraphModelCapabilities['routes']; locked: boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; onUnavailable: () => void;
};
function memory(value: string): number | null | undefined {
  if (!value.trim()) return null;
  if (!/^\d+$/.test(value)) return undefined;
  const result = Number(value); return Number.isSafeInteger(result) && result >= 1 && result <= 10 ** 7 ? result : undefined;
}

/** Read-only explanations, isolated from selected execution routes and consent. */
export function ProviderTaskMatchPanel({ client, routes = [], locked, isCurrent, read, onUnavailable }: Props) {
  const [catalog, setCatalog] = useState<StudioProviderCatalog>(), [result, setResult] = useState<StudioTaskMatchResult>();
  const [task, setTask] = useState<StudioTaskType>('TEXT_GENERATION'), [preferred, setPreferred] = useState('');
  const [ram, setRam] = useState(''), [vram, setVram] = useState(''), [synthetic, setSynthetic] = useState(false);
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), sequence = useRef(0), pending = useRef<{ id: number; controller: AbortController }>();
  const latest = useRef({ client, locked, isCurrent }); latest.current = { client, locked, isCurrent };
  const valid = (id: number) => alive.current && sequence.current === id && latest.current.client === client && !latest.current.locked && latest.current.isCurrent();
  function invalidate() { sequence.current++; pending.current?.controller.abort(); pending.current = undefined; setLoading(false); setResult(undefined); setError(''); }
  useEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; pending.current?.controller.abort(); }; }, []);
  useEffect(() => { invalidate(); setCatalog(undefined); setPreferred(''); setSynthetic(false); }, [client]);
  useEffect(() => { if (locked || !isCurrent()) { invalidate(); setCatalog(undefined); } }, [locked, isCurrent]);
  useEffect(() => { if (preferred && !routes.some(route => route.route_id === preferred)) { invalidate(); setPreferred(''); setSynthetic(false); } }, [routes, preferred]);
  const ramValue = memory(ram), vramValue = memory(vram), invalidMemory = ramValue === undefined || vramValue === undefined;
  const disabled = locked || !isCurrent();
  function change(work: () => void) { invalidate(); work(); }

  async function request(kind: 'catalog' | 'match') {
    if (pending.current || disabled || !alive.current || kind === 'match' && (!catalog || invalidMemory)) return;
    const id = ++sequence.current, controller = new AbortController(); pending.current = { id, controller }; setLoading(true); setError(''); setResult(undefined);
    if (kind === 'catalog') setCatalog(undefined);
    try {
      if (kind === 'catalog') {
        const value = await read(() => client.providerContracts(controller.signal)); if (valid(id)) setCatalog(value);
      } else {
        const requirement: StudioTaskRequirement = { task_type: task, preferred_route: preferred || null, min_host_ram_mib: ramValue!, min_host_vram_mib: vramValue!, local_only: true, api_available: false, allow_synthetic: synthetic };
        const value = await read(() => client.modelMatch(requirement, controller.signal)); if (valid(id)) setResult(value);
      }
    } catch (value) {
      if (valid(id)) {
        setResult(undefined); setError(apiErrorView(value, '提供方说明读取失败，请核对当前项目权限。').message);
        if (value instanceof ApiError && [401, 403, 404].includes(value.status)) { setCatalog(undefined); setPreferred(''); setSynthetic(false); onUnavailable(); }
      }
    } finally { if (pending.current?.id === id) pending.current = undefined; if (valid(id)) setLoading(false); }
  }

  return <section className="studio-graph-model" aria-label="提供方与任务匹配说明">
    <h4>提供方与任务匹配说明</h4>
    <p>只读取契约与筛选说明，不会选择执行路由、调用模型或自动回退。提供方声明的能力与已验证的适配器契约分别显示；真实推理验收尚未运行。</p>
    <Button disabled={disabled || loading} onClick={() => void request('catalog')}>读取提供方契约</Button>
    {loading && <StatusMessage>正在读取提供方与任务匹配说明…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}
    {!disabled && catalog && <>
      {catalog.providers.map(provider => <details key={provider.family}>
        <summary>{familyLabels[provider.family]} · {statusLabels[provider.availability.status]}</summary>
        <p>声明能力：{provider.capability.advertised.map(item => taskLabels[item]).join('、')}</p>
        <p>已验证适配器契约：{provider.capability.verified.map(item => taskLabels[item]).join('、') || '无'}。不代表推理质量或模型执行授权。</p>
        <p>此契约执行入口：关闭。已注册路由数：{provider.registered_routes.length}。</p>
        {provider.availability.reasons.map(reason => <StatusMessage key={reason} tone="warning">{reason}</StatusMessage>)}
        {provider.family === 'LM_STUDIO' && <p>LM Studio 仍缺少可信本地性证据，不能调用。</p>}
        {provider.family === 'COMFYUI' && <p>图片和视频生成仅预留，图执行尚未开放。</p>}
        {provider.family === 'API' && <p>API 仅预留，不可执行，也不会成为自动回退目标。</p>}
      </details>)}
      <label>匹配任务类型<select aria-label="匹配任务类型" value={task} disabled={disabled} onChange={event => change(() => { setTask(event.target.value as StudioTaskType); setSynthetic(false); })}>{catalog.task_types.map(item => <option key={item} value={item}>{taskLabels[item]}</option>)}</select></label>
      <label>匹配指定路由<select aria-label="匹配指定路由" value={preferred} disabled={disabled} onChange={event => change(() => { setPreferred(event.target.value); setSynthetic(false); })}><option value="">不指定；仅列出说明</option>{routes.map(route => <option key={route.route_id} value={route.route_id}>{route.display_name} · {route.provider_id} / {route.model_id}{route.synthetic ? ' · 测试适配器' : ''}</option>)}</select></label>
      {!routes.length && <p>先读取本地模型能力，可在此明确限制匹配路由。匹配结果不会更改执行路由。</p>}
      <label>最低主机 RAM（MiB，可选）<input aria-label="最低主机 RAM（MiB，可选）" type="number" min="1" max="10000000" step="1" value={ram} disabled={disabled} onChange={event => change(() => setRam(event.target.value))} /></label>
      <label>最低主机 VRAM（MiB，可选）<input aria-label="最低主机 VRAM（MiB，可选）" type="number" min="1" max="10000000" step="1" value={vram} disabled={disabled} onChange={event => change(() => setVram(event.target.value))} /></label>
      {invalidMemory && <StatusMessage tone="warning">内存要求须为 1 至 10000000 的整数，或留空。</StatusMessage>}
      <label><input type="checkbox" checked={synthetic} disabled={disabled} onChange={event => change(() => setSynthetic(event.target.checked))} />明确将测试适配器纳入匹配；这不是模型调用授权</label>
      <p>仅本地匹配。API 可用性：预留。内存数据仅为主机总容量，不是可用内存，也不保证 GPU 可容纳模型。</p>
      {task !== 'TEXT_GENERATION' && <StatusMessage tone="warning">{taskLabels[task]} 执行未开放；这里只显示不匹配原因。</StatusMessage>}
      <Button disabled={disabled || loading || invalidMemory} onClick={() => void request('match')}>查看任务匹配说明</Button>
      {result && <section aria-label="任务匹配结果"><Badge tone="info">仅建议，不授权执行</Badge>
        <p>主机总容量 RAM：{result.hardware.ram_mib ?? '未知'} MiB · VRAM：{result.hardware.vram_mib ?? '未知'} MiB。当前可用内存：未知；GPU 适配：未验证。</p>
        {!result.matches.length && <StatusMessage tone="warning">没有可说明的本地模型路由。</StatusMessage>}
        {result.matches.map(match => <details key={match.route_id} open><summary>{match.display_name} · {match.eligible ? '满足当前筛选（仅建议）' : '不满足当前筛选'}</summary>
          <p>{match.provider_id} / {match.model_id}{match.synthetic ? ' · 测试适配器' : ''}{match.preferred ? ' · 明确指定的匹配路由' : ''} · {hardwareLabels[match.hardware_state]}</p>
          {match.reasons.map(reason => <StatusMessage key={reason} tone="warning">{reason}</StatusMessage>)}
        </details>)}
      </section>}
    </>}
  </section>;
}
