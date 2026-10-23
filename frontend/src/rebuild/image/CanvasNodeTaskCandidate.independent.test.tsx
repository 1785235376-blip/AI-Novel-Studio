// @vitest-environment jsdom
// Independent read-only candidate QA. HTTP and image URIs are software fixtures;
// this does not establish live provider, File, media bytes or browser acceptance.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {captureCanvasTaskOwner, writeCanvasTaskBinding} from './canvasTaskBinding';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';
import {ImageRebuild} from './ImageRebuild';

const project = 'candidate-project', nodeId = 'candidate-node';
const taskId = '33333333-3333-4333-8333-333333333333';
const originalPrompt = 'Fixture historical candidate prompt';
const token = 'fixture-host-token-never-display';
const pngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII=';
const uri = `data:image/png;base64,${pngBase64}`;
const externalUri = 'https://images.example.invalid/candidates/original.png?signature=fixture-url-secret';
const assetId = 'candidate-approved-asset';
const assetPath = `/api/assets/${assetId}/download?novel_id=${project}`;
const NativeURL = URL;
const createUrl = vi.fn(() => 'blob:fixture-approved-candidate');
const revokeUrl = vi.fn();
const pngResponse = (headers: Record<string, string> = {}) => new Response(Uint8Array.from(atob(pngBase64), char => char.charCodeAt(0)).buffer, {headers: {'Content-Type': 'image/png', ...headers}});
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
const row = (changes: Record<string, unknown> = {}) => ({
  id: taskId, novel_id: project, branch_id: null, owner_actor_id: null,
  status: 'SUCCEEDED', approval_status: 'PENDING', provider_id: 'fixture-local-service', model_id: 'fixture-model',
  prompt: originalPrompt, request_sha256: 'd'.repeat(64), attempt: 1,
  updated_at: '2026-10-23T14:00:00Z', asset_uri: uri, execution_token: 'fixture-execution-token-never-display', ...changes,
});
const approved = (changes: Record<string, unknown> = {}) => row({approval_status: 'APPROVED', asset_id: assetId, asset_uri: externalUri, ...changes});
function seed(novelId = project, prompt = originalPrompt) {
  localStorage.setItem(canvasStorageKey('image', novelId), JSON.stringify({nodes: [{id: nodeId, t: 'image_generate', title: 'Fixture candidate node', x: 0, y: 0, prompt}], edges: []}));
}
function host(actor = 'candidate-author-a') {
  bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: actor});
}
function bind(jobId = taskId, novelId = project) {
  const owner = captureCanvasTaskOwner(novelId);
  if (!owner || !writeCanvasTaskBinding(owner, nodeId, jobId)) throw new Error('Candidate fixture requires a verified current owner and existing image node');
  return owner;
}
function localSetup() {host(); seed(); return bind();}
function onlyReads(fetcher: ReturnType<typeof vi.fn>) {
  expect(fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET')).toHaveLength(0);
  expect(fetcher.mock.calls.filter(([url]) => /\/(execute|accept|retry)(?:\?|$)/.test(String(url)))).toHaveLength(0);
}
function http(reader: (index: number) => Promise<Response> | Response, root = false, assetReader?: () => Promise<Response> | Response) {
  let reads = 0;
  const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
    if (url === `/api/novels/${project}/image-jobs` && (!init.method || init.method === 'GET')) return Promise.resolve(reader(++reads));
    if (url === assetPath && (!init.method || init.method === 'GET') && assetReader) return Promise.resolve(assetReader());
    if (root && (url === '/api/asset-providers' || /\/(image-generations|visual-references)$/.test(url))) return Promise.resolve(json({items: []}));
    throw new Error(`Readonly candidate fixture unexpected ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
const status = (novelId = project) => <CanvasNodeTaskStatus novelId={novelId} nodeId={nodeId} nodePrompt={originalPrompt}/>;
const previewName = '预览原任务候选结果';
async function preview() {
  fireEvent.click(await screen.findByRole('button', {name: previewName}));
  return screen.findByRole('img', {name: '原节点任务候选结果'});
}
function selectNode() {
  const node = document.querySelector(`[data-node-id="${nodeId}"]`)!;
  fireEvent.pointerDown(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
  fireEvent.pointerUp(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  vi.stubGlobal('PointerEvent', MouseEvent);
  createUrl.mockReset().mockReturnValue('blob:fixture-approved-candidate'); revokeUrl.mockReset();
  vi.stubGlobal('URL', class extends NativeURL {static createObjectURL = createUrl; static revokeObjectURL = revokeUrl;});
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('independent historical image-node candidate preview', () => {
  it('requires explicit preview plus a matching second GET and displays no secret or complete URI as text', async () => {
    localSetup();
    const fetcher = http(() => json({items: [row()]}));
    const view = render(status());
    await screen.findByRole('button', {name: previewName});
    expect(screen.queryByRole('img')).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(view.container.textContent).not.toContain(uri);
    expect(view.container.textContent).not.toContain(token);
    expect(view.container.textContent).not.toContain('fixture-execution-token-never-display');
    const image = await preview();
    expect(image.getAttribute('src')).toBe(uri);
    expect(image.getAttribute('referrerpolicy')).toBe('no-referrer');
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText(/原任务读取快照/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/候选只读，未自动采用/).length).toBeGreaterThan(0);
    expect(view.container.textContent).not.toContain(uri);
    onlyReads(fetcher);
  });

  it.each(['RUNNING', 'CANCELLED', 'FAILED'])('does not create a candidate from a %s row', async state => {
    localSetup(); const fetcher = http(() => json({items: [row({status: state})]}));
    render(status()); await screen.findByText(state);
    expect(screen.queryByRole('button', {name: previewName})).toBeNull();
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it.each([
    ['missing digest', {request_sha256: undefined}], ['invalid attempt', {attempt: -1}],
    ['invalid timestamp', {updated_at: 'not-a-time'}], ['unsupported URI', {asset_uri: 'javascript:fixtureCandidate()'}],
  ])('does not allow image preview with %s', async (_label, changes) => {
    localSetup(); const fetcher = http(() => json({items: [row(changes as Record<string, unknown>)]}));
    render(status()); await screen.findByText('SUCCEEDED');
    const button = screen.queryByRole('button', {name: previewName}) as HTMLButtonElement | null;
    expect(!button || button.disabled).toBe(true);
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it.each([
    ['URI', {asset_uri: `${uri}&revision=2`}], ['request digest', {request_sha256: 'e'.repeat(64)}],
    ['attempt', {attempt: 2}], ['timestamp', {updated_at: '2026-10-23T14:01:00Z'}],
  ])('does not use old preview confirmation when the second GET changed the %s', async (_label, changes) => {
    localSetup(); const fetcher = http(index => json({items: [row(index === 1 ? {} : changes as Record<string, unknown>)]}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await act(async () => {});
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it.each([403, 404])('removes an open candidate at refresh start and does not restore it after HTTP %s', async code => {
    localSetup(); let finishRefresh!: (value: Response) => void;
    const fetcher = http(index => index < 3 ? json({items: [row()]}) : new Promise(resolve => {finishRefresh = resolve;}));
    render(status()); await preview();
    fireEvent.click(screen.getByRole('button', {name: '刷新原任务状态'}));
    expect(screen.queryByRole('img')).toBeNull();
    await act(async () => {finishRefresh(json({detail: 'Fixture candidate no longer readable'}, code));});
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('button', {name: previewName})).toBeNull(); onlyReads(fetcher);
  });

  it.each([403, 404, 'RUNNING', 'CANCELLED'])('retires old candidate provenance when preview revalidation returns %s', async result => {
    localSetup();
    const fetcher = http(index => index === 1 ? json({items: [row()]}) : typeof result === 'number'
      ? json({detail: 'Fixture preview read no longer permitted'}, result) : json({items: [row({status: result})]}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await act(async () => {});
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('region', {name: '原任务候选结果'})).toBeNull();
    expect(screen.queryByLabelText('原任务提示词')).toBeNull(); onlyReads(fetcher);
  });

  it('retires a pending preview across an API-only owner switch without parent rerender', async () => {
    localSetup(); let finishPreview!: (value: Response) => void;
    const fetcher = http(index => index === 1 ? json({items: [row()]}) : new Promise(resolve => {finishPreview = resolve;}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishPreview).toBeTypeOf('function'));
    act(() => setCollaborationContext({sessionToken: 'fixture-other-api-owner'}));
    await act(async () => {finishPreview(json({items: [row()]}));});
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('button', {name: previewName})).toBeNull(); onlyReads(fetcher);
  });

  it('does not revive preview consent after a verified Host A/B/A even if a fresh legal GET succeeds', async () => {
    localSetup(); let finishInitialPreview!: (value: Response) => void;
    const fetcher = http(index => index === 2 ? new Promise(resolve => {finishInitialPreview = resolve;}) : json({items: [row()]}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishInitialPreview).toBeTypeOf('function'));
    act(() => {host('candidate-author-b'); host('candidate-author-a');});
    await screen.findByRole('button', {name: previewName});
    await act(async () => {finishInitialPreview(json({items: [row()]}));});
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('does not carry a pending original preview into another project', async () => {
    localSetup(); seed('candidate-other-project'); let finishInitialPreview!: (value: Response) => void;
    const fetcher = http(index => index === 1 ? json({items: [row()]}) : new Promise(resolve => {finishInitialPreview = resolve;}));
    const view = render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishInitialPreview).toBeTypeOf('function'));
    view.rerender(status('candidate-other-project'));
    await act(async () => {finishInitialPreview(json({items: [row()]}));});
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByText(`原入队任务 ID：${taskId}`)).toBeNull(); onlyReads(fetcher);
  });

  it('does not attach an old pending preview to a newly bound task on the same node', async () => {
    const owner = localSetup(); const nextId = '44444444-4444-4444-8444-444444444444';
    let finishInitialPreview!: (value: Response) => void;
    const fetcher = http(index => index === 2 ? new Promise(resolve => {finishInitialPreview = resolve;})
      : json({items: [row(index > 2 ? {id: nextId} : {})]}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishInitialPreview).toBeTypeOf('function'));
    act(() => {expect(writeCanvasTaskBinding(owner, nodeId, nextId)).toBe(true);});
    await screen.findByText(`原入队任务 ID：${nextId}`);
    await act(async () => {finishInitialPreview(json({items: [row()]}));});
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('retires an old candidate callback when its selected node prompt changes in the same batch', async () => {
    localSetup(); const fetcher = http(() => json({items: [row()]}), true);
    render(<ImageRebuild novelId={project} view="canvas" shellMode="basic" onViewChange={() => {}}/>);
    selectNode(); const oldPreview = await screen.findByRole('button', {name: previewName});
    const editor = screen.getByLabelText('本次提示词');
    act(() => {
      fireEvent.change(editor, {target: {value: 'A different unqueued candidate draft'}});
      fireEvent.click(oldPreview);
    });
    await act(async () => {});
    expect(screen.queryByRole('img')).toBeNull();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('A different unqueued candidate draft');
    expect(screen.getAllByText(/原任务不代表当前提示词已经入队/).length).toBeGreaterThan(0);
    onlyReads(fetcher);
  });

  it('retires an old candidate callback when its original node is deleted before React commits', async () => {
    localSetup(); const fetcher = http(() => json({items: [row()]}), true);
    render(<ImageRebuild novelId={project} view="canvas" shellMode="basic" onViewChange={() => {}}/>);
    selectNode(); const oldPreview = await screen.findByRole('button', {name: previewName});
    fireEvent.contextMenu(document.querySelector(`[data-node-id="${nodeId}"]`)!, {clientX: 40, clientY: 40});
    act(() => {fireEvent.click(screen.getByRole('menuitem', {name: '删除节点'})); fireEvent.click(oldPreview);});
    await act(async () => {});
    expect(screen.queryByRole('img')).toBeNull();
    expect(document.querySelector(`[data-node-id="${nodeId}"]`)).toBeNull(); onlyReads(fetcher);
  });

  it.each(['http://images.example.invalid/result.png', externalUri, '/api/private-result.png', 'blob:https://images.example.invalid/original'])('does not directly preview a PENDING network or blob result %s', async source => {
    localSetup(); const fetcher = http(() => json({items: [row({asset_uri: source})]}));
    const view = render(status());
    const button = await screen.findByRole('button', {name: previewName}) as HTMLButtonElement;
    expect(button.disabled).toBe(true); fireEvent.click(button);
    await act(async () => {});
    expect(screen.queryByRole('img')).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
    expect(createUrl).not.toHaveBeenCalled(); expect(view.container.textContent).not.toContain(source);
    expect(screen.getByText(/当前接口未提供未入库网络候选的内容读取/)).toBeTruthy(); onlyReads(fetcher);
  });

  it('reads an APPROVED exact asset with captured authentication between two matching job confirmations', async () => {
    seed();
    const actor = {id: 'candidate-author-a', displayName: 'Fixture author', workspaceId: 'candidate-workspace'};
    const scope = {workspaceId: 'candidate-workspace', projectId: project, storylineId: 'candidate-story', branchId: 'candidate-branch'};
    useStudio.getState().setCollaboration('fixture-approved-session', actor, scope); bind();
    const original = approved({branch_id: scope.branchId, owner_actor_id: actor.id});
    const fetcher = http(() => json({items: [original]}), false, () => pngResponse());
    const view = render(status());
    await screen.findByRole('button', {name: previewName});
    expect(screen.queryByRole('img')).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
    const image = await preview();
    expect(image.getAttribute('src')).toBe('blob:fixture-approved-candidate');
    expect(image.getAttribute('src')).not.toBe(externalUri);
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      `/api/novels/${project}/image-jobs`, `/api/novels/${project}/image-jobs`, assetPath, `/api/novels/${project}/image-jobs`,
    ]);
    const download = fetcher.mock.calls.find(([url]) => url === assetPath)![1]!;
    expect(download).toMatchObject({redirect: 'error', credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer'});
    expect(new Headers(download.headers).get('X-Session-Token')).toBe('fixture-approved-session');
    expect(new Headers(download.headers).get('X-Branch-Id')).toBe(scope.branchId);
    expect((download as RequestInit & {maxBytes?: number}).maxBytes).toBeUndefined();
    expect(download.signal?.aborted).toBe(false);
    expect(createUrl).toHaveBeenCalledTimes(1);
    expect(view.container.textContent).not.toContain(externalUri);
    onlyReads(fetcher);
  });

  it.each([401, 403])('does not fall back to the source URI after approved asset download HTTP %s', async code => {
    localSetup(); const fetcher = http(() => json({items: [approved()]}), false, () => json({detail: 'Fixture asset denied'}, code));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert');
    expect(screen.queryByRole('img')).toBeNull(); expect(createUrl).not.toHaveBeenCalled();
    expect(fetcher).toHaveBeenCalledTimes(3); onlyReads(fetcher);
  });

  it('cancels a failed bounded asset response without reading or displaying its arbitrary error body', async () => {
    localSetup();
    const response = json({detail: 'fixture-untrusted-download-error-not-to-render'}, 403);
    const text = vi.spyOn(response, 'text'), cancel = vi.spyOn(response.body!, 'cancel');
    const fetcher = http(() => json({items: [approved()]}), false, () => response);
    const view = render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert');
    expect(text).not.toHaveBeenCalled(); expect(cancel).toHaveBeenCalledTimes(1);
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull();
    expect(view.container.textContent).not.toContain('fixture-untrusted-download-error-not-to-render');
    expect(view.container.textContent).not.toContain(externalUri);
    expect(fetcher).toHaveBeenCalledTimes(3); onlyReads(fetcher);
  });

  it.each(['image/svg+xml', 'text/html', 'empty-raster'])('rejects approved asset content %s without creating an object URL', async mime => {
    localSetup(); const fetcher = http(() => json({items: [approved()]}), false,
      () => new Response(mime === 'empty-raster' ? '' : 'Fixture non-raster content', {headers: {'Content-Type': mime === 'empty-raster' ? 'image/png' : mime}}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert'); expect(screen.queryByRole('img')).toBeNull();
    expect(createUrl).not.toHaveBeenCalled(); expect(fetcher).toHaveBeenCalledTimes(3); onlyReads(fetcher);
  });

  it('rejects a declared oversized approved asset before consuming the stream', async () => {
    localSetup(); const response = pngResponse({'Content-Length': String(37 * 1024 * 1024)});
    const read = vi.spyOn(response.body!, 'getReader');
    const fetcher = http(() => json({items: [approved()]}), false, () => response);
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert'); expect(read).not.toHaveBeenCalled();
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('cancels an approved asset stream that exceeds the cap without a declared size', async () => {
    localSetup(); const cancel = vi.fn();
    // One in-memory boundary chunk; no network or file allocation is involved.
    const stream = new ReadableStream<Uint8Array>({start(controller) {controller.enqueue(new Uint8Array(36 * 1024 * 1024 + 1));}, cancel});
    const fetcher = http(() => json({items: [approved()]}), false, () => new Response(stream, {headers: {'Content-Type': 'image/png'}}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert'); expect(cancel).toHaveBeenCalledTimes(1);
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('rejects an already redirected asset response rather than displaying it', async () => {
    localSetup(); const response = pngResponse(); Object.defineProperty(response, 'redirected', {value: true});
    const fetcher = http(() => json({items: [approved()]}), false, () => response);
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert'); expect(createUrl).not.toHaveBeenCalled();
    expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('does not allocate an object URL when the third job GET changed the approved asset snapshot', async () => {
    localSetup(); const fetcher = http(index => json({items: [approved(index === 3 ? {asset_id: 'replacement-approved-asset'} : {})]}), false, () => pngResponse());
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await screen.findByRole('alert'); expect(fetcher).toHaveBeenCalledTimes(4);
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it.each(['hide', 'unmount'])('aborts a pending approved download on %s and ignores its late response', async action => {
    localSetup(); let finishDownload!: (value: Response) => void;
    const fetcher = http(() => json({items: [approved()]}), false, () => new Promise(resolve => {finishDownload = resolve;}));
    const view = render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishDownload).toBeTypeOf('function'));
    const signal = fetcher.mock.calls.find(([url]) => url === assetPath)![1]!.signal;
    if (action === 'hide') fireEvent.click(screen.getByRole('button', {name: '隐藏候选预览'})); else view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => {finishDownload(pngResponse());});
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3); onlyReads(fetcher);
  });

  it('does not revive a pending approved download after the exact API owner context goes A/B/A', async () => {
    seed(); const actor = {id: 'candidate-author-a', displayName: 'Fixture author', workspaceId: 'candidate-workspace'};
    const scope = {workspaceId: 'candidate-workspace', projectId: project, storylineId: 'candidate-story', branchId: 'candidate-branch'};
    useStudio.getState().setCollaboration('fixture-approved-session', actor, scope); bind();
    const originalContext = getCollaborationContext();
    let finishDownload!: (value: Response) => void;
    const fetcher = http(() => json({items: [approved({branch_id: scope.branchId, owner_actor_id: actor.id})]}), false,
      () => new Promise(resolve => {finishDownload = resolve;}));
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishDownload).toBeTypeOf('function'));
    act(() => {setCollaborationContext({...originalContext, sessionToken: 'fixture-transient-client'}); setCollaborationContext(originalContext);});
    expect(getCollaborationContext()).toBe(originalContext);
    await screen.findByRole('button', {name: previewName});
    await act(async () => {finishDownload(pngResponse());});
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it('does not allocate an object URL when hidden while the final job confirmation is pending', async () => {
    localSetup(); let finishFinal!: (value: Response) => void;
    const fetcher = http(index => index === 3 ? new Promise(resolve => {finishFinal = resolve;}) : json({items: [approved()]}), false, () => pngResponse());
    render(status()); fireEvent.click(await screen.findByRole('button', {name: previewName}));
    await waitFor(() => expect(finishFinal).toBeTypeOf('function'));
    fireEvent.click(screen.getByRole('button', {name: '隐藏候选预览'}));
    await act(async () => {finishFinal(json({items: [approved()]}));});
    expect(createUrl).not.toHaveBeenCalled(); expect(screen.queryByRole('img')).toBeNull(); onlyReads(fetcher);
  });

  it.each(['hide', 'unmount', 'image-error', 'refresh', 'host-ABA'])('revokes a displayed approved object URL on %s', async action => {
    localSetup(); const fetcher = http(() => json({items: [approved()]}), false, () => pngResponse());
    const view = render(status()); const image = await preview();
    expect(createUrl).toHaveBeenCalledTimes(1); expect(revokeUrl).not.toHaveBeenCalled();
    if (action === 'hide') fireEvent.click(screen.getByRole('button', {name: '隐藏候选预览'}));
    else if (action === 'unmount') view.unmount();
    else if (action === 'image-error') fireEvent.error(image);
    else if (action === 'refresh') fireEvent.click(screen.getByRole('button', {name: '刷新原任务状态'}));
    else act(() => {host('candidate-author-b'); host('candidate-author-a');});
    await act(async () => {});
    expect(screen.queryByRole('img')).toBeNull();
    expect(revokeUrl).toHaveBeenCalledTimes(1);
    expect(revokeUrl).toHaveBeenCalledWith('blob:fixture-approved-candidate'); onlyReads(fetcher);
  });
});
