// @vitest-environment jsdom
// Original File/API fixture replay. No inference, media ingestion or human approval is simulated as fact.
import {webcrypto} from 'node:crypto';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import fixture from '../../creative/fixtures/cloud-canvas-candidate.file-api.json';
import {api, setCollaborationContext, type CollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskBinding} from './canvasTaskBinding';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';

afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
});

it('reads the original File metadata projection with the explicit project and captured transport identity', async () => {
  const context: CollaborationContext = {sessionToken: 'synthetic-read-session',
    actor: {id: 'synthetic-author', displayName: 'Fixture', workspaceId: 'synthetic-workspace'},
    scope: {workspaceId: 'synthetic-workspace', projectId: fixture.project_id, storylineId: 'synthetic-story', branchId: 'synthetic-branch'}};
  setCollaborationContext({sessionToken: 'different-current-session'});
  const controller = new AbortController();
  const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(fixture.approved_asset), {headers: {'Content-Type': 'application/json'}}));
  vi.stubGlobal('fetch', fetcher);
  const observed = await api.assetMetadata(fixture.approved_asset.id, fixture.project_id, context, {
    signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer',
  });
  expect(observed).toEqual(fixture.approved_asset);
  expect(observed.version).toBe(2);
  expect(observed.sha256).toBe(fixture.download.headers['x-asset-sha256']);
  const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(fixture.paths.approved_asset_metadata);
  expect(init).toMatchObject({signal: controller.signal, cache: 'no-store', redirect: 'error', credentials: 'omit', referrerPolicy: 'no-referrer'});
  expect(init.method).toBeUndefined();
  expect(init.headers).toMatchObject({'X-Session-Token': context.sessionToken, 'X-Branch-Id': context.scope!.branchId});
});

it('does not fall back to a bare asset read or download when scoped metadata is refused', async () => {
  const fetcher = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({detail: {code: 'FORBIDDEN'}}), {status: 403}));
  vi.stubGlobal('fetch', fetcher);
  await expect(api.assetMetadata(fixture.approved_asset.id, fixture.project_id, {sessionToken: 'synthetic-denied-session'})).rejects.toMatchObject({status: 403});
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe(fixture.paths.approved_asset_metadata);
});

it('uses actual File/API fields and bytes for explicit local adoption, without writing server approval or the graph', async () => {
  localStorage.clear(); setCollaborationContext({sessionToken: ''});
  useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  bindLocalHostSession('synthetic-file-review-host', {session_mode: 'LOCAL_HOST', actor_id: 'synthetic-file-review-author'});
  const nodeId = 'file-review-original-node', NativeURL = URL;
  vi.stubGlobal('crypto', webcrypto);
  vi.stubGlobal('URL', class extends NativeURL {static createObjectURL = vi.fn(() => 'blob:file-review-synthetic'); static revokeObjectURL = vi.fn();});
  const graphKey = canvasStorageKey('image', fixture.project_id);
  const graph = JSON.stringify({nodes: [{id: nodeId, t: 'image_generate', title: 'File review fixture node', x: 0, y: 0,
    prompt: fixture.approved.items[0].prompt}], edges: []});
  localStorage.setItem(graphKey, graph);
  const owner = captureCanvasTaskOwner(fixture.project_id)!;
  expect(writeCanvasTaskBinding(owner, nodeId, fixture.task_id)).toBe(true);
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    expect(!init.method || init.method === 'GET').toBe(true);
    if (url === fixture.paths.jobs) return new Response(JSON.stringify(fixture.approved), {headers: {'Content-Type': 'application/json'}});
    if (url === fixture.paths.approved_asset_metadata) return new Response(JSON.stringify(fixture.approved_asset), {headers: {'Content-Type': 'application/json'}});
    if (url === fixture.download.path) return new Response(Uint8Array.from(atob(fixture.download.body_b64), value => value.charCodeAt(0)).buffer,
      {headers: fixture.download.headers});
    throw new Error('Unexpected File review fixture request');
  });
  vi.stubGlobal('fetch', fetcher);
  render(<CanvasNodeTaskStatus novelId={fixture.project_id} nodeId={nodeId} nodePrompt={fixture.approved.items[0].prompt}/>);
  fireEvent.click(await screen.findByRole('button', {name: '预览原任务候选结果'}));
  const image = await screen.findByRole('img', {name: '原节点任务候选结果'});
  expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined();
  // Explicit software load event: not proof of browser decoding or a human reviewing this fixture.
  Object.defineProperties(image, {naturalWidth: {value: 1}, naturalHeight: {value: 1}});
  fireEvent.load(image);
  const prepare = screen.getByRole('button', {name: '准备人工核对'}) as HTMLButtonElement;
  await waitFor(() => expect(prepare.disabled).toBe(false));
  fireEvent.click(prepare);
  fireEvent.click(await screen.findByRole('checkbox', {name: '已查看上述图片，并确认仅采用到此浏览器的原节点'}));
  fireEvent.click(screen.getByRole('button', {name: '采用到此浏览器原节点'}));
  await waitFor(() => expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toMatchObject({
    assetId: fixture.approved_asset.id, assetVersion: fixture.approved_asset.version, assetSha256: fixture.approved_asset.sha256,
  }));
  expect(localStorage.getItem(graphKey)).toBe(graph);
  expect(fetcher.mock.calls.filter(([url]) => url === fixture.download.path)).toHaveLength(2);
  expect(fetcher.mock.calls.every(([url]) => [fixture.paths.jobs, fixture.paths.approved_asset_metadata, fixture.download.path].includes(url))).toBe(true);
});
