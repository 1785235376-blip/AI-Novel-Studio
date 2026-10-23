// @vitest-environment jsdom
// Independent boundary review: real components/client with explicitly synthetic HTTP responses.
// No provider, File backend, media execution or browser acceptance is represented here.
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext, type AssetProviderStatus} from '../../api';
import {bindLocalHostSession, useLocalHostSession} from '../../localHostSession';
import {useStudio} from '../../store';
import {CanvasImageQueue} from './CanvasImageQueue';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});
const provider = (id = 'review-local', local = true): AssetProviderStatus => ({provider_id: id, display_name: id, default_model: `${id}-model`, configured: true, registered: true, reachable: true, local});
const job = {id: 'review-server-job', status: 'QUEUED', prompt: 'Review-owned prompt', provider_id: 'review-local', model_id: 'review-local-model', approval_status: 'PENDING', attempt: 0};
const commandPosts = (fetcher: ReturnType<typeof vi.fn>) => fetcher.mock.calls.filter(([url, init]) => /\/image-jobs$/.test(String(url)) && init?.method === 'POST');
const executions = (fetcher: ReturnType<typeof vi.fn>) => fetcher.mock.calls.filter(([url]) => /\/(execute|accept|retry)(?:\?|$)/.test(String(url)));
const props = {novelId: 'review-project', nodeId: 'review-node', prompt: 'Review-owned prompt', onClose: () => {}};
function http(options: {providers?: AssetProviderStatus[]; providerStatus?: number; postStatus?: number; post?: () => Promise<Response>; jobs?: unknown[]} = {}) {
  let jobs = options.jobs || [];
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if (url === '/api/asset-providers') return options.providerStatus
      ? json({code: options.providerStatus === 401 ? 'SESSION_REQUIRED' : 'FORBIDDEN', message: 'Review permission denied'}, options.providerStatus)
      : json({items: options.providers || [provider()]});
    if (/^\/api\/novels\/[^/]+\/image-jobs$/.test(url)) {
      if (init.method === 'POST') {
        if (options.post) return options.post();
        if (options.postStatus) return json({code: 'FORBIDDEN', message: 'Review queue write denied'}, options.postStatus);
        jobs = [job];
        return json(job, 202);
      }
      return json({items: jobs});
    }
    throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
async function ready(id = 'review-local') {
  await screen.findByRole('option', {name: id});
  fireEvent.change(screen.getByLabelText('画布任务图片服务'), {target: {value: id}});
}
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('independent image queue boundary review', () => {
  it.each([401, 403])('does not permit creation after provider configuration HTTP %s', async status => {
    const fetcher = http({providerStatus: status});
    render(<CanvasImageQueue {...props}/>);
    await screen.findByRole('alert');
    const save = screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(save);
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it.each([401, 403])('surfaces queue POST HTTP %s without inventing a Job ID or executing', async status => {
    const fetcher = http({postStatus: status});
    render(<CanvasImageQueue {...props}/>);
    await ready();
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    await screen.findByRole('alert');
    expect(commandPosts(fetcher)).toHaveLength(1);
    expect(screen.queryByText(/任务 ID：/)).toBeNull();
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('submits one request for repeated clicks while the same queue save is pending', async () => {
    let finish!: (response: Response) => void;
    const fetcher = http({post: () => new Promise(resolve => {finish = resolve;})});
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const save = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {fireEvent.click(save); fireEvent.click(save); fireEvent.click(save);});
    expect(commandPosts(fetcher)).toHaveLength(1);
    await act(async () => {finish(json(job, 202));});
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('invalidates cloud consent when the selected service changes and when it is revoked', async () => {
    const fetcher = http({providers: [provider('review-cloud-a', false), provider('review-cloud-b', false)]});
    render(<CanvasImageQueue {...props}/>);
    await ready('review-cloud-a');
    fireEvent.click(screen.getByRole('checkbox', {name: /^允许本次向/}));
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('画布任务图片服务'), {target: {value: 'review-cloud-b'}});
    expect((screen.getByRole('checkbox', {name: /^允许本次向/}) as HTMLInputElement).checked).toBe(false);
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', {name: /^允许本次向/}));
    fireEvent.click(screen.getByRole('checkbox', {name: /^允许本次向/}));
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    expect(commandPosts(fetcher)).toHaveLength(0);
  });

  it.each(['service', 'model', 'consent'])('rejects the old save after a same-batch input %s change invalidates confirmation', async changed => {
    const fetcher = http({providers: [provider('review-cloud-a', false), provider('review-cloud-b', false)]});
    render(<CanvasImageQueue {...props}/>);
    await ready('review-cloud-a');
    fireEvent.click(screen.getByRole('checkbox', {name: /^允许本次向/}));
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement;
    expect(oldSave.disabled).toBe(false);
    act(() => {
      if (changed === 'service') fireEvent.change(screen.getByLabelText('画布任务图片服务'), {target: {value: 'review-cloud-b'}});
      else if (changed === 'model') fireEvent.change(screen.getByLabelText('画布任务模型'), {target: {value: 'review-new-model'}});
      else fireEvent.click(screen.getByRole('checkbox', {name: /^允许本次向/}));
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('clears previously read private tasks and blocks writes after queue refresh is forbidden', async () => {
    let reads = 0;
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === '/api/asset-providers') return json({items: [provider()]});
      if (url === '/api/novels/review-project/image-jobs') {
        if (init.method === 'POST') return json(job, 202);
        return ++reads === 1 ? json({items: [{...job, prompt: 'Private permission-retired prompt'}]})
          : json({code: 'FORBIDDEN', message: 'Review queue read denied'}, 403);
      }
      throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue {...props}/>);
    await ready();
    await screen.findByText('任务 ID：review-server-job');
    fireEvent.click(screen.getByRole('button', {name: '刷新任务'}));
    await screen.findByRole('alert');
    expect(screen.queryAllByText(/任务 ID：review-server-job|Private permission-retired prompt/)).toHaveLength(0);
    const save = screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(save);
    expect(commandPosts(fetcher)).toHaveLength(0);
  });

  it('does not send old input when identity changes and the old save callback runs before React commits', async () => {
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      useStudio.getState().setCollaboration('review-next-client');
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('does not revive an old save callback during a same-batch identity A/B/A transition', async () => {
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      useStudio.getState().setCollaboration('review-transient-client');
      useStudio.getState().setCollaboration('');
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
  });

  it('blocks the old save callback when the shared API client context changes before the store rerenders', async () => {
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      setCollaborationContext({sessionToken: 'review-rebound-api-client'});
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('drops late provider metadata when only the shared API client context has changed', async () => {
    let finishProviders!: (response: Response) => void;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') return new Promise(resolve => {finishProviders = resolve;});
      if (url === '/api/novels/review-project/image-jobs') return Promise.resolve(json({items: []}));
      throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue {...props}/>);
    await act(async () => {
      setCollaborationContext({sessionToken: 'review-rebound-api-client'});
      finishProviders(json({items: [provider('review-private-retired-service')]}));
    });
    expect(screen.queryByRole('option', {name: 'review-private-retired-service'})).toBeNull();
    expect(commandPosts(fetcher)).toHaveLength(0);
  });

  it('blocks an old save across API-only A/B/A even when the exact original client context object returns', async () => {
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const originalContext = getCollaborationContext();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      setCollaborationContext({sessionToken: 'review-api-only-transient'});
      setCollaborationContext(originalContext);
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('drops deferred private provider and jobs across API-only A/B/A back to the same client context object', async () => {
    let finishProviders!: (response: Response) => void, finishJobs!: (response: Response) => void;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') return new Promise(resolve => {finishProviders = resolve;});
      if (url === '/api/novels/review-project/image-jobs') return new Promise(resolve => {finishJobs = resolve;});
      throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue {...props}/>);
    const originalContext = getCollaborationContext();
    act(() => {
      setCollaborationContext({sessionToken: 'review-api-only-transient'});
      setCollaborationContext(originalContext);
    });
    await act(async () => {
      finishProviders(json({items: [provider('review-api-aba-private-service')]}));
      finishJobs(json({items: [{...job, id: 'review-api-aba-private-job', prompt: 'Private API ABA prompt'}]}));
    });
    expect(screen.queryByRole('option', {name: 'review-api-aba-private-service'})).toBeNull();
    expect(screen.queryAllByText(/review-api-aba-private-job|Private API ABA prompt/)).toHaveLength(0);
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it.each(['project', 'branch'])('blocks the old save callback after a same-batch collaboration %s change', async changed => {
    const actor = {id: 'review-author', displayName: 'Review author', workspaceId: 'review-workspace'};
    const scope = {workspaceId: 'review-workspace', projectId: 'review-project', storylineId: 'review-story', branchId: 'review-branch-a'};
    useStudio.getState().setCollaboration('review-shared-session', actor, scope);
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      useStudio.getState().setCollaboration('review-shared-session', actor, {...scope,
        ...(changed === 'project' ? {projectId: 'review-other-project'} : {branchId: 'review-branch-b'}),
      });
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('blocks the old save callback during a same-batch verified local-host client change', async () => {
    bindLocalHostSession('review-host-a', {session_mode: 'LOCAL_HOST', actor_id: 'review-actor-a'});
    const fetcher = http();
    render(<CanvasImageQueue {...props}/>);
    await ready();
    const oldSave = screen.getByRole('button', {name: '保存到生成队列'});
    act(() => {
      bindLocalHostSession('review-host-b', {session_mode: 'LOCAL_HOST', actor_id: 'review-actor-b'});
      fireEvent.click(oldSave);
    });
    expect(commandPosts(fetcher)).toHaveLength(0);
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('does not dispatch an old queued task when identity changes before the old execute callback runs', async () => {
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === '/api/asset-providers') return json({items: [provider()]});
      if (url === '/api/novels/review-project/image-jobs') return json({items: [job]});
      // This is only a denied synthetic HTTP response, never a media backend call.
      if (url.endsWith('/execute')) return json({message: 'Review retired execution request'}, 403);
      throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue {...props}/>);
    const oldExecute = await screen.findByRole('button', {name: '执行任务'});
    expect(executions(fetcher)).toHaveLength(0);
    act(() => {
      useStudio.getState().setCollaboration('review-next-client');
      fireEvent.click(oldExecute);
    });
    expect(executions(fetcher)).toHaveLength(0);
  });

  it('retires private queued content when the verified local-host client changes', async () => {
    bindLocalHostSession('review-host-a', {session_mode: 'LOCAL_HOST', actor_id: 'review-actor-a'});
    const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url === '/api/asset-providers') return json({items: [provider()]});
      if (url === '/api/novels/review-project/image-jobs') {
        const caller = new Headers(init.headers).get('X-Session-Token');
        return json({items: caller === 'review-host-a' ? [{...job, id: 'review-old-host-job', prompt: 'Private old host prompt'}] : []});
      }
      throw new Error(`Unexpected review fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue {...props}/>);
    await screen.findByText('任务 ID：review-old-host-job');
    act(() => {bindLocalHostSession('review-host-b', {session_mode: 'LOCAL_HOST', actor_id: 'review-actor-b'});});
    expect(screen.queryAllByText(/任务 ID：review-old-host-job|Private old host prompt/)).toHaveLength(0);
    expect(commandPosts(fetcher)).toHaveLength(0);
  });
});
