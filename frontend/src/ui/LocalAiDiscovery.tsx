import {useEffect, useRef, useState, type FormEvent} from 'react';
import {ApiError} from '../api';
import {
  localAiDiscoveryApi as discovery,
  type LocalDiscoverySnapshot, type LocalDiscoveryScan, type LocalModelCandidate,
  type LocalModelRegistration, type LocalRuntime, type LocalRuntimeConfiguration, type LocalRuntimeType,
} from '../localAiDiscoveryApi';
import {Badge, Button, EmptyState, Panel, StatusMessage} from './primitives';
import './LocalAiDiscovery.css';

const SCANNING = new Set(['QUEUED', 'RUNNING', 'SCANNING', 'CANCELLING']);
const AUTH_ERRORS = new Set(['SESSION_REQUIRED', 'INVALID_SESSION', 'FORBIDDEN']);
const RUNTIME_TYPES: LocalRuntimeType[] = ['OLLAMA', 'LLAMA_CPP', 'COMFYUI', 'AUTOMATIC1111', 'OPENAI_COMPATIBLE_LOCAL', 'CUSTOM_HTTP'];
const MODALITIES = ['UNKNOWN', 'TEXT', 'VISION', 'IMAGE', 'VIDEO', 'AUDIO', 'TTS', 'RESTORATION', 'INTERPOLATION'];
const GROUPS = ['Text 文本', 'Image 图片', 'Video 视频', 'Audio 音频', 'Utilities 工具', 'Unknown 待确认'];
const COMPATIBILITY: Record<string, string> = {COMPATIBLE: 'Compatible · 兼容', POSSIBLY_COMPATIBLE: 'Possibly Compatible · 可能兼容', UNSUPPORTED: 'Unsupported · 不支持', NOT_VERIFIED: 'Not Verified · 未验证'};
const emptyRuntime = (): LocalRuntimeConfiguration => ({name: '', type: 'OLLAMA', endpoint: 'http://127.0.0.1:11434', model_id: '', modality: 'UNKNOWN', health_endpoint: '', credential_required: false, management: 'EXTERNAL'});
const activeScan = (scan: LocalDiscoveryScan | null | undefined) => !!scan && SCANNING.has(scan.status);
const text = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value) : '未检测';
const bytes = (value: unknown) => typeof value === 'number' && value > 0 ? `${(value / 1024 ** 3).toFixed(1)} GiB` : '未检测';
const tone = (status: string): 'neutral' | 'success' | 'warning' | 'error' => ['READY', 'RUNNING', 'COMPLETED'].includes(status) ? 'success' : ['INCOMPATIBLE', 'FAILED', 'UNSUPPORTED'].includes(status) ? 'error' : ['NOT_FOUND', 'DISABLED', 'CANCELLED'].includes(status) ? 'neutral' : 'warning';
function groupOf(model: LocalModelCandidate) {
  const capabilities = [...(model.declared_capabilities || []), ...(model.verified_capabilities || []), model.modality];
  if (capabilities.some(value => ['RESTORATION', 'INTERPOLATION'].includes(value))) return GROUPS[4];
  if (capabilities.includes('VIDEO')) return GROUPS[2];
  if (capabilities.some(value => ['AUDIO', 'TTS'].includes(value))) return GROUPS[3];
  if (capabilities.includes('IMAGE')) return GROUPS[1];
  if (capabilities.some(value => ['TEXT', 'VISION'].includes(value))) return GROUPS[0];
  return GROUPS[5];
}

function Hardware({value}: {value: Record<string, unknown>}) {
  const gpus = Array.isArray(value.gpus) ? value.gpus as Record<string, unknown>[] : [];
  return <section aria-label="系统硬件" className="local-ai__section">
    <h3>系统硬件</h3>
    <dl className="local-ai__facts"><div><dt>系统 / 架构</dt><dd>{text(value.platform)} / {text(value.architecture)}</dd></div><div><dt>CPU</dt><dd>{text(value.cpu)}</dd></div><div><dt>系统内存</dt><dd>{bytes(value.ram_bytes)}</dd></div><div><dt>硬件检测状态</dt><dd>{text(value.status)}</dd></div></dl>
    {gpus.length ? gpus.map((gpu, index) => <p key={index}>GPU：{text(gpu.vendor)} · {text(gpu.name)} · 独立显存 {bytes(gpu.dedicated_vram_bytes)}</p>) : <p>GPU / 独立显存：未检测</p>}
    {Array.isArray(value.notes) && value.notes.filter(note => typeof note === 'string').map((note, index) => <p key={index}>{String(note)}</p>)}
  </section>;
}

function ModelEvidence({model}: {model: LocalModelCandidate}) {
  const evidence = model.evidence || {};
  const file = evidence.file_exists ?? evidence.model_file_exists;
  const nodes = Array.isArray(evidence.loader_nodes) ? evidence.loader_nodes.filter(value => typeof value === 'string') : [];
  return <dl className="local-ai__facts" aria-label="验证依据">
    <div><dt>模型文件</dt><dd>{file === true ? '文件存在（不代表可生成）' : file === false ? '文件未找到' : evidence.model_listed === true ? 'Runtime 已列出，文件存在性未独立验证' : '存在性未独立验证'}</dd></div>
    {typeof evidence.header_valid === 'boolean' && <div><dt>GGUF Header</dt><dd>{evidence.header_valid ? '格式验证通过' : '格式验证未通过'}</dd></div>}
    {model.runtime_type === 'COMFYUI' && <><div><dt>已发现加载节点</dt><dd>{nodes.length ? nodes.join(' · ') : '未确认'}</dd></div><div><dt>工作流条件</dt><dd>{evidence.workflow_status === 'STRUCTURE_VALIDATED_NOT_GENERATED' ? '结构验证通过，尚未实际生成' : '尚未配置 / 未验证'}</dd></div></>}
    <div><dt>实际生成验证</dt><dd>{model.verified && evidence.generation_verified === true ? '通过' : 'NOT_RUN · 尚未运行生成测试'}</dd></div>
    {typeof evidence.size === 'number' && <div><dt>模型大小</dt><dd>{bytes(evidence.size)}</dd></div>}
    {typeof evidence.modified_at === 'string' && <div><dt>模型更新时间</dt><dd>{evidence.modified_at}</dd></div>}
  </dl>;
}

export function LocalAiDiscovery({canMutate = false, onRegistryChange}: {canMutate?: boolean; onRegistryChange?: () => void}) {
  const [snapshot, setSnapshot] = useState<LocalDiscoverySnapshot>();
  const [scan, setScan] = useState<LocalDiscoveryScan | null>(null);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [stateUncertain, setStateUncertain] = useState(false), [expired, setExpired] = useState(false), [collapsed, setCollapsed] = useState(false), [pollPaused, setPollPaused] = useState(false), [pollVersion, setPollVersion] = useState(0), [cancelRequested, setCancelRequested] = useState(false);
  const [roots, setRoots] = useState(''), [editRoots, setEditRoots] = useState(false);
  const [runtimeForm, setRuntimeForm] = useState<LocalRuntimeConfiguration>(), [runtimeId, setRuntimeId] = useState<string>();
  const [confirmation, setConfirmation] = useState<{kind: 'enable' | 'remove'; model: LocalModelRegistration}>();
  const [registrationForm, setRegistrationForm] = useState<{id: string; workflow_adapter_id: string; license_confirmed: boolean}>();
  const mounted = useRef(false), generation = useRef(0), pollGeneration = useRef(0), busyRef = useRef(false);
  const mutable = canMutate && !expired;
  const scanning = activeScan(scan);
  const locked = !mutable || loading || !snapshot || stateUncertain || !!busy;

  function report(caught: unknown) {
    if (!mounted.current || (caught instanceof Error && caught.name === 'AbortError')) return;
    if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code))) {
      setExpired(true); setPollPaused(true); setConfirmation(undefined);
      setError('受信任的桌面会话已失效或权限不足，本地 AI 操作已禁用。请重新连接桌面会话。');
    } else {
      const code = caught instanceof ApiError && /^[A-Z0-9_]{1,80}$/.test(caught.problem.code) ? `（${caught.problem.code}）` : '';
      setError(`本地 AI 操作未完成${code}。已有结果已保留，请重试。`);
    }
  }
  async function refresh(signal?: AbortSignal) {
    const current = ++generation.current;
    const result = await discovery.snapshot(signal);
    if (!mounted.current || current !== generation.current) return;
    setSnapshot(result); setScan(result.scan); setRoots(result.settings.scan_roots.join('\n')); setLoading(false);
  }
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refresh(controller.signal).catch(caught => {if (controller.signal.aborted) return; report(caught); if (mounted.current) setLoading(false);});
    return () => {mounted.current = false; generation.current++; pollGeneration.current++; controller.abort();};
  }, []);

  // Only the current scan owns updates. Cancel/restart and unmount invalidate
  // pending requests; a late RUNNING response cannot revive a cancelled scan.
  useEffect(() => {
    if (!scan || !activeScan(scan) || pollPaused || expired) return;
    const scanId = scan.id, current = ++pollGeneration.current;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await discovery.scanStatus(scanId, controller.signal);
        if (!mounted.current || controller.signal.aborted || current !== pollGeneration.current) return;
        setScan(result);
        if (!activeScan(result)) setCancelRequested(false);
        if (activeScan(result)) timer = setTimeout(poll, 1000);
      } catch (caught) {
        if (controller.signal.aborted || current !== pollGeneration.current) return;
        report(caught);
        if (!(caught instanceof ApiError && (caught.status === 401 || caught.status === 403))) timer = setTimeout(poll, 3000);
      }
    };
    timer = setTimeout(poll, 1000);
    return () => {controller.abort(); clearTimeout(timer);};
  }, [scan?.id, scanning, pollPaused, pollVersion, expired]);

  // Hardware facts are collected during scanning, not when this page opens.
  // Refresh them once a scan reaches a terminal state without replacing the
  // current candidate state or allowing an older read to overwrite a mutation.
  useEffect(() => {
    if (!scan || activeScan(scan) || expired) return;
    const current = generation.current, controller = new AbortController();
    void discovery.snapshot(controller.signal).then(result => {
      if (mounted.current && !controller.signal.aborted && current === generation.current) setSnapshot(result);
    }).catch(caught => {if (!controller.signal.aborted && current === generation.current) report(caught);});
    return () => controller.abort();
  }, [scan?.id, scanning, expired]);

  async function recoverProtectedState() {
    const current = ++generation.current;
    try {
      const result = await discovery.snapshot();
      if (!mounted.current || current !== generation.current) return;
      setSnapshot(result); setScan(result.scan); setStateUncertain(false);
      setConfirmation(undefined); setRegistrationForm(undefined);
      onRegistryChange?.();
    } catch (caught) {
      if (!mounted.current || current !== generation.current) return;
      setStateUncertain(true);
      if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code))) report(caught);
      else setError(previous => `${previous} 状态重新读取失败，请重新读取后再操作。`.trim());
    }
  }
  async function run(key: string, task: () => Promise<void>, recoverOnFailure = false) {
    if (!mutable || !snapshot || loading || busyRef.current || (scanning && key !== 'cancel') || (stateUncertain && key !== 'refresh-state')) return;
    generation.current++; busyRef.current = true; setBusy(key); setError('');
    try {await task();} catch (caught) {
      report(caught);
      if (recoverOnFailure && mounted.current) {
        // Validation can revoke a registration before a failed response arrives.
        // Never retain routing authority or an old license confirmation on error.
        setStateUncertain(true); setConfirmation(undefined); setRegistrationForm(undefined);
        if (!(caught instanceof ApiError && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code)))) await recoverProtectedState();
      }
    } finally {busyRef.current = false; if (mounted.current) setBusy('');}
  }
  async function scanAction(cancel = false) {
    await run(cancel ? 'cancel' : 'scan', async () => {
      pollGeneration.current++; setPollPaused(true); setPollVersion(value => value + 1); generation.current++;
      try {
        const result = cancel && scan ? await discovery.cancelScan(scan.id) : await discovery.scan();
        if (mounted.current) {setScan(result); setCancelRequested(cancel && activeScan(result)); setCollapsed(false); setConfirmation(undefined);}
      } finally {if (mounted.current) setPollPaused(false);}
    });
  }
  function updateRegistration(registration: LocalModelRegistration) {
    setSnapshot(current => current ? {...current, registrations: [...current.registrations.filter(item => item.id !== registration.id), registration]} : current);
    onRegistryChange?.();
  }
  async function candidateAction(model: LocalModelCandidate, action: 'validate' | 'register') {
    await run(`${model.id}:${action}`, async () => {
      if (action === 'validate') {
        const result = await discovery.validate(model.id);
        if (mounted.current) {
          setScan(current => current ? {...current, candidates: current.candidates.map(item => item.id === result.id ? result : item)} : current);
          const registered = snapshot?.registrations.find(item => item.id === result.id || item.candidate_id === result.id);
          if (registered) updateRegistration({...registered, ...result, id: registered.id, enabled: false});
        }
      } else {
        const result = await discovery.register(model.id);
        if (mounted.current) updateRegistration(result);
      }
    }, true);
  }
  async function registrationAction(model: LocalModelRegistration, action: 'enable' | 'disable' | 'remove') {
    await run(`${model.id}:${action}`, async () => {
      if (action === 'remove') {
        await discovery.remove(model.id);
        if (mounted.current) {setSnapshot(current => current ? {...current, registrations: current.registrations.filter(item => item.id !== model.id)} : current); onRegistryChange?.();}
      } else {
        const result = await discovery[action](model.id);
        if (mounted.current) updateRegistration(result);
      }
      if (mounted.current) setConfirmation(undefined);
    }, true);
  }
  function editRuntime(runtime?: LocalRuntime) {
    const configured = snapshot?.settings.runtimes.find(item => item.id === runtime?.id);
    const saved = configured || scan?.candidates.find(item => item.runtime_id === runtime?.id)?.runtime_config;
    setRuntimeId(configured?.id);
    // Explicit allowlist prevents server-only capability/evidence fields from
    // being replayed as user configuration.
    const type = runtime?.type || runtime?.runtime_type || 'OLLAMA';
    setRuntimeForm({name: runtime?.name || '', type, endpoint: runtime?.endpoint || '', model_id: saved?.model_id || '', modality: saved?.modality || 'UNKNOWN', health_endpoint: saved?.health_endpoint || '', credential_required: saved?.credential_required ?? false, management: saved?.management || runtime?.management || 'EXTERNAL', ...(type === 'LLAMA_CPP' ? {executable: saved?.executable || '', model_path: saved?.model_path || '', context_size: saved?.context_size ?? 8192, gpu_layers: saved?.gpu_layers ?? 0, threads: saved?.threads ?? 4, batch_size: saved?.batch_size ?? 512} : {})});
    if (!runtime) setRuntimeForm(emptyRuntime());
  }
  async function saveRuntime(event: FormEvent) {
    event.preventDefault(); if (!runtimeForm) return;
    await run('runtime', async () => {await discovery.saveRuntime(runtimeForm, runtimeId); if (mounted.current) {setRuntimeForm(undefined); await refresh();}}, true);
  }
  const runtimeField = (key: 'name' | 'endpoint' | 'model_id' | 'health_endpoint' | 'executable' | 'model_path' | 'context_size' | 'gpu_layers' | 'threads' | 'batch_size', label: string, numeric = false, required = false) => <label>{label}<input type={numeric ? 'number' : 'text'} required={required} min={numeric ? key === 'gpu_layers' ? 0 : key === 'context_size' ? 512 : 1 : undefined} max={numeric ? ({context_size: 131072, gpu_layers: 999, threads: 512, batch_size: 4096} as Record<string, number>)[key] : undefined} value={runtimeForm?.[key] ?? ''} onChange={event => setRuntimeForm(current => current ? {...current, [key]: numeric ? event.target.value === '' ? undefined : Number(event.target.value) : event.target.value} : current)}/></label>;
  const registrations = snapshot?.registrations || [];
  const candidates = scan?.candidates || [];
  const runtimeMap = new Map<string, LocalRuntime>();
  snapshot?.settings.runtimes.forEach(item => runtimeMap.set(item.id, item));
  scan?.runtimes.forEach(item => runtimeMap.set(item.id, {...runtimeMap.get(item.id), ...item}));
  const models: {model: LocalModelCandidate; registration?: LocalModelRegistration}[] = candidates.map(model => ({model, registration: registrations.find(item => item.id === model.id || item.candidate_id === model.id)}));
  registrations.filter(item => !models.some(row => row.registration?.id === item.id)).forEach(registration => models.push({model: registration, registration}));
  const controlsLocked = locked || scanning;

  return <Panel title="Local AI · 本地 AI 发现" className="local-ai" actions={<Button variant="ghost" onClick={() => setCollapsed(value => !value)} aria-expanded={!collapsed}>{collapsed ? '展开本地 AI' : !scan && !registrations.length ? '跳过 / 收起' : '收起'}</Button>}>
    {!collapsed && <div className="local-ai__body">
      <p>只读检测本机 Runtime 和指定模型目录。发现 → 验证 → 注册 → 确认启用 → 按需启动；扫描不会启动 Runtime 或加载模型。</p>
      <p className="local-ai__muted">扫描结果保留在本地，不上传路径、文件名或硬件信息到云 Provider；不会读取小说正文或私人文档。</p>
      {error && <StatusMessage tone="error">{error}</StatusMessage>}
      {snapshot?.persistence_error && <StatusMessage tone="warning">本地 AI 配置无法完整读取，请检查本地服务。已有模型文件不受影响。</StatusMessage>}
      {stateUncertain && <StatusMessage tone="warning">当前启用状态尚未确认；重新读取成功前，所有接入变更已暂时禁用。</StatusMessage>}
      {!mutable && !error && <StatusMessage tone="warning">本地 AI 操作需要受信任的桌面会话。</StatusMessage>}
      <div className="local-ai__actions">
        <Button variant="primary" disabled={locked || scanning} loading={busy === 'scan'} onClick={() => void scanAction()}>{scan ? '重新扫描' : '检测本机 AI 环境'}</Button>
        {scanning && <Button disabled={locked || cancelRequested} loading={busy === 'cancel'} onClick={() => void scanAction(true)}>{cancelRequested ? '正在取消扫描…' : '取消扫描'}</Button>}
        <Button disabled={controlsLocked} onClick={() => editRuntime()}>添加本地 Runtime</Button>
        <Button disabled={controlsLocked} onClick={() => setEditRoots(value => !value)}>配置扫描目录</Button>
        {stateUncertain && <Button disabled={!!busy || !mutable} onClick={() => void run('refresh-state', recoverProtectedState)}>重新读取状态</Button>}
        {!snapshot && !loading && <Button disabled={!!busy || expired} onClick={() => {setLoading(true); setError(''); void refresh().catch(caught => {report(caught); if (mounted.current) setLoading(false);});}}>重试读取</Button>}
      </div>
      {loading && <p role="status">正在读取本地 AI 状态…</p>}
      {scan && <div className="local-ai__summary" role="status"><Badge tone={tone(scan.status)}>{scan.status}</Badge><span>发现 {candidates.length} 个模型 · 已注册 {registrations.length} 个 · {stateUncertain ? '启用状态待确认' : `已启用 ${registrations.filter(item => item.enabled).length} 个`} · {scan.runtimes.filter(item => item.status === 'RUNNING').length} 个 Runtime 可用 · {scan.errors.length} 个检测问题</span>{scanning && <span>{cancelRequested ? '已请求取消，等待当前只读探测结束…' : '扫描中，已显示当前部分结果…'}</span>}{scan.status === 'CANCELLED' && <span>扫描已取消，保留已发现结果。</span>}</div>}
      {!!scan?.errors.length && <StatusMessage tone="warning">部分检测未完成，不影响其他结果。{scan.errors.map((item, index) => <p key={index}>{typeof item === 'string' ? item : [item.runtime_id, item.code].filter(Boolean).join(' · ') || 'Runtime 检测未完成'}</p>)}</StatusMessage>}
      {editRoots && <form className="local-ai__form" aria-label="扫描目录配置" onSubmit={event => {event.preventDefault(); void run('roots', async () => {await discovery.settings(roots.split(/\r?\n/).map(value => value.trim()).filter(Boolean)); if (mounted.current) {setEditRoots(false); await refresh();}}, true);}}>
        <label className="local-ai__wide">模型目录（每行一个完整路径）<textarea rows={4} value={roots} placeholder="D:\AI\models" onChange={event => setRoots(event.target.value)}/></label>
        <p className="local-ai__wide">仅扫描明确配置的目录，受深度和数量限制；保存目录不会开始扫描。请勿选择磁盘根目录或私人文档目录。</p>
        <div className="local-ai__actions local-ai__wide"><Button type="submit" disabled={controlsLocked}>保存扫描目录</Button><Button type="button" variant="ghost" onClick={() => {setEditRoots(false); setRoots(snapshot?.settings.scan_roots.join('\n') || '');}}>取消</Button></div>
      </form>}
      {runtimeForm && <form className="local-ai__form" aria-label="本地 Runtime 配置" onSubmit={saveRuntime}>
        <h3 className="local-ai__wide">{runtimeId ? '配置本地 Runtime' : '添加本地 Runtime'}</h3>
        {runtimeField('name', 'Runtime 名称', false, true)}
        <label>Runtime 类型<select value={runtimeForm.type} onChange={event => setRuntimeForm(current => current ? {...current, type: event.target.value as LocalRuntimeType, management: 'EXTERNAL', executable: undefined, model_path: undefined, context_size: undefined, gpu_layers: undefined, threads: undefined, batch_size: undefined} : current)}>{RUNTIME_TYPES.map(value => <option key={value}>{value}</option>)}</select></label>
        {runtimeField('endpoint', '本机地址 Endpoint', false, true)}{runtimeField('health_endpoint', '健康检查路径（可选）')}{runtimeField('model_id', '模型 ID（可选）')}
        <label>声明模态（仍需验证）<select value={runtimeForm.modality} onChange={event => setRuntimeForm(current => current ? {...current, modality: event.target.value} : current)}>{MODALITIES.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>生命周期<select value={runtimeForm.management} onChange={event => setRuntimeForm(current => current ? {...current, management: event.target.value as 'EXTERNAL' | 'MANAGED'} : current)}><option value="EXTERNAL">EXTERNAL_RUNTIME · 用户自行启停</option>{runtimeForm.type === 'LLAMA_CPP' && <option value="MANAGED">MANAGED · 仅按需启动</option>}</select></label>
        <label className="local-ai__check"><input type="checkbox" checked={runtimeForm.credential_required} onChange={event => setRuntimeForm(current => current ? {...current, credential_required: event.target.checked} : current)}/>需要凭据（未绑定受支持凭据库前不能启用）</label>
        {runtimeForm.type === 'LLAMA_CPP' && <>{runtimeField('executable', 'llama.cpp executable')}{runtimeField('model_path', 'GGUF 模型路径')}{runtimeField('context_size', 'Context Size', true)}{runtimeField('gpu_layers', 'GPU Layers', true)}{runtimeField('threads', 'Threads', true)}{runtimeField('batch_size', 'Batch Size', true)}</>}
        <p className="local-ai__wide">仅接受本机地址，不在地址中填写密码或 Token。保存和验证不会启动程序；未知 Runtime 不会自动获得已验证能力。</p>
        <div className="local-ai__actions local-ai__wide"><Button type="submit" disabled={controlsLocked}>保存 Runtime</Button><Button type="button" variant="ghost" onClick={() => setRuntimeForm(undefined)}>取消</Button></div>
      </form>}
      {snapshot && <Hardware value={snapshot.hardware}/>}
      {!!runtimeMap.size && <section className="local-ai__section" aria-label="发现的 Runtime"><h3>本地 Runtime（{runtimeMap.size}）</h3><div className="local-ai__list">{Array.from(runtimeMap.values()).map(runtime => <article key={runtime.id} aria-label={runtime.name || runtime.id}><header><strong>{runtime.name || runtime.id}</strong><Badge tone={tone(runtime.status || 'NOT_VERIFIED')}>{runtime.status || 'NOT_VERIFIED'}</Badge></header><p>{runtime.type || runtime.runtime_type} · {runtime.management || 'EXTERNAL'}</p><p>地址：{runtime.endpoint || '未配置'} · 版本：{runtime.version || '未检测'}</p><p>运行状态：{runtime.status === 'RUNNING' ? '正在运行' : runtime.status === 'NOT_FOUND' ? '未发现运行服务' : '未确认'}</p>{runtime.executable_exists !== undefined && <p>Executable：{runtime.executable_exists ? '已找到' : '未找到'} · CUDA：{runtime.cuda_status || '未验证'}</p>}{runtime.notes?.map((note, index) => <p key={index}>{note}</p>)}<Button disabled={controlsLocked} onClick={() => editRuntime(runtime)}>配置 Runtime</Button></article>)}</div></section>}
      {!loading && !models.length && <EmptyState title={scan ? '尚未发现模型' : '尚未开始扫描'} detail="可跳过检测，也可添加 Runtime 或模型目录后主动扫描。未安装的 Runtime 不影响应用使用。"/>}
      {GROUPS.map(group => {const rows = models.filter(row => groupOf(row.model) === group); return rows.length ? <section className="local-ai__section" key={group} aria-label={group}><h3>{group}（{rows.length}）</h3><div className="local-ai__list">{rows.map(({model, registration}) => {const current = registration || model; return <article key={model.id} aria-label={`${model.display_name} 本地模型`}>
        <header><strong>{model.display_name}</strong><Badge tone={stateUncertain ? 'warning' : tone(current.status)}>{stateUncertain ? 'NOT_VERIFIED' : current.status}</Badge></header>
        <div className="local-ai__actions"><Badge>本地</Badge><Badge tone={stateUncertain ? 'warning' : registration?.enabled ? 'success' : 'neutral'}>{stateUncertain && registration ? '接入状态待确认' : registration?.enabled ? '已启用' : registration ? '已注册 · 未启用' : '候选 · 未注册'}</Badge><Badge tone={current.verified ? 'success' : 'warning'}>{current.verified ? '已通过实际生成验证' : '尚未实际生成验证'}</Badge></div>
        <dl className="local-ai__facts"><div><dt>Runtime / 来源</dt><dd>{model.runtime_type} · {model.runtime_id} · {model.source}</dd></div><div><dt>模型族 / 模型 ID</dt><dd>{model.family} · {model.model_id}</dd></div><div><dt>声明能力</dt><dd>{current.declared_capabilities.join(' · ') || 'UNKNOWN'}</dd></div><div><dt>已验证能力</dt><dd>{current.verified_capabilities.join(' · ') || 'CAPABILITY_UNVERIFIED'}</dd></div><div><dt>只读接入验证</dt><dd>{current.validated_at ? '已完成检查（不代表实际生成验证）' : '尚未验证 / 需重新验证'}</dd></div><div><dt>兼容性</dt><dd>{COMPATIBILITY[current.compatible] || current.compatible || 'Not Verified · 未验证'}</dd></div><div><dt>模型路径 / 文件 / 来源</dt><dd>{model.local_path || model.model_name || model.source}</dd></div></dl>
        <ModelEvidence model={current}/>
        {!!current.validation_notes?.length && <ul className="local-ai__notes">{current.validation_notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
        {!!current.enable_blockers?.length && <p>启用前仍需：{current.enable_blockers.join(' · ')}</p>}
        <div className="local-ai__actions">
          <Button disabled={controlsLocked} onClick={() => void candidateAction(model, 'validate')}>验证</Button>
          {!registration && <><Button disabled={controlsLocked || !model.validated_at} title={!model.validated_at ? '请先验证候选模型' : undefined} onClick={() => void candidateAction(model, 'register')}>注册</Button></>}
          {registration && <>{registration.enabled ? <Button disabled={controlsLocked} onClick={() => void registrationAction(registration, 'disable')}>停用</Button> : <Button disabled={controlsLocked || !registration.enable_eligible} onClick={() => setConfirmation({kind: 'enable', model: registration})}>启用</Button>}<Button disabled={controlsLocked} onClick={() => setRegistrationForm({id: registration.id, workflow_adapter_id: registration.workflow_adapter_id || '', license_confirmed: registration.license_confirmed ?? false})}>配置接入条件</Button><Button variant="ghost" disabled={controlsLocked} onClick={() => setConfirmation({kind: 'remove', model: registration})}>移除注册</Button></>}
        </div>
        {registrationForm?.id === registration?.id && registrationForm && <form className="local-ai__form" aria-label={`${model.display_name} 接入条件`} onSubmit={event => {event.preventDefault(); void run('registration-config', async () => {const result = await discovery.configureRegistration(registrationForm.id, {workflow_adapter_id: registrationForm.workflow_adapter_id, license_confirmed: registrationForm.license_confirmed}); if (mounted.current) {updateRegistration(result); setRegistrationForm(undefined);}}, true);}}>
          <label className="local-ai__wide">Workflow Adapter<select value={registrationForm.workflow_adapter_id} onChange={event => setRegistrationForm({...registrationForm, workflow_adapter_id: event.target.value})}><option value="">未选择</option>{snapshot?.workflow_adapters?.map(adapter => <option value={adapter.id} key={adapter.id}>{adapter.display_name || adapter.id}{adapter.capability ? ` · ${adapter.capability}` : ''}</option>)}</select></label>
          <label className="local-ai__check local-ai__wide"><input type="checkbox" checked={registrationForm.license_confirmed} onChange={event => setRegistrationForm({...registrationForm, license_confirmed: event.target.checked})}/>我已核对该模型授权，允许在约定用途内使用</label><p className="local-ai__wide">发现模型不代表获得商业授权；勾选仅记录你的确认，不提供商业使用保证。无兼容工作流时仍无法启用。</p>
          <div className="local-ai__actions local-ai__wide"><Button type="submit" disabled={controlsLocked}>保存接入条件</Button><Button type="button" variant="ghost" onClick={() => setRegistrationForm(undefined)}>取消</Button></div>
        </form>}
        {confirmation?.model.id === registration?.id && confirmation && <section className="local-ai__confirmation" aria-label={confirmation.kind === 'enable' ? '确认启用模型' : '确认移除注册'}><p>{confirmation.kind === 'enable' ? `确认允许 ${model.display_name} 进入实际任务路由？启用不会立即加载模型或常驻显存。` : `移除 ${model.display_name} 的注册？只移除接入记录，不删除真实模型文件。`}</p><div className="local-ai__actions"><Button variant={confirmation.kind === 'enable' ? 'primary' : 'danger'} disabled={controlsLocked} onClick={() => void registrationAction(confirmation.model, confirmation.kind)}>{confirmation.kind === 'enable' ? '确认启用' : '确认移除注册'}</Button><Button variant="ghost" disabled={!!busy} onClick={() => setConfirmation(undefined)}>取消</Button></div></section>}
      </article>;})}</div></section> : null;})}
    </div>}
  </Panel>;
}
