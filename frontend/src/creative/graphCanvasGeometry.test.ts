// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import {
  GRAPH_NODE_HEADER_HEIGHT, GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT, GRAPH_POSITION_LIMIT,
  alignGraphNodes, snapGraphNodes, clampGraphZoom, graphEdgePath, graphNodeHeight, graphNodesInScreenRect, graphPortPosition,
  graphScreenToWorld, graphSelectionRect, graphWorldToScreen, isGraphEditableTarget, moveGraphNodes, removeGraphNodes, zoomGraphAt,
} from './graphCanvasGeometry';
import type { GraphCanvasNodeDefinition } from './graphCanvasGeometry';
import type { StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';

const descriptors: GraphCanvasNodeDefinition[] = [
  { id: 'text_input', inputs: [], outputs: [{ id: 'text', type: 'TEXT' }] },
  { id: 'draft_prepare', inputs: [{ id: 'text', type: 'TEXT' }, { id: 'direction', type: 'DIRECTOR_NOTES' }], outputs: [{ id: 'draft', type: 'DRAFT' }] },
];
const node = (id: string, x = 0, y = 0): StudioGraphNode => ({ id, definition_id: 'text_input', definition_version: 1, enabled: true, position: { x, y }, parameters: { text: '' } });
const graph = (): StudioGraphDefinition => ({ schema_version: 1, title: '节点图', nodes: [node('one', 10, 20), node('two', 700, 400)], edges: [{ id: 'link', source_node_id: 'one', source_port: 'text', target_node_id: 'two', target_port: 'text' }], viewport: { x: 100, y: -80, zoom: 2 } });

describe('typed graph domain geometry', () => {
  it('round-trips positions through panned and zoomed coordinate systems', () => {
    const viewport = { x: -57, y: 91, zoom: 0.35 }, point = { x: -240, y: 380 };
    const screen = graphWorldToScreen(point, viewport);
    expect(graphScreenToWorld(screen, viewport).x).toBeCloseTo(point.x);
    expect(graphScreenToWorld(screen, viewport).y).toBeCloseTo(point.y);
  });

  it('preserves the cursor world anchor while clamping zoom', () => {
    const viewport = { x: -20, y: 40, zoom: 1 }, anchor = { x: 200, y: 120 };
    const before = graphScreenToWorld(anchor, viewport), next = zoomGraphAt(viewport, anchor, 10);
    expect(next.zoom).toBe(2.5);
    expect(graphScreenToWorld(anchor, next)).toEqual(before);
    expect(clampGraphZoom(0.01)).toBe(0.35);
    expect(clampGraphZoom(Number.NaN)).toBe(1);
  });

  it('normalizes reverse marquee directions and scales intersection bounds', () => {
    const rect = graphSelectionRect({ x: 790, y: 250 }, { x: 115, y: -45 });
    expect(rect).toEqual({ x: 115, y: -45, width: 675, height: 295 });
    expect(graphNodesInScreenRect(graph().nodes, rect, graph().viewport, descriptors)).toEqual(['one']);
  });

  it('uses the real typed-port node height when selecting its lower row', () => {
    const target = { ...node('prepare'), definition_id: 'draft_prepare' as const };
    expect(graphNodeHeight(descriptors[1])).toBe(GRAPH_NODE_HEADER_HEIGHT + 2 * GRAPH_PORT_ROW_HEIGHT);
    const rect = { x: 10, y: 145, width: 10, height: 10 };
    expect(graphNodesInScreenRect([target], rect, { x: 0, y: 0, zoom: 1 }, descriptors)).toEqual(['prepare']);
  });

  it('moves only selected nodes by inverse zoom without mutating the definition', () => {
    const before = graph(), next = moveGraphNodes(before, ['one'], { x: 40, y: -24 });
    expect(next.nodes[0].position).toEqual({ x: 30, y: 8 });
    expect(before.nodes[0].position).toEqual({ x: 10, y: 20 });
    expect(next.nodes[1]).toBe(before.nodes[1]);
    expect(next.edges).toBe(before.edges);
    expect(next.viewport).toBe(before.viewport);
  });

  it('clamps node and viewport positions to backend finite geometry bounds', () => {
    const before = graph(); before.nodes[0].position = { x: GRAPH_POSITION_LIMIT, y: -GRAPH_POSITION_LIMIT };
    expect(moveGraphNodes(before, ['one'], { x: 30, y: -30 }).nodes[0].position).toEqual(before.nodes[0].position);
    const next = zoomGraphAt({ x: GRAPH_POSITION_LIMIT, y: -GRAPH_POSITION_LIMIT, zoom: 0.35 }, { x: 0, y: 0 }, 2.5);
    expect(next.x).toBe(GRAPH_POSITION_LIMIT); expect(next.y).toBe(-GRAPH_POSITION_LIMIT);
  });

  it('anchors each typed port at its actual row and follows moved nodes', () => {
    const target = { ...node('prepare', 500, 100), definition_id: 'draft_prepare' as const };
    const output = graphPortPosition(node('one', 10, 20), descriptors[0], 'output', 'text')!;
    const input = graphPortPosition(target, descriptors[1], 'input', 'direction')!;
    expect(output).toEqual({ x: 10 + GRAPH_NODE_WIDTH, y: 20 + GRAPH_NODE_HEADER_HEIGHT + GRAPH_PORT_ROW_HEIGHT / 2 });
    expect(input).toEqual({ x: 500, y: 100 + GRAPH_NODE_HEADER_HEIGHT + GRAPH_PORT_ROW_HEIGHT * 1.5 });
    expect(graphEdgePath(output, input)).toMatch(/^M 330 108 C /);
    expect(graphPortPosition(target, descriptors[1], 'input', 'missing')).toBeNull();
    expect(graphPortPosition(target, undefined, 'input', 'text')).toBeNull();
  });

  it('deletes incident edges atomically but preserves protected references', () => {
    const before = graph(), protectedResult = removeGraphNodes(before, ['one', 'two'], ['one']);
    expect(protectedResult.nodes.map(item => item.id)).toEqual(['one']);
    expect(protectedResult.edges).toEqual([]);
    expect(removeGraphNodes(before, ['one'], ['one']).edges).toEqual(before.edges);
    expect(before.nodes).toHaveLength(2);
  });

  it('recognizes nested editable content and all form controls as shortcut exclusions', () => {
    for (const tag of ['input', 'textarea', 'select']) expect(isGraphEditableTarget(document.createElement(tag))).toBe(true);
    const editor = document.createElement('div'), child = document.createElement('span');
    editor.setAttribute('contenteditable', 'true'); editor.append(child);
    expect(isGraphEditableTarget(child)).toBe(true);
    editor.setAttribute('contenteditable', 'false'); expect(isGraphEditableTarget(child)).toBe(false);
    editor.setAttribute('role', 'textbox'); expect(isGraphEditableTarget(child)).toBe(true);
    expect(isGraphEditableTarget(null)).toBe(false);
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
