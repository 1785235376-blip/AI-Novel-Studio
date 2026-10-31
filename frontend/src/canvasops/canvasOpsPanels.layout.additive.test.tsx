// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphNode, StudioGraphPort, StudioGraphPortType } from '../creative/studioGraphTypes';
import { autoLayout, blankLocalCanvasState, canvasPortKey } from './canvasOps';
import { CanvasOpsRail } from './CanvasOpsRail';

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

const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;

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

  it('applies only by explicit original-owner callback and disables readonly, no-op and preview-only consumers', () => {
    const onApplyLayout = vi.fn(), props = railProps({ onApplyLayout });
    const view = render(<CanvasOpsRail {...props}/>);
    expect(onApplyLayout).not.toHaveBeenCalled();
    fireEvent.click(button('应用自动布局到草稿'));
    expect(onApplyLayout).toHaveBeenCalledTimes(1);
    for (const patch of [{ editable: false }, { onApplyLayout: undefined },
      { definition: autoLayout(props.definition, { definitions: catalog.definitions }) }, { definition: graph({ nodes: [] }) }]) {
      view.rerender(<CanvasOpsRail {...props} {...patch}/>);
      expect(button('应用自动布局到草稿').disabled).toBe(true);
      fireEvent.click(button('应用自动布局到草稿'));
    }
    expect(onApplyLayout).toHaveBeenCalledTimes(1);
  });
});
