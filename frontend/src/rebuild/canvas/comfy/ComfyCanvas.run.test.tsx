// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY RUN] Quote → explicit confirm → completed local run.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, waitFor} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {canvasStorageKey, sessionCanvasStore} from '../RebuildCanvas';
import {useStudio} from '../../../store';

const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const quote = {
  quote_id: 'lcq_' + 'a'.repeat(24), quote_digest: 'b'.repeat(64), kind: 'image', draft_version: 2,
  provider_id: 'comfy', node_count: 1, edge_count: 0, output_nodes: ['remote-save'],
  price: {currency: 'USD', amount_micros: 0, reason: 'LOCAL_COMFYUI_NO_BILLING'},
  expires_at: '2099-01-01T00:00:00+00:00', confirmation_required: true,
};
const run = {
  contract: 'studio-lower-canvas-run/1', id: 'lcr_run1', kind: 'image', status: 'COMPLETED',
  draft_version: 2, quote_digest: quote.quote_digest, provider_id: 'comfy', node_count: 1,
  edge_count: 0, output_nodes: ['remote-save'],
  assets: [{id: 'asset-out-1', kind: 'image', version: 1, filename: 'out.png', media_type: 'image/png', sha256: 'c'.repeat(64), size: 4},
    {id: 'asset-video-1', kind: 'video', version: 1, filename: 'out.mp4', media_type: 'video/mp4', sha256: 'd'.repeat(64), size: 4}],
  error: null, created_at: '2026-10-31T00:00:00+00:00', updated_at: '2026-10-31T00:00:00+00:00',
};

const blobResponse = (value: Blob) => ({
  ok: true, status: 200, blob: async () => value,
  headers: {get: () => null},
} as unknown as Response);
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => ({
  ok: status < 400, status, json: async () => value,
  headers: {get: (key: string) => headers[key.toLowerCase()] ?? headers[key] ?? null},
} as unknown as Response);

beforeEach(() => {
  cleanup(); localStorage.clear(); sessionCanvasStore.clear();
  Object.assign(URL, {createObjectURL: vi.fn(() => 'blob:mock-result'), revokeObjectURL: vi.fn()});
  useStudio.setState({novelId: 'n1', actor: {id: 'actor-1', displayName: 'A', workspaceId: 'ws1'} as never,
    scope: COLLAB as never, sessionToken: 'session-a'});
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  useStudio.setState({actor: undefined, scope: undefined, sessionToken: ''}); });

it('requires a quote confirmation before dispatching and shows the completed assets', async () => {
  const calls: {url: string; method: string; body?: string}[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    calls.push({url, method, body: init?.body as string | undefined});
    if (url.endsWith('/api/comfy/object_info')) return json({});
    if (url.includes('/studio/lower-canvas/image') && method === 'GET') {
      return json({kind: 'image', version: 1, graph: {nodes: [{id: 'remote-save', t: 'SaveImage', x: 10, y: 10, title: 'save'}], edges: []}});
    }
    if (url.includes('/studio/lower-canvas/image') && method === 'PUT') {
      return json({kind: 'image', version: 2, graph: JSON.parse(String(init?.body)).graph});
    }
    if (url.endsWith('/studio/lower-canvas/image/runs/preflight') && method === 'POST') return json(quote);
    if (url.endsWith('/studio/lower-canvas/image/runs') && method === 'POST') return json(run);
    if (url.endsWith('/studio/assets/asset-out-1/download')) return blobResponse(new Blob([new Uint8Array([1, 2, 3, 4])], {type: 'image/png'}));
    if (url.endsWith('/studio/assets/asset-video-1/download')) return blobResponse(new Blob([new Uint8Array([5, 6, 7, 8])], {type: 'video/mp4'}));
    return json({detail: {code: 'NOT_FOUND'}}, 404);
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<DualStack kind="image" scope="n1" />);
  await waitFor(() => expect(document.querySelector('[data-comfy-remote="ready"]')).toBeTruthy());
  fireEvent.click(document.querySelector('[data-comfy-run]')!);
  const panel = await waitFor(() => {
    const found = document.querySelector('[data-comfy-run-quote]');
    expect(found).toBeTruthy();
    return found as HTMLElement;
  });
  expect(panel.textContent).toContain('本地 ComfyUI');
  expect(panel.textContent).toContain('运行报价');

  const preflight = calls.find(c => c.url.endsWith('/runs/preflight'))!;
  expect(preflight.method).toBe('POST');
  expect(JSON.parse(String(preflight.body))).toEqual({expected_version: 2});
  const preflightFetch = fetchMock.mock.calls.find(c => String(c[0]).endsWith('/runs/preflight'));
  expect((preflightFetch?.[1] as RequestInit | undefined)?.headers)
    .toMatchObject({'X-Session-Token': 'session-a', 'X-Branch-Id': 'b1'});

  fireEvent.click(panel.querySelector('[data-run-confirm]')!);
  const result = await waitFor(() => {
    const found = document.querySelector('[data-comfy-run-result]');
    expect(found).toBeTruthy();
    return found as HTMLElement;
  }, {timeout: 4000});
  expect(result.getAttribute('data-run-status')).toBe('COMPLETED');
  expect(result.textContent).toContain('运行完成');
  expect(result.querySelector('[data-run-asset="asset-out-1"]')).toBeTruthy();
  expect(result.textContent).toContain('out.png');
  await waitFor(() => expect(document.querySelector('[data-run-thumb]')).toBeTruthy());
  await waitFor(() => expect(document.querySelector('[data-run-thumb-video]')).toBeTruthy());
  expect(document.querySelector('[data-run-asset="asset-video-1"] [data-run-adopt]')).toBeNull();
  fireEvent.click(document.querySelector('[data-run-adopt]')!);
  const upper = JSON.parse(localStorage.getItem(canvasStorageKey('image', 'n1'))!);
  expect(upper.nodes[0]).toMatchObject({t: 'image_reference', assetId: 'asset-out-1',
    assetSha256: 'c'.repeat(64), assetVersion: 1});

  const dispatch = calls.find(c => c.url.endsWith('/studio/lower-canvas/image/runs') && c.method === 'POST')!;
  expect(JSON.parse(String(dispatch.body))).toEqual({
    expected_version: 2, quote_id: quote.quote_id, quote_digest: quote.quote_digest,
  });
});

it('keeps the run button disabled until the cloud draft is ready', async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).endsWith('/api/comfy/object_info')) return json({});
    if (String(url).includes('/studio/lower-canvas/image') && (init?.method ?? 'GET') === 'GET') {
      return Promise.reject(new TypeError('offline'));
    }
    return json({}, 500);
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<DualStack kind="image" scope="n1" />);
  const button = await waitFor(() => {
    const found = document.querySelector('[data-comfy-run]') as HTMLButtonElement | null;
    expect(found).toBeTruthy();
    return found!;
  });
  await waitFor(() => expect(document.querySelector('[data-comfy-remote="unavailable"]')).toBeTruthy());
  expect(button.disabled).toBe(true);
});
