import { describe, expect, it } from 'vitest';
import { createGraphDisplayIndex, projectGraphDisplay } from './graphCanvasPresentation';
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
