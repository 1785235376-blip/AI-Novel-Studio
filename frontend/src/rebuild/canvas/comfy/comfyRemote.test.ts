// [HERMIA-FE-20261031 DUALCANVAS-COMFY WIRING] Pure transport tests: the lower canvas imports
// a read-only ComfyUI object_info and syncs its draft through the project lower-canvas API.
// No real server, no ComfyUI, no execution is invoked here.
import {afterEach, describe, expect, it, vi} from 'vitest';
import {fetchImportedObjectInfo, loadRemoteComfyGraph, saveRemoteComfyGraph} from './comfyRemote';

const remote = {projectId: 'novel-a', token: 'session-a', branchId: 'branch-a'};
const fakeResponse = (value: unknown, init: {status?: number; ok?: boolean; headers?: Record<string, string>} = {}) => ({
  ok: init.ok ?? (init.status ?? 200) < 400,
  status: init.status ?? 200,
  headers: {get: (key: string) => init.headers?.[key.toLowerCase()] ?? init.headers?.[key] ?? null},
  json: async () => value,
} as unknown as Response);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('comfyRemote', () => {
  it('imports object_info definitions and exposes the source version header', async () => {
    const fetchMock = vi.fn(async () => fakeResponse({
      CustomNodeX: {input: {required: {image: [['a.png', 'b.png']]}}, output: ['IMAGE'],
        category: 'custom', display_name: 'Custom X'},
    }, {headers: {'x-comfy-source-version': 'abcd1234'}}));
    vi.stubGlobal('fetch', fetchMock);
    const result = await fetchImportedObjectInfo();
    expect(fetchMock).toHaveBeenCalledWith('/api/comfy/object_info', expect.objectContaining({method: 'GET', cache: 'no-store'}));
    expect(result?.sourceVersion).toBe('abcd1234');
    expect(result?.defs.find(d => d.name === 'CustomNodeX')).toMatchObject({source: 'imported', outputs: [{type: 'IMAGE'}]});
  });

  it('keeps the built-in registry when the ComfyUI provider is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => fakeResponse({detail: {code: 'comfy_unavailable'}}, {status: 503})));
    expect(await fetchImportedObjectInfo()).toBeNull();
  });

  it('loads a project lower canvas with branch/session headers', async () => {
    const fetchMock = vi.fn(async () => fakeResponse({kind: 'image', version: 2,
      graph: {nodes: [{id: 'r1', t: 'KSampler', x: 1, y: 2, title: 'remote'}], edges: []}}));
    vi.stubGlobal('fetch', fetchMock);
    const result = await loadRemoteComfyGraph('image', remote);
    expect(result.version).toBe(2);
    expect(result.graph.nodes[0]).toMatchObject({id: 'r1', t: 'KSampler'});
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/projects/novel-a/studio/lower-canvas/image');
    expect(init.headers).toMatchObject({'X-Session-Token': 'session-a', 'X-Branch-Id': 'branch-a'});
  });

  it('treats an unauthorized/unknown lower canvas as an empty draft', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => fakeResponse({}, {status: 403})));
    await expect(loadRemoteComfyGraph('video', remote)).resolves.toEqual({version: 0, graph: {nodes: [], edges: []}});
  });

  it('saves with expected_version and returns the new version', async () => {
    const fetchMock = vi.fn(async () => fakeResponse({kind: 'image', version: 3}));
    vi.stubGlobal('fetch', fetchMock);
    const graph = {nodes: [{id: 'n1', t: 'KSampler', x: 0, y: 0, title: 'n'}],
      edges: [{id: 'e1', a: 'n1', as: 0, b: 'n1', bs: 0}]};
    await expect(saveRemoteComfyGraph('image', remote, 2, graph)).resolves.toEqual({ok: true, version: 3});
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/projects/novel-a/studio/lower-canvas/image');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(String(init.body))).toEqual({expected_version: 2, graph});
  });

  it('reports the server version on a CAS conflict instead of overwriting', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => fakeResponse({detail: {code: 'LOWER_CANVAS_VERSION_CONFLICT', current_version: 4}}, {status: 409})));
    await expect(saveRemoteComfyGraph('video', remote, 1, {nodes: [], edges: []}))
      .resolves.toEqual({ok: false, currentVersion: 4});
  });
});
