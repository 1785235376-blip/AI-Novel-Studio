// @vitest-environment jsdom
// HTTP-shaped software fixtures only: these tests never contact or execute a provider.
// They exercise the real api client and ImageQueuePanel, replacing only global fetch.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type AssetProviderStatus} from '../../api';
import {useStudio} from '../../store';
import {CanvasImageQueue} from './CanvasImageQueue';

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json'}});
const provider = (changes: Partial<AssetProviderStatus> = {}): AssetProviderStatus => ({
  provider_id: 'fixture-local', display_name: 'Fixture local service', default_model: 'fixture-model',
  local: true, configured: true, registered: true, enabled: true, reachable: true, ...changes,
});
const job = (changes: Record<string, unknown> = {}) => ({id: 'fixture-job-1', status: 'QUEUED', approval_status: 'PENDING', prompt: '节点的手工提示词', provider_id: 'fixture-local', model_id: 'fixture-edited-model', attempt: 0, ...changes});
const writes = (fetcher: ReturnType<typeof vi.fn>) => fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');
const executeCalls = (fetcher: ReturnType<typeof vi.fn>) => fetcher.mock.calls.filter(([url]) => /\/execute(?:\?|$)/.test(String(url)));
function basicFetch(providers: AssetProviderStatus[], createFailure = false) {
  let jobs: ReturnType<typeof job>[] = [];
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === '/api/asset-providers') return json({items: providers});
    if (url === '/api/novels/novel-a/image-jobs' && (!init.method || init.method === 'GET')) return json({items: jobs});
    if (url === '/api/novels/novel-a/image-jobs' && init.method === 'POST') {
      if (createFailure) return json({code: 'QUEUE_UNAVAILABLE', message: '队列写入暂不可用'}, 503);
      const command = JSON.parse(String(init.body));
      jobs = [job({provider_id: command.provider_id, model_id: command.model_id, prompt: command.prompt})];
      return json(jobs[0]);
    }
    throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
async function selectProvider(id = 'fixture-local') {
  await screen.findByRole('option', {name: /Fixture/});
  fireEvent.change(screen.getByLabelText('画布任务图片服务'), {target: {value: id}});
}
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined});
  setCollaborationContext({sessionToken: ''});
});
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); setCollaborationContext({sessionToken: ''});});

describe('CanvasImageQueue', () => {
  it('keeps queue creation disabled when no configured service is available', async () => {
    const fetcher = basicFetch([provider({configured: false, registered: false})]);
    render(<CanvasImageQueue novelId="novel-a" nodeId="canvas-node-a" prompt="节点的手工提示词" onClose={() => {}} />);
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url === '/api/asset-providers')).toBe(true));
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    expect(writes(fetcher)).toHaveLength(0);
    expect(executeCalls(fetcher)).toHaveLength(0);
  });

  it('requires explicit service choice and persists edited model and image parameters before displaying a returned Job ID', async () => {
    const fetcher = basicFetch([provider()]);
    render(<CanvasImageQueue novelId="novel-a" nodeId="canvas-node-a" prompt="节点的手工提示词" onClose={() => {}} />);
    await screen.findByRole('option', {name: /Fixture local service/});
    expect((screen.getByLabelText('画布任务图片服务') as HTMLSelectElement).value).toBe('');
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    expect(writes(fetcher)).toHaveLength(0);
    await selectProvider();
    const model = screen.getByLabelText('画布任务模型') as HTMLInputElement;
    expect(model.value).toBe('fixture-model');
    fireEvent.change(model, {target: {value: 'fixture-edited-model'}});
    fireEvent.change(screen.getByLabelText('队列图片宽度'), {target: {value: '768'}});
    expect(writes(fetcher)).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    await screen.findByText('任务 ID：fixture-job-1');
    const posts = writes(fetcher);
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe('/api/novels/novel-a/image-jobs');
    expect(JSON.parse(String(posts[0][1].body))).toMatchObject({
      provider_id: 'fixture-local', model_id: 'fixture-edited-model', prompt: '节点的手工提示词',
      parameters: {width: 768, height: 1024, steps: 28, seed: 1},
    });
    expect(screen.getByRole('button', {name: '执行任务'})).toBeTruthy();
    expect(executeCalls(fetcher)).toHaveLength(0);
    expect(fetcher.mock.calls.some(([url]) => /image-generations/.test(String(url)))).toBe(false);
  });

  it.each([false, undefined])('requires consent for a provider whose local flag is %s and invalidates it after a model edit', async local => {
    const fetcher = basicFetch([provider({provider_id: 'fixture-cloud', display_name: 'Fixture cloud service', local})]);
    render(<CanvasImageQueue novelId="novel-a" nodeId="canvas-node-a" prompt="节点的手工提示词" onClose={() => {}} />);
    await selectProvider('fixture-cloud');
    const save = screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    let consent = screen.getByRole('checkbox', {name: /^允许本次向/}) as HTMLInputElement;
    expect(consent.checked).toBe(false);
    fireEvent.click(consent);
    expect(save.disabled).toBe(false);
    fireEvent.change(screen.getByLabelText('画布任务模型'), {target: {value: 'another-fixture-model'}});
    consent = screen.getByRole('checkbox', {name: /^允许本次向/}) as HTMLInputElement;
    expect(consent.checked).toBe(false);
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    expect(writes(fetcher)).toHaveLength(0);
    fireEvent.click(consent);
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    await screen.findByText('任务 ID：fixture-job-1');
    expect(JSON.parse(String(writes(fetcher)[0][1].body))).toMatchObject({provider_id: 'fixture-cloud', model_id: 'another-fixture-model', prompt: '节点的手工提示词'});
    expect(executeCalls(fetcher)).toHaveLength(0);
  });

  it('drops providers and private queued jobs returned after switching to another novel', async () => {
    let finishProviders!: (value: Response) => void, finishJobs!: (value: Response) => void;
    let providerReads = 0;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') return ++providerReads === 1
        ? new Promise(resolve => {finishProviders = resolve;})
        : Promise.resolve(json({items: [provider({provider_id: 'fixture-b', display_name: 'Fixture B service', default_model: 'b-model'})]}));
      if (url === '/api/novels/novel-a/image-jobs') return new Promise(resolve => {finishJobs = resolve;});
      if (url === '/api/novels/novel-b/image-jobs') return Promise.resolve(json({items: []}));
      throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    const view = render(<CanvasImageQueue novelId="novel-a" nodeId="canvas-node-a" prompt="A private prompt" onClose={() => {}} />);
    view.rerender(<CanvasImageQueue novelId="novel-b" nodeId="canvas-node-a" prompt="B prompt" onClose={() => {}} />);
    await screen.findByRole('option', {name: /Fixture B service/});
    await act(async () => {
      finishProviders(json({items: [provider({provider_id: 'old-private-service', display_name: 'A private service'})]}));
      finishJobs(json({items: [job({id: 'private-a-job', prompt: 'Late private A result'})]}));
    });
    expect(screen.queryByRole('option', {name: 'A private service'})).toBeNull();
    expect(screen.queryByText(/private-a-job|Late private A result|A private prompt/)).toBeNull();
    expect((screen.getByLabelText('画布任务图片服务') as HTMLSelectElement).value).toBe('');
    expect(writes(fetcher)).toHaveLength(0);
  });

  it('does not revive the first A session when a late provider response follows an A/B/A round trip', async () => {
    let finishFirst!: (value: Response) => void;
    let providerReads = 0;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') {
        providerReads++;
        return providerReads === 1 ? new Promise(resolve => {finishFirst = resolve;}) : Promise.resolve(json({items: [provider({display_name: `Fixture current ${providerReads}`})]}));
      }
      if (/\/image-jobs$/.test(url)) return Promise.resolve(json({items: []}));
      throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    const view = render(<CanvasImageQueue novelId="novel-a" nodeId="node-a" prompt="A prompt" onClose={() => {}} />);
    view.rerender(<CanvasImageQueue novelId="novel-b" nodeId="node-b" prompt="B prompt" onClose={() => {}} />);
    await screen.findByRole('option', {name: 'Fixture current 2'});
    view.rerender(<CanvasImageQueue novelId="novel-a" nodeId="node-a" prompt="A prompt" onClose={() => {}} />);
    await screen.findByRole('option', {name: 'Fixture current 3'});
    await act(async () => {finishFirst(json({items: [provider({display_name: 'Fixture stale first A'})]}));});
    expect(screen.queryByRole('option', {name: 'Fixture stale first A'})).toBeNull();
    expect(screen.getByRole('option', {name: 'Fixture current 3'})).toBeTruthy();
    expect(writes(fetcher)).toHaveLength(0);
  });

  it('retires late providers and private tasks across a batched identity A/B/A transition', async () => {
    let finishProviders!: (value: Response) => void, finishJobs!: (value: Response) => void;
    let providerReads = 0, jobReads = 0;
    const fetcher = vi.fn((url: string, init: RequestInit = {}): Promise<Response> => {
      if (url === '/api/asset-providers') return ++providerReads === 1
        ? new Promise(resolve => {finishProviders = resolve;})
        : Promise.resolve(json({items: [provider({display_name: 'Fixture fresh identity service'})]}));
      if (url === '/api/novels/novel-a/image-jobs') return ++jobReads === 1
        ? new Promise(resolve => {finishJobs = resolve;})
        : Promise.resolve(json({items: []}));
      throw new Error(`Unexpected software-fixture request ${init.method || 'GET'} ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue novelId="novel-a" nodeId="node-a" prompt="A prompt" onClose={() => {}} />);
    act(() => {
      useStudio.getState().setCollaboration('fixture-transient-identity');
      useStudio.getState().setCollaboration('');
    });
    await act(async () => {
      finishProviders(json({items: [provider({display_name: 'Fixture retired identity service'})]}));
      finishJobs(json({items: [job({id: 'retired-identity-job', prompt: 'Private retired identity prompt'})]}));
    });
    expect(screen.queryByRole('option', {name: 'Fixture retired identity service'})).toBeNull();
    expect(screen.queryByText(/retired-identity-job|Private retired identity prompt/)).toBeNull();
    expect(writes(fetcher)).toHaveLength(0);
  });

  it('shows a provider lookup error and never enables an unsupported submission', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url === '/api/asset-providers') return json({code: 'SERVICE_UNAVAILABLE', message: '配置服务暂不可用'}, 503);
      if (url === '/api/novels/novel-a/image-jobs') return json({items: []});
      throw new Error(`Unexpected software-fixture request GET ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    render(<CanvasImageQueue novelId="novel-a" nodeId="node-a" prompt="不会派发" onClose={() => {}} />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/配置服务暂不可用|503|图片服务|加载|服务暂时无法连接/);
    expect((screen.getByRole('button', {name: '保存到生成队列'}) as HTMLButtonElement).disabled).toBe(true);
    expect(writes(fetcher)).toHaveLength(0);
  });

  it('shows a rejected queue write instead of inventing a successful Job', async () => {
    const fetcher = basicFetch([provider()], true);
    render(<CanvasImageQueue novelId="novel-a" nodeId="canvas-node-a" prompt="节点的手工提示词" onClose={() => {}} />);
    await selectProvider();
    fireEvent.click(screen.getByRole('button', {name: '保存到生成队列'}));
    expect((await screen.findByRole('alert')).textContent).toMatch(/队列写入暂不可用|服务暂时无法连接/);
    expect(screen.queryByText('任务 ID：fixture-job-1')).toBeNull();
    expect(writes(fetcher)).toHaveLength(1);
    expect(executeCalls(fetcher)).toHaveLength(0);
  });
});
