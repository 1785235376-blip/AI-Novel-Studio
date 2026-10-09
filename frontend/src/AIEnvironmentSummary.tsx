import {useEffect, useState} from 'react';
import {ApiError} from './api';
import {localAiDiscoveryApi, type AIEnvironmentReport, type HardwareComponentEvidence} from './localAiDiscoveryApi';
import {Badge, Button, Panel, StatusMessage} from './ui/primitives';
import './AIEnvironmentSummary.css';

const statuses: Record<AIEnvironmentReport['status'], string> = {
  NOT_SCANNED: '尚未检测', RUNNING: '检测中', COMPLETED: '检测结束', PARTIAL: '部分结果', CANCELLED: '已取消',
};
const memory = (bytes: number | null) => bytes === null ? '未确认' : `${(bytes / 1024 ** 3).toFixed(1)} GiB`;
const component = (value: HardwareComponentEvidence) => value.status === 'COMPONENT_FOUND_NOT_VERIFIED'
  ? '发现组件，未实测' : value.status === 'NOT_FOUND' ? '未发现系统组件' : '未确认';
const failure = (error: unknown) => error instanceof ApiError && ['SESSION_REQUIRED', 'INVALID_SESSION', 'FORBIDDEN'].includes(error.problem.code)
  ? '需要有效的主机授权会话。请到模型中心重新连接。'
  : error instanceof ApiError && error.problem.code === 'EXPERIMENTAL_FEATURE_DISABLED'
    ? '此主机尚未开启 V2 环境检测。'
    : '暂时无法读取环境结果。可重新读取或到模型中心查看。';

/** Read-only inspector summary. Detect/Validate/Register/Enable stay in Model Center. */
export function AIEnvironmentSummary({enabled, onOpenModels}: {enabled: boolean; onOpenModels: () => void}) {
  const [report, setReport] = useState<AIEnvironmentReport>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setReport(undefined); setError('');
    if (!enabled) { setLoading(false); return; }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const read = async () => {
      try {
        const value = await localAiDiscoveryApi.environment(controller.signal);
        if (!alive) return;
        setReport(value); setLoading(false);
        if (value.status === 'RUNNING') timer = setTimeout(() => { void read(); }, 1500);
      } catch (caught) {
        if (!alive) return;
        setReport(undefined); setLoading(false); setError(failure(caught));
      }
    };
    setLoading(true); void read();
    return () => { alive = false; controller.abort(); if (timer) clearTimeout(timer); };
  }, [enabled, revision]);
  if (!enabled) return null;
  const status = report?.status ?? 'NOT_SCANNED';
  return <Panel title="本地 AI 环境" className="ai-environment-summary" aria-label="本地 AI 环境摘要"
    actions={<Badge tone={status === 'PARTIAL' ? 'warning' : 'neutral'}>{loading ? '读取中' : statuses[status]}</Badge>}>
    <p className="ai-environment-summary__note">仅检测运行后端的主机；云端结果不代表你的电脑。</p>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    {!loading && !error && report?.status === 'NOT_SCANNED' && <p role="status">到模型中心点击检测，即可查找已有服务和常用模型目录。</p>}
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
      <Button type="button" variant="ghost" disabled={loading} onClick={() => setRevision(value => value + 1)}>重新读取</Button>
    </div>
  </Panel>;
}
