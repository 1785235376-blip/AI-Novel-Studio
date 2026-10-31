// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { describe, expect, it } from 'vitest';

import { graphNodeHeight } from '../creative/graphCanvasGeometry';
import type { StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId, StudioGraphNode, StudioGraphParameters, StudioGraphPort, StudioGraphPortType } from '../creative/studioGraphTypes';
import { autoLayout, classifyGraphChange } from './canvasOps';

/* ------------------------------------------------------------------ *
 * 目录与图夹具（本地构造，不发任何请求）
 * ------------------------------------------------------------------ */
const port = (id: string, type: StudioGraphPortType, required = false): StudioGraphPort => ({ id, type, required, multiple: false });
const entry = (id: StudioGraphDefinitionId, inputs: StudioGraphPort[], outputs: StudioGraphPort[]): StudioGraphCatalogDefinition => ({
  id, version: 1, inputs, outputs, parameters_schema: { type: 'object', additionalProperties: false, properties: {} },
  default_parameters: {}, executable: true, model_called: false, blockers: [],
});

function node(id: string, definitionId: StudioGraphDefinitionId = 'text_reference', parameters: StudioGraphParameters = {}): StudioGraphNode {
  return { id, definition_id: definitionId, definition_version: 1, enabled: true, position: { x: 24, y: 48 }, parameters };
}

function graph(overrides: Partial<StudioGraphDefinition> = {}): StudioGraphDefinition {
  return {
    schema_version: 1, title: '独立节点图', viewport: { x: 0, y: 0, zoom: 1 }, edges: [], nodes: [node('source', 'text_input')],
    ...overrides,
  };
}

/* ------------------------------------------------------------------ *
 * 自动布局
 * ------------------------------------------------------------------ */
describe('canvas ops · deterministic auto layout', () => {

  it('preserves exact source pins and camera while leaving room for tall catalog cards', () => {
    const before = graph({ schema_version: 4, viewport: { x: -450, y: 700, zoom: 0.5 }, nodes: [
      node('director', 'director_plan', { document_snapshot: { id: 'director-original', version: 7, digest: 'a'.repeat(64) } }),
      node('asset', 'asset_reference', { asset_id: 'original-asset', version: 9, digest: 'b'.repeat(64), kind: 'image' }),
    ] });
    const tall = entry('director_plan', Array.from({ length: 6 }, (_, i) => port(`input${i}`, 'TEXT')), []);
    const after = autoLayout(before, { definitions: [tall] });
    expect(after.nodes[1].position.y).toBe(graphNodeHeight(tall) + 48);
    expect(after.viewport).toBe(before.viewport);
    for (let index = 0; index < before.nodes.length; index++) {
      expect(after.nodes[index].parameters).toBe(before.nodes[index].parameters);
      expect({ ...after.nodes[index], position: before.nodes[index].position }).toEqual(before.nodes[index]);
    }
    expect(classifyGraphChange(before, after)).toMatchObject({ verdict: 'PRESENTATION', reasonCodes: ['POSITION_CHANGED'] });
  });
});
