// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY WIRING] Real identity: import read-only ComfyUI nodes and
// sync the lower-canvas draft through the project API. No real backend/ComfyUI; fetch is mocked.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, waitFor, within} from '@testing-library/react';
import {DualStack} from './DualStack';
import {sessionCanvasStore} from './RebuildCanvas';
import {useStudio} from '../../store';

const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const lower = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;

const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => ({
  ok: status < 400, status, json: async () => value,
  headers: {get: (key: string) => headers[key.toLowerCase()] ?? headers[key] ?? null},
} as unknown as Response);

beforeEach(() => {
  cleanup(); localStorage.clear(); sessionCanvasStore.clear();
  useStudio.setState({novelId: 'n1', actor: {id: 'actor-1', displayName: 'A', workspaceId: 'ws1'} as never,
    scope: COLLAB as never, sessionToken: 'session-a'});
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  useStudio.setState({actor: undefined, scope: undefined, sessionToken: ''}); });

it('real identity: imports object_info, loads the cloud draft and saves edits with CAS version', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/api/comfy/object_info')) {
      return json({CustomNodeX: {input: {required: {}}, output: ['IMAGE'], category: 'custom', display_name: 'Custom X'}},
        200, {'x-comfy-source-version': 'source-1'});
    }
    if (url.includes('/studio/lower-canvas/image') && (!init?.method || init.method === 'GET')) {
      return json({kind: 'image', version: 2, graph: {nodes: [{id: 'remote-1', t: 'KSampler', x: 100, y: 100, title: '云端 K 采样器'}], edges: []}});
    }
    if (url.includes('/studio/lower-canvas/image') && init?.method === 'PUT') {
      return json({kind: 'image', version: 3, graph: JSON.parse(String(init.body)).graph});
    }
    return json({detail: {code: 'NOT_FOUND'}}, 404);
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<DualStack kind="image" scope="n1" />);
  await waitFor(() => expect(document.querySelector('[data-node-id="remote-1"]')).toBeTruthy());
  expect(lower().querySelector('[data-comfy-status]')!.getAttribute('data-comfy-remote')).toBe('ready');

  // imported object_info node is available in the lower palette (merged on top of built-ins)
  fireEvent.contextMenu(within(lower()).getByRole('application'), {clientX: 40, clientY: 40});
  const option = await waitFor(() => {
    const found = lower().querySelector('[data-add-node-menu] [data-node-type="CustomNodeX"]');
    expect(found).toBeTruthy();
    return found as HTMLElement;
  });
  fireEvent.click(option);

  await waitFor(() => {
    const put = fetchMock.mock.calls.find(([url, init]) =>
      String(url).includes('/studio/lower-canvas/image') && (init as RequestInit | undefined)?.method === 'PUT');
    expect(put).toBeTruthy();
  }, {timeout: 4000});
  const putCall = fetchMock.mock.calls.find(([url, init]) =>
    String(url).includes('/studio/lower-canvas/image') && (init as RequestInit | undefined)?.method === 'PUT')!;
  const body = JSON.parse(String((putCall[1] as RequestInit).body));
  expect(body.expected_version).toBe(2);
  expect(body.graph.nodes).toHaveLength(2);
  expect(body.graph.nodes[1].t).toBe('CustomNodeX');
  expect((putCall[1] as RequestInit).headers).toMatchObject({'X-Session-Token': 'session-a', 'X-Branch-Id': 'b1'});
});
