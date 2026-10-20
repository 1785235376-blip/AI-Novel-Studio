import { expect, it, vi } from 'vitest';
import * as draftIds from './graphDraft';
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

function annotated(): StudioGraphDefinition { return { ...graph(), presentation: {
 groups: [{ id: 'Parent', name: '父分组', node_ids: ['Input'] }, { id: 'Child', name: '子分组', node_ids: ['Draft'], parent_id: 'Parent' }],
 notes: [{ id: 'Note', text: '镜头节奏\n作者便笺 🐈', position: { x: 20, y: 280 } }],
} }; }
it('roundtrips visual hierarchy and Unicode author notes in the portable v2 contract', () => {
 const source = annotated(), before = structuredClone(source), raw = exportTextGraphTemplate(source);
 expect(JSON.parse(raw).contract).toBe('poemseed-text-graph-template/2');
 expect(readTextGraphTemplate(raw)).toEqual(source); expect(source).toEqual(before);
});
it('maps every imported visual identity and parent/member reference, offsets notes with nodes, preserves target presentation', () => {
 const source = annotated(), target = graph(); target.nodes = target.nodes.map(n => ({ ...n, id: `Target_${n.id}` })); target.edges = [];
 target.presentation = { comment: '保留目标说明', view: { show_grid: false, snap: false, grid_step: 16, show_minimap: false },
  groups: [{ id: 'Existing', name: '目标分组', node_ids: ['Target_Input'] }], notes: [{ id: 'ExistingNote', text: '保留目标便笺', position: { x: 0, y: 0 } }] };
 const before = structuredClone(target), plan = planTextGraphTemplate(exportTextGraphTemplate(source), target, modelCatalog()), next = plan.result.definition;
 expect(target).toEqual(before); expect(next.presentation?.comment).toBe(before.presentation!.comment); expect(next.presentation?.view).toEqual(before.presentation!.view);
 expect(next.presentation?.groups?.[0]).toEqual(before.presentation!.groups![0]); expect(next.presentation?.notes?.[0]).toEqual(before.presentation!.notes![0]);
 const [parent, child] = next.presentation!.groups!.slice(1); expect(parent.id).not.toBe('Parent'); expect(child.parent_id).toBe(parent.id);
 expect(parent.node_ids).toEqual([plan.result.selected[0]]); expect(child.node_ids).toEqual([plan.result.selected[1]]);
 const note = next.presentation!.notes![1]; expect(note.id).not.toBe('Note'); expect(note.text).toBe(source.presentation!.notes![0].text);
 expect(note.position).toEqual({ x: 20 + plan.result.delta.x, y: 280 + plan.result.delta.y });
});
it.each([3, 4, 5, 6, 7] as const)('never broadens the portable text contract to schema%s when local draft recovery supports it', schema => {
 const source = { ...graph(), schema_version: schema }; expect(() => exportTextGraphTemplate(source)).toThrow();
});
it.each(['grouped node budget', 'note budget', 'text budget', 'note boundary', 'extra receipt', 'wrong parent', 'unknown version'])('rejects %s atomically with no target mutation', mode => {
 const source = annotated(), target = blankGraph();
 if (mode === 'grouped node budget') { target.presentation = { groups: Array.from({ length: 16 }, (_, i) => ({ id: `G${i}`, name: '组', node_ids: [`Target${i}`] })) }; target.nodes = target.presentation.groups!.map(g => ({ ...graph().nodes[0], id: g.node_ids[0] })); }
 if (mode === 'note budget') target.presentation = { notes: Array.from({ length: 1024 }, (_, i) => ({ id: `N${i}`, text: '', position: { x: 0, y: 0 } })) };
 if (mode === 'text budget') target.presentation = { notes: Array.from({ length: 48 }, (_, i) => ({ id: `N${i}`, text: '字'.repeat(250), position: { x: 0, y: 0 } })) };
 if (mode === 'note boundary') source.presentation!.notes![0].position.x = 100_000;
 let raw = exportTextGraphTemplate(source); const row = JSON.parse(raw);
 if (mode === 'extra receipt') row.definition.presentation.groups[0].approved = true;
 if (mode === 'wrong parent') row.definition.presentation.groups[1].parent_id = 'Unknown';
 if (mode === 'unknown version') row.contract = 'poemseed-text-graph-template/999';
 raw = JSON.stringify(row); const before = structuredClone(target); expect(() => planTextGraphTemplate(raw, target, modelCatalog())).toThrow(); expect(target).toEqual(before);
});
it('rejects a generated visual-ID collision rather than aliasing an existing note', () => {
 const source = annotated(), target = blankGraph(); target.presentation = { notes: [{ id: 'Reserved', text: 'existing', position: { x: 0, y: 0 } }] };
 let i = 0; const spy = vi.spyOn(draftIds, 'graphId').mockImplementation((prefix = 'node') => prefix === 'group' ? 'Reserved' : `Fresh_${i++}`);
 try { expect(() => planTextGraphTemplate(exportTextGraphTemplate(source), target, modelCatalog())).toThrow(/视觉标识冲突/); expect(target.presentation.notes).toHaveLength(1); } finally { spy.mockRestore(); }
});
it('applies the original byte budget after adding visual author content', () => {
 const source = annotated(); source.presentation!.notes![0].text = '字'.repeat(256); const target = blankGraph();
 target.nodes = Array.from({ length: 4 }, (_, i) => ({ ...graph().nodes[0], id: `Existing_${i}`, parameters: { text: '字'.repeat(7850) } }));
 const before = structuredClone(target);
 const plain = structuredClone(source); delete plain.presentation;
 expect(() => planTextGraphTemplate(exportTextGraphTemplate(plain), target, modelCatalog())).not.toThrow();
 expect(() => planTextGraphTemplate(exportTextGraphTemplate(source), target, modelCatalog())).toThrow('模板追加将超过原图定义大小限制。');
 expect(target).toEqual(before);
});
it.each(['groups', 'notes'] as const)('retains schema2 %s without exporting graph comments or target view settings', field => {
 const source = annotated(); source.schema_version = 2;
 source.presentation = { [field]: source.presentation![field], comment: 'Private graph comment', view: { show_grid: true, snap: true, grid_step: 16, show_minimap: true } };
 const restored = readTextGraphTemplate(exportTextGraphTemplate(source));
 expect(restored.schema_version).toBe(2); expect(restored.presentation).toEqual({ [field]: source.presentation[field] });
});
