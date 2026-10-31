// @vitest-environment jsdom
// [HERMIA-FE-20261031 COMFY INPUT ASSETS] Bind a Studio image asset to a ComfyUI file widget;
// the binding is persisted in the lower canvas draft and later uploaded server-side.
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, waitFor} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {sessionCanvasStore} from '../RebuildCanvas';
import {useStudio} from '../../../store';

const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const json = (value: unknown, status = 200) => ({
  ok: status < 400, status, json: async () => value,
  headers: {get: () => null},
} as unknown as Response);

beforeEach(() => {
  cleanup(); localStorage.clear(); sessionCanvasStore.clear();
  useStudio.setState({novelId: 'n1', actor: {id: 'actor-1', displayName: 'A', workspaceId: 'ws1'} as never,
    scope: COLLAB as never, sessionToken: 'session-a'});
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  useStudio.setState({actor: undefined, scope: undefined, sessionToken: ''}); });

it('binds a Studio asset to a file widget and saves inputAssets with the draft', async () => {
  const lower = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
  const calls: {url: string; method: string; body?: string}[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    calls.push({url, method, body: init?.body as string | undefined});
    if (url.endsWith('/api/comfy/object_info')) {
      return json({LoadImage: {input: {required: {image: [['server.png']]}}, output: ['IMAGE'],
        output_name: ['IMAGE'], category: 'image', display_name: 'Load Image'}});
    }
    if (url.includes('/studio/assets?kind=image')) {
      return json({items: [{id: 'asset-ref-1', filename: 'ref.png', kind: 'image',
        media_type: 'image/png', version: 1}]});
    }
    if (url.includes('/studio/lower-canvas/image') && method === 'GET') {
      return json({kind: 'image', version: 1, graph: {nodes: [{id: 'load1', t: 'LoadImage', x: 10, y: 10, title: 'load'}], edges: []}});
    }
    if (url.includes('/studio/lower-canvas/image') && method === 'PUT') {
      return json({kind: 'image', version: 2, graph: JSON.parse(String(init?.body)).graph});
    }
    return json({detail: {code: 'NOT_FOUND'}}, 404);
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<DualStack kind="image" scope="n1" />);
  await waitFor(() => expect(document.querySelector('[data-comfy-remote="ready"]')).toBeTruthy());
  const node = await waitFor(() => {
    const found = lower().querySelector('[data-node-id="load1"]');
    expect(found).toBeTruthy();
    return found as HTMLElement;
  });
  fireEvent.pointerDown(node, {clientX: 12, clientY: 12, pointerId: 1});
  const select = await waitFor(() => {
    const found = lower().querySelector('[data-comfy-params] [data-asset-binding="image"]') as HTMLSelectElement | null;
    expect(found).toBeTruthy();
    expect(found!.querySelector('option[value="asset-ref-1"]')?.textContent).toContain('ref.png');
    return found!;
  });
  fireEvent.change(select, {target: {value: 'asset-ref-1'}});
  await waitFor(() => expect((lower().querySelector('[data-asset-binding="image"]') as HTMLSelectElement).value).toBe('asset-ref-1'));
  const localKey = Object.keys(localStorage).find(k => k.includes('dualcv.lower'));

  await waitFor(() => {
    const puts = calls.filter(c => c.url.includes('/studio/lower-canvas/image') && c.method === 'PUT');
    expect(puts.length).toBeGreaterThan(0);
    const nodes = JSON.parse(String(puts[puts.length - 1].body)).graph.nodes;
    expect(nodes[0].input_assets).toEqual({image: 'asset-ref-1'});
    expect(nodes[0].inputAssets).toBeUndefined();
  }, {timeout: 4000});
});
