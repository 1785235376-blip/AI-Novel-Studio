// @vitest-environment jsdom
// Independent browser-local review QA. HTTP/PNG bytes are software fixtures;
// explicit synthetic load events do not establish browser decoding or live media acceptance.
import {createHash, webcrypto} from 'node:crypto';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskBinding} from './canvasTaskBinding';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';
import {ImageRebuild} from './ImageRebuild';

const project = 'review-project', nodeId = 'review-original-node', taskId = '66666666-6666-4666-8666-666666666666', assetId = 'review-approved-asset';
const token = 'fixture-review-token-never-store', prompt = 'Fixture original reviewed image prompt';
const sourceUri = 'https://images.example.invalid/approved.png?signature=fixture-private-uri';
const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII='), value => value.charCodeAt(0));
const digest = createHash('sha256').update(png).digest('hex');
const actor = {id: 'review-author', displayName: 'Fixture author', workspaceId: 'review-workspace'};
const scope = {workspaceId: actor.workspaceId, projectId: project, storylineId: 'review-story', branchId: 'review-branch'};
const jobsPath = `/api/novels/${project}/image-jobs`, metadataPath = `/api/assets/${assetId}?novel_id=${project}`;
const downloadPath = `/api/assets/${assetId}/download?novel_id=${project}`;
const previewName = '预览原任务候选结果', prepareName = '准备人工核对', adoptName = '采用到此浏览器原节点';
const checkName = '已查看上述图片，并确认仅采用到此浏览器的原节点';
const NativeURL = URL;
const createUrl = vi.fn(), revokeUrl = vi.fn();
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json'}});
const job = (changes: Record<string, unknown> = {}) => ({id: taskId, novel_id: project, branch_id: null, owner_actor_id: null,
  status: 'SUCCEEDED', approval_status: 'APPROVED', asset_id: assetId, provider_id: 'review-local', model_id: 'review-model', prompt,
  request_sha256: 'c'.repeat(64), attempt: 1, updated_at: '2026-10-24T08:00:00Z', asset_uri: sourceUri, ...changes});
const metadata = (changes: Record<string, unknown> = {}) => ({id: assetId, novel_id: project, branch_id: null, filename: 'fixture-approved.png',
  kind: 'image', media_type: 'image/png', size: png.byteLength, sha256: digest, version: 2, deleted_at: null,
  created_at: '2026-10-24T07:59:00Z', updated_at: '2026-10-24T08:00:00Z', source_job_id: taskId,
  provider_id: 'review-local', model_id: 'review-model', parameters: {width: 1024, height: 1024}, ...changes});
function host(who = actor.id) {bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: who});}
function seed(novelId = project) {
  localStorage.setItem(canvasStorageKey('image', novelId), JSON.stringify({nodes: [{id: nodeId, t: 'image_generate', title: 'Fixture original node', x: 0, y: 0, prompt}], edges: []}));
}
function setup(collaboration = false) {
  if (collaboration) useStudio.getState().setCollaboration(token, actor, scope); else host();
  seed(); const owner = captureCanvasTaskOwner(project);
  if (!owner || !writeCanvasTaskBinding(owner, nodeId, taskId)) throw new Error('Review fixture needs verified owner and unique original image node');
  return owner;
}
function http(options: {collaboration?: boolean; root?: boolean; download?: (index: number) => Promise<Response>; meta?: (index: number) => Promise<Response>} = {}) {
  const state = {job: job(options.collaboration ? {branch_id: scope.branchId, owner_actor_id: actor.id} : {}),
    asset: metadata(options.collaboration ? {branch_id: scope.branchId} : {}), bytes: png.slice(),
    permission: {actor_id: actor.id, domain: 'NOVEL', capabilities: {'domain.write': true}}, downloads: 0, metadataReads: 0};
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if (init.method && init.method !== 'GET') throw new Error(`Review fixture forbids mutation ${init.method} ${url}`);
    if (url === jobsPath) return json({items: [state.job]});
    if (url === metadataPath) return options.meta ? options.meta(++state.metadataReads) : (state.metadataReads++, json(state.asset));
    if (url === downloadPath) return options.download ? options.download(++state.downloads)
      : (state.downloads++, new Response(state.bytes.slice().buffer, {headers: {'Content-Type': 'image/png'}}));
    if (url.endsWith('/permissions')) return json(state.permission);
    if (options.root && (url === '/api/asset-providers' || /\/(image-generations|visual-references)$/.test(url))) return json({items: []});
    throw new Error(`Review fixture unexpected GET ${url}`);
  });
  vi.stubGlobal('fetch', fetcher); return {state, fetcher};
}
const viewStatus = (novelId = project) => <CanvasNodeTaskStatus novelId={novelId} nodeId={nodeId} nodePrompt={prompt}/>;
function noWrites(fetcher: ReturnType<typeof vi.fn>) {expect(fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET')).toHaveLength(0);}
function load(image: HTMLElement, width = 1, height = 1) {
  Object.defineProperties(image, {naturalWidth: {configurable: true, value: width}, naturalHeight: {configurable: true, value: height}});
  fireEvent.load(image);
}
async function preview() {
  fireEvent.click(await screen.findByRole('button', {name: previewName}));
  return await screen.findByRole('img', {name: '原节点任务候选结果'});
}
async function prepare() {
  const image = await preview(); load(image);
  await waitFor(() => expect((screen.getByRole('button', {name: prepareName}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', {name: prepareName}));
  const check = await screen.findByRole('checkbox', {name: checkName});
  return {image, check, adopt: screen.getByRole('button', {name: adoptName})};
}
async function tryAdopt() {
  const prepareButton = screen.queryByRole('button', {name: prepareName}); if (prepareButton) fireEvent.click(prepareButton);
  await act(async () => {});
  const check = screen.queryByRole('checkbox', {name: checkName}); if (check) fireEvent.click(check);
  const adopt = screen.queryByRole('button', {name: adoptName}); if (adopt) fireEvent.click(adopt);
  await act(async () => {});
}
function selectNode() {
  const element = document.querySelector(`[data-node-id="${nodeId}"]`)!;
  fireEvent.pointerDown(element, {button: 0, pointerId: 1, clientX: 40, clientY: 40}); fireEvent.pointerUp(element, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
beforeEach(() => {
  localStorage.clear(); useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('PointerEvent', MouseEvent);
  let urls = 0; createUrl.mockReset().mockImplementation(() => `blob:review-fixture-${++urls}`); revokeUrl.mockReset();
  vi.stubGlobal('URL', class extends NativeURL {static createObjectURL = createUrl; static revokeObjectURL = revokeUrl;});
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('independent browser-local original-node candidate review', () => {
  it('requires successful image load and explicit confirmation before storing only the original asset observation', async () => {
    const owner = setup(); const {state, fetcher} = http(); const graph = localStorage.getItem(canvasStorageKey('image', project));
    const view = render(viewStatus()); const image = await preview();
    await tryAdopt(); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined();
    load(image); await waitFor(() => expect((screen.getByRole('button', {name: prepareName}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', {name: prepareName}));
    const check = await screen.findByRole('checkbox', {name: checkName});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined();
    fireEvent.click(check); fireEvent.click(screen.getByRole('button', {name: adoptName}));
    await waitFor(() => expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toMatchObject({assetId, assetVersion: 2, assetSha256: digest}));
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption?.jobObservationSha256).toMatch(/^[a-f0-9]{64}$/);
    const stored = localStorage.getItem(canvasTaskBindingKey(owner, nodeId))!;
    expect(stored).not.toContain(token); expect(stored).not.toContain(prompt); expect(stored).not.toContain(sourceUri); expect(stored).not.toContain('blob:');
    expect(localStorage.getItem(canvasStorageKey('image', project))).toBe(graph);
    expect(state.downloads).toBeGreaterThanOrEqual(2); expect(view.container.textContent).toMatch(/此浏览器|本浏览器/); noWrites(fetcher);
  });

  it.each([[0, 1], [1, 0], [0, 0]])('does not treat an image load with dimensions %j as a reviewed raster', async (width, height) => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const image = await preview(); load(image, width, height);
    await tryAdopt(); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('does not let duplicate load notifications adopt anything without user confirmation', async () => {
    const owner = setup(); const {state, fetcher} = http(); render(viewStatus()); const image = await preview(); load(image); load(image);
    await act(async () => {}); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined();
    expect(state.metadataReads).toBe(0); noWrites(fetcher);
  });

  it('does not let an old hidden image load activate review of its new unloaded replacement', async () => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const old = await preview(); load(old);
    fireEvent.click(screen.getByRole('button', {name: '隐藏候选预览'})); const replacement = await preview();
    expect(replacement).not.toBe(old); load(old); await tryAdopt();
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it.each(['hide', 'error'])('retires a checked review on image %s before its old confirmation callback', async action => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const {image, check, adopt} = await prepare(); fireEvent.click(check);
    act(() => {if (action === 'hide') fireEvent.click(screen.getByRole('button', {name: '隐藏候选预览'})); else fireEvent.error(image); fireEvent.click(adopt);});
    await act(async () => {}); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('does not review an inline PENDING image as an already approved asset', async () => {
    const owner = setup(); const {state, fetcher} = http();
    state.job = job({approval_status: 'PENDING', asset_id: undefined, asset_uri: `data:image/png;base64,${btoa(String.fromCharCode(...png))}`});
    render(viewStatus()); const image = await preview(); load(image); await tryAdopt();
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); expect(state.metadataReads).toBe(0); noWrites(fetcher);
  });

  it.each([
    ['version', {version: 3}], ['hash', {sha256: 'b'.repeat(64)}], ['branch', {branch_id: 'foreign-branch'}],
    ['source job', {source_job_id: 'foreign-job'}], ['deleted asset', {deleted_at: '2026-10-24T08:01:00Z'}],
  ])('rejects changed asset %s after the user checked the review', async (_label, changes) => {
    const owner = setup(); const {state, fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    state.asset = metadata(changes as Record<string, unknown>); fireEvent.click(adopt); await act(async () => {});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('rejects different downloaded bytes even when metadata and the job snapshot still match', async () => {
    const owner = setup(); const {state, fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    state.bytes = png.slice(); state.bytes[state.bytes.length - 1] ^= 1;
    fireEvent.click(adopt); await act(async () => {});
    expect(state.asset.sha256).toBe(digest); expect(state.bytes.byteLength).toBe(png.byteLength);
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('does not confirm after collaboration write permission is revoked', async () => {
    const owner = setup(true); const {state, fetcher} = http({collaboration: true}); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    state.permission = {...state.permission, capabilities: {'domain.write': false}}; fireEvent.click(adopt); await act(async () => {});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('does not apply a checked review to a changed original job observation', async () => {
    const owner = setup(); const {state, fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    state.job = job({attempt: 2, request_sha256: 'd'.repeat(64), updated_at: '2026-10-24T08:02:00Z'});
    fireEvent.click(adopt); await act(async () => {});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('retires a checked local review across verified Host A/B/A', async () => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    act(() => {host('transient-local-review-author'); host(); fireEvent.click(adopt);});
    await act(async () => {}); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it.each(['client', 'project'])('retires a checked review across same-object API %s A/B/A', async changed => {
    const owner = setup(true); const {fetcher} = http({collaboration: true}); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    const original = getCollaborationContext();
    act(() => {
      setCollaborationContext(changed === 'client' ? {...original, sessionToken: 'transient-review-client'} : {...original, scope: {...scope, projectId: 'transient-project'}});
      setCollaborationContext(original); fireEvent.click(adopt);
    });
    expect(getCollaborationContext()).toBe(original); await act(async () => {});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('retires checked review after source prompt A/B/A before the old adoption callback runs', async () => {
    const owner = setup(); const {fetcher} = http({root: true});
    render(<ImageRebuild novelId={project} view="canvas" shellMode="basic" onViewChange={() => {}}/>); selectNode();
    const {check, adopt} = await prepare(); fireEvent.click(check); const editor = screen.getByLabelText('本次提示词');
    act(() => {fireEvent.change(editor, {target: {value: 'Transient other prompt'}}); fireEvent.change(editor, {target: {value: prompt}}); fireEvent.click(adopt);});
    await act(async () => {}); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('writes at most one browser-local association for repeated confirm clicks', async () => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    const set = vi.spyOn(Storage.prototype, 'setItem'); act(() => {fireEvent.click(adopt); fireEvent.click(adopt); fireEvent.click(adopt);});
    await waitFor(() => expect(readCanvasTaskBinding(owner, nodeId)?.adoption?.assetId).toBe(assetId));
    expect(set.mock.calls.filter(([key]) => key === canvasTaskBindingKey(owner, nodeId))).toHaveLength(1); noWrites(fetcher);
  });

  it('does not report a local association when browser storage rejects the write', async () => {
    const owner = setup(); const {fetcher} = http(); render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check);
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {throw new Error('Fixture storage unavailable');});
    fireEvent.click(adopt); await waitFor(() => expect(set).toHaveBeenCalled()); await act(async () => {});
    expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); expect(set).toHaveBeenCalledTimes(1); noWrites(fetcher);
  });

  it('does not retry a timed-out confirmation download or create a local association', async () => {
    const owner = setup(); const {state, fetcher} = http({download: async index => {
      if (index > 1) throw new DOMException('Fixture review read timeout', 'TimeoutError');
      return new Response(png.slice().buffer, {headers: {'Content-Type': 'image/png'}});
    }});
    render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check); fireEvent.click(adopt); await act(async () => {});
    expect(state.downloads).toBe(2); expect(readCanvasTaskBinding(owner, nodeId)?.adoption).toBeUndefined(); noWrites(fetcher);
  });

  it('preserves only a historical browser-local association across reopening and requires a fresh image load for new confirmation', async () => {
    const owner = setup(); const {fetcher} = http(); let view = render(viewStatus()); const {check, adopt} = await prepare(); fireEvent.click(check); fireEvent.click(adopt);
    await waitFor(() => expect(readCanvasTaskBinding(owner, nodeId)?.adoption?.assetId).toBe(assetId));
    view.unmount(); view = render(viewStatus()); await screen.findByRole('button', {name: previewName});
    expect(screen.queryByRole('img')).toBeNull(); expect(screen.queryByRole('checkbox', {name: checkName})).toBeNull();
    await preview(); await tryAdopt(); expect(screen.queryByRole('checkbox', {name: checkName})).toBeNull(); noWrites(fetcher);
  });
});
