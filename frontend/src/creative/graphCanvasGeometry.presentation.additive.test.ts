// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { describe, expect, it } from 'vitest';
import { alignGraphNodes, snapGraphNodes, removeGraphNodes } from './graphCanvasGeometry';

import type { StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';

const node = (id: string, x = 0, y = 0): StudioGraphNode => ({ id, definition_id: 'text_input', definition_version: 1, enabled: true, position: { x, y }, parameters: { text: '' } });
const graph = (): StudioGraphDefinition => ({ schema_version: 1, title: '节点图', nodes: [node('one', 10, 20), node('two', 700, 400)], edges: [{ id: 'link', source_node_id: 'one', source_port: 'text', target_node_id: 'two', target_port: 'text' }], viewport: { x: 100, y: -80, zoom: 2 } });

describe('typed graph domain geometry', () => {
  it('cleans deleted group membership and drops empty groups without touching protected nodes or comments', () => {
    const definition: StudioGraphDefinition = { ...graph(), presentation: { comment: '', groups: [
      { id: 'g', name: 'Group', node_ids: ['one', 'two'] }] } };
    const kept = removeGraphNodes(definition, ['one', 'two'], ['two']);
    expect(kept.presentation).toEqual({ comment: '', groups: [{ id: 'g', name: 'Group', node_ids: ['two'] }] });
    expect(removeGraphNodes(kept, ['two']).presentation).toEqual({ comment: '' });
    const groupsOnly = { ...definition, presentation: { groups: definition.presentation!.groups } };
    expect(removeGraphNodes(groupsOnly, ['one', 'two'])).not.toHaveProperty('presentation');
    expect(definition.presentation!.groups![0].node_ids).toEqual(['one', 'two']);
  });
});

describe('selected alignment geometry', () => {
  it('aligns left, center and top in world coordinates without changing other data', () => {
    const before = graph(); before.nodes.push(node('outside', -800, -900));
    before.nodes[0].parameters = { text: 'dirty', document_snapshot: { id: 'pin', version: 7, digest: 'a'.repeat(64) } };
    const snapshot = structuredClone(before);
    for (const [mode, expected] of [['left', [{ x: 10, y: 20 }, { x: 10, y: 400 }]], ['center', [{ x: 355, y: 20 }, { x: 355, y: 400 }]], ['top', [{ x: 10, y: 20 }, { x: 700, y: 20 }]]] as const) {
      const after = alignGraphNodes(before, ['two', 'one'], mode);
      expect(after.nodes.slice(0, 2).map(n => n.position)).toEqual(expected);
      expect(after.nodes[2]).toBe(before.nodes[2]); expect(after.edges).toBe(before.edges); expect(after.viewport).toBe(before.viewport);
      expect(after.nodes[0].parameters).toBe(before.nodes[0].parameters);
    }
    expect(before).toEqual(snapshot);
  });
  it('distributes deterministically while preserving endpoints, y and source order', () => {
    const before = graph(); before.nodes = [node('right', 100000, 5), node('middle', -90000, 6), node('left', -100000, 7)];
    const after = alignGraphNodes(before, ['middle', 'left', 'right'], 'distribute');
    expect(after.nodes.map(n => [n.id, n.position])).toEqual([['right', { x: 100000, y: 5 }], ['middle', { x: 0, y: 6 }], ['left', { x: -100000, y: 7 }]]);
    expect(alignGraphNodes(after, ['left', 'middle', 'right'], 'distribute')).toBe(after);
  });
  it('rejects invalid geometry, missing selection and insufficient counts without repair', () => {
    const before = graph();
    expect(alignGraphNodes(before, ['one'], 'left')).toBe(before);
    expect(alignGraphNodes(before, ['one', 'two'], 'distribute')).toBe(before);
    expect(alignGraphNodes(before, ['one', 'two', 'stale'], 'left')).toBe(before);
    for (const value of [NaN, Infinity, -Infinity, 100001, -100001]) {
      const bad = graph(); bad.nodes[0].position.x = value;
      expect(alignGraphNodes(bad, ['one', 'two'], 'center')).toBe(bad);
    }
  });
});

describe('world-grid group snapping', () => {
  it.each([0.35, 1, 2.5])('snaps the grabbed anchor at zoom %s without changing group offsets', zoom => {
    const original = graph(); original.viewport.zoom = zoom;
    const next = snapGraphNodes(original, ['one', 'two'], 'two', { x: 17 * zoom, y: -19 * zoom }, 24);
    expect(next.nodes[1].position).toEqual({ x: 720, y: 384 });
    expect(next.nodes[0].position).toEqual({ x: 30, y: 4 });
    expect(next.edges).toBe(original.edges); expect(next.viewport).toBe(original.viewport);
    expect(original.nodes[0].position).toEqual({ x: 10, y: 20 });
  });
  it('bounds the common translation rather than squashing group offsets at either limit', () => {
    const original = graph(); original.nodes = [node('one', 99997, -99999), node('two', 99990, -99990)];
    const next = snapGraphNodes(original, ['one', 'two'], 'two', { x: 1000, y: -1000 }, 32);
    expect(next.nodes[0].position).toEqual({ x: 100000, y: -100000 });
    expect(next.nodes[1].position).toEqual({ x: 99993, y: -99991 });
  });
  it('rejects invalid input, stale selection and a zero drag', () => {
    const original = graph();
    for (const [ids, anchor, delta, step] of [
      [['one'], 'missing', { x: 1, y: 2 }, 24], [['one', 'missing'], 'one', { x: 1, y: 2 }, 24],
      [['one'], 'one', { x: NaN, y: 2 }, 24], [['one'], 'one', { x: 1, y: 2 }, 0],
      [['one'], 'one', { x: 0, y: 0 }, 24],
    ] as const) expect(snapGraphNodes(original, ids, anchor, delta, step)).toBe(original);
    original.nodes[0].position.x = Infinity;
    expect(snapGraphNodes(original, ['one'], 'one', { x: 1, y: 2 }, 24)).toBe(original);
  });
});
