import {useEffect, useRef, useState, type FormEvent} from 'react';
import {ApiError} from '../api';
import {useLocalAiDiscoveryOwner, useLocalAiOwnerKey, type LocalAiOnboardingOwner} from '../localAiDiscoveryOwner';
export type {LocalAiOnboardingOwner} from '../localAiDiscoveryOwner';
import {
  localAiDiscoveryApi as legacyDiscovery,
  type LocalAiDiscoveryClient, type LocalAiScanScope,
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
const DIAGNOSTIC_GUIDANCE: Record<string, string> = {
  EXTERNAL_RUNTIME_NOT_RUNNING: '已发现文件，但服务尚未启动。请在已有安装中手动启动 Runtime，再重新检测；不会代你启动或升级。',
  RUNTIME_REQUIRED: '缺少可用 Runtime。核对已有安装或服务配置，然后重新验证。',
  MODEL_OR_RUNTIME_NOT_FOUND: '当前未找到模型或运行服务。先确认服务已启动，再核对模型 ID；不会自动下载模型。',
  RUNTIME_MODEL_UNVERIFIED: '服务没有报告所选模型。核对模型 ID 与当前加载模型，再重新验证。',
  RUNTIME_MODEL_PATH_MISMATCH: '当前 Runtime 的模型路径与候选不一致。先核对原配置，不会自动移动或替换文件。',
  GGUF_HEADER_INVALID: '模型文件头未通过检查。核对文件是否完整、格式是否正确；不会覆盖已有模型。',
  WORKFLOW_ADAPTER_REQUIRED: '缺少匹配的工作流、模型组件或节点绑定。核对已安装节点与已审核 Adapter；不会安装未知节点。',
  ADAPTER_REQUIRED: '当前 Runtime 尚无可用 Adapter。保留候选，等待受支持的适配器；不执行第三方插件。',
  LICENSE_VALIDATION_REQUIRED: '模型许可未确认。阅读原模型许可证后，在“配置接入条件”明确确认用途。',
  VALIDATION_REQUIRED: '还没有验证此候选。点击“验证”检查已有服务的元数据；不会发起生成。',
  REVALIDATION_REQUIRED: '之前的验证已失效。重新验证并核对许可与接入条件，然后再明确启用。',
  MODEL_CHANGED_REVIEW_REQUIRED: '模型身份已变化。旧许可确认不再适用，请重新核对该版本。',
  LOCAL_MODEL_EVIDENCE_CHANGED: '模型或环境元数据已变化，旧接入不能继续使用。重新验证后再确认启用。',
  LOCAL_AI_CONNECTION_FAILED: 'Endpoint 无法连接。核对本机地址、端口和服务状态；此诊断不说明模型已损坏。',
  LOCAL_AI_TIMEOUT: 'Endpoint 检查超时。确认服务负载和端口，再手动重试。',
  CAPABILITY_UNVERIFIED: '尚无足够能力证据。模型目录声明不能代替接入验证或真实推理验收。',
  CURRENT_GPU_NOT_VERIFIED: '当前 GPU 未实测。无法保证显存足够；请在本机验证，不会升级 Torch、CUDA 或驱动。',
  CPU_OFFLOAD_MAY_BE_REQUIRED: 'GPU 分层配置可能需要 CPU 分担。当前未测显存余量，请在本机评估后调整原配置。',
  MEMORY_AND_CONTEXT_NOT_VERIFIED: '模型文件大小与已检测内存提示容量风险；上下文和 KV 缓存尚未测量，不能保证可运行。',
  CUDA_NOT_VERIFIED: 'CUDA 兼容性尚未实测。保留当前环境，后续本机验证；不会自动升级。',
  INFERENCE_NOT_RUN: '这里只验证已有元数据，尚未运行真实模型。质量、速度与峰值内存仍待本机验收。',
  TEXT_GENERATION_UNSUPPORTED: '该模型未报告文本续写能力；嵌入能力不能当作正文生成能力。',
  OLLAMA_REMOTE_MODEL_BLOCKED: '该 Ollama 模型属于远程托管来源，禁止冒充本地模型或静默外发。',
  OLLAMA_LOCALITY_UNVERIFIED: '尚未证明该 Ollama 模型会在本机执行，不能用于本地隐私路线。',
  OLLAMA_IDENTITY_CHANGED: 'Ollama 模型身份已变化。重新验证并确认来源后才能恢复接入。',
  LOCAL_AI_CREDENTIAL_BINDING_REQUIRED: '此 Runtime 需要独立的安全凭据绑定；不要把密钥粘贴到诊断或模型名称中。',
};
export function localAiDiagnostic(code: string): string | undefined { return DIAGNOSTIC_GUIDANCE[code]; }

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

type DiscoveryProps = {canMutate?: boolean; onRegistryChange?: () => void; onboarding?: LocalAiOnboardingOwner; scopeRevision?: number};
/** The legacy path stays default-off. V2 consumes the same discovery registry. */
export function LocalAiDiscovery(props: DiscoveryProps) {
  return props.onboarding ? <OwnedLocalAiDiscovery {...props} onboarding={props.onboarding}/> : <LocalAiDiscoveryContent {...props}/>;
}
function OwnedLocalAiDiscovery(props: DiscoveryProps & {onboarding: LocalAiOnboardingOwner}) {
  const ownerKey = useLocalAiOwnerKey(props.onboarding);
  return <LocalAiDiscoveryOwner key={ownerKey} {...props}/>;
}
function LocalAiDiscoveryOwner(props: DiscoveryProps & {onboarding: LocalAiOnboardingOwner}) {
  const owner = useLocalAiDiscoveryOwner(props.onboarding);
  return <LocalAiDiscoveryContent {...props} canMutate={props.canMutate && !owner.invalidated} v2={owner.client} isCurrentOwner={owner.current} ownerInvalidated={owner.invalidated}/>;
}

function ScanScopeDetails({scope}: {scope: LocalAiScanScope}) {
  return <>
    <p>检测位置：BACKEND_HOST · 运行后端的主机。云端主机的结果不代表你的电脑。</p>
    <p>仅检查下列已有服务、目录与文件元数据，不搜索其他端口。不启动程序、不加载模型、不调用云端模型，真实推理仍为 NOT_RUN。</p>
    <p>发现服务或模型已失效时，可能停用旧注册及路由，并保存该安全状态；不会自动注册或启用模型。</p>
    <div className="local-ai__section"><h3>将检查的服务（{scope.services.length}）</h3>
      {scope.services.length ? <ul className="local-ai__notes">{scope.services.map(service => <li key={service.id}>{service.name} · {service.type} · {service.endpoint}<br/>读取：{service.probe_paths.join('、') || '无 HTTP 探测路径'}</li>)}</ul> : <p>未配置可检查的服务。仍可手动使用创作功能。</p>}
    </div>
    <dl className="local-ai__facts">
      <div><dt>模型目录</dt><dd>{scope.roots.filter(root => root.source === 'CONFIGURED').length} 个已配置目录 · {scope.roots.filter(root => root.source === 'COMMON').length} 个常用目录</dd></div>
      <div><dt>文件元数据检查</dt><dd>{scope.metadata_inspections.length} 项范围内检查；只读取有界元数据</dd></div>
      <div><dt>硬件信息类别</dt><dd>{scope.hardware_categories.map(scopeHardwareLabel).join(' · ') || '无硬件检查'}</dd></div>
      <div><dt>常用目录</dt><dd>{scope.include_common_model_dirs ? '本次明确选择包含' : '本次不包含'}；不会更改已保存设置</dd></div>
    </dl>
    <section aria-label="检测范围限制" className="local-ai__section"><h3>本次检测上限</h3><dl className="local-ai__facts">{Object.entries(scope.limits).map(([key, value]) => <div key={key}><dt>{scopeLimitLabel(key)}</dt><dd>{value}</dd></div>)}</dl></section>
    <details className="local-ai__section"><summary>高级：查看具体路径与文件检查</summary>
      {scope.roots.length ? <ul className="local-ai__notes">{scope.roots.map((root, index) => <li key={index}>{root.source === 'COMMON' ? '常用目录' : '已配置目录'}：{root.path}</li>)}</ul> : <p>没有目录扫描。</p>}
      <p>递归目录共享上面的文件数与条目数限制；字节上限适用于单文件 / 单次读取。</p>
      <ul className="local-ai__notes">{scope.metadata_inspections.map((item, index) => <li key={index}>{scopeInspectionLabel(item.kind)}：{item.path} · 最多 {item.max_entries} 项，单文件 / 单次最多 {item.max_bytes} bytes</li>)}</ul>
    </details>
  </>;
}
function scopeHardwareLabel(key: string) {
  const labels: Record<string, string> = {OS_PLATFORM: '操作系统', CPU_ARCHITECTURE: 'CPU 架构', CPU_LOGICAL_COUNT: 'CPU 逻辑核心数', PHYSICAL_RAM: '物理内存', WINDOWS_DXGI_GPU_AND_VRAM: 'Windows GPU 与显存', WINDOWS_SYSTEM_CUDA_DIRECTML_COMPONENT_METADATA: 'Windows CUDA / DirectML 系统组件元数据'};
  return labels[key] || key;
}
function scopeInspectionLabel(key: string) {
  const labels: Record<string, string> = {CONFIGURED_GGUF_HEADER: '已配置 GGUF 文件头', REGISTERED_GGUF_HEADER: '已注册 GGUF 安全复查', EXECUTABLE_VERSION_RESOURCE: '已配置程序的版本元数据', EXECUTABLE_DIRECTORY_SIBLINGS: '已配置程序的同目录组件', RECURSIVE_MODEL_METADATA: '目录内模型元数据（有界递归）'};
  return labels[key] || key;
}
function scopeLimitLabel(key: string) {
  const labels: Record<string, string> = {planning_budget_seconds: '范围预览时间（秒）', scan_budget_seconds: '总时间（秒）', request_timeout_seconds: '单次请求（秒）', max_services: '服务数', max_models_per_service: '每项服务模型数', max_response_bytes: '响应大小（bytes）', max_roots: '目录数', max_entries: '目录条目数', max_files: '模型文件数', max_depth: '递归深度', max_metadata_bytes: '文件元数据（bytes）', max_metadata_read_bytes: '单次元数据读取（bytes）', max_executable_siblings: '程序同目录条目数', max_executable_version_bytes: '程序版本元数据（bytes）', max_windows_gpu_adapters: 'Windows GPU 数', max_registration_metadata_inspections: '已注册模型安全复查数', preview_ttl_seconds: '预览有效期（秒）'};
  return labels[key] || key;
}

function LocalAiDiscoveryContent({canMutate = false, onRegistryChange, v2, isCurrentOwner = () => true, ownerInvalidated = false, scopeRevision = 0}: DiscoveryProps & {v2?: LocalAiDiscoveryClient; isCurrentOwner?: () => boolean; ownerInvalidated?: boolean}) {
  const discovery = v2 || legacyDiscovery;
  const [snapshot, setSnapshot] = useState<LocalDiscoverySnapshot>();
  const [scan, setScan] = useState<LocalDiscoveryScan | null>(null);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [stateUncertain, setStateUncertain] = useState(false), [expired, setExpired] = useState(false), [collapsed, setCollapsed] = useState(false), [pollPaused, setPollPaused] = useState(false), [pollVersion, setPollVersion] = useState(0), [cancelRequested, setCancelRequested] = useState(false);
  const [roots, setRoots] = useState(''), [editRoots, setEditRoots] = useState(false);
  const [runtimeForm, setRuntimeForm] = useState<LocalRuntimeConfiguration>(), [runtimeId, setRuntimeId] = useState<string>();
  const [confirmation, setConfirmation] = useState<{kind: 'enable' | 'remove'; model: LocalModelRegistration}>();
  const [registrationForm, setRegistrationForm] = useState<{id: string; workflow_adapter_id: string; license_confirmed: boolean}>();
  const mounted = useRef(false), generation = useRef(0), pollGeneration = useRef(0), busyRef = useRef(false);
  const [previewOpen, setPreviewOpen] = useState(false), [scopePreview, setScopePreview] = useState<LocalAiScanScope>(), [includeCommon, setIncludeCommon] = useState(false), [previewBusy, setPreviewBusy] = useState(false);
  const previousScopeRevision = useRef(scopeRevision);
  const previewEpoch = useRef(0), previewController = useRef<AbortController>(), previewFlight = useRef(false);
  const permission = useRef(canMutate), previouslyMutable = useRef(canMutate), ownerDenied = useRef(false);
  if (v2 && previouslyMutable.current && !canMutate) ownerDenied.current = true;
  permission.current = canMutate;
  const isCurrent = () => mounted.current && isCurrentOwner() && (!v2 || !ownerDenied.current);
  const mutable = canMutate && !expired && !ownerDenied.current && isCurrentOwner();
  const scanning = activeScan(scan);
  const locked = !mutable || loading || !snapshot || stateUncertain || !!busy;

  function report(caught: unknown) {
    if (!isCurrent() || (caught instanceof Error && caught.name === 'AbortError')) return;
    if (caught instanceof ApiError && caught.problem.code !== 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE' && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code))) {
      setExpired(true); setPollPaused(true); setConfirmation(undefined); invalidatePreview();
      if (v2) ownerDenied.current = true;
      if (v2) {setSnapshot(undefined); setScan(null);}
      setError(v2 ? '后端主机授权已失效或权限不足，检测与接入操作已禁用。可继续手动创作。' : '受信任的桌面会话已失效或权限不足，本地 AI 操作已禁用。请重新连接桌面会话。');
    } else if (v2 && caught instanceof ApiError && caught.problem.code === 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE') {
      invalidatePreview(); ownerDenied.current = true; setExpired(true); setPollPaused(true); setSnapshot(undefined); setScan(null);
      setError('此后端未提供本地 AI 主机授权，无法检测主机环境。协作项目权限不能授权主机扫描；可继续手动创作。');
    } else if (v2 && caught instanceof ApiError && caught.problem.code.startsWith('LOCAL_AI_SCOPE_')) {
      invalidatePreview();
      setError('检测范围、预览时效或授权已变化。请重新预览并确认；未自动重试检测。');
    } else if (v2 && caught instanceof ApiError && caught.problem.code === 'EXPERIMENTAL_FEATURE_DISABLED') {
      invalidatePreview(); setExpired(true); setError('此后端尚未开启 V2 环境检测，可继续手动创作。');
    } else {
      const code = caught instanceof ApiError && /^[A-Z0-9_]{1,80}$/.test(caught.problem.code) ? `（${caught.problem.code}）` : '';
      setError(`本地 AI 操作未完成${code}。已有结果已保留，请重试。`);
    }
  }
  async function refresh(signal?: AbortSignal) {
    const current = ++generation.current;
    const result = await discovery.snapshot(signal);
    if (!isCurrent() || current !== generation.current) return;
    setSnapshot(result); setScan(result.scan); setRoots(result.settings.scan_roots.join('\n')); setLoading(false);
  }
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refresh(controller.signal).catch(caught => {if (controller.signal.aborted) return; report(caught); if (mounted.current && isCurrentOwner()) setLoading(false);});
    return () => {mounted.current = false; generation.current++; pollGeneration.current++; previewEpoch.current++; previewController.current?.abort(); controller.abort();};
  }, []);

  function invalidatePreview() {
    previewEpoch.current++; previewController.current?.abort(); previewFlight.current = false;
    setScopePreview(undefined); setPreviewBusy(false); setPreviewOpen(false);
  }
  useEffect(() => {
    if (!v2) return;
    if (previouslyMutable.current && !canMutate) {
      invalidatePreview(); generation.current++; pollGeneration.current++; setExpired(true); setPollPaused(true);
      setSnapshot(undefined); setScan(null); setConfirmation(undefined); setRuntimeForm(undefined); setRegistrationForm(undefined);
      setError(ownerInvalidated ? '项目或会话已改变，原检测确认已清除。请重新打开模型中心。' : '后端主机权限已撤回，检测与接入操作已禁用。可继续手动创作。');
    }
    previouslyMutable.current = canMutate;
  }, [canMutate, v2, ownerInvalidated]);
  useEffect(() => {
    if (v2 && previousScopeRevision.current !== scopeRevision) invalidatePreview();
    previousScopeRevision.current = scopeRevision;
  }, [scopeRevision, v2]);
  async function loadPreview(common: boolean, replacing = false) {
    if (!v2 || !isCurrent() || !permission.current || expired || scanning || runtimeForm || editRoots || busyRef.current || (previewFlight.current && !replacing)) return;
    previewController.current?.abort();
    const ticket = ++previewEpoch.current, controller = new AbortController();
    previewController.current = controller; previewFlight.current = true;
    setScopePreview(undefined); setIncludeCommon(common); setPreviewOpen(true); setPreviewBusy(true); setError('');
    try {
      const value = await v2.previewScope(common, controller.signal);
      if (isCurrent() && permission.current && !controller.signal.aborted && ticket === previewEpoch.current) setScopePreview(value);
    } catch (caught) {if (isCurrent() && permission.current && !controller.signal.aborted && ticket === previewEpoch.current) report(caught);}
    finally {if (isCurrent() && ticket === previewEpoch.current) {previewFlight.current = false; setPreviewBusy(false);}}
  }

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
        if (!isCurrent() || controller.signal.aborted || current !== pollGeneration.current) return;
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
      if (isCurrent() && !controller.signal.aborted && current === generation.current) setSnapshot(result);
    }).catch(caught => {if (!controller.signal.aborted && current === generation.current) report(caught);});
    return () => controller.abort();
  }, [scan?.id, scanning, expired]);

  async function recoverProtectedState() {
    const current = ++generation.current;
    try {
      const result = await discovery.snapshot();
      if (!isCurrent() || current !== generation.current) return;
      setSnapshot(result); setScan(result.scan); setStateUncertain(false);
      setConfirmation(undefined); setRegistrationForm(undefined);
      onRegistryChange?.();
    } catch (caught) {
      if (!isCurrent() || current !== generation.current) return;
      setStateUncertain(true);
      if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code))) report(caught);
      else setError(previous => `${previous} 状态重新读取失败，请重新读取后再操作。`.trim());
    }
  }
  async function run(key: string, task: () => Promise<void>, recoverOnFailure = false) {
    if (!mutable || (v2 && (!permission.current || !isCurrent())) || !snapshot || loading || busyRef.current || (scanning && key !== 'cancel') || (stateUncertain && key !== 'refresh-state')) return;
    if (v2) invalidatePreview();
    generation.current++; busyRef.current = true; setBusy(key); setError('');
    try {await task();} catch (caught) {
      report(caught);
      if (recoverOnFailure && isCurrent()) {
        // Validation can revoke a registration before a failed response arrives.
        // Never retain routing authority or an old license confirmation on error.
        setStateUncertain(true); setConfirmation(undefined); setRegistrationForm(undefined);
        if (!(caught instanceof ApiError && (caught.status === 401 || caught.status === 403 || AUTH_ERRORS.has(caught.problem.code)))) await recoverProtectedState();
      }
    } finally {busyRef.current = false; if (isCurrent()) setBusy('');}
  }
  async function scanAction(cancel = false, scope?: LocalAiScanScope) {
    if (v2 && !cancel && (!scope || scope !== scopePreview || !permission.current)) return;
    await run(cancel ? 'cancel' : 'scan', async () => {
      pollGeneration.current++; setPollPaused(true); setPollVersion(value => value + 1); generation.current++;
      try {
        const result = cancel && scan ? await discovery.cancelScan(scan.id) : v2 && scope ? await v2.confirmScan(scope.scope_digest) : await legacyDiscovery.scan();
        if (isCurrent()) {setScan(result); setCancelRequested(cancel && activeScan(result)); if (!v2) setCollapsed(false); setConfirmation(undefined);}
      } finally {if (isCurrent()) setPollPaused(false);}
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
        if (isCurrent()) {
          setScan(current => current ? {...current, candidates: current.candidates.map(item => item.id === result.id ? result : item)} : current);
          const registered = snapshot?.registrations.find(item => item.id === result.id || item.candidate_id === result.id);
          if (registered) updateRegistration({...registered, ...result, id: registered.id, enabled: false});
        }
      } else {
        const result = await discovery.register(model.id);
        if (isCurrent()) updateRegistration(result);
      }
    }, true);
  }
  async function registrationAction(model: LocalModelRegistration, action: 'enable' | 'disable' | 'remove') {
    await run(`${model.id}:${action}`, async () => {
      if (action === 'remove') {
        await discovery.remove(model.id);
        if (isCurrent()) {setSnapshot(current => current ? {...current, registrations: current.registrations.filter(item => item.id !== model.id)} : current); onRegistryChange?.();}
      } else {
        const result = await discovery[action](model.id);
        if (isCurrent()) updateRegistration(result);
      }
      if (isCurrent()) setConfirmation(undefined);
    }, true);
  }
  function editRuntime(runtime?: LocalRuntime) {
    if (v2) invalidatePreview();
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
    await run('runtime', async () => {await discovery.saveRuntime(runtimeForm, runtimeId); if (isCurrent()) {setRuntimeForm(undefined); await refresh();}}, true);
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

  return <Panel title="Local AI · 本地 AI 发现" className="local-ai" actions={<Button variant="ghost" onClick={() => {if (v2) invalidatePreview(); setCollapsed(value => !value);}} aria-expanded={!collapsed}>{collapsed ? '展开本地 AI' : !scan && !registrations.length ? '跳过 / 收起' : '收起'}</Button>}>
    {!collapsed && <div className="local-ai__body">
      <p>{v2 ? '先预览后端主机的检测范围，再明确确认。发现 → 验证 → 注册 → 确认启用；不会启动 Runtime 或加载模型。无需填写路径或端口即可查看已有配置。' : '只读检测本机 Runtime 和指定模型目录。发现 → 验证 → 注册 → 确认启用 → 按需启动；扫描不会启动 Runtime 或加载模型。'}</p>
      <p className="local-ai__muted">{v2 ? '范围仅限运行后端的主机（BACKEND_HOST），云端结果不代表你的电脑。未配置模型或跳过检测时，仍可手动创作。' : '扫描结果保留在本地，不上传路径、文件名或硬件信息到云 Provider；不会读取小说正文或私人文档。'}</p>
      {error && <StatusMessage tone="error">{error}</StatusMessage>}
      {snapshot?.persistence_error && <StatusMessage tone="warning">本地 AI 配置无法完整读取，请检查本地服务。已有模型文件不受影响。</StatusMessage>}
      {stateUncertain && <StatusMessage tone="warning">当前启用状态尚未确认；重新读取成功前，所有接入变更已暂时禁用。</StatusMessage>}
      {!mutable && !error && <StatusMessage tone="warning">{v2 ? '本地 AI 检测需要后端主机授权。未授权时可继续手动创作。' : '本地 AI 操作需要受信任的桌面会话。'}</StatusMessage>}
      <div className="local-ai__actions">
        <Button variant="primary" disabled={locked || scanning || previewBusy || (!!v2 && (!!runtimeForm || editRoots))} loading={busy === 'scan'} onClick={() => v2 ? void loadPreview(false) : void scanAction()}>{v2 ? scan ? '重新预览检测范围' : '预览 AI 检测范围' : scan ? '重新扫描' : '检测本机 AI 环境'}</Button>
        {scanning && <Button disabled={locked || cancelRequested} loading={busy === 'cancel'} onClick={() => void scanAction(true)}>{cancelRequested ? '正在取消扫描…' : '取消扫描'}</Button>}
        <Button disabled={controlsLocked} onClick={() => editRuntime()}>{v2 ? '高级：添加本地 Runtime' : '添加本地 Runtime'}</Button>
        <Button disabled={controlsLocked} onClick={() => {if (v2) invalidatePreview(); setEditRoots(value => !value);}}>{v2 ? '高级：配置扫描目录' : '配置扫描目录'}</Button>
        {stateUncertain && <Button disabled={!!busy || !mutable} onClick={() => void run('refresh-state', recoverProtectedState)}>重新读取状态</Button>}
        {!snapshot && !loading && <Button disabled={!!busy || expired} onClick={() => {setLoading(true); setError(''); void refresh().catch(caught => {report(caught); if (mounted.current && isCurrentOwner()) setLoading(false);});}}>重试读取</Button>}
      </div>
      {v2 && (!!runtimeForm || editRoots) && <p role="status">先保存或取消高级配置，再预览检测范围。</p>}
      {v2 && previewOpen && <section className="local-ai__confirmation" aria-label="确认后端主机检测范围">
        <h3>确认本次检测范围</h3>
        <label className="local-ai__check"><input type="checkbox" checked={includeCommon} disabled={!mutable || !!busy} onChange={event => void loadPreview(event.target.checked, true)}/>本次包含后端主机的常用模型目录（可选）</label>
        {previewBusy && <p role="status">正在读取有效范围，尚未开始检测…</p>}
        {scopePreview && <ScanScopeDetails scope={scopePreview}/>}
        <p>确认仅适用于当前范围和主机授权，预览短期有效；取消或更改范围后需重新确认。</p>
        <div className="local-ai__actions"><Button variant="primary" disabled={locked || scanning || previewBusy || !scopePreview} onClick={() => scopePreview && void scanAction(false, scopePreview)}>确认此范围并检测</Button><Button variant="ghost" onClick={invalidatePreview}>取消预览</Button></div>
      </section>}
      {loading && <p role="status">正在读取本地 AI 状态…</p>}
      {scan && <div className="local-ai__summary" role="status"><Badge tone={tone(scan.status)}>{scan.status}</Badge><span>发现 {candidates.length} 个模型 · 已注册 {registrations.length} 个 · {stateUncertain ? '启用状态待确认' : `已启用 ${registrations.filter(item => item.enabled).length} 个`} · {scan.runtimes.filter(item => item.status === 'RUNNING').length} 个 Runtime 可用 · {scan.errors.length} 个检测问题</span>{scanning && <span>{cancelRequested ? '已请求取消，等待当前只读探测结束…' : '扫描中，已显示当前部分结果…'}</span>}{scan.status === 'CANCELLED' && <span>扫描已取消，保留已发现结果。</span>}</div>}
      {!!scan?.errors.length && <StatusMessage tone="warning">部分检测未完成，不影响其他结果。{scan.errors.map((item, index) => <p key={index}>{typeof item === 'string' ? item : [item.runtime_id, item.code].filter(Boolean).join(' · ') || 'Runtime 检测未完成'}</p>)}</StatusMessage>}
      {editRoots && <form className="local-ai__form" aria-label="扫描目录配置" onSubmit={event => {event.preventDefault(); void run('roots', async () => {await discovery.settings(roots.split(/\r?\n/).map(value => value.trim()).filter(Boolean)); if (isCurrent()) {setEditRoots(false); await refresh();}}, true);}}>
        <label className="local-ai__wide">模型目录（每行一个完整路径）<textarea rows={4} value={roots} placeholder="D:\AI\models" onChange={event => {if (v2) invalidatePreview(); setRoots(event.target.value);}}/></label>
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
      {!!runtimeMap.size && <section className="local-ai__section" aria-label="发现的 Runtime"><h3>本地 Runtime（{runtimeMap.size}）</h3><div className="local-ai__list">{Array.from(runtimeMap.values()).map(runtime => <article key={runtime.id} aria-label={runtime.name || runtime.id}><header><strong>{runtime.name || runtime.id}</strong><Badge tone={tone(runtime.status || 'NOT_VERIFIED')}>{runtime.status || 'NOT_VERIFIED'}</Badge></header><p>{runtime.type || runtime.runtime_type} · {runtime.management || 'EXTERNAL'}</p><p>地址：{runtime.endpoint || '未配置'} · 版本：{runtime.version || '未检测'}</p><p>运行状态：{runtime.status === 'RUNNING' ? '正在运行' : runtime.status === 'NOT_FOUND' ? '未发现运行服务' : '未确认'}</p>{runtime.executable_exists !== undefined && <p>Executable：{runtime.executable_exists ? '已找到' : '未找到'} · CUDA：{runtime.cuda_status || '未验证'}</p>}{runtime.notes?.map((note, index) => <p key={index}>{note}{localAiDiagnostic(note) ? `：${localAiDiagnostic(note)}` : ''}</p>)}<Button disabled={controlsLocked} onClick={() => editRuntime(runtime)}>配置 Runtime</Button></article>)}</div></section>}
      {!loading && !models.length && (!v2 || !!snapshot) && <EmptyState title={scan ? '尚未发现模型' : '尚未开始扫描'} detail={v2 ? '未配置或未发现可用模型时，可继续手动创作。可先预览已有服务；自定义路径与端口仅用于高级配置。' : '可跳过检测，也可添加 Runtime 或模型目录后主动扫描。未安装的 Runtime 不影响应用使用。'}/>}
      {GROUPS.map(group => {const rows = models.filter(row => groupOf(row.model) === group); return rows.length ? <section className="local-ai__section" key={group} aria-label={group}><h3>{group}（{rows.length}）</h3><div className="local-ai__list">{rows.map(({model, registration}) => {const current = registration || model; return <article key={model.id} aria-label={`${model.display_name} ${model.local === false ? "非本地来源" : "本地模型"}`}>
        <header><strong>{model.display_name}</strong><Badge tone={stateUncertain ? 'warning' : tone(current.status)}>{stateUncertain ? 'NOT_VERIFIED' : current.status}</Badge></header>
        <div className="local-ai__actions"><Badge tone={model.local === false ? "warning" : "neutral"}>{model.local === false ? "云端或非本地来源 · 禁止本地路由" : "本地候选"}</Badge><Badge tone={stateUncertain ? 'warning' : registration?.enabled ? 'success' : 'neutral'}>{stateUncertain && registration ? '接入状态待确认' : registration?.enabled ? '已启用' : registration ? '已注册 · 未启用' : '候选 · 未注册'}</Badge><Badge tone={current.verified ? 'success' : 'warning'}>{current.verified ? '已通过实际生成验证' : '尚未实际生成验证'}</Badge></div>
        <dl className="local-ai__facts"><div><dt>Runtime / 来源</dt><dd>{model.runtime_type} · {model.runtime_id} · {model.source}</dd></div><div><dt>模型族 / 模型 ID</dt><dd>{model.family} · {model.model_id}</dd></div><div><dt>声明能力</dt><dd>{current.declared_capabilities.join(' · ') || 'UNKNOWN'}</dd></div><div><dt>已验证能力</dt><dd>{current.verified_capabilities.join(' · ') || 'CAPABILITY_UNVERIFIED'}</dd></div><div><dt>只读接入验证</dt><dd>{current.validated_at ? '已完成检查（不代表实际生成验证）' : '尚未验证 / 需重新验证'}</dd></div><div><dt>兼容性</dt><dd>{COMPATIBILITY[current.compatible] || current.compatible || 'Not Verified · 未验证'}</dd></div><div><dt>模型路径 / 文件 / 来源</dt><dd>{v2 ? <details><summary>高级：查看模型来源详情</summary>{model.local_path || model.model_name || model.source}</details> : model.local_path || model.model_name || model.source}</dd></div></dl>
        <ModelEvidence model={current}/>
        {!!current.validation_notes?.length && <ul className="local-ai__notes">{current.validation_notes.map((note, index) => <li key={index}>{note}{localAiDiagnostic(note) ? `：${localAiDiagnostic(note)}` : ''}</li>)}</ul>}
        {!!current.enable_blockers?.length && <section aria-label="启用前的诊断与下一步"><strong>启用前仍需：</strong><ul className="local-ai__notes">{current.enable_blockers.map(code => <li key={code}>{code}：{localAiDiagnostic(code) || '该检查尚未通过，请核对当前元数据并重新验证；不会自动修复环境。'}</li>)}</ul></section>}
        <div className="local-ai__actions">
          <Button disabled={controlsLocked} onClick={() => void candidateAction(model, 'validate')}>验证</Button>
          {!registration && <><Button disabled={controlsLocked || !model.validated_at} title={!model.validated_at ? '请先验证候选模型' : undefined} onClick={() => void candidateAction(model, 'register')}>注册</Button></>}
          {registration && <>{registration.enabled ? <Button disabled={controlsLocked} onClick={() => void registrationAction(registration, 'disable')}>停用</Button> : <Button disabled={controlsLocked || !registration.enable_eligible} onClick={() => setConfirmation({kind: 'enable', model: registration})}>启用</Button>}<Button disabled={controlsLocked} onClick={() => setRegistrationForm({id: registration.id, workflow_adapter_id: registration.workflow_adapter_id || '', license_confirmed: registration.license_confirmed ?? false})}>配置接入条件</Button><Button variant="ghost" disabled={controlsLocked} onClick={() => setConfirmation({kind: 'remove', model: registration})}>移除注册</Button></>}
        </div>
        {registrationForm?.id === registration?.id && registrationForm && <form className="local-ai__form" aria-label={`${model.display_name} 接入条件`} onSubmit={event => {event.preventDefault(); void run('registration-config', async () => {const result = await discovery.configureRegistration(registrationForm.id, {workflow_adapter_id: registrationForm.workflow_adapter_id, license_confirmed: registrationForm.license_confirmed}); if (isCurrent()) {updateRegistration(result); setRegistrationForm(undefined);}}, true);}}>
          <label className="local-ai__wide">Workflow Adapter<select value={registrationForm.workflow_adapter_id} onChange={event => setRegistrationForm({...registrationForm, workflow_adapter_id: event.target.value})}><option value="">未选择</option>{snapshot?.workflow_adapters?.map(adapter => <option value={adapter.id} key={adapter.id}>{adapter.display_name || adapter.id}{adapter.capability ? ` · ${adapter.capability}` : ''}</option>)}</select></label>
          <label className="local-ai__check local-ai__wide"><input type="checkbox" checked={registrationForm.license_confirmed} onChange={event => setRegistrationForm({...registrationForm, license_confirmed: event.target.checked})}/>我已核对该模型授权，允许在约定用途内使用</label><p className="local-ai__wide">发现模型不代表获得商业授权；勾选仅记录你的确认，不提供商业使用保证。无兼容工作流时仍无法启用。</p>
          <div className="local-ai__actions local-ai__wide"><Button type="submit" disabled={controlsLocked}>保存接入条件</Button><Button type="button" variant="ghost" onClick={() => setRegistrationForm(undefined)}>取消</Button></div>
        </form>}
        {confirmation?.model.id === registration?.id && confirmation && <section className="local-ai__confirmation" aria-label={confirmation.kind === 'enable' ? '确认启用模型' : '确认移除注册'}><p>{confirmation.kind === 'enable' ? `确认允许 ${model.display_name} 进入实际任务路由？启用不会立即加载模型或常驻显存。` : `移除 ${model.display_name} 的注册？只移除接入记录，不删除真实模型文件。`}</p><div className="local-ai__actions"><Button variant={confirmation.kind === 'enable' ? 'primary' : 'danger'} disabled={controlsLocked} onClick={() => void registrationAction(confirmation.model, confirmation.kind)}>{confirmation.kind === 'enable' ? '确认启用' : '确认移除注册'}</Button><Button variant="ghost" disabled={!!busy} onClick={() => setConfirmation(undefined)}>取消</Button></div></section>}
      </article>;})}</div></section> : null;})}
    </div>}
  </Panel>;
}
