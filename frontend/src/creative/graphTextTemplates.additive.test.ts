import { expect, it } from 'vitest';
import { blankGraph } from './graphDraft';
import { modelCatalog } from './studioGraphModel.testFixtures';
import { exportTextGraphTemplate, planTextGraphTemplate, readTextGraphTemplate } from './graphTextTemplates';
import type { StudioGraphDefinition } from './studioGraphTypes';
const graph = (): StudioGraphDefinition => ({ ...blankGraph(), nodes: [{ id: 'Input', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Author text' } }, { id: 'Draft', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 400, y: 0 }, parameters: {} }], edges: [{ id: 'Edge', source_node_id: 'Input', source_port: 'text', target_node_id: 'Draft', target_port: 'text' }] });
it('roundtrips bounded text nodes and uses original copy planning with new IDs', () => { const source = graph(), raw = exportTextGraphTemplate(source), before = structuredClone(source); expect(readTextGraphTemplate(raw)).toEqual(source); const target = blankGraph(), planned = planTextGraphTemplate(raw, target, modelCatalog()); expect(planned.result.definition.nodes).toHaveLength(2); expect(planned.result.definition.nodes[0].id).not.toBe('Input'); expect(planned.result.definition.edges[0].source_node_id).toBe(planned.result.definition.nodes[0].id); expect(target.nodes).toEqual([]); expect(source).toEqual(before); });
it.each(['owner', 'receipt', 'asset', 'media', 'oversize', 'different schema', 'presentation'])('refuses %s without inheriting authority', mode => { const source = graph(); let raw = exportTextGraphTemplate(source), target = blankGraph();
 if (mode === 'owner') { const value = JSON.parse(raw); value.owner = { project_id: 'foreign' }; raw = JSON.stringify(value); }
 if (mode === 'receipt') { const value = JSON.parse(raw); value.definition.reviewed = true; raw = JSON.stringify(value); }
 if (mode === 'asset') { source.nodes = [{ ...source.nodes[0], definition_id: 'asset_reference', parameters: { asset_id: 'foreign', version: 1, digest: 'a'.repeat(64), kind: 'image' } }]; source.edges = []; raw = JSON.stringify({ contract: 'poemseed-text-graph-template/1', definition: source }); }
 if (mode === 'media') { source.schema_version = 3; raw = JSON.stringify({ contract: 'poemseed-text-graph-template/1', definition: source }); }
 if (mode === 'oversize') raw += ' '.repeat(110001);
 if (mode === 'different schema') target.schema_version = 2;
 if (mode === 'presentation') { const value = JSON.parse(raw); value.definition.presentation = { comment: 'No hidden notes' }; raw = JSON.stringify(value); }
 expect(() => planTextGraphTemplate(raw, target, modelCatalog())).toThrow(); expect(target.nodes).toEqual([]);
});
it('retains original node and edge budgets', () => { const source = graph(), target = graph(), catalog = modelCatalog(); target.nodes = Array.from({ length: 15 }, (_, i) => ({ ...graph().nodes[0], id: `Existing_${i}` })); target.edges = []; expect(() => planTextGraphTemplate(exportTextGraphTemplate(source), target, catalog)).toThrow(); expect(target.nodes).toHaveLength(15); });
it.each(['node', 'parameters', 'position', 'edge'])('rejects extra authority-shaped fields on %s instead of silently dropping them', location => { const value = JSON.parse(exportTextGraphTemplate(graph())); const node = value.definition.nodes[0]; if (location === 'node') node.approved = true; if (location === 'parameters') node.parameters.api_key = 'not-a-real-key'; if (location === 'position') node.position.owner = 'other'; if (location === 'edge') value.definition.edges[0].execution_id = 'foreign'; expect(() => readTextGraphTemplate(JSON.stringify(value))).toThrow(); });
