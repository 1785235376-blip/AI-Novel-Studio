import { useMemo } from 'react';
import { connectionIssue, graphCatalogForSchema } from '../creative/graphDraft';
import { GRAPH_NODE_LABELS } from '../creative/studioGraphLabels';
import type { StudioGraphEdge } from '../creative/studioGraphTypes';
import { Badge, Button } from '../ui/primitives';
import {
  canvasEdgeBudget, canvasPortKey, compatibleTargets, explainConnection, parseCanvasPortKey,
  requiredInputGaps, staleReferenceNodeIds,
} from './canvasOps';
import type { ConnectionAdvisorPanelProps } from './canvasOpsTypes';
import './canvasOps.css';

const TARGET_PREVIEW_LIMIT = 8;
/** 与原编辑器同名控件区分开，保证精确无障碍名称查询无歧义。 */
const SOURCE_PORT_LABEL = '连接建议 · 起始输出端口';
const TARGET_PORT_LABEL = '连接建议 · 目标输入端口';

/**
 * 连接建议：连接前的端口类型、兼容目标，以及被拒绝时的具体中文原因。
 *
 * 合法性只有一位权威：`connectionIssue`（`../creative/graphDraft`）。本面板
 * 只是把它的结果翻译成可读原因，并把兼容候选列出来；**不提供任何绕过入口**：
 * 类型不匹配、未审核候选、过期绑定或缺失必填输入都会在这里被说明，连接动作本身
 * 仍由原创作图控制器的 `connect()` 执行（它会再次调用 `connectionIssue`）。
 *
 * 位置/折叠之类的呈现操作永远不会在这里触发模型调用或任务入队：本面板没有任何网络请求。
 */
export function ConnectionAdvisorPanel({
  definition, catalog, sourcePort, targetPort, connectionExplanation, editable, referenceStates,
  onSourcePort, onTargetPort, onConnect,
}: ConnectionAdvisorPanelProps) {
  const descriptors = useMemo(
    () => graphCatalogForSchema(catalog?.definitions ?? [], definition.schema_version),
    [catalog, definition.schema_version],
  );
  const source = parseCanvasPortKey(sourcePort), target = parseCanvasPortKey(targetPort);
  const sourceNode = source ? definition.nodes.find(node => node.id === source.nodeId) : undefined;
  const targetNode = target ? definition.nodes.find(node => node.id === target.nodeId) : undefined;
  const sourceOutput = sourceNode
    ? descriptors.find(row => row.id === sourceNode.definition_id)?.outputs.find(port => port.id === source!.portId)
    : undefined;
  const probe: StudioGraphEdge | null = sourceNode && targetNode && source && target ? {
    id: 'canvasops-advisor', source_node_id: source.nodeId, source_port: source.portId,
    target_node_id: target.nodeId, target_port: target.portId,
  } : null;
  /** 已选端口组合的原所有者判定；这是本面板唯一的合法性来源。 */
  const selectedIssue = probe && catalog ? connectionIssue(definition, catalog.definitions, probe) ?? null : null;

  const sourceOptions = useMemo(() => catalog ? definition.nodes.flatMap(node =>
    (descriptors.find(row => row.id === node.definition_id)?.outputs ?? []).map(port => ({
      value: canvasPortKey(node.id, port.id), legal: true,
      label: `${GRAPH_NODE_LABELS[node.definition_id]} · ${node.id} · ${port.id} (${port.type})`,
    }))) : [], [catalog, definition.nodes, descriptors]);
  const targetOptions = useMemo(() => catalog ? definition.nodes.flatMap(node =>
    (descriptors.find(row => row.id === node.definition_id)?.inputs ?? []).map(port => {
      if (!sourceNode || !source || !sourceOutput) return {
        value: canvasPortKey(node.id, port.id), legal: false, code: 'PORT_UNKNOWN' as const,
        label: `${GRAPH_NODE_LABELS[node.definition_id]} · ${node.id} · ${port.id} (${port.type}) · 请先选择起始输出端口`,
      };
      const issue = connectionIssue(definition, catalog.definitions, {
        id: 'canvasops-option', source_node_id: source.nodeId, source_port: source.portId,
        target_node_id: node.id, target_port: port.id,
      }) ?? null;
      const explanation = explainConnection(issue);
      return {
        value: canvasPortKey(node.id, port.id), legal: issue === null, code: explanation.code,
        label: `${GRAPH_NODE_LABELS[node.definition_id]} · ${node.id} · ${port.id} (${port.type}) · ${issue === null ? '本地检查通过' : `不可连接 ${explanation.code}`}`,
      };
    })) : [], [catalog, definition, descriptors, sourceNode, source, sourceOutput]);

  const targets = useMemo(
    () => source && sourceOutput ? compatibleTargets(definition, catalog, source.nodeId, source.portId) : [],
    [definition, catalog, source, sourceOutput],
  );
  const stale = staleReferenceNodeIds(referenceStates);
  const facts = {
    staleSourceNodeIds: sourceNode ? stale.filter(id => id === sourceNode.id) : [],
    // 待建立的这条连接本身就会满足目标端口的必填要求，所以不把它算成「必填输入缺失」。
    missingRequiredInputNodeIds: (targetNode ? requiredInputGaps(definition, catalog, [targetNode.id]) : [])
      .filter(gap => gap.nodeId !== target?.nodeId || gap.portId !== target?.portId)
      .map(gap => `${gap.nodeId}.${gap.portId}`),
  };
  const ownerIssue = connectionExplanation?.trim() ? connectionExplanation : selectedIssue;
  const explanation = explainConnection(ownerIssue, facts);
  const blocked = probe !== null && selectedIssue !== null;
  const budget = canvasEdgeBudget(catalog, definition);

  return <section aria-label="连接建议">
    <h3>连接建议</h3>
    {!catalog && <p className="canvas-ops__note">节点目录尚未读取，无法给出兼容目标；请先按需读取目录。本面板自身不发请求。</p>}
    {/*
      端口选择器的无障碍名称带「连接建议 ·」前缀：原创作图编辑器已有一组同名控件
      （`studioGraphEditorView.tsx` 的「起始输出端口」「目标输入端口」），
      精确名称查询必须保持无歧义，两套控件都通过同一个原控制器回调改状态。
    */}
    <div className="canvas-ops__row">
      <label className="canvas-ops__field"><span>{SOURCE_PORT_LABEL}</span>
        <select aria-label={SOURCE_PORT_LABEL} value={sourcePort} disabled={!editable || !catalog}
          onChange={event => onSourcePort(event.target.value)}>
          <option value="">选择输出端口</option>
          {sourceOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label className="canvas-ops__field"><span>{TARGET_PORT_LABEL}</span>
        <select aria-label={TARGET_PORT_LABEL} value={targetPort} disabled={!editable || !catalog}
          onChange={event => onTargetPort(event.target.value)}>
          <option value="">选择输入端口</option>
          {targetOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
    </div>
    <p>
      待连接来源：{source && sourceOutput
        ? <><code>{source.nodeId}.{source.portId}</code> · 类型 <b>{sourceOutput.type}</b> · {GRAPH_NODE_LABELS[sourceNode!.definition_id]}</>
        : <span>尚未选择有效的起始输出端口（请选择现存节点上由目录声明的输出端口）</span>}
    </p>
    {source && !sourceOutput && <p className="canvas-ops__note is-warning" role="status">所选输出端口在当前图格式下不存在：原目录不会自动改写，请重新选择端口。</p>}

    <h4>兼容目标（由目录端口声明与 <code>connectionIssue</code> 判定）</h4>
    {!source || !sourceOutput
      ? <p className="canvas-ops__empty" role="status">选择起始输出端口后，这里会列出端口类型一致的候选目标。</p>
      : targets.length === 0
        ? <p className="canvas-ops__empty" role="status">当前图中没有与 {sourceOutput.type} 类型一致的输入端口：请先添加相应节点，或改用其他输出端口。</p>
        : <ul className="canvas-ops__list">{targets.slice(0, TARGET_PREVIEW_LIMIT).map(row => <li key={`${row.nodeId}.${row.portId}`}>
          <button type="button" className="canvas-ops__item" aria-pressed={target?.nodeId === row.nodeId && target?.portId === row.portId}
            onClick={() => onTargetPort(canvasPortKey(row.nodeId, row.portId))}>
            <span className="canvas-ops__item-head">
              <strong>{row.label}</strong><code>{row.nodeId}.{row.portId}</code>
              <Badge tone={row.legal ? 'success' : 'warning'}>{row.legal ? '本地检查通过' : row.explanation.code}</Badge>
              {row.required && <Badge tone="neutral">必填输入</Badge>}
              {row.occupied && <Badge tone="warning">端口已占用</Badge>}
            </span>
            <span className="canvas-ops__ports"><span className={`canvas-ops__port${row.legal ? ' is-legal' : ' is-blocked'}`}>{row.portType}</span></span>
            <small>{row.issue ?? '类型一致、无环、输入端口未被占用。'}</small>
          </button>
        </li>)}</ul>}
    {targets.length > TARGET_PREVIEW_LIMIT && <p>另有 {targets.length - TARGET_PREVIEW_LIMIT} 个候选目标未列出；可用上面的目标输入端口下拉框选择。</p>}

    <div className="canvas-ops__actions">
      <Button variant="primary" disabled={!editable || !catalog || !probe || blocked} onClick={onConnect}>连接所选端口（由原控制器执行）</Button>
    </div>
    <div className="canvas-ops__note is-warning" role="status" data-canvas-ops-connection={explanation.code}>
      <p><strong>{blocked ? '本地连接检查未通过' : explanation.legal ? '本地连接检查通过' : '尚无可判定的端口组合'}</strong> · <code>{explanation.code}</code>（{explanation.category}）</p>
      <p>{explanation.message}</p>
      {explanation.ownerMessage && <p>原所有者原文：<code>{explanation.ownerMessage}</code></p>}
      {explanation.hints.length > 0 && <ul>{explanation.hints.map(hint => <li key={hint}>{hint}</li>)}</ul>}
    </div>
    {budget.message && <p className="canvas-ops__note is-warning" role="status">{budget.message}</p>}
    <p className="canvas-ops__note">
      本面板不提供绕过入口：类型不匹配、未审核候选、过期来源绑定与缺失必填输入都会在这里以原所有者的结果说明，连接仍由原控制器的 <code>connect()</code> 与 <code>connectionIssue</code> 判定。服务端校验、版本与摘要校验永远不会被跳过。
    </p>
  </section>;
}
