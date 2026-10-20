import {useMemo, useState} from 'react';
import type {LocalDiscoveryScan, WorkflowPrerequisiteEvidence, WorkflowPrerequisiteObservation, WorkflowPrerequisiteReport} from '../localAiDiscoveryApi';
import {Badge, Button, StatusMessage} from './primitives';

const PAGE_SIZE = 20;
const OBSERVATION: Record<WorkflowPrerequisiteObservation, string> = {
  observed: '已观察到（observed）', not_observed: '本次未观察到（not_observed）', unknown: '未知（unknown）',
};
const EVIDENCE: Record<WorkflowPrerequisiteEvidence['evidence_status'], string> = {
  COMPLETE: '有界响应已检查（COMPLETE）', UNAVAILABLE: '响应不可用（UNAVAILABLE）',
  MALFORMED: '响应无法解析（MALFORMED）', BOUNDED: '达到观察上限（BOUNDED）',
  CANCELLED: '观察已取消（CANCELLED）', NOT_SCANNED: '尚未观察（NOT_SCANNED）',
};
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const string = (value: unknown, max = 256): value is string => typeof value === 'string' && value.trim().length > 0
  && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
const observation = (value: unknown): value is WorkflowPrerequisiteObservation => value === 'observed' || value === 'not_observed' || value === 'unknown';
const bounded = (value: unknown, max: number, check: (item: unknown) => boolean): value is unknown[] => Array.isArray(value) && value.length <= max && value.every(check);
const unverified = (value: Record<string, unknown>) => value.metadata_status === 'NOT_VERIFIED' && value.inference_status === 'NOT_RUN';

/** Validate optional display evidence, not readiness. Unknown versions, incomplete
 * shapes, oversized results and another scan's evidence cannot make assertions. */
function currentReport(value: unknown, scan: LocalDiscoveryScan): WorkflowPrerequisiteReport | undefined {
  if (!record(value) || value.schema_version !== 1 || !string(value.scan_id, 64) || value.scan_id !== scan.id || value.scan_status !== scan.status
    || !['RUNNING', 'COMPLETED', 'PARTIAL', 'CANCELLED'].includes(String(value.scan_status))
    || !['COMPLETE', 'BOUNDED', 'MALFORMED'].includes(String(value.definition_status))
    || !bounded(value.workflows, 320, item => {
      if (!record(item) || !string(item.runtime_id) || !string(item.adapter_id, 100) || !string(item.display_name)
        || typeof item.evidence_status !== 'string' || !Object.hasOwn(EVIDENCE, item.evidence_status) || !unverified(item)
        || !bounded(item.nodes, 64, node => record(node) && string(node.node_class) && observation(node.observation))
        || !record(item.loader)) return false;
      const loader = item.loader;
      return string(loader.node_class) && string(loader.input_field) && observation(loader.observation)
        && (loader.advertised_count === null || (typeof loader.advertised_count === 'number' && Number.isSafeInteger(loader.advertised_count) && loader.advertised_count >= 0 && loader.advertised_count <= 512))
        && bounded(loader.candidate_ids, 512, id => string(id));
    })
    || !bounded(value.components, 512, item => record(item) && string(item.model_id) && string(item.model_display_name)
      && string(item.component_id) && (item.component_type === null || string(item.component_type))
      && item.observation === 'unknown' && ['NO_COMPONENT_IDENTITY_EVIDENCE', 'COMPONENT_DEFINITION_UNAVAILABLE'].includes(String(item.reason)) && unverified(item))) return undefined;
  const report = value as unknown as WorkflowPrerequisiteReport;
  if (new Set(report.workflows.map(row => JSON.stringify([row.runtime_id, row.adapter_id]))).size !== report.workflows.length
    || new Set(report.components.map(row => JSON.stringify([row.model_id, row.component_id]))).size !== report.components.length) return undefined;
  for (const row of report.workflows) {
    const loader = row.loader, classes = new Set(row.nodes.map(node => node.node_class));
    if (classes.size !== row.nodes.length || !classes.has(loader.node_class)
      || new Set(loader.candidate_ids).size !== loader.candidate_ids.length
      || (loader.observation === 'observed' && (!(loader.advertised_count !== null && loader.advertised_count > 0)
        || row.nodes.find(node => node.node_class === loader.node_class)?.observation !== 'observed'))
      || (loader.observation === 'not_observed' && (loader.advertised_count !== 0 || loader.candidate_ids.length > 0))
      || (loader.observation === 'unknown' && (loader.advertised_count !== null || loader.candidate_ids.length > 0))) return undefined;
  }
  return report;
}

function ObservationPages({count, requestedPage, onPage, label}: {count: number; requestedPage: number; onPage: (page: number) => void; label: string}) {
  const pages = Math.ceil(count / PAGE_SIZE), page = Math.min(requestedPage, pages - 1);
  return <div className="local-ai__summary"><span>{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, count)} / {count} 条{label}</span>{pages > 1 && <>
    <Button disabled={page === 0} onClick={() => onPage(page - 1)}>上一页{label}</Button>
    <Button disabled={page === pages - 1} onClick={() => onPage(page + 1)}>下一页{label}</Button>
  </>}</div>;
}

/** Pure, paged consumer of the existing owner's current scan. It never fetches,
 * probes, enables, installs or changes registry/routing/generation authority. */
export function LocalAiWorkflowPrerequisites({scan, stateUncertain}: {scan: LocalDiscoveryScan; stateUncertain: boolean}) {
  const [workflowPage, setWorkflowPage] = useState(0), [componentPage, setComponentPage] = useState(0);
  const candidateIds = useMemo(() => new Set(scan.candidates.filter(candidate => candidate.runtime_type === 'COMFYUI')
    .map(candidate => JSON.stringify([candidate.runtime_id, candidate.id]))), [scan.candidates]);
  const runningRuntimeIds = useMemo(() => {
    const counts = new Map<string, number>();
    for (const runtime of scan.runtimes) counts.set(runtime.id, (counts.get(runtime.id) || 0) + 1);
    return new Set(scan.runtimes.filter(runtime => counts.get(runtime.id) === 1
      && (runtime.type || runtime.runtime_type) === 'COMFYUI' && runtime.status === 'RUNNING').map(runtime => runtime.id));
  }, [scan.runtimes]);
  const raw = scan.workflow_prerequisites, report = currentReport(raw, scan);
  const workflows = report?.workflows || [], components = report?.components || [];
  const workflowOffset = Math.min(workflowPage, Math.max(0, Math.ceil(workflows.length / PAGE_SIZE) - 1)) * PAGE_SIZE;
  const componentOffset = Math.min(componentPage, Math.max(0, Math.ceil(components.length / PAGE_SIZE) - 1)) * PAGE_SIZE;
  return <section className="local-ai__section" aria-label="本次扫描的工作流前置条件观察">
    <h3>工作流前置条件观察</h3>
    <p>仅展示本次后端主机扫描已有的节点与加载器广告信息。本次未观察到不等于未安装；已观察到不代表权重完整、组件兼容或模型可运行。</p>
    <p className="local-ai__muted">元数据验证：NOT_VERIFIED · 实际生成：NOT_RUN。查看、展开与翻页不会发起检测或生成，也不会改变模型接入状态。</p>
    {raw == null ? <p>本次扫描未提供工作流前置条件观察，节点与组件状态仍未知。</p> : !report ? <StatusMessage tone="warning">观察数据无法确认：版本、扫描身份、状态或数据格式不匹配，前置条件仍未知。</StatusMessage> : <>
      {stateUncertain && <StatusMessage tone="warning">状态待重新确认，工作流观察暂按未知显示；请使用已有的重新读取状态操作。</StatusMessage>}
      {report.scan_status === 'RUNNING' && <p role="status">扫描尚未结束，当前观察仅覆盖已返回的范围。</p>}
      {report.scan_status === 'PARTIAL' && <StatusMessage tone="warning">本次扫描部分未完成；单个服务的已检查响应不代表全部前置条件已确认。</StatusMessage>}
      {report.scan_status === 'CANCELLED' && <StatusMessage tone="warning">扫描已取消，节点与加载器观察均按未知显示。</StatusMessage>}
      {report.definition_status !== 'COMPLETE' && <StatusMessage tone="warning">需求定义范围未完整确认（{report.definition_status}），未列出的条件仍未知。</StatusMessage>}
      {!workflows.length ? <p>本次没有可显示的工作流观察；不能推断没有前置条件，也不能据此判断模型已完整安装。</p> : <>
        <ObservationPages count={workflows.length} requestedPage={workflowPage} onPage={setWorkflowPage} label="工作流观察"/>
        <div className="local-ai__list">{workflows.slice(workflowOffset, workflowOffset + PAGE_SIZE).map((workflow, index) => {
          const runtimeConfirmed = runningRuntimeIds.has(workflow.runtime_id);
          const trusted = !stateUncertain && scan.status !== 'CANCELLED' && runtimeConfirmed && workflow.evidence_status === 'COMPLETE';
          const loaderObservation = trusted ? workflow.loader.observation : 'unknown';
          const linked = trusted && loaderObservation === 'observed' ? [...new Set(workflow.loader.candidate_ids)].filter(id => candidateIds.has(JSON.stringify([workflow.runtime_id, id]))) : [];
          const missing = trusted && loaderObservation === 'observed' && linked.length !== new Set(workflow.loader.candidate_ids).size;
          return <article key={`${workflow.runtime_id}:${workflow.adapter_id}:${index}`} aria-label={`${workflow.display_name} 工作流观察`}>
            <header className="local-ai__actions"><strong>{workflow.display_name}</strong><Badge tone={trusted ? 'neutral' : 'warning'}>{stateUncertain || !runtimeConfirmed ? '观察状态未知' : scan.status === 'CANCELLED' ? EVIDENCE.CANCELLED : EVIDENCE[workflow.evidence_status]}</Badge></header>
            <p>Runtime：{workflow.runtime_id} · Adapter：{workflow.adapter_id}</p>
            {!runtimeConfirmed && <p className="local-ai__muted">Runtime 身份或运行状态未在本次扫描中确认，节点与加载器观察均按未知显示。</p>}
            <p>元数据验证：NOT_VERIFIED · 实际生成：NOT_RUN</p>
            <details><summary>查看所需节点（{workflow.nodes.length}）</summary>
              {workflow.nodes.length ? <ul className="local-ai__notes">{workflow.nodes.map((node, nodeIndex) => <li key={nodeIndex}>{node.node_class} · {OBSERVATION[trusted ? node.observation : 'unknown']}</li>)}</ul> : <p>没有可显示的节点定义；节点要求仍未知。</p>}
            </details>
            <p>加载器：{workflow.loader.node_class}.{workflow.loader.input_field} · {OBSERVATION[loaderObservation]}</p>
            <p>服务广告条目：{loaderObservation === 'unknown' ? '未知' : workflow.loader.advertised_count ?? '未知'}；广告信息不验证模型文件。</p>
            {trusted && loaderObservation === 'observed' && <p>可对应同次 Runtime 候选：{linked.length}；候选关联不验证组件身份。</p>}
            {missing && <p className="local-ai__muted">部分候选引用无法对应本次 Runtime，对应关联仍未知。</p>}
          </article>;
        })}</div>
      </>}
      <h3>目录模型的组件需求声明</h3>
      <p>以下来自现有 Model Center 目录声明，不表示这些组件已安装或属于上述工作流；尚无组件身份与本次扫描的对应证据。</p>
      {!components.length ? <p>本次没有可显示的组件声明，不能推断没有组件需求。</p> : <details><summary>目录组件声明（{components.length}）</summary>
        <ObservationPages count={components.length} requestedPage={componentPage} onPage={setComponentPage} label="组件声明"/>
        <ul className="local-ai__notes">{components.slice(componentOffset, componentOffset + PAGE_SIZE).map((component, index) => <li key={`${component.model_id}:${component.component_id}:${index}`}>
          {component.model_display_name}（{component.model_id}） · {component.component_id} · {component.component_type || '组件类型未知'} · 未知（unknown）
          <p>{component.reason === 'NO_COMPONENT_IDENTITY_EVIDENCE' ? '组件身份无对应证据' : '组件定义不可用'} · 元数据验证：NOT_VERIFIED · 实际生成：NOT_RUN</p>
        </li>)}</ul>
      </details>}
    </>}
  </section>;
}
