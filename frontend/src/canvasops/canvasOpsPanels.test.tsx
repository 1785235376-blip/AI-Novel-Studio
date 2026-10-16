// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { connectionIssue } from '../creative/graphDraft';
import type {
  StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphNode, StudioGraphPort, StudioGraphPortType, StudioGraphReferenceState,
} from '../creative/studioGraphTypes';
import { autoLayout, blankLocalCanvasState, canvasPortKey, createLocalGroup } from './canvasOps';
import { CanvasOpsRail } from './CanvasOpsRail';
import { CanvasSelectionBar } from './CanvasSelectionBar';
import { ChangeImpactNotice } from './ChangeImpactNotice';
import { ConnectionAdvisorPanel } from './ConnectionAdvisorPanel';
import { NodePalettePanel } from './NodePalettePanel';

/**
 * 这个套件同时承担一条硬约束：**任何面板都不得发起网络请求**。
 * 每个用例的 afterEach 都会断言 fetch 与 XMLHttpRequest 完全没有被触碰。
 */
const fetchSpy = vi.fn(() => Promise.reject(new Error('canvasops 组件不得发起网络请求')));
const xhrOpen = vi.fn(), xhrSend = vi.fn();
class RecordingXhr { open = xhrOpen; send = xhrSend; }
beforeEach(() => {
  fetchSpy.mockClear(); xhrOpen.mockClear(); xhrSend.mockClear();
  vi.stubGlobal('fetch', fetchSpy);
  vi.stubGlobal('XMLHttpRequest', RecordingXhr);
});
afterEach(() => {
  expect(fetchSpy).not.toHaveBeenCalled();
  expect(xhrOpen).not.toHaveBeenCalled();
  expect(xhrSend).not.toHaveBeenCalled();
  cleanup();
  vi.unstubAllGlobals();
});

const port = (id: string, type: StudioGraphPortType, required = false): StudioGraphPort => ({ id, type, required, multiple: false });
const entry = (id: StudioGraphDefinitionId, inputs: StudioGraphPort[], outputs: StudioGraphPort[]): StudioGraphCatalogDefinition => ({
  id, version: 1, inputs, outputs, parameters_schema: { type: 'object', additionalProperties: false, properties: {} },
  default_parameters: {}, executable: true, model_called: false, blockers: [],
});
const definitions: StudioGraphCatalogDefinition[] = [
  entry('text_input', [], [port('text', 'TEXT')]),
  entry('text_reference', [port('text', 'TEXT', true)], [port('text', 'TEXT')]),
  entry('draft_prepare', [port('text', 'TEXT', true), port('direction', 'DIRECTOR_NOTES')], [port('draft', 'DRAFT')]),
  entry('director_note', [], [port('direction', 'DIRECTOR_NOTES')]),
  entry('image_prompt', [port('references', 'IMAGE_REFERENCES')], [port('prompt', 'IMAGE_PROMPT')]),
];
const catalog: StudioGraphCatalog = {
  definitions,
  limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
  capabilities: {
    local_execution: true, chapter_required: false, model_execution: true, external_reference_execution: false,
    external_reference_detach: false, binary_cache: false, parallel_execution: false, automatic_retry: false,
    actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY',
  },
};
function node(id: string, definitionId: StudioGraphDefinitionId, position = { x: 0, y: 0 }): StudioGraphNode {
  return { id, definition_id: definitionId, definition_version: 1, enabled: true, position, parameters: {} };
}
const graph = (overrides: Partial<StudioGraphDefinition> = {}): StudioGraphDefinition => ({
  schema_version: 1, title: '独立节点图', viewport: { x: 0, y: 0, zoom: 1 }, edges: [],
  nodes: [node('source', 'text_input'), node('ref', 'text_reference')],
  ...overrides,
});
const region = (name: string) => screen.getByRole('region', { name });
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const queryButton = (name: string | RegExp) => screen.queryByRole('button', { name }) as HTMLButtonElement | null;

/* ------------------------------------------------------------------ *
 * 节点面板
 * ------------------------------------------------------------------ */
describe('canvas ops panel · node palette', () => {
  const renderPalette = (patch: Partial<Parameters<typeof NodePalettePanel>[0]> = {}) => {
    const props = {
      catalog, definition: graph(), kind: 'text_input', editable: true, onKind: vi.fn(), onAddNode: vi.fn(), ...patch,
    };
    render(<NodePalettePanel {...props}/>);
    return props;
  };

  it('lists catalogue definitions with their declared input and output ports', () => {
    renderPalette();
    const list = within(region('节点面板')).getByRole('list');
    expect(within(list).getByText('本地草稿整理')).toBeTruthy();
    expect(list.textContent).toContain('输入 text TEXT · 必填');
    expect(list.textContent).toContain('输入 direction DIRECTOR_NOTES');
    expect(list.textContent).toContain('输出 draft DRAFT');
    expect(list.textContent).toContain('text_input');
  });

  it('filters by search text and by category without inventing node types', () => {
    renderPalette();
    fireEvent.change(screen.getByLabelText('搜索节点'), { target: { value: '整理' } });
    let list = within(region('节点面板')).getByRole('list');
    expect(list.textContent).toContain('本地草稿整理');
    expect(list.textContent).not.toContain('文本引用');

    fireEvent.change(screen.getByLabelText('搜索节点'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('节点分类'), { target: { value: 'IMAGE' } });
    list = within(region('节点面板')).getByRole('list');
    expect(list.textContent).toContain('图片提示词');
    expect(list.textContent).not.toContain('本地草稿整理');
  });

  it('marks definitions the current graph format does not allow and cannot select them', () => {
    const props = renderPalette();
    const blocked = button(/图片提示词/) as HTMLButtonElement;
    expect(blocked.disabled).toBe(true);
    expect(blocked.textContent).toContain('当前图格式不可用');
    fireEvent.click(blocked);
    expect(props.onKind).not.toHaveBeenCalled();
    fireEvent.click(button(/本地草稿整理/));
    expect(props.onKind).toHaveBeenCalledWith('draft_prepare');
  });

  it('delegates adding to the original controller and never raises the node limit', () => {
    const props = renderPalette();
    fireEvent.click(button('添加所选节点（由原控制器执行）'));
    expect(props.onAddNode).toHaveBeenCalledTimes(1);
    cleanup();

    const full = graph({ nodes: Array.from({ length: 16 }, (_, index) => node(`n${index}`, 'text_input')) });
    renderPalette({ definition: full, onAddNode: vi.fn() });
    const add = button('添加所选节点（由原控制器执行）');
    expect(add.disabled).toBe(true);
    expect(region('节点面板').textContent).toContain('已达本图节点上限 16 个');
    expect(region('节点面板').textContent).toContain('拆分工作流');
    cleanup();

    renderPalette({ editable: false });
    expect(button('添加所选节点（由原控制器执行）').disabled).toBe(true);
    expect(region('节点面板').textContent).toContain('不会抬高任何节点或任务上限');
  });

  it('explains an unread catalogue instead of showing fabricated entries', () => {
    renderPalette({ catalog: undefined });
    expect(region('节点面板').textContent).toContain('节点目录尚未读取');
    expect(screen.queryByRole('list')).toBeNull();
  });
});

/* ------------------------------------------------------------------ *
 * 选择与历史
 * ------------------------------------------------------------------ */
describe('canvas ops panel · selection and history', () => {
  const renderBar = (patch: Partial<Parameters<typeof CanvasSelectionBar>[0]> = {}) => {
    const props = {
      selected: ['node_a', 'node_b'], past: 2, future: 1, editable: true, protectedNodeIds: ['node_c'],
      onFocusSelected: vi.fn(), onSelect: vi.fn(), onTravel: vi.fn(), ...patch,
    };
    render(<CanvasSelectionBar {...props}/>);
    return props;
  };

  it('summarizes multi-selection, marquee count and protected nodes', () => {
    renderBar({ marqueeCount: 4 });
    const text = region('选择与历史').textContent ?? '';
    expect(text).toContain('2');
    expect(text).toContain('已选节点');
    expect(text).toContain('框选命中 4 个节点');
    expect(text).toContain('受保护节点 1 个');
    cleanup();
    renderBar();
    expect(region('选择与历史').textContent).toContain('框选命中：未提供');
  });

  it('focuses one selected node and can select only the protected nodes', () => {
    const props = renderBar();
    fireEvent.click(button('定位 node_a'));
    expect(props.onFocusSelected).toHaveBeenCalledWith('node_a');
    fireEvent.click(button('只选择全部受保护节点（1）'));
    expect(props.onSelect).toHaveBeenCalledWith(['node_c']);
    fireEvent.click(button('清空选择'));
    expect(props.onSelect).toHaveBeenCalledWith([]);
  });

  it('describes undo and redo as local-draft-only and never as a rollback of spent cost', () => {
    const props = renderBar();
    const text = region('选择与历史').textContent ?? '';
    expect(text).toContain('只回退本地草稿操作');
    expect(text).toContain('已经发生的模型调用与费用、远端任务与已提交的审核都不会被撤销或回滚');
    expect(button('撤销本地草稿编辑（可撤销 2 步）').disabled).toBe(false);
    fireEvent.click(button('撤销本地草稿编辑（可撤销 2 步）'));
    expect(props.onTravel).toHaveBeenCalledWith('UNDO');
    fireEvent.click(button('重做本地草稿编辑（可重做 1 步）'));
    expect(props.onTravel).toHaveBeenCalledWith('REDO');
    cleanup();

    renderBar({ past: 0, future: 0, editable: false });
    expect(button('撤销本地草稿编辑（可撤销 0 步）').disabled).toBe(true);
    expect(button('重做本地草稿编辑（可重做 0 步）').disabled).toBe(true);
  });

  it('keeps the local collapse state session-local and explains the persistence rule', () => {
    const onLocal = vi.fn();
    const local = createLocalGroup(blankLocalCanvasState(), 'g1', '第一组', ['node_a']).state;
    renderBar({ selected: ['node_a'], local, onLocal });
    const text = region('选择与历史').textContent ?? '';
    expect(text).toContain('本地折叠 0 · 分组 1 · 标注 0');
    expect(text).toContain('不会写入已保存的创作图');
    fireEvent.click(button('折叠 node_a（仅本地）'));
    expect(onLocal).toHaveBeenCalledWith({ ...local, collapsed: ['node_a'] });
    cleanup();
    renderBar({ selected: ['node_a'], local: { ...local, collapsed: ['node_a'] }, onLocal });
    expect(button('展开本地折叠 node_a')).toBeTruthy();
  });
});

/* ------------------------------------------------------------------ *
 * 连接建议
 * ------------------------------------------------------------------ */
describe('canvas ops panel · connection advisor cannot bypass connectionIssue', () => {
  const renderAdvisor = (patch: Partial<Parameters<typeof ConnectionAdvisorPanel>[0]> = {}) => {
    const props = {
      definition: graph(), catalog, sourcePort: canvasPortKey('source', 'text'), targetPort: '',
      editable: true, onSourcePort: vi.fn(), onTargetPort: vi.fn(), onConnect: vi.fn(), ...patch,
    };
    render(<ConnectionAdvisorPanel {...props}/>);
    return props;
  };

  it('shows the pending source port type and the compatible targets from the catalogue declarations', () => {
    renderAdvisor();
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('source.text');
    expect(text).toContain('TEXT');
    const list = within(region('连接建议')).getByRole('list');
    expect(list.textContent).toContain('ref.text');
    expect(list.textContent).toContain('本地检查通过');
    expect(list.textContent).not.toContain('director_note.direction');
  });

  it('selects a compatible target through the original callback and then enables connecting', () => {
    const props = renderAdvisor();
    fireEvent.click(within(region('连接建议')).getByRole('button', { name: /ref\.text/ }));
    expect(props.onTargetPort).toHaveBeenCalledWith(canvasPortKey('ref', 'text'));
    expect(props.onConnect).not.toHaveBeenCalled();
  });

  it('cannot bypass a type mismatch: the reason is shown and connecting stays disabled', () => {
    const definition = graph({ nodes: [node('source', 'text_input'), node('prepare', 'draft_prepare')] });
    const targetPort = canvasPortKey('prepare', 'direction');
    const ownerIssue = connectionIssue(definition, catalog.definitions, {
      id: 'probe', source_node_id: 'source', source_port: 'text', target_node_id: 'prepare', target_port: 'direction',
    })!;
    expect(ownerIssue).toBe('端口类型不匹配：TEXT → DIRECTOR_NOTES。');
    const props = renderAdvisor({ definition, targetPort });
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('端口类型不匹配：TEXT → DIRECTOR_NOTES');
    expect(text).toContain('PORT_TYPE_MISMATCH');
    expect(text).toContain(ownerIssue);
    expect(text).toContain('不提供绕过入口');
    expect(button('连接所选端口（由原控制器执行）').disabled).toBe(true);
    fireEvent.click(button('连接所选端口（由原控制器执行）'));
    expect(props.onConnect).not.toHaveBeenCalled();
    const targetSelect = screen.getByLabelText('连接建议 · 目标输入端口') as HTMLSelectElement;
    fireEvent.change(targetSelect, { target: { value: targetPort } });
    expect(props.onTargetPort).toHaveBeenCalledWith(targetPort);
    expect(targetSelect.textContent).toContain('不可连接 PORT_TYPE_MISMATCH');
  });

  it('enables the connect callback for a legal pair and reports the owner result', () => {
    const props = renderAdvisor({ targetPort: canvasPortKey('ref', 'text') });
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('本地连接检查通过');
    expect(text).toContain('CONNECTION_LEGAL');
    // 待建立的这条连接本身会满足 ref.text 的必填要求，所以不能把它报成「必填输入缺失」。
    expect(text).not.toContain('REQUIRED_INPUT_MISSING');
    const connect = button('连接所选端口（由原控制器执行）');
    expect(connect.disabled).toBe(false);
    fireEvent.click(connect);
    expect(props.onConnect).toHaveBeenCalledTimes(1);
  });

  it('reports a required input gap on the target node without blocking the pending connection', () => {
    const definition = graph({ nodes: [node('note', 'director_note'), node('prepare', 'draft_prepare')] });
    renderAdvisor({ definition, sourcePort: canvasPortKey('note', 'direction'), targetPort: canvasPortKey('prepare', 'direction') });
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('REQUIRED_INPUT_MISSING');
    expect(text).toContain('prepare.text');
    expect(text).not.toContain('prepare.direction。');
    expect(button('连接所选端口（由原控制器执行）').disabled).toBe(false);
  });

  it('shows a stale source binding and a missing required input as owner facts, not as a new legality rule', () => {
    const definition = graph({ nodes: [node('source', 'text_input'), node('review', 'text_reference')] });
    const referenceStates: StudioGraphReferenceState[] = [{ node_id: 'source', state: 'STALE' }];
    renderAdvisor({ definition, targetPort: canvasPortKey('review', 'text'), referenceStates });
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('SOURCE_BINDING_STALE');
    expect(text).toContain('已过期');
    expect(text).toContain('重新绑定');
    expect(button('连接所选端口（由原控制器执行）').disabled).toBe(false);
    cleanup();

    renderAdvisor({ definition, targetPort: canvasPortKey('review', 'text'), referenceStates: [{ node_id: 'source', state: 'CURRENT' }] });
    const current = region('连接建议').textContent ?? '';
    expect(current).toContain('CONNECTION_LEGAL');
    expect(current).not.toContain('SOURCE_BINDING_STALE');
  });

  it('reports the missing required input of a different node and never invents a replacement', () => {
    const definition = graph({ nodes: [node('source', 'text_input'), node('ref', 'text_reference')] });
    renderAdvisor({ definition, targetPort: canvasPortKey('ref', 'text') });
    const sourceSelect = screen.getByLabelText('连接建议 · 起始输出端口') as HTMLSelectElement;
    expect(sourceSelect.textContent).toContain('文本输入 · source · text (TEXT)');
    cleanup();
    renderAdvisor({ definition, sourcePort: '', targetPort: '' });
    expect(region('连接建议').textContent).toContain('尚未选择有效的起始输出端口');
    expect(button('连接所选端口（由原控制器执行）').disabled).toBe(true);
    cleanup();
    renderAdvisor({ definition, sourcePort: canvasPortKey('source', 'nope'), targetPort: '' });
    expect(region('连接建议').textContent).toContain('当前图格式下不存在');
  });

  it('shows the owner explanation passed by the integrator and the edge-limit split advice', () => {
    renderAdvisor({ connectionExplanation: '此连接会形成循环，无法保存。' });
    const text = region('连接建议').textContent ?? '';
    expect(text).toContain('CYCLE');
    expect(text).toContain('此连接会形成循环，无法保存。');
    expect(text).toContain('拆成两张可独立保存的图');
    cleanup();

    const saturated = graph({ edges: Array.from({ length: 40 }, (_, index) => ({
      id: `e${index}`, source_node_id: 'source', source_port: 'text', target_node_id: 'ref', target_port: 'text',
    })) });
    renderAdvisor({ definition: saturated });
    expect(region('连接建议').textContent).toContain('已达本图连接上限 40 条');
    expect(region('连接建议').textContent).toContain('拆分工作流');
  });
});

/* ------------------------------------------------------------------ *
 * 变更影响
 * ------------------------------------------------------------------ */
describe('canvas ops panel · change impact notice', () => {
  const base = graph();

  it('labels a layout-only difference as presentation-only and states both mandatory facts', () => {
    const moved = { ...base, nodes: base.nodes.map((row, index) => index === 0 ? { ...row, position: { x: 900, y: 30 } } : row) };
    const { container } = render(<ChangeImpactNotice definition={moved} base={base} dirty/>);
    const notice = container.querySelector('[data-canvas-ops-verdict]')!;
    expect(notice.getAttribute('data-canvas-ops-verdict')).toBe('PRESENTATION');
    expect(notice.getAttribute('data-canvas-ops-dirty')).toBe('true');
    const text = notice.textContent ?? '';
    expect(text).toContain('仅呈现');
    expect(text).toContain('PRESENTATION');
    expect(text).toContain('不会重新运行模型');
    expect(text).toContain('永远不会绕过原图的版本与摘要校验');
    expect(text).toContain('只有节点位置发生变化');
  });

  it('treats the deterministic auto layout result as presentation-only and parameter edits as generation affecting', () => {
    const { container } = render(<ChangeImpactNotice definition={autoLayout(base)} base={base} dirty/>);
    expect(container.querySelector('[data-canvas-ops-verdict]')!.getAttribute('data-canvas-ops-verdict')).toBe('PRESENTATION');
    cleanup();

    const edited = { ...base, nodes: base.nodes.map((row, index) => index === 0 ? { ...row, parameters: { text: '改过' } } : row) };
    const second = render(<ChangeImpactNotice definition={edited} base={base} dirty/>);
    const notice = second.container.querySelector('[data-canvas-ops-verdict]')!;
    expect(notice.getAttribute('data-canvas-ops-verdict')).toBe('GENERATION_AFFECTING');
    expect(notice.textContent).toContain('可能影响生成');
    expect(notice.textContent).toContain('NODE_PARAMETERS_CHANGED');
    expect(notice.textContent).toContain('永远不会绕过原图的版本与摘要校验');
  });

  it('stays conservative without a saved version to compare and when nothing is dirty', () => {
    const { container } = render(<ChangeImpactNotice definition={graph()} dirty={false}/>);
    const notice = container.querySelector('[data-canvas-ops-verdict]')!;
    expect(notice.getAttribute('data-canvas-ops-verdict')).toBe('GENERATION_AFFECTING');
    expect(notice.textContent).toContain('尚无已保存版本');
    cleanup();

    const clean = render(<ChangeImpactNotice definition={base} base={base} dirty={false}/>);
    const same = clean.container.querySelector('[data-canvas-ops-verdict]')!;
    expect(same.getAttribute('data-canvas-ops-verdict')).toBe('PRESENTATION');
    expect(same.textContent).toContain('未保存修改：无');
  });
});

/* ------------------------------------------------------------------ *
 * 组合操作栏（冻结 props）
 * ------------------------------------------------------------------ */
describe('canvas ops rail · frozen composition', () => {
  const railProps = (patch: Partial<Parameters<typeof CanvasOpsRail>[0]> = {}) => ({
    catalog, definition: graph(), base: graph(), selected: ['source'], past: 1, future: 0, editable: true,
    protectedNodeIds: ['ref'], kind: 'text_input', sourcePort: canvasPortKey('source', 'text'),
    targetPort: canvasPortKey('ref', 'text'), local: blankLocalCanvasState(),
    onLocal: vi.fn(), onKind: vi.fn(), onSourcePort: vi.fn(), onTargetPort: vi.fn(), onAddNode: vi.fn(),
    onConnect: vi.fn(), onSelect: vi.fn(), onTravel: vi.fn(), ...patch,
  });

  it('composes the four panels plus a deterministic layout preview', () => {
    render(<CanvasOpsRail {...railProps()}/>);
    expect(region('画布操作栏')).toBeTruthy();
    expect(region('节点面板')).toBeTruthy();
    expect(region('选择与历史')).toBeTruthy();
    expect(region('连接建议')).toBeTruthy();
    expect(region('变更影响')).toBeTruthy();
    const preview = region('自动布局预览');
    expect(preview.getAttribute('data-canvas-ops-layout-verdict')).toBe('PRESENTATION');
    expect(preview.textContent).toContain('只改坐标');
    expect(preview.textContent).toContain('不会改动参数、来源绑定、启用状态、连接或图格式');
    expect(preview.textContent).toContain('change()');
  });

  it('reports whether the current draft really differs from the saved definition', () => {
    const { container } = render(<CanvasOpsRail {...railProps()}/>);
    expect(container.querySelector('[data-canvas-ops-dirty]')!.getAttribute('data-canvas-ops-dirty')).toBe('false');
    cleanup();

    const moved = graph({ nodes: [node('source', 'text_input', { x: 500, y: 500 }), node('ref', 'text_reference')] });
    const second = render(<CanvasOpsRail {...railProps({ definition: moved })}/>);
    expect(second.container.querySelector('[data-canvas-ops-dirty]')!.getAttribute('data-canvas-ops-dirty')).toBe('true');
    expect(second.container.querySelector('[data-canvas-ops-verdict]')!.getAttribute('data-canvas-ops-verdict')).toBe('PRESENTATION');
  });

  it('wires every frozen callback through to the original controller surface', () => {
    const props = railProps({ targetPort: '' });
    render(<CanvasOpsRail {...props}/>);
    fireEvent.click(button('添加所选节点（由原控制器执行）'));
    expect(props.onAddNode).toHaveBeenCalledTimes(1);
    fireEvent.click(button('定位 source'));
    expect(props.onSelect).toHaveBeenCalledWith(['source']);
    fireEvent.click(button('撤销本地草稿编辑（可撤销 1 步）'));
    expect(props.onTravel).toHaveBeenCalledWith('UNDO');
    fireEvent.click(button('重做本地草稿编辑（可重做 0 步）'));
    expect(props.onTravel).toHaveBeenCalledTimes(1);
    fireEvent.click(button('连接所选端口（由原控制器执行）'));
    expect(props.onConnect).not.toHaveBeenCalled();
    cleanup();

    const connectable = railProps();
    render(<CanvasOpsRail {...connectable}/>);
    fireEvent.click(button('连接所选端口（由原控制器执行）'));
    expect(connectable.onConnect).toHaveBeenCalledTimes(1);
  });

  it('surfaces an invalid session-local structure instead of applying it', () => {
    const props = railProps({ local: { schema: 'canvasops-local/1', collapsed: [], groups: 'oops', annotations: [] } as never });
    render(<CanvasOpsRail {...props}/>);
    expect(region('画布操作栏').textContent).toContain('本地分组数据不可用，已按空分组处理。');
    expect(props.onLocal).not.toHaveBeenCalled();
    // 失败关闭为空状态：折叠开关仍然可用，但写回的只能是空状态派生的结构，坏数据不会被转交。
    fireEvent.click(queryButton(/仅本地/)!);
    expect(props.onLocal).toHaveBeenCalledWith({ ...blankLocalCanvasState(), collapsed: ['source'] });
    cleanup();

    const unknownField = railProps({ local: { schema: 'canvasops-local/1', collapsed: [], groups: [], annotations: [], extra: true } as never });
    render(<CanvasOpsRail {...unknownField}/>);
    expect(region('画布操作栏').textContent).toContain('本地画布状态不可用，已按空状态处理。');
  });

  it('explains the node limit inside the rail when the graph is saturated', () => {
    const full = graph({ nodes: Array.from({ length: 16 }, (_, index) => node(`n${index}`, 'text_input')) });
    render(<CanvasOpsRail {...railProps({ definition: full, base: full })}/>);
    expect(region('节点面板').textContent).toContain('已达本图节点上限 16 个');
    expect(queryButton('添加所选节点（由原控制器执行）')!.disabled).toBe(true);
  });
});
