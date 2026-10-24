// @vitest-environment jsdom
// Independent browser-local history QA. Module writes below construct local
// fixtures; HTTP/PNG/load events do not establish real provider or browser approval.
import {Blob as NodeBlob} from 'node:buffer';
import {createHash, webcrypto} from 'node:crypto';
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskAdoption, writeCanvasTaskBinding,
  MAX_CANVAS_TASK_HISTORY, type CanvasTaskHistoryEntry} from './canvasTaskBinding';
import {checkedCanvasTaskCandidate} from './canvasTaskCandidate';
import {canvasCandidateObservationSha256} from './canvasCandidateReview';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';
import {ImageRebuild} from './ImageRebuild';

const project = 'history-project', nodeId = 'history-original-node', otherNode = 'history-other-node';
const token = 'fixture-history-token-never-store', draftPrompt = 'Fixture current unqueued canvas prompt';
const tasks = {A: '77777777-7777-4777-8777-777777777777', B: '88888888-8888-4888-8888-888888888888', C: '99999999-9999-4999-8999-999999999999'};
const assets = {A: 'history-asset-a', B: 'history-asset-b', C: 'history-asset-c'}, versions = {A: 2, B: 3, C: 4};
type Source = keyof typeof tasks;
const sources: Source[] = ['A', 'C', 'B'];
const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII='), char => char.charCodeAt(0));
const sha = createHash('sha256').update(png).digest('hex');
const actor = {id: 'history-author', displayName: 'Fixture author', workspaceId: 'history-workspace'};
const scope = {workspaceId: actor.workspaceId, projectId: project, storylineId: 'history-story', branchId: 'history-branch'};
const regionName = '此浏览器原节点采用历史', readName = '读取所选历史原任务';
const previewName = '预览原任务候选结果', prepareName = '准备历史恢复核对';
const checkName = '已查看上述图片，并确认仅恢复此浏览器原节点的历史关联', restoreName = '明确恢复此浏览器原节点';
const NativeURL = URL, makeUrl = vi.fn(), revokeUrl = vi.fn();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
const imageResponse = (bytes = png) => new Response(bytes.slice().buffer, {headers: {'Content-Type': 'image/png'}});
const row = (source: Source, collaboration = false, changes: Record<string, unknown> = {}) => ({id: tasks[source], novel_id: project,
  branch_id: collaboration ? scope.branchId : null, owner_actor_id: collaboration ? actor.id : null, status: 'SUCCEEDED', approval_status: 'APPROVED',
  asset_id: assets[source], provider_id: 'history-local', model_id: 'history-model', prompt: `Fixture historical ${source} prompt`,
  request_sha256: source.toLowerCase().repeat(64), attempt: 1, updated_at: '2026-10-24T12:00:00Z',
  asset_uri: `https://images.example.invalid/${source}.png?signature=fixture-only`, ...changes});
const metadata = (source: Source, collaboration = false, changes: Record<string, unknown> = {}) => ({id: assets[source], novel_id: project,
  branch_id: collaboration ? scope.branchId : null, source_job_id: tasks[source], filename: `${source}-fixture.png`, kind: 'image', media_type: 'image/png',
  size: png.byteLength, sha256: sha, version: versions[source], deleted_at: null, provider_id: 'history-local', model_id: 'history-model',
  created_at: '2026-10-24T12:00:00Z', updated_at: '2026-10-24T12:00:00Z', ...changes});
function host(who = actor.id) {bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: who});}
function seed() {
  localStorage.setItem(canvasStorageKey('image', project), JSON.stringify({nodes: [nodeId, otherNode].map(id => ({id, t: 'image_generate', title: id, x: 0, y: 0, prompt: draftPrompt})), edges: []}));
}
async function historyFixture(collaboration = false, legacyFirst = false) {
  if (collaboration) useStudio.getState().setCollaboration(token, actor, scope); else host(); seed();
  const owner = captureCanvasTaskOwner(project)!;
  if (legacyFirst) {
    const legacy = {schema_version: 1 as const, owner, nodeId, taskId: tasks.A};
    const candidate = checkedCanvasTaskCandidate(legacy, row('A', collaboration));
    if (!candidate) throw new Error('Expected valid old-client source observation');
    // This is the exact previous-client storage shape, before any v2 mutation.
    localStorage.setItem(canvasTaskBindingKey(owner, nodeId), JSON.stringify({...legacy, adoption: {
      assetId: assets.A, assetVersion: versions.A, assetSha256: sha, jobObservationSha256: await canvasCandidateObservationSha256(candidate),
    }}));
  }
  const writes: Source[] = legacyFirst ? ['B'] : sources;
  for (const source of writes) {
    expect(writeCanvasTaskBinding(owner, nodeId, tasks[source])).toBe(true);
    const observed = readCanvasTaskBinding(owner, nodeId)!;
    const candidate = checkedCanvasTaskCandidate(observed, row(source, collaboration));
    if (!candidate) throw new Error('Historical source fixture must satisfy the original candidate contract');
    expect(writeCanvasTaskAdoption(observed, {assetId: assets[source], assetVersion: versions[source], assetSha256: sha,
      jobObservationSha256: await canvasCandidateObservationSha256(candidate)}, () => true)).toBe(true);
  }
  const binding = readCanvasTaskBinding(owner, nodeId)!;
  if (binding.schema_version !== 2) throw new Error('Historical fixture requires the actual typed journal');
  const key = canvasTaskBindingKey(owner, nodeId), raw = localStorage.getItem(key)!;
  const target = binding.history.find(entry => entry.taskId === tasks.A && entry.adoption)!;
  const alternate = binding.history.find(entry => entry.taskId === tasks.C && entry.adoption) || target;
  return {owner, binding, key, raw, target, alternate};
}
function http(options: {collaboration?: boolean; root?: boolean; download?: (source: Source, index: number) => Promise<Response>} = {}) {
  const state = {jobs: Object.fromEntries(sources.map(source => [source, row(source, options.collaboration)])) as Record<Source, ReturnType<typeof row>>,
    assets: Object.fromEntries(sources.map(source => [source, metadata(source, options.collaboration)])) as Record<Source, ReturnType<typeof metadata>>, downloads: 0, permission: true};
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if (init.method && init.method !== 'GET') throw new Error(`History fixture forbids mutation ${init.method} ${url}`);
    if (url === `/api/novels/${project}/image-jobs`) return json({items: sources.map(source => state.jobs[source])});
    for (const source of sources) {
      if (url === `/api/assets/${assets[source]}?novel_id=${project}`) return json(state.assets[source]);
      if (url === `/api/assets/${assets[source]}/download?novel_id=${project}`) return options.download
        ? options.download(source, ++state.downloads) : (state.downloads++, imageResponse());
    }
    if (url.endsWith('/permissions')) return json({actor_id: actor.id, domain: 'NOVEL', capabilities: {'domain.write': state.permission}});
    if (options.root && (url === '/api/asset-providers' || /\/(image-generations|visual-references)$/.test(url))) return json({items: []});
    throw new Error(`History fixture unexpected GET ${url}`);
  });
  vi.stubGlobal('fetch', fetcher); return {state, fetcher};
}
const view = (novelId = project, selectedNode = nodeId) => <CanvasNodeTaskStatus novelId={novelId} nodeId={selectedNode} nodePrompt={draftPrompt}/>;
const noWrites = (fetcher: ReturnType<typeof vi.fn>) => expect(fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET')).toHaveLength(0);
async function select(entry: CanvasTaskHistoryEntry) {
  const history = await screen.findByRole('region', {name: regionName});
  fireEvent.click(within(history).getByRole('radio', {name: `选择历史记录 ${entry.eventId}`})); return history;
}
async function read(entry: CanvasTaskHistoryEntry) {
  const history = await select(entry); fireEvent.click(within(history).getByRole('button', {name: readName}));
  await within(history).findByRole('button', {name: previewName}); return history;
}
async function prepare(entry: CanvasTaskHistoryEntry) {
  const history = await read(entry); fireEvent.click(within(history).getByRole('button', {name: previewName}));
  const image = await within(history).findByRole('img', {name: '原节点任务候选结果'});
  Object.defineProperties(image, {naturalWidth: {configurable: true, value: 1}, naturalHeight: {configurable: true, value: 1}}); fireEvent.load(image);
  await waitFor(() => expect((within(history).getByRole('button', {name: prepareName}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(within(history).getByRole('button', {name: prepareName}));
  const check = await within(history).findByRole('checkbox', {name: checkName});
  return {history, image, check, restore: within(history).getByRole('button', {name: restoreName})};
}
beforeEach(() => {
  localStorage.clear(); useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NodeBlob); vi.stubGlobal('PointerEvent', MouseEvent);
  let count = 0; makeUrl.mockReset().mockImplementation(() => `blob:history-fixture-${++count}`); revokeUrl.mockReset();
  vi.stubGlobal('URL', class extends NativeURL {static createObjectURL = makeUrl; static revokeObjectURL = revokeUrl;});
});
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});});

describe('independent browser-local adoption history restoration', () => {
  it('exposes local history after the initial status deadline without retrying or accepting its late response', async () => {
    const fixture = await historyFixture(); let finishFirst!: (value: Response) => void, firstSignal!: AbortSignal, reads = 0;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url !== `/api/novels/${project}/image-jobs` || init.method && init.method !== 'GET') throw new Error('Deadline fixture permits only the original job GET');
      if (++reads === 1) {firstSignal = init.signal as AbortSignal; return new Promise(resolve => {finishFirst = resolve;});}
      return Promise.resolve(json({items: sources.map(source => row(source))}));
    });
    vi.stubGlobal('fetch', fetcher);
    const nativeSetTimeout = globalThis.setTimeout, callbacks: Array<() => void> = [];
    const timer = vi.spyOn(globalThis, 'setTimeout');
    timer.mockImplementation(((callback: (...args: unknown[]) => void, delay?: number, ...args: unknown[]) => {
      if (delay === 15_000) callbacks.push(() => callback(...args));
      return nativeSetTimeout(callback, delay, ...args);
    }) as typeof setTimeout);
    try {
      render(view());
      expect(fetcher).toHaveBeenCalledTimes(1); expect(callbacks).toHaveLength(1);
      expect(screen.queryByRole('region', {name: regionName})).toBeNull(); expect(firstSignal.aborted).toBe(false);
      await act(async () => {callbacks[0]();});
      expect(firstSignal.aborted).toBe(true);
      const history = await screen.findByRole('region', {name: regionName});
      expect(fetcher).toHaveBeenCalledTimes(1); expect(localStorage.getItem(fixture.key)).toBe(fixture.raw);
      await act(async () => {finishFirst(json({items: sources.map(source => row(source))}));});
      expect(screen.queryByRole('region', {name: '原任务候选结果'})).toBeNull();
      expect(screen.queryByText('SUCCEEDED')).toBeNull(); expect(fetcher).toHaveBeenCalledTimes(1);
      await select(fixture.target); fireEvent.click(within(history).getByRole('button', {name: readName}));
      await within(history).findByRole('button', {name: previewName});
      expect(fetcher).toHaveBeenCalledTimes(2); expect(within(history).queryByRole('img')).toBeNull();
      expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
    } finally {timer.mockRestore();}
  });

  it('shows the current pin separately and selects historical A without reading or mutating current B', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); render(view());
    const history = await screen.findByRole('region', {name: regionName});
    const current = fixture.binding.history.at(-1)!;
    expect((within(history).getByRole('radio', {name: `选择历史记录 ${current.eventId}`}) as HTMLInputElement).disabled).toBe(true);
    expect(history.textContent).toContain(assets.A); expect(history.textContent).toContain(assets.B);
    const currentPin = within(history).getByLabelText('当前本机关联 pin');
    expect(currentPin.textContent).toContain(tasks.B); expect(currentPin.textContent).toContain(assets.B); expect(currentPin.textContent).not.toContain(assets.A);
    const calls = fetcher.mock.calls.length; await select(fixture.target); await act(async () => {});
    expect(fetcher).toHaveBeenCalledTimes(calls); expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('freshly previews and confirms historical A then appends a restore record while preserving every old record', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); const graph = localStorage.getItem(canvasStorageKey('image', project)); render(view());
    const {check, restore} = await prepare(fixture.target);
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); fireEvent.click(check); fireEvent.click(restore);
    await waitFor(() => expect(readCanvasTaskBinding(fixture.owner, nodeId)?.taskId).toBe(tasks.A));
    const result = readCanvasTaskBinding(fixture.owner, nodeId)!; if (result.schema_version !== 2) throw new Error('Expected journal');
    expect(result.revision).toBe(fixture.binding.revision + 1);
    expect(result.history.slice(0, -1)).toEqual(fixture.binding.history);
    expect(result.history.at(-1)).toMatchObject({operation: 'restore', taskId: tasks.A, sourceEventId: fixture.target.eventId, adoption: fixture.target.adoption});
    expect(result.adoption).toEqual(fixture.target.adoption); expect(localStorage.getItem(canvasStorageKey('image', project))).toBe(graph); noWrites(fetcher);
  });

  it('imports actual previous-client v1 pin A only when queuing B and explicitly restores that imported A after fresh review', async () => {
    const fixture = await historyFixture(false, true); const {fetcher} = http();
    expect(fixture.binding.history.map(entry => entry.operation)).toEqual(['import', 'queue', 'adopt']);
    expect(fixture.target).toMatchObject({operation: 'import', revision: 1, taskId: tasks.A, adoption: {assetId: assets.A}});
    render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check); fireEvent.click(restore);
    await waitFor(() => expect(readCanvasTaskBinding(fixture.owner, nodeId)?.taskId).toBe(tasks.A));
    const result = readCanvasTaskBinding(fixture.owner, nodeId)!;
    if (result.schema_version !== 2) throw new Error('Expected journal');
    expect(result.history.slice(0, -1)).toEqual(fixture.binding.history);
    expect(result.history.at(-1)).toMatchObject({operation: 'restore', sourceEventId: fixture.target.eventId, taskId: tasks.A, adoption: fixture.target.adoption});
    noWrites(fetcher);
  });

  it('preserves corrupt raw history and explains that it cannot be restored or overwritten', async () => {
    const fixture = await historyFixture(); const {fetcher} = http();
    const corrupt = '{"schema_version":2,"history":"fixture-broken"}'; localStorage.setItem(fixture.key, corrupt);
    render(view());
    expect(screen.getByText(/本机关联不可读取或格式无法核实/)).toBeTruthy();
    expect(screen.queryByRole('radio')).toBeNull(); expect(localStorage.getItem(fixture.key)).toBe(corrupt);
    expect(fetcher).not.toHaveBeenCalled(); noWrites(fetcher);
  });

  it('explains full capacity without pruning old records or offering a new prepared restore', async () => {
    const fixture = await historyFixture(); const {fetcher} = http();
    let current = readCanvasTaskBinding(fixture.owner, nodeId)!;
    while (current.schema_version === 2 && current.history.length < MAX_CANVAS_TASK_HISTORY) {
      expect(writeCanvasTaskBinding(fixture.owner, nodeId, `fixture-capacity-${current.revision + 1}`)).toBe(true);
      current = readCanvasTaskBinding(fixture.owner, nodeId)!;
    }
    const full = localStorage.getItem(fixture.key); render(view());
    expect(await screen.findByText(/历史容量已满，旧记录全部保留/)).toBeTruthy();
    expect(screen.queryByRole('checkbox', {name: checkName})).toBeNull();
    expect(localStorage.getItem(fixture.key)).toBe(full); noWrites(fetcher);
  });

  it('does not invent asset recovery targets when the saved journal contains only a queued task', async () => {
    host(); seed(); const owner = captureCanvasTaskOwner(project)!;
    expect(writeCanvasTaskBinding(owner, nodeId, tasks.B)).toBe(true); const {fetcher} = http(); render(view());
    expect(await screen.findByText(/当前历史没有可作为资产恢复目标的记录/)).toBeTruthy();
    expect(screen.queryByRole('radio')).toBeNull(); expect(screen.queryByRole('button', {name: readName})).toBeNull(); noWrites(fetcher);
  });

  it('requires a new image load and checkbox after reopening instead of treating stored history as approval', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); let mounted = render(view());
    const original = await prepare(fixture.target); fireEvent.click(original.check); mounted.unmount(); mounted = render(view());
    const history = await read(fixture.target); expect(within(history).queryByRole('img')).toBeNull();
    fireEvent.click(within(history).getByRole('button', {name: previewName})); await within(history).findByRole('img');
    expect(within(history).queryByRole('checkbox', {name: checkName})).toBeNull();
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('does not resurrect a checked historical A review after selecting C and A without a new read or load', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    act(() => {
      fireEvent.click(screen.getByRole('radio', {name: `选择历史记录 ${fixture.alternate.eventId}`}));
      fireEvent.click(screen.getByRole('radio', {name: `选择历史记录 ${fixture.target.eventId}`})); fireEvent.click(restore);
    });
    await act(async () => {}); expect(screen.queryByRole('checkbox', {name: checkName})).toBeNull();
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it.each([
    ['deleted asset', {deleted_at: '2026-10-24T13:00:00Z'}], ['version', {version: 9}], ['hash', {sha256: 'f'.repeat(64)}],
  ])('does not restore historical A when its %s changed after the review', async (_label, changes) => {
    const fixture = await historyFixture(); const {state, fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    state.assets.A = metadata('A', false, changes as Record<string, unknown>); fireEvent.click(restore); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('does not restore a historical pin if its source job observation changed', async () => {
    const fixture = await historyFixture(); const {state, fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    state.jobs.A = row('A', false, {attempt: 2, updated_at: '2026-10-24T13:00:00Z'}); fireEvent.click(restore); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('does not restore after collaboration write permission is revoked', async () => {
    const fixture = await historyFixture(true); const {state, fetcher} = http({collaboration: true}); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    state.permission = false; fireEvent.click(restore); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it.each(['client', 'project'])('retires old restore consent after same-object API %s A/B/A', async changed => {
    const fixture = await historyFixture(true); const {fetcher} = http({collaboration: true}); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    const original = getCollaborationContext();
    act(() => {
      setCollaborationContext(changed === 'client' ? {...original, sessionToken: 'transient-history-client'} : {...original, scope: {...scope, projectId: 'other-history-project'}});
      setCollaborationContext(original); fireEvent.click(restore);
    });
    expect(getCollaborationContext()).toBe(original); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('retires old restore consent after verified Host A/B/A', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    act(() => {host('transient-history-author'); host(); fireEvent.click(restore);}); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it.each(['project', 'node'])('does not carry historical restore consent into another %s', async changed => {
    const fixture = await historyFixture(); const {fetcher} = http(); const mounted = render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    mounted.rerender(changed === 'project' ? view('other-history-project') : view(project, otherNode)); fireEvent.click(restore); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('does not carry a historical restore through a current source prompt A/B/A', async () => {
    const fixture = await historyFixture(); const {fetcher} = http({root: true}); render(<ImageRebuild novelId={project} view="canvas" shellMode="basic" onViewChange={() => {}}/>);
    const element = document.querySelector(`[data-node-id="${nodeId}"]`)!;
    fireEvent.pointerDown(element, {button: 0, pointerId: 1, clientX: 40, clientY: 40}); fireEvent.pointerUp(element, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
    const {check, restore} = await prepare(fixture.target); fireEvent.click(check); const editor = screen.getByLabelText('本次提示词');
    act(() => {fireEvent.change(editor, {target: {value: 'Transient source draft'}}); fireEvent.change(editor, {target: {value: draftPrompt}}); fireEvent.click(restore);});
    await act(async () => {}); expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('ignores a late confirmation download after the selected history source was retired', async () => {
    const fixture = await historyFixture(); let finish!: (value: Response) => void;
    const {fetcher} = http({download: (_source, index) => index === 1 ? Promise.resolve(imageResponse()) : new Promise(resolve => {finish = resolve;})});
    render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check); fireEvent.click(restore);
    await waitFor(() => expect(finish).toBeTypeOf('function')); await select(fixture.alternate);
    await act(async () => {finish(imageResponse());}); expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); noWrites(fetcher);
  });

  it('does not overwrite a newer observed current binding while a history restore is pending', async () => {
    const fixture = await historyFixture(); let finish!: (value: Response) => void;
    const {fetcher} = http({download: (_source, index) => index === 1 ? Promise.resolve(imageResponse()) : new Promise(resolve => {finish = resolve;})});
    render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check); fireEvent.click(restore);
    await waitFor(() => expect(finish).toBeTypeOf('function'));
    act(() => {expect(writeCanvasTaskBinding(fixture.owner, nodeId, 'newer-observed-task')).toBe(true);});
    const newer = localStorage.getItem(fixture.key);
    await act(async () => {finish(imageResponse());}); expect(localStorage.getItem(fixture.key)).toBe(newer); noWrites(fetcher);
  });

  it('appends only one restore event for duplicate confirm clicks', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    act(() => {fireEvent.click(restore); fireEvent.click(restore); fireEvent.click(restore);});
    await waitFor(() => expect(readCanvasTaskBinding(fixture.owner, nodeId)?.taskId).toBe(tasks.A));
    const current = readCanvasTaskBinding(fixture.owner, nodeId)!;
    expect(current.schema_version === 2 && current.history.length).toBe(fixture.binding.history.length + 1); noWrites(fetcher);
  });

  it('preserves the complete old history if storage rejects the restore append', async () => {
    const fixture = await historyFixture(); const {fetcher} = http(); render(view()); const {check, restore} = await prepare(fixture.target); fireEvent.click(check);
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {throw new Error('Fixture history storage rejected');});
    fireEvent.click(restore); await waitFor(() => expect(set).toHaveBeenCalled()); await act(async () => {});
    expect(localStorage.getItem(fixture.key)).toBe(fixture.raw); expect(set).toHaveBeenCalledTimes(1); noWrites(fetcher);
  });
});
