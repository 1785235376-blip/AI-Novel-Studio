// @vitest-environment jsdom
// Independent binding/reopen tests. HTTP replies are software fixtures, not File/provider/media acceptance.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {ImageQueuePanel} from '../../novel/ImageQueuePanel';
import {canvasStorageKey} from '../canvas/RebuildCanvas';
import {canvasTaskBindingKey, captureCanvasTaskOwner, readCanvasTaskBinding, writeCanvasTaskBinding} from './canvasTaskBinding';
import {CanvasNodeTaskStatus} from './CanvasNodeTaskStatus';
import {CanvasImageQueue} from './CanvasImageQueue';
import {ImageRebuild} from './ImageRebuild';

const project = 'binding-project', nodeId = 'binding-image-node';
const taskId = '11111111-1111-4111-8111-111111111111';
const originalPrompt = 'Fixture original queued lighthouse prompt';
const secret = 'fixture-host-token-do-not-persist';
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
const provider = {provider_id: 'binding-local', display_name: 'Binding fixture service', default_model: 'binding-model', configured: true, registered: true, reachable: true, local: true};
const row = (status = 'QUEUED', changes: Record<string, unknown> = {}) => ({
  id: taskId, novel_id: project, branch_id: null, owner_actor_id: 'binding-author-a',
  status, approval_status: 'PENDING', attempt: 0, provider_id: provider.provider_id,
  model_id: provider.default_model, prompt: originalPrompt,
  parameters: {width: 1024, height: 1024, steps: 28, seed: 1}, allow_cloud_prompt: false,
  request_sha256: 'a'.repeat(64), created_at: '2026-10-23T12:00:00Z', updated_at: '2026-10-23T12:00:00Z', ...changes,
});
function seed(novelId = project, prompt = originalPrompt, type = 'image_generate') {
  localStorage.setItem(canvasStorageKey('image', novelId), JSON.stringify({nodes: [{id: nodeId, t: type, title: 'Fixture image node', x: 0, y: 0, prompt}], edges: []}));
}
function host(actor = 'binding-author-a') {
  bindLocalHostSession(secret, {session_mode: 'LOCAL_HOST', actor_id: actor});
}
function selectNode() {
  const node = document.querySelector(`[data-node-id="${nodeId}"]`)!;
  fireEvent.pointerDown(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
  fireEvent.pointerUp(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
function image(novelId = project) {
  return <ImageRebuild novelId={novelId} view="dual" shellMode="pro" onViewChange={() => {}}/>;
}
async function expectServerStatus(container: HTMLElement, value: string) {
  const badge = await within(container).findByText(value);
  expect(badge.closest('p')?.textContent).toBe(`服务端任务状态：${value}`);
}
function bindFixture() {
  const owner = captureCanvasTaskOwner(project);
  if (!owner) throw new Error('Independent fixture requires an actual verified owner');
  expect(writeCanvasTaskBinding(owner, nodeId, taskId)).toBe(true);
  return owner;
}
function posts(fetcher: ReturnType<typeof vi.fn>) {
  return fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');
}
function jobGetCount(fetcher: ReturnType<typeof vi.fn>) {
  return fetcher.mock.calls.filter(([url, init]) => String(url).endsWith('/image-jobs') && (!init?.method || init.method === 'GET')).length;
}
function queueFixture(options: {deferCreate?: boolean; providers?: unknown[]; receiptChanges?: Record<string, unknown>} = {}) {
  const state = {jobs: [] as ReturnType<typeof row>[], status: 'QUEUED', finish: undefined as undefined | (() => void)};
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if (url === '/api/asset-providers') return json({items: options.providers ?? [provider]});
    if (/^\/api\/novels\/[^/]+\/image-jobs$/.test(url)) {
      if (init.method === 'POST') {
        const command = JSON.parse(String(init.body));
        const created = row('QUEUED', {...command, id: taskId, ...options.receiptChanges});
        if (options.deferCreate) return new Promise(resolve => {
          state.finish = () => {state.jobs = [created]; resolve(json(created, 202));};
        });
        state.jobs = [created];
        return json(created, 202);
      }
      return json({items: state.jobs.map(job => ({...job, status: state.status}))});
    }
    if (/\/(?:image-generations|visual-references)$/.test(url)) return json({items: []});
    throw new Error(`Unexpected independent binding fixture ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return {state, fetcher};
}
async function startQueue() {
  selectNode();
  fireEvent.click(screen.getByRole('button', {name: '为此节点准备图片任务'}));
  const drawer = screen.getByRole('complementary', {name: '画布图片任务'});
  await within(drawer).findByRole('option', {name: provider.display_name});
  fireEvent.change(within(drawer).getByLabelText('画布任务图片服务'), {target: {value: provider.provider_id}});
  fireEvent.click(within(drawer).getByRole('button', {name: '保存到生成队列'}));
  return drawer;
}

beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  vi.stubGlobal('PointerEvent', MouseEvent);
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('independent original image-node task binding', () => {
  it('binds only the returned queued ID, reopens from storage and reads fresh server status without execution', async () => {
    host(); seed();
    const {state, fetcher} = queueFixture();
    let view = render(image());
    await startQueue();
    const owner = captureCanvasTaskOwner(project)!;
    await waitFor(() => expect(readCanvasTaskBinding(owner, nodeId)?.taskId).toBe(taskId));
    const stored = localStorage.getItem(canvasTaskBindingKey(owner, nodeId))!;
    expect(stored).toContain(taskId);
    expect(stored).not.toContain(secret);
    expect(stored).not.toContain(originalPrompt);
    expect(stored).not.toContain('binding-model');
    expect(posts(fetcher)).toHaveLength(1);
    view.unmount();
    state.status = 'RUNNING';
    view = render(image());
    selectNode();
    const status = screen.getByRole('region', {name: '原节点图片任务'});
    await expectServerStatus(status, 'RUNNING');
    expect(within(status).getByText(`原入队任务 ID：${taskId}`)).toBeTruthy();
    expect(posts(fetcher)).toHaveLength(1);
    fireEvent.click(within(status).getByRole('button', {name: '打开原图片任务'}));
    const drawer = screen.getByRole('complementary', {name: '画布图片任务'});
    await within(drawer).findByText(`任务 ID：${taskId}`);
    expect(drawer.querySelector('article[aria-current="true"]')?.textContent).toContain(taskId);
    expect(posts(fetcher)).toHaveLength(1);
  });

  it('reads an already bound original task without provider configuration or a new queue request', async () => {
    host(); seed(); bindFixture();
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === `/api/novels/${project}/image-jobs`) return json({items: [row('SUCCEEDED')]});
      throw new Error(`Read-only status must not ask for providers or mutate: ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await expectServerStatus(screen.getByRole('region', {name: '原节点图片任务'}), 'SUCCEEDED');
    expect(jobGetCount(fetcher)).toBe(1);
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('does not infer original task access for an anonymous owner or an absent image node', async () => {
    seed();
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    const view = render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    expect(screen.getByText(/尚未验证可持久关联的身份/)).toBeTruthy();
    expect(captureCanvasTaskOwner(project)).toBeUndefined();
    expect(fetcher).not.toHaveBeenCalled();
    view.unmount();
    host(); seed(project, originalPrompt, 'image_reference');
    const owner = captureCanvasTaskOwner(project)!;
    expect(writeCanvasTaskBinding(owner, nodeId, taskId)).toBe(false);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    expect(screen.getByText('此节点尚未关联已入队任务。')).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each(['actor', 'project', 'branch'])('keeps the original binding private after a collaboration %s owner change', async changed => {
    seed(); seed('binding-project-b');
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-collaboration-secret', actor, scope);
    const owner = bindFixture();
    expect(localStorage.getItem(canvasTaskBindingKey(owner, nodeId))).not.toContain('fixture-collaboration-secret');
    const nextProject = changed === 'project' ? 'binding-project-b' : project;
    useStudio.getState().setCollaboration('fixture-second-client-secret', {...actor, ...(changed === 'actor' ? {id: 'binding-author-b'} : {})},
      {...scope, projectId: nextProject, ...(changed === 'branch' ? {branchId: 'binding-branch-b'} : {})});
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={nextProject} nodeId={nodeId}/>);
    expect(screen.getByText('此节点尚未关联已入队任务。')).toBeTruthy();
    expect(screen.queryByText(`原入队任务 ID：${taskId}`)).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('rejects a forged storage binding rather than using an arbitrary requested task ID', () => {
    host(); seed(); const owner = bindFixture();
    const key = canvasTaskBindingKey(owner, nodeId);
    localStorage.setItem(key, JSON.stringify({schema_version: 1, owner: {...owner, actorId: 'foreign-author'}, nodeId, taskId}));
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    expect(screen.getByText(/本机关联不可读取或格式无法核实/)).toBeTruthy();
    expect(localStorage.getItem(key)).toContain('foreign-author');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('does not attach a late queue receipt after the original node was deleted', async () => {
    host(); seed(); const {state, fetcher} = queueFixture({deferCreate: true});
    render(image());
    await startQueue();
    await waitFor(() => expect(state.finish).toBeTypeOf('function'));
    const original = document.querySelector(`[data-node-id="${nodeId}"]`)!;
    fireEvent.contextMenu(original, {clientX: 40, clientY: 40});
    await act(async () => {
      fireEvent.click(screen.getByRole('menuitem', {name: '删除节点'}));
      state.finish!();
    });
    const owner = captureCanvasTaskOwner(project)!;
    expect(readCanvasTaskBinding(owner, nodeId)).toBeUndefined();
    expect(posts(fetcher)).toHaveLength(1);
  });

  it('does not attach a late queue receipt after the originating owner went A/B/A', async () => {
    host(); seed(); const {state, fetcher} = queueFixture({deferCreate: true});
    render(image()); await startQueue();
    await waitFor(() => expect(state.finish).toBeTypeOf('function'));
    act(() => {host('binding-author-b'); host('binding-author-a');});
    await act(async () => {state.finish!();});
    expect(readCanvasTaskBinding(captureCanvasTaskOwner(project)!, nodeId)).toBeUndefined();
    expect(posts(fetcher)).toHaveLength(1);
  });

  it('does not overwrite a newer original-task status with an older late status read', async () => {
    host(); seed(); bindFixture();
    let reads = 0, finishOld!: (value: Response) => void;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === `/api/novels/${project}/image-jobs`) return ++reads === 1
        ? new Promise(resolve => {finishOld = resolve;}) : Promise.resolve(json({items: [row('RUNNING')]}));
      throw new Error(`Read-only fixture unexpected ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    fireEvent.click(screen.getByRole('button', {name: '刷新原任务状态'}));
    await expectServerStatus(screen.getByRole('region', {name: '原节点图片任务'}), 'RUNNING');
    await act(async () => {finishOld(json({items: [row('QUEUED')]}));});
    expect(screen.queryByText('QUEUED')).toBeNull();
    expect(screen.getByText('RUNNING')).toBeTruthy();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('does not present an original queued task as confirmation that a newly edited node prompt was queued', async () => {
    host(); seed(); bindFixture(); seed(project, 'A different unqueued draft prompt');
    const {state, fetcher} = queueFixture(); state.jobs = [row('QUEUED')];
    render(image()); selectNode();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('A different unqueued draft prompt');
    const status = screen.getByRole('region', {name: '原节点图片任务'});
    await expectServerStatus(status, 'QUEUED');
    expect(within(status).getByText(/原任务不代表当前提示词已经入队/)).toBeTruthy();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('reopens the same original task from the basic single image canvas without automatically posting', async () => {
    host(); seed(); bindFixture();
    const {state, fetcher} = queueFixture(); state.jobs = [row('RUNNING')]; state.status = 'RUNNING';
    render(<ImageRebuild novelId={project} view="canvas" shellMode="basic" onViewChange={() => {}}/>);
    selectNode();
    const status = screen.getByRole('region', {name: '原节点图片任务'});
    await expectServerStatus(status, 'RUNNING');
    fireEvent.click(within(status).getByRole('button', {name: '打开原图片任务'}));
    const drawer = screen.getByRole('complementary', {name: '画布图片任务'});
    await within(drawer).findByText(`任务 ID：${taskId}`);
    expect(drawer.querySelector('article[aria-current="true"]')?.textContent).toContain(taskId);
    expect(posts(fetcher)).toHaveLength(0);
  });

  it.each([401, 403])('clears previously verified status after a %s refresh instead of retaining a success claim', async denied => {
    host(); seed(); bindFixture();
    let permitted = true;
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === `/api/novels/${project}/image-jobs`) return permitted
        ? json({items: [row('RUNNING')]}) : json({detail: 'Independent fixture permission expired'}, denied);
      throw new Error(`Readonly permission fixture unexpected ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await expectServerStatus(screen.getByRole('region', {name: '原节点图片任务'}), 'RUNNING');
    permitted = false;
    fireEvent.click(screen.getByRole('button', {name: '刷新原任务状态'}));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toBeTruthy());
    expect(screen.queryByText('RUNNING')).toBeNull();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it.each(['absent', 'duplicate', 'foreign-project', 'unrecognized-state'])('does not infer a verified original status from a %s response', async invalid => {
    host(); seed(); bindFixture();
    const items = invalid === 'absent' ? [] : invalid === 'duplicate' ? [row(), row()]
      : [row(invalid === 'unrecognized-state' ? 'INVENTED_COMPLETE' : 'QUEUED', invalid === 'foreign-project' ? {novel_id: 'foreign-project'} : {})];
    const fetcher = vi.fn(async () => json({items})); vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await screen.findByText('原任务当前不可读或状态无法核实；不会新建替代任务。');
    expect(screen.queryByText('QUEUED')).toBeNull();
    expect(screen.queryByText('INVENTED_COMPLETE')).toBeNull();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('retires a pending status read through an API-only A/B/A transport change', async () => {
    host(); seed(); bindFixture();
    let reads = 0, finishOld!: (value: Response) => void;
    const fetcher = vi.fn(() => ++reads === 1 ? new Promise<Response>(resolve => {finishOld = resolve;})
      : Promise.resolve(json({items: [row('RUNNING')]})));
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await waitFor(() => expect(finishOld).toBeTypeOf('function'));
    act(() => {
      setCollaborationContext({sessionToken: '', localHostToken: 'other-fixture-client'});
      setCollaborationContext({sessionToken: ''});
    });
    await act(async () => {finishOld(json({items: [row('SUCCEEDED')]}));});
    expect(screen.queryByText('SUCCEEDED')).toBeNull();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('does not apply a previous task read after the same original node receives a new explicit binding', async () => {
    host(); seed(); const owner = bindFixture();
    const nextId = '22222222-2222-4222-8222-222222222222';
    let reads = 0, finishOld!: (value: Response) => void;
    const fetcher = vi.fn((): Promise<Response> => ++reads === 1 ? new Promise(resolve => {finishOld = resolve;})
      : Promise.resolve(json({items: [row('RUNNING', {id: nextId})]})));
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await waitFor(() => expect(finishOld).toBeTypeOf('function'));
    act(() => {expect(writeCanvasTaskBinding(owner, nodeId, nextId)).toBe(true);});
    const region = screen.getByRole('region', {name: '原节点图片任务'});
    await expectServerStatus(region, 'RUNNING');
    await act(async () => {finishOld(json({items: [row('SUCCEEDED')]}));});
    expect(within(region).getByText(`原入队任务 ID：${nextId}`)).toBeTruthy();
    expect(within(region).queryByText(`原入队任务 ID：${taskId}`)).toBeNull();
    expect(within(region).queryByText('SUCCEEDED')).toBeNull();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('reads the bound original job only from its matching collaboration branch', async () => {
    seed();
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-collaboration-secret', actor, scope);
    bindFixture();
    const fetcher = vi.fn(async () => json({items: [row('RUNNING', {branch_id: scope.branchId})]}));
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await expectServerStatus(screen.getByRole('region', {name: '原节点图片任务'}), 'RUNNING');
    expect(jobGetCount(fetcher)).toBe(1);
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('rejects an original-job row from another collaboration branch even with the same project and task ID', async () => {
    seed();
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-collaboration-secret', actor, scope);
    bindFixture();
    const fetcher = vi.fn(async () => json({items: [row('RUNNING', {branch_id: 'foreign-branch'})]}));
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await screen.findByText('原任务当前不可读或状态无法核实；不会新建替代任务。');
    expect(screen.queryByText('RUNNING')).toBeNull();
    expect(posts(fetcher)).toHaveLength(0);
  });

  it.each(['prompt', 'model_id'])('does not bind a returned queued ID when the POST receipt has a different %s', async field => {
    host(); seed();
    const {fetcher} = queueFixture({receiptChanges: {[field]: 'A different independent fixture value'}});
    render(image());
    await startQueue();
    await screen.findByText(/任务回执/);
    expect(readCanvasTaskBinding(captureCanvasTaskOwner(project)!, nodeId)).toBeUndefined();
    expect(posts(fetcher)).toHaveLength(1);
  });

  it('API-only owner rerender does not re-adopt old provider metadata and prompt for a new transport owner', async () => {
    seed();
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-client-a', actor, scope);
    const {fetcher} = queueFixture();
    render(<CanvasImageQueue novelId={project} nodeId={nodeId} prompt={originalPrompt} onClose={() => {}}/>);
    await screen.findByRole('option', {name: provider.display_name});
    fireEvent.change(screen.getByLabelText('画布任务图片服务'), {target: {value: provider.provider_id}});
    expect((screen.getByLabelText('画布任务模型') as HTMLInputElement).value).toBe(provider.default_model);
    act(() => setCollaborationContext({sessionToken: 'fixture-client-b', actor: {...actor, id: 'binding-author-b'}, scope: {...scope, branchId: 'binding-branch-b'}}));
    // Updating a field rerenders the old panel without a store identity change.
    fireEvent.change(screen.getByLabelText('画布任务模型'), {target: {value: 'edited-fixture-model'}});
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    await act(async () => {});
    expect(useStudio.getState().actor?.id).toBe(actor.id);
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('API-only owner notification immediately retires a previously displayed original status under a new transport owner', async () => {
    seed();
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-client-a', actor, scope);
    bindFixture();
    const fetcher = vi.fn(async () => json({items: [row('RUNNING', {branch_id: scope.branchId})]}));
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasNodeTaskStatus novelId={project} nodeId={nodeId}/>);
    await expectServerStatus(screen.getByRole('region', {name: '原节点图片任务'}), 'RUNNING');
    act(() => setCollaborationContext({sessionToken: 'fixture-client-b', actor: {...actor, id: 'binding-author-b'}, scope: {...scope, branchId: 'binding-branch-b'}}));
    expect(screen.queryByText('RUNNING')).toBeNull();
    expect(screen.queryByText(`原入队任务 ID：${taskId}`)).toBeNull();
    expect(jobGetCount(fetcher)).toBe(1);
    expect(posts(fetcher)).toHaveLength(0);
  });

  it('standalone queue client notification clears old jobs and prevents reads or writes after parameter rerender', async () => {
    const actor = {id: 'binding-author-a', displayName: 'Fixture author', workspaceId: 'binding-workspace'};
    const scope = {workspaceId: 'binding-workspace', projectId: project, storylineId: 'binding-story', branchId: 'binding-branch-a'};
    useStudio.getState().setCollaboration('fixture-client-a', actor, scope);
    const {state, fetcher} = queueFixture(); state.jobs = [row()];
    const draft = {provider_id: provider.provider_id, model_id: provider.default_model, prompt: originalPrompt};
    render(<ImageQueuePanel novelId={project} draft={draft} local/>);
    await screen.findByText(`任务 ID：${taskId}`);
    const readsBefore = jobGetCount(fetcher);
    act(() => setCollaborationContext({sessionToken: 'fixture-client-b', actor: {...actor, id: 'binding-author-b'}, scope: {...scope, branchId: 'binding-branch-b'}}));
    expect(screen.queryByText(`任务 ID：${taskId}`)).toBeNull();
    expect(screen.getByText(/图片任务客户端已切换/)).toBeTruthy();
    const save = screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('队列图片宽度'), {target: {value: '768'}});
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    fireEvent.click(screen.getByRole('button', {name: '刷新任务'}));
    await act(async () => {});
    expect(screen.queryByText(`任务 ID：${taskId}`)).toBeNull();
    expect(jobGetCount(fetcher)).toBe(readsBefore);
    expect(posts(fetcher)).toHaveLength(0);
  });
});
