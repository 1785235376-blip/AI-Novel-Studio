import { useMemo } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioGraphCatalog, StudioGraphDefinition } from '../creative/studioGraphTypes';
import { autoLayout, classifyGraphChange, normalizeLocalCanvasState } from './canvasOps';
import type { LocalCanvasState, PositionedPaletteInsertion } from './canvasOpsTypes';
import { CanvasSelectionBar } from './CanvasSelectionBar';
import { ChangeImpactNotice } from './ChangeImpactNotice';
import { ConnectionAdvisorPanel } from './ConnectionAdvisorPanel';
import { NodePalettePanel } from './NodePalettePanel';
import './canvasOps.css';

/**
 * 画布操作栏组合 props：接进现有创作图编辑器，
 * 所有变更都通过原控制器的回调完成，本组件自身不改图、不保存、不发请求。
 */
export type CanvasOpsRailProps = {
  insertion?: PositionedPaletteInsertion;
  catalog?: StudioGraphCatalog;
  definition: StudioGraphDefinition;
  base?: StudioGraphDefinition;
  selected: string[];
  past: number;
  future: number;
  editable: boolean;
  protectedNodeIds: string[];
  kind: string;
  sourcePort: string;
  targetPort: string;
  connectionExplanation?: string;
  local: LocalCanvasState;
  onLocal: (next: LocalCanvasState) => void;
  onKind: (kind: string) => void;
  onSourcePort: (port: string) => void;
  onTargetPort: (port: string) => void;
  onAddNode: () => void;
  onConnect: () => void;
  onSelect: (ids: string[]) => void;
  onTravel: (direction: 'UNDO' | 'REDO') => void;
  /** Optional for preview-only consumers; the original owner computes and applies current positions. */
  onApplyLayout?: () => void;
};

/**
 * 无限画布与节点工作流的操作栏：节点面板 + 选择与历史 + 连接建议 + 变更影响 + 自动布局预览。
 *
 * 边界（与本批硬约束一致）：
 * - 连接合法性只看 `connectionIssue`；本栏不重实现连通性、schema 校验或运行器；
 * - 节点/连接上限只读展示，达到上限时说明并建议拆分工作流，绝不抬高上限；
 * - 折叠、分组与标注只是会话内呈现状态，不会写入已保存的创作图；
 * - 自动布局是确定性的纯函数，只改变节点坐标；本栏给出预览与差异分类，
 *   真正的提交必须由原控制器的 `change()`（进入本地撤销栈）完成。
 */
export function CanvasOpsRail(props: CanvasOpsRailProps) {
  const {
    catalog, definition, base, selected, past, future, editable, protectedNodeIds, kind,
    sourcePort, targetPort, connectionExplanation, local, onLocal, onKind, onSourcePort,
    onTargetPort, onAddNode, onConnect, onSelect, onTravel, onApplyLayout,
  } = props;
  const normalized = useMemo(() => normalizeLocalCanvasState(local), [local]);
  const localState = normalized.state;
  const layoutPreview = useMemo(() => autoLayout(definition, { definitions: catalog?.definitions }), [definition, catalog?.definitions]);
  const layoutImpact = useMemo(() => classifyGraphChange(definition, layoutPreview), [definition, layoutPreview]);
  /** 本地草稿差异由定义本身比较得出，不用撤销栈深度猜测。 */
  const draftImpact = useMemo(() => classifyGraphChange(base, definition), [base, definition]);
  const dirty = base
    ? !(draftImpact.reasonCodes.length === 1 && draftImpact.reasonCodes[0] === 'NO_CHANGE')
    : definition.nodes.length > 0 || definition.edges.length > 0;
  const moved = useMemo(() => definition.nodes.filter(node => {
    const next = layoutPreview.nodes.find(row => row.id === node.id);
    return next ? next.position.x !== node.position.x || next.position.y !== node.position.y : false;
  }).length, [definition, layoutPreview]);
  const columns = useMemo(() => new Set(layoutPreview.nodes.map(node => node.position.x)).size, [layoutPreview]);

  return <section className="canvas-ops" aria-label="画布操作栏">
    {normalized.issue && <StatusMessage tone="warning">{normalized.issue}</StatusMessage>}
    <NodePalettePanel insertion={props.insertion} catalog={catalog} definition={definition} kind={kind} editable={editable} onKind={onKind} onAddNode={onAddNode}/>
    <CanvasSelectionBar
      selected={selected} past={past} future={future} editable={editable} protectedNodeIds={protectedNodeIds}
      local={localState} onLocal={onLocal} onSelect={onSelect} onTravel={onTravel}
      onFocusSelected={nodeId => onSelect([nodeId])}/>
    <ConnectionAdvisorPanel
      definition={definition} catalog={catalog} sourcePort={sourcePort} targetPort={targetPort}
      connectionExplanation={connectionExplanation} editable={editable} onSourcePort={onSourcePort}
      onTargetPort={onTargetPort} onConnect={onConnect}/>
    <ChangeImpactNotice definition={definition} base={base} dirty={dirty}/>
    <section aria-label="自动布局预览" data-canvas-ops-layout-verdict={layoutImpact.verdict}>
      <h3>自动布局预览（确定性，只改坐标）</h3>
      <p>
        若应用自动布局：会分为 {columns} 列，移动 {moved} 个节点的坐标；差异分类为 <code>{layoutImpact.verdict}</code>
        （原因：{layoutImpact.reasonCodes.join('、')}）。它不会改动参数、来源绑定、启用状态、连接或图格式。
      </p>
      <p className="canvas-ops__note">
        应用只将节点坐标写入当前草稿，保留未保存的文字、来源绑定和视口；通过原控制器的 <code>change()</code> 进入撤销/重做栈。保存创作图后才会持久化；保存冲突或回执不确定时保留草稿，不自动覆盖或重试。
      </p>
      <Button disabled={!editable || !onApplyLayout || moved === 0 || layoutImpact.verdict !== 'PRESENTATION'}
        onClick={() => { if (editable && moved > 0 && layoutImpact.verdict === 'PRESENTATION') onApplyLayout?.(); }}>应用自动布局到草稿</Button>
      {!onApplyLayout && <p>当前视图仅提供布局预览。</p>}
    </section>
  </section>;
}
