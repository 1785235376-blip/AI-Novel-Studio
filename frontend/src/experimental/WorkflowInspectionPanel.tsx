import { useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import type { ExperimentalClient } from './api';
import { Details, ErrorMessage, Field, ResourceState, useResource } from './shared';

const base = '/local-ai/workflow-inspections';
const MAX_BYTES = 512 * 1024;
type Summary = { schema: string; inspection_version: number; execution_policy: 'DENY_ALL'; status: string; verification: string; real_runtime: string; real_model: string; counts: { nodes: number; edges: number; model_components: number; output_candidates: number; bytes: number; issues: Record<string, number> }; issue_codes: string[]; raw_workflow_included: false; literal_values_included: false; host_inventory_included: false; uploaded: false };
type Metadata = { runtimes: { id: string; label: string; observed_status: string; version: string | null }[]; snapshot_state: string; observed_at: string | null; limits: { nodes: number }; official_sources: { label: string; url: string }[] };
type Report = Summary & { nodes: { ref: string; class_type: string; registry_status: string; inputs: { ref: string; name: string; kind: string; source?: string; output_slot?: number }[] }[]; edges: unknown[]; model_components: { node: string; field: string; reference: string; status: string }[]; outputs: unknown[]; issues: { code: string; severity: string; node?: string; input?: string }[]; adapters: { id: string; source: string; state: string; imported_graph_bound: false }[]; declared_alias: { label: string | null; verification: string }; snapshot: { state: string; observed_at: string | null; runtime_version: string | null }; export_summary: Summary };
type Saved = { id: string; version: number; created_at: string; summary: Summary };
const explanations: Record<string, string> = {
  RUNTIME_SNAPSHOT_REQUIRED: '未选择已扫描的 ComfyUI。可先做结构检查，或到模型中心手动扫描后刷新。',
  RUNTIME_NOT_AVAILABLE_IN_SNAPSHOT: '上次扫描未发现可用运行时；请在现有环境自行启动后重新扫描。',
  DISCOVERY_SNAPSHOT_INCOMPLETE: '扫描尚未完成或没有扫描记录。这里不会启动扫描。',
  NODE_CATALOG_NOT_CAPTURED: '没有可用节点目录，节点存在性未知。',
  NODE_NOT_LISTED: '该节点未出现在所选运行时的有限快照中；请核对节点版本。',
  NODE_IMPLEMENTATION_UNKNOWN: '节点实现未知；节点名称或目录存在都不能证明代码安全。',
  MODEL_COMPONENT_NOT_LISTED: '模型组件与加载节点/字段的精确组合未被枚举；请核对已有模型与映射。',
  MODEL_COMPONENT_UNKNOWN: '没有足够模型元数据；不会检查磁盘或下载模型。',
  CREDENTIAL_MATERIAL: '检测到疑似密钥字段或凭据。请从原文件移除后重检。值不会写入报告。',
  CODE_EXECUTION_NODE: '节点名称提示代码执行能力，必须独立审核。',
  CODE_INPUT: '输入字段提示代码/命令，必须独立审核。',
  NETWORK_NODE: '节点名称提示外联能力，必须独立审核。',
  NETWORK_REFERENCE: '文件包含网络引用，检查器不会访问。',
  FILESYSTEM_REFERENCE: '文件包含本地/网络路径引用，检查器不会读取。',
  FILE_IO_NODE: '节点名称提示文件读写；需要另行审核目标与范围。',
  LINK_SOURCE_MISSING: '连接引用不存在的节点，请修正导出的 API 工作流。',
  LINK_SLOT_INVALID: '输出端口编号无效，请在 ComfyUI 核对连接。',
  WORKFLOW_CYCLE: '检测到循环连接，不能作为有效的有向无环 API 图。',
  NODE_INPUT_OUTPUT_SCHEMA_NOT_CAPTURED: '已有发现快照未保存完整端口类型；这里不能证明类型/必填输入兼容。',
  INPUT_LITERAL_SCHEMA_UNVERIFIED: '复合输入的类型尚未验证。',
  OUTPUT_MAPPING_UNVERIFIED: '没有识别到标准图像输出节点；自定义输出契约尚未验证。',
  SNAPSHOT_IS_NOT_LIVE_VALIDATION: '结果使用已有快照，不代表运行时此刻在线或版本未变。',
  LICENSE_REVIEW_REQUIRED: '模型许可尚未确认，请在模型中心独立审核使用许可。',
  LICENSE_SCOPE_NOT_BOUND_TO_IMPORTED_GRAPH: '已有许可确认不能代替对该导入工作流及所有组件的许可审核。',
  HARDWARE_MEMORY_NOT_ESTIMATED: '未运行硬件或显存测量，不提供虚构的 8GB/桌面性能档位。',
  IMPORTED_GRAPH_HAS_NO_REVIEWED_ADAPTER: '导入图未绑定经过审核的精确 Adapter。需要节点名称齐全仍不能执行。',
};

function download(summary: Summary) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = 'local-ai-inspection-summary.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function WorkflowInspectionPanel({ client }: { client: ExperimentalClient }) {
  const meta = useResource(signal => client.get<Metadata>(base, signal), [client]);
  const saved = useResource(signal => client.get<{ items: Saved[] }>(base + '/reports', signal), [client]);
  const [text, setText] = useState(''), [runtime, setRuntime] = useState(''), [alias, setAlias] = useState('');
  const [report, setReport] = useState<Report>(), [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState(''), [inputError, setInputError] = useState(''), [busy, setBusy] = useState(false);
  const epoch = useRef(0), active = useRef(true), running = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; epoch.current += 1; }; }, []);
  useEffect(() => { epoch.current += 1; setReport(undefined); setError(undefined); setNotice(''); setText(''); setRuntime(''); setAlias(''); setBusy(false); running.current = false; }, [client]);
  const invalidate = () => { epoch.current += 1; setReport(undefined); setNotice(''); setError(undefined); setInputError(''); setBusy(false); running.current = false; };
  const importFile = async (file?: File) => {
    invalidate(); if (!file) return;
    const ticket = epoch.current;
    if (file.size > MAX_BYTES) { setInputError('文件超过 512 KiB；请导出更小的 API 工作流。'); return; }
    setBusy(true);
    try { const content = await file.text(); if (active.current && ticket === epoch.current) setText(content); }
    catch { if (active.current && ticket === epoch.current) setInputError('文件读取失败，请重新选择或粘贴文本。'); }
    finally { if (active.current && ticket === epoch.current) setBusy(false); }
  };
  const inspect = async (persist = false) => {
    if (running.current || !text.trim()) return;
    if (new TextEncoder().encode(text).byteLength > MAX_BYTES) { setInputError('工作流超过 512 KiB；请缩小输入。'); return; }
    running.current = true; setBusy(true); setError(undefined); setNotice(''); setInputError('');
    const ticket = epoch.current;
    try {
      const body = { workflow_json: text, runtime_id: runtime, declared_alias: alias };
      if (persist) {
        await client.post<Saved>(base + '/reports', body);
        if (active.current && ticket === epoch.current) { saved.reload(); setNotice('已保存重新检查后的脱敏摘要，未保存工作流或输入值。'); }
      } else {
        const value = await client.post<Report>(base + '/inspect', body);
        if (active.current && ticket === epoch.current) setReport(value);
      }
    } catch (failure) { if (active.current && ticket === epoch.current) setError(failure); }
    finally { if (active.current && ticket === epoch.current) { running.current = false; setBusy(false); } }
  };
  return <Panel title="Local AI 工作流检查器">
    <StatusMessage>只读检查用户导出的 ComfyUI API JSON，使用已有发现快照。DENY_ALL：不会执行工作流、联网、安装节点、下载模型或修改现有运行时。</StatusMessage>
    <ResourceState loading={meta.loading} error={meta.error} />
    <div className="experimental-actions"><Badge>快照：{meta.data?.snapshot_state || '未知'}</Badge><Button disabled={busy} onClick={() => { invalidate(); meta.reload(); saved.reload(); }}>刷新已有快照</Button></div>
    <p>缺少运行时或模型时仍可做结构检查。需要新元数据时，请到主控设置 → 模型中心 → Local AI 显式扫描。</p>
    <Field label="ComfyUI 运行时快照"><select value={runtime} disabled={busy || !!meta.error} onChange={event => { invalidate(); setRuntime(event.target.value); }}><option value="">仅结构检查（不读取运行时节点目录）</option>{meta.data?.runtimes.map(item => <option key={item.id} value={item.id}>{item.label} · {item.observed_status} · {item.version || '版本未知'}</option>)}</select></Field>
    <Field label="用户称呼 / 别名（可选）"><input value={alias} maxLength={100} onChange={event => { invalidate(); setAlias(event.target.value); }} /></Field>
    <Field label="导入 ComfyUI API JSON 文件"><input type="file" accept=".json,application/json" onChange={event => void importFile(event.target.files?.[0])} /></Field>
    <Field label="ComfyUI API 工作流 JSON"><textarea value={text} placeholder="粘贴导出的 API 节点图或含 prompt 的 API 请求" onChange={event => { invalidate(); setText(event.target.value); }} /></Field>
    <p>原始 JSON 会发送给本应用的服务端作检查，不会发送给 ComfyUI 或模型。请先移除密钥、私人路径和不需要的提示词。报告只显示连接与脱敏字段。</p>
    <div className="experimental-actions"><Button disabled={!text.trim() || busy || !!meta.error} loading={busy} onClick={() => void inspect()}>检查工作流</Button><Button disabled={!text && !report && !busy} onClick={() => { invalidate(); setText(''); }}>清除输入与结果</Button></div>
    {busy && <StatusMessage>正在读取或检查…</StatusMessage>}{inputError && <StatusMessage tone="error">{inputError}</StatusMessage>}{!!error && <ErrorMessage error={error} />}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {!report && !busy && <EmptyState title="尚无检查结果" detail="导入 API 工作流后点击检查；失败时输入会保留，可修改后重试。" />}
    {report && <section className="experimental-section" aria-label="工作流检查结果">
      <div className="experimental-actions"><Badge tone="warning">{report.status}</Badge><Badge>DENY_ALL</Badge><Badge>模型 / GPU：NOT_RUN</Badge></div>
      <p>{report.counts.nodes} 个节点，{report.counts.edges} 条连接，{report.counts.model_components} 个模型组件。结构通过、元数据存在和实际可运行是不同证据。</p>
      {report.declared_alias.label && <p>用户别名：{report.declared_alias.label} · USER_DECLARED_NOT_VERIFIED</p>}
      <div className="experimental-list">{report.issues.map((item, index) => <div className="experimental-record" key={index}><strong>{item.severity} · {item.code}{item.node ? ` · ${item.node}` : ''}</strong><p>{explanations[item.code] || '该项尚未验证，请检查原工作流与已有环境。'}</p></div>)}</div>
      <Details label="节点与输入 / 输出连接映射（值已隐藏）" value={{ nodes: report.nodes, edges: report.edges, outputs: report.outputs }} />
      <Details label="模型组件与已有快照" value={report.model_components} />
      <Details label="既有 Adapter 对照（不授权导入图执行）" value={report.adapters} />
      <Details label="可导出摘要预览（不含路径 / 提示词 / 密钥 / 主机信息）" value={report.export_summary} />
      <div className="experimental-actions"><Button disabled={busy} onClick={() => download(report.export_summary)}>下载脱敏摘要</Button><Button disabled={busy || !!meta.error} onClick={() => void inspect(true)}>重新检查并保存脱敏摘要</Button></div>
    </section>}
    <section className="experimental-section" aria-label="已保存检查摘要"><h3>已保存检查摘要</h3><ResourceState loading={saved.loading} error={saved.error} empty={saved.data?.items.length === 0} />{!saved.error && saved.data?.items.map(item => <article className="experimental-record" key={item.id}><span>{item.created_at} · v{item.version} · {item.summary.status}</span><p>历史检查结果，不代表当前环境。原工作流未保留，重新检查需再次导入。</p><Button onClick={() => download(item.summary)}>下载历史脱敏摘要</Button></article>)}</section>
    <p><a href="https://docs.comfy.org/development/comfyui-server/comms_routes" target="_blank" rel="noreferrer">ComfyUI 官方 API 路由说明</a></p>
  </Panel>;
}
