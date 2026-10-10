import {useEffect, useRef, useState} from 'react';
import {ApiError} from './api';
import {localAiDiscoveryApi, type AIEnvironmentReport, type HardwareComponentEvidence, type LocalAiDiscoveryClient} from './localAiDiscoveryApi';
import {Badge, Button, Panel, StatusMessage} from './ui/primitives';
import './AIEnvironmentSummary.css';
import {useLocalAiDiscoveryOwner, useLocalAiOwnerKey, type LocalAiOnboardingOwner} from './localAiDiscoveryOwner';

const statuses: Record<AIEnvironmentReport['status'], string> = {
  NOT_SCANNED: '尚未检测', RUNNING: '检测中', COMPLETED: '检测结束', PARTIAL: '部分结果', CANCELLED: '已取消',
};
const memory = (bytes: number | null) => bytes === null ? '未确认' : `${(bytes / 1024 ** 3).toFixed(1)} GiB`;
const component = (value: HardwareComponentEvidence) => value.status === 'COMPONENT_FOUND_NOT_VERIFIED'
  ? '发现组件，未实测' : value.status === 'NOT_FOUND' ? '未发现系统组件' : '未确认';
const failure = (error: unknown) => error instanceof ApiError && error.problem.code === 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE'
  ? '此后端未提供本地 AI 主机授权，无法读取主机环境；可继续手动创作。'
  : error instanceof ApiError && ['SESSION_REQUIRED', 'INVALID_SESSION', 'FORBIDDEN'].includes(error.problem.code)
  ? '需要有效的主机授权会话。请到模型中心重新连接。'
  : error instanceof ApiError && error.problem.code === 'EXPERIMENTAL_FEATURE_DISABLED'
    ? '此主机尚未开启 V2 环境检测。'
    : '暂时无法读取环境结果。可重新读取或到模型中心查看。';

/** Read-only inspector summary. Detect/Validate/Register/Enable stay in Model Center. */
type SummaryProps = {enabled: boolean; onOpenModels: () => void; onboarding?: LocalAiOnboardingOwner};
export function AIEnvironmentSummary(props: SummaryProps) {
  return props.onboarding ? <OwnedEnvironmentSummary {...props} onboarding={props.onboarding}/> : <EnvironmentSummaryContent {...props}/>;
}
function OwnedEnvironmentSummary(props: SummaryProps & {onboarding: LocalAiOnboardingOwner}) {
  const ownerKey = useLocalAiOwnerKey(props.onboarding);
  return <EnvironmentSummaryOwner key={ownerKey} {...props}/>;
}
function EnvironmentSummaryOwner(props: SummaryProps & {onboarding: LocalAiOnboardingOwner}) {
  const owner = useLocalAiDiscoveryOwner(props.onboarding);
  return <EnvironmentSummaryContent {...props} client={owner.client} currentOwner={owner.current} ownerInvalidated={owner.invalidated}/>;
}
function EnvironmentSummaryContent({enabled, onOpenModels, client, currentOwner, ownerInvalidated}: SummaryProps & {client?: LocalAiDiscoveryClient; currentOwner?: () => boolean; ownerInvalidated?: boolean}) {
  const [report, setReport] = useState<AIEnvironmentReport>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const denied = useRef(false);
  useEffect(() => {
    setReport(undefined); setError('');
    if (!enabled) { setLoading(false); return; }
    if (ownerInvalidated || (currentOwner && !currentOwner())) {setLoading(false); setError('项目或会话已改变，旧环境结果已清除。请重新打开模型中心。'); return;}
    if (client && denied.current) {setLoading(false); setError('主机授权已失效，旧环境结果已清除。请核对授权后重新打开。'); return;}
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const read = async () => {
      try {
        const value = await (client || localAiDiscoveryApi).environment(controller.signal);
        if (!alive || (currentOwner && !currentOwner())) return;
        setReport(value); setLoading(false);
        if (value.status === 'RUNNING') timer = setTimeout(() => { void read(); }, 1500);
      } catch (caught) {
        if (!alive || (currentOwner && !currentOwner())) return;
        if (client && caught instanceof ApiError && ([401, 403].includes(caught.status) || caught.problem.code === 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE')) denied.current = true;
        setReport(undefined); setLoading(false); setError(failure(caught));
      }
    };
    setLoading(true); void read();
    return () => { alive = false; controller.abort(); if (timer) clearTimeout(timer); };
  }, [enabled, revision, client, currentOwner, ownerInvalidated]);
  if (!enabled) return null;
  const status = report?.status ?? 'NOT_SCANNED';
  return <Panel title="本地 AI 环境" className="ai-environment-summary" aria-label="本地 AI 环境摘要"
    actions={<Badge tone={status === 'PARTIAL' ? 'warning' : 'neutral'}>{loading ? '读取中' : statuses[status]}</Badge>}>
    <p className="ai-environment-summary__note">仅检测运行后端的主机；云端结果不代表你的电脑。</p>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {!loading && !error && report?.status === 'NOT_SCANNED' && <p role="status">到模型中心先预览检测范围，再确认查找已有服务；常用模型目录需明确选择。</p>}
    {report && report.status !== 'NOT_SCANNED' && <div aria-live="polite">
      <dl className="ai-environment-summary__facts">
        <div><dt>CPU</dt><dd>{report.hardware.cpu === 'NOT_VERIFIED' ? '未确认' : report.hardware.cpu}</dd></div>
        <div><dt>内存</dt><dd>{memory(report.hardware.ram_bytes)}</dd></div>
        <div><dt>GPU / 显存</dt><dd>{report.hardware.gpus.length ? report.hardware.gpus.map(gpu => `${gpu.name} · ${memory(gpu.dedicated_vram_bytes)}`).join('；') : '未确认'}</dd></div>
        <div><dt>CUDA</dt><dd>{component(report.hardware.cuda)}</dd></div>
        <div><dt>DirectML</dt><dd>{component(report.hardware.directml)}</dd></div>
        <div><dt>检测结果</dt><dd>{report.services.filter(service => service.status === 'RUNNING').length} 个服务可访问 · {report.model_files.length} 个模型文件</dd></div>
      </dl>
      {report.services.length > 0 && <ul className="ai-environment-summary__services">{report.services.map(service => <li key={service.id}>
        <span>{service.name}</span><span>{service.status === 'RUNNING' ? `可访问 · ${service.available_models.length} 个模型` : service.status === 'DISCOVERED' ? '发现文件，服务未运行' : '未检测到运行服务'}</span>
      </li>)}</ul>}
      {report.status === 'PARTIAL' && <p className="ai-environment-summary__note">部分服务或目录尚未确认，已保留其余结果。</p>}
      {report.status === 'CANCELLED' && <p className="ai-environment-summary__note">检测已取消，仅显示取消前的结果。</p>}
    </div>}
    <p className="ai-environment-summary__note">真实推理：NOT_RUN。Windows 实机验收：NOT_RUN。发现模型不会自动启用或加载。</p>
    <div className="ai-environment-summary__actions">
      <Button type="button" onClick={onOpenModels}>打开模型中心</Button>
      <Button type="button" variant="ghost" disabled={loading || (!!client && (denied.current || !!ownerInvalidated))} onClick={() => setRevision(value => value + 1)}>重新读取</Button>
    </div>
  </Panel>;
}
