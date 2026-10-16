import { describe, expect, it } from 'vitest';
import { collapseGraphDisplay, createGraphDisplayIndex, projectGraphDisplay, projectGraphMiniMap } from './graphCanvasPresentation';
import type { GraphDisplayNode } from './graphCanvasPresentation';
import type { GraphCanvasNodeDefinition } from './graphCanvasGeometry';
const definitions: GraphCanvasNodeDefinition[] = [{ id: 'text_input', inputs: [{ id: 'in', type: 'TEXT' }], outputs: [{ id: 'out', type: 'TEXT' }] }];
const node = (id: string, x: number, y = 0): GraphDisplayNode => ({ id, definition_id: 'text_input', position: { x, y } });
const edge = (id: string, source_node_id: string, target_node_id: string) => ({ id, source_node_id, target_node_id, source_port: 'out', target_port: 'in' });
const viewport = { x: 0, y: 0, zoom: 1 }, size = { width: 800, height: 400 };
describe('disposable canvas presentation projection', () => {
  it('culls offscreen cards while preserving boundary intersections and explicit retained IDs', () => {
    const index = createGraphDisplayIndex([node('left', -321), node('touch', -320), node('in', 20), node('right', 801), node('below', 0, 401)], [], definitions);
    expect([...projectGraphDisplay(index, viewport, size, [], 0).nodeIds]).toEqual(['touch', 'in']);
    expect([...projectGraphDisplay(index, viewport, size, ['left', 'right', 'below'], 0).nodeIds]).toEqual(['left', 'right', 'below', 'touch', 'in']);
  });
  it('keeps overscan in screen pixels across zoom and pan, and recomputes on resize', () => {
    const index = createGraphDisplayIndex([node('near', 470), node('far', 481)], [], definitions);
    expect([...projectGraphDisplay(index, { x: 0, y: 0, zoom: 2 }, size).nodeIds]).toEqual(['near']);
    expect(projectGraphDisplay(index, { x: -200, y: 0, zoom: 2 }, size).nodeIds.size).toBe(2);
    expect(projectGraphDisplay(index, viewport, { width: 100, height: 400 }).nodeIds.size).toBe(0);
  });
  it('does not cull before a valid measured layout or for a hidden viewport', () => {
    const index = createGraphDisplayIndex([node('far', 90000)], [], definitions);
    for (const layout of [null, { width: 0, height: 0 }, { width: NaN, height: 400 }]) expect(projectGraphDisplay(index, viewport, layout).nodeIds.has('far')).toBe(true);
  });
  it('keeps crossing and reversed curves with offscreen endpoints, culls distant edges and skips broken ports', () => {
    const index = createGraphDisplayIndex([node('left', -1000), node('right', 2000), node('below', 2000, 2000)],
      [edge('cross', 'left', 'right'), edge('reverse', 'right', 'left'), edge('far', 'below', 'below'), edge('missing', 'left', 'absent'), { ...edge('port', 'left', 'right'), target_port: 'invalid' }], definitions);
    const projection = projectGraphDisplay(index, viewport, size, [], 0);
    expect(projection.nodeIds.size).toBe(0); expect(projection.edges.map(item => item.id)).toEqual(['cross', 'reverse']);
  });
  it('preserves tall port rows and does not mutate display inputs or retain execution parameters', () => {
    const nodes = [node('tall', 20, -300)]; const before = JSON.stringify(nodes);
    const index = createGraphDisplayIndex(nodes, [], [{ ...definitions[0], inputs: Array.from({ length: 8 }, (_, id) => ({ id: String(id), type: 'TEXT' })) }]);
    expect(projectGraphDisplay(index, viewport, size, [], 0).nodeIds.has('tall')).toBe(true);
    expect(JSON.stringify(nodes)).toBe(before); expect(Object.keys(index.cards[0])).toEqual(['id', 'bounds']);
  });
  it('projects 1000 display-only objects without creating an executable graph or losing offscreen data', () => {
    const nodes = Array.from({ length: 1000 }, (_, id) => node(String(id), (id % 40) * 500, Math.floor(id / 40) * 300));
    const index = createGraphDisplayIndex(nodes, [], definitions);
    expect(projectGraphDisplay(index, viewport, size).nodeIds.size).toBe(4);
    expect(projectGraphDisplay(index, { x: -19500, y: -7200, zoom: 1 }, size).nodeIds.has('999')).toBe(true);
    expect(nodes).toHaveLength(1000); expect(index.cards).toHaveLength(1000);
  });
});

describe('MiniMap geometry', () => {
  it('includes every card, edge extent and the current camera in bounded display coordinates', () => {
    const index = createGraphDisplayIndex([node('left', -100000), node('right', 100000, 100000)], [edge('reverse', 'right', 'left')], definitions);
    const map = projectGraphMiniMap(index, { x: -100000, y: 100000, zoom: 0.35 }, size);
    expect(map.cards).toHaveLength(2);
    for (const rect of [...map.cards.map(card => card.bounds), map.camera!]) {
      expect(rect.x).toBeGreaterThanOrEqual(0); expect(rect.y).toBeGreaterThanOrEqual(0);
      expect(rect.x + rect.width).toBeLessThanOrEqual(200); expect(rect.y + rect.height).toBeLessThanOrEqual(120);
    }
    const point = map.worldAt(map.cards[0].bounds.x, map.cards[0].bounds.y);
    expect(point.x).toBeCloseTo(-100000); expect(point.y).toBeCloseTo(0);
  });
  it('handles empty, unmeasured, invalid, huge and resized display geometry without NaN', () => {
    const index = createGraphDisplayIndex([node('huge', 1e12), node('invalid', Infinity)], [], definitions);
    const map = projectGraphMiniMap(index, viewport, size);
    expect(map.cards.map(card => card.id)).toEqual(['huge']);
    expect(JSON.stringify(map)).not.toMatch(/null/);
    expect(projectGraphMiniMap(index, viewport, null).camera).toBeNull();
    expect(projectGraphMiniMap(index, viewport, { width: NaN, height: 0 }).camera).toBeNull();
    expect(projectGraphMiniMap(index, viewport, { width: 1600, height: 800 }).camera!.width).toBeGreaterThan(map.camera!.width);
    expect(projectGraphMiniMap(createGraphDisplayIndex([], [], []), viewport, null).cards).toEqual([]);
  });
  it('projects 1000 display objects without changing source objects or executable budgets', () => {
    const index = createGraphDisplayIndex(Array.from({ length: 1000 }, (_, id) => node(String(id), id * 500)), [], definitions);
    expect(projectGraphMiniMap(index, viewport, size).cards).toHaveLength(1000);
    expect(index.cards[999].bounds.x).toBe(499500);
  });
});


describe('derived visual group frames', () => {
  const groups = [{ id: 'scene', name: '场景 🎬', node_ids: ['a', 'b'] }];
  it('bounds all member cards including tall ports with label band and gutter, without mutation', () => {
    const nodes = [node('a', -100, -50), node('b', 500, 200)];
    const before = JSON.stringify({ nodes, groups });
    const index = createGraphDisplayIndex(nodes, [], [{ ...definitions[0], inputs: Array.from({ length: 4 }, (_, i) => ({ id: String(i), type: 'TEXT' })) }], groups);
    expect(index.frames[0].bounds).toEqual({ x: -116, y: -98, width: 952, height: 570 });
    expect(index.frames[0].nodeIds).toEqual(['a', 'b']);
    expect(JSON.stringify({ nodes, groups })).toBe(before);
    expect(projectGraphMiniMap(index, viewport, size).cards).toHaveLength(2);
  });
  it('keeps crossing frames when all members are culled; culls distant frames, retaining focused labels', () => {
    const index = createGraphDisplayIndex([node('a', -1000), node('b', 2000)], [], definitions, groups);
    expect(projectGraphDisplay(index, viewport, size, [], 0).nodeIds.size).toBe(0);
    expect(projectGraphDisplay(index, viewport, size, [], 0).frames).toHaveLength(1);
    expect(projectGraphDisplay(index, { x: 0, y: -5000, zoom: 2.5 }, size, [], 0).frames).toHaveLength(0);
    expect(projectGraphDisplay(index, { x: 0, y: -5000, zoom: 2.5 }, size, [], 0, 'scene').frames).toHaveLength(1);
    expect(projectGraphDisplay(index, viewport, null).frames).toHaveLength(1);
  });
  it('does not fabricate dangling/empty/invalid frames and renders control-stripped plain labels', () => {
    const index = createGraphDisplayIndex([node('a', 0), node('b', Infinity)], [], definitions,
      [...groups, { id: 'empty', name: 'Empty', node_ids: [] }, { id: 'missing', name: 'Missing', node_ids: ['absent'] },
        { id: 'valid', name: '<img>\u202e\n标题', node_ids: ['a'] }]);
    expect(index.frames).toHaveLength(1);
    expect(index.frames[0].label).toBe('<img>  标题');
    expect(createGraphDisplayIndex([node('a', 0)], [], definitions).frames).toEqual([]);
  });
});


describe('non-executable collapse projection', () => {
  it('counts internal, incoming, outgoing and group-to-group edges exactly without synthetic endpoints', () => {
    const nodes = [node('a', 0), node('b', 500), node('c', 1000), node('d', 1500)];
    const edges = [edge('internal', 'a', 'b'), edge('out', 'a', 'c'), edge('in', 'c', 'b'), edge('other', 'c', 'd')];
    const index = createGraphDisplayIndex(nodes, edges, definitions, [{ id: 'g', name: 'G', node_ids: ['a', 'b'] }, { id: 'h', name: 'H', node_ids: ['c'] }]);
    const before = JSON.stringify({ index, nodes, edges });
    const result = collapseGraphDisplay(index, edges, ['g'], []);
    expect(result.index.cards.map(card => card.id)).toEqual(['c', 'd']);
    expect(result.index.connections).toEqual(index.connections.filter(item => item.id === 'other'));
    expect(result.summaries[0].externalEdges.map(item => item.id)).toEqual(['out', 'in']);
    expect(result.summaries[0].internalCount).toBe(1);
    expect(collapseGraphDisplay(index, edges, ['g', 'h'], []).index.connections).toEqual([]);
    expect(collapseGraphDisplay(index, edges, ['g'], ['b']).index).toEqual(index);
    expect(JSON.stringify({ index, nodes, edges })).toBe(before);
  });
  it('culls by compact card extent and can retain focused collapsed groups', () => {
    const index = createGraphDisplayIndex([node('a', -1000), node('b', 2000)], [], definitions, [{ id: 'g', name: 'G', node_ids: ['a', 'b'] }]);
    const collapsed = collapseGraphDisplay(index, [], ['g'], []).index;
    expect(projectGraphDisplay(collapsed, viewport, size, [], 0).frames).toEqual([]);
    expect(projectGraphDisplay(collapsed, viewport, size, [], 0, 'g').frames).toHaveLength(1);
    expect(projectGraphDisplay(collapsed, viewport, null).nodeIds.size).toBe(0);
  });
});

it('projects two-level descendant bounds, selection and nonduplicated collapse with retained anchors', () => {
  const groups = [{ id: 'root', name: 'Root', node_ids: ['a'] }, { id: 'child', name: 'Child', node_ids: ['b'], parent_id: 'root' }];
  const edges = [edge('internal', 'a', 'b'), edge('external', 'b', 'c')];
  const index = createGraphDisplayIndex([node('a', 0), node('b', 2000), node('c', 3000)], edges, definitions, groups);
  const root = index.frames[0], child = index.frames[1];
  expect(root.nodeIds).toEqual(['a', 'b']);
  expect(root.bounds.x).toBeLessThan(child.bounds.x);
  expect(root.bounds.y).toBeLessThan(child.bounds.y);
  expect(root.bounds.x + root.bounds.width).toBeGreaterThan(child.bounds.x + child.bounds.width);
  const folded = collapseGraphDisplay(index, edges, ['root', 'child'], []);
  expect(folded.summaries.map(item => item.id)).toEqual(['root']);
  expect(folded.index.frames.map(item => item.id)).toEqual(['root']);
  expect(folded.summaries[0].internalCount).toBe(1);
  expect(folded.summaries[0].externalEdges.map(item => item.id)).toEqual(['external']);
  expect([...folded.hiddenNodeIds]).toEqual(['a', 'b']);
  expect(collapseGraphDisplay(index, edges, ['root', 'child'], ['b']).hiddenNodeIds.size).toBe(0);
  expect(projectGraphDisplay(index, { x: -2000, y: 0, zoom: 1 }, size, [], 0).frames.map(item => item.id)).toEqual(['root', 'child']);
});
