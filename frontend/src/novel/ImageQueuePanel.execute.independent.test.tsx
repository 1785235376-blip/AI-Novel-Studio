// @vitest-environment jsdom
// Independent execution-control QA: all HTTP replies are software fixtures.
// No real provider, File backend, media safety review or inference runs here.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {getCollaborationContext, setCollaborationContext} from '../api';
import {bindLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {ImageQueuePanel} from './ImageQueuePanel';

const project = 'execute-project', jobId = '55555555-5555-4555-8555-555555555555';
const token = 'fixture-execute-token-never-persist', prompt = 'Fixture original queued execution prompt';
const jobsUrl = `/api/novels/${project}/image-jobs`, executeUrl = `${jobsUrl}/${jobId}/execute`;
const confirmationUrl = `${jobsUrl}?execution_confirmation=1`;
const actor = {id: 'execute-author', displayName: 'Fixture author', workspaceId: 'execute-workspace'};
const scope = {workspaceId: actor.workspaceId, projectId: project, storylineId: 'execute-story', branchId: 'execute-branch'};
const json = (body: unknown, code = 200) => new Response(JSON.stringify(body), {status: code, headers: {'Content-Type': 'application/json'}});
const job = (changes: Record<string, unknown> = {}) => ({id: jobId, novel_id: project, branch_id: null, owner_actor_id: null,
  status: 'QUEUED', approval_status: 'PENDING', provider_id: 'execute-local', model_id: 'execute-model', prompt,
  parameters: {width: 1024, height: 1024, steps: 28, seed: 1}, allow_cloud_prompt: false,
  request_sha256: 'a'.repeat(64), attempt: 0, updated_at: '2026-10-23T15:00:00Z', ...changes});
const provider = (changes: Record<string, unknown> = {}) => ({provider_id: 'execute-local', display_name: 'Fixture local service',
  default_model: 'execute-model', endpoint: 'http://127.0.0.1:8188', api_style: 'comfyui', configured: true,
  registered: true, reachable: true, enabled: true, local: true, credential_configured: true, requires_credential: false, ...changes});
const permission = (changes: Record<string, unknown> = {}) => ({actor_id: actor.id, domain: 'NOVEL', capabilities: {'domain.write': true}, ...changes});
const draft = {provider_id: 'different-unqueued-service', model_id: 'different-unqueued-model', prompt: 'A different unqueued draft'};
const panel = (novelId = project) => <ImageQueuePanel novelId={novelId} draft={draft} local/>;
function host(who = actor.id) {bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: who});}
function collaboration() {useStudio.getState().setCollaboration(token, actor, scope);}
function executePosts(fetcher: ReturnType<typeof vi.fn>) {return fetcher.mock.calls.filter(([url, init]) => url === executeUrl && init?.method === 'POST');}
function writes(fetcher: ReturnType<typeof vi.fn>) {return fetcher.mock.calls.filter(([, init]) => init?.method && init.method !== 'GET');}
function stored() {return Array.from({length: localStorage.length}, (_, index) => `${localStorage.key(index)}:${localStorage.getItem(localStorage.key(index)!)}`).join('\n');}
function http(options: {collaboration?: boolean; confirmationSupported?: boolean; execute?: () => Promise<Response>; jobs?: (index: number) => Promise<Response>; providers?: () => Promise<Response>; permissions?: () => Promise<Response>} = {}) {
  const initial = job(options.collaboration ? {branch_id: scope.branchId, owner_actor_id: actor.id} : {});
  const state = {jobs: [initial], providers: [provider()], permission: permission(), reads: 0};
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}): Promise<Response> => {
    if ((url === jobsUrl || url === confirmationUrl) && (!init.method || init.method === 'GET')) return options.jobs ? options.jobs(++state.reads)
      : (state.reads++, json({items: state.jobs, ...(url === confirmationUrl && options.confirmationSupported !== false ? {execution_confirmation: 'legacy-image-confirmation/1'} : {})}));
    if (url === '/api/asset-providers' && (!init.method || init.method === 'GET')) return options.providers ? options.providers() : json({items: state.providers});
    if (url.endsWith('/permissions') && (!init.method || init.method === 'GET')) return options.permissions ? options.permissions() : json(state.permission);
    if (url === executeUrl && init.method === 'POST') {
      if (options.execute) return options.execute();
      state.jobs = [job({...initial, status: 'RUNNING', attempt: 1, updated_at: '2026-10-23T15:01:00Z'})];
      return json(state.jobs[0]);
    }
    throw new Error(`Independent execution fixture unexpected ${init.method || 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return {state, fetcher};
}
const confirmName = '确认执行这一个任务', checkboxName = '我已核对任务、参数和可能费用';
async function prepare() {
  await screen.findByText(`任务 ID：${jobId}`);
  fireEvent.click(screen.getByRole('button', {name: '执行任务'}));
  const region = await screen.findByRole('region', {name: '执行原图片任务确认'});
  const check = await within(region).findByRole('checkbox', {name: checkboxName});
  return {region, check, confirm: within(region).getByRole('button', {name: confirmName}) as HTMLButtonElement};
}
async function attemptConfirmation() {
  await screen.findByText(`任务 ID：${jobId}`);
  const open = screen.queryByRole('button', {name: '执行任务'});
  if (open) fireEvent.click(open);
  await act(async () => {});
  const check = screen.queryByRole('checkbox', {name: checkboxName});
  if (check) fireEvent.click(check);
  const confirm = screen.queryByRole('button', {name: confirmName});
  if (confirm) fireEvent.click(confirm);
  await act(async () => {});
}
beforeEach(() => {
  localStorage.clear(); useStudio.setState({sessionToken: '', actor: undefined, scope: undefined, novelId: ''});
  setCollaborationContext({sessionToken: ''}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('independent explicit original image-job execution', () => {
  it('mounts and prepares only reads, then explicitly sends one exact queued-job CAS confirmation', async () => {
    host(); const {fetcher} = http(); render(panel());
    await screen.findByText(`任务 ID：${jobId}`); expect(writes(fetcher)).toHaveLength(0);
    const {region, check, confirm} = await prepare();
    expect(executePosts(fetcher)).toHaveLength(0); expect(confirm.disabled).toBe(true);
    expect(region.textContent).toContain('Fixture local service'); expect(region.textContent).toContain('execute-model');
    expect(region.textContent).not.toContain(draft.provider_id); expect(region.textContent).not.toContain(token);
    fireEvent.click(check); fireEvent.click(confirm);
    await waitFor(() => expect(executePosts(fetcher)).toHaveLength(1));
    expect(JSON.parse(String(executePosts(fetcher)[0][1]!.body))).toEqual({confirmed: true,
      expected_request_sha256: 'a'.repeat(64), expected_attempt: 0, expected_updated_at: '2026-10-23T15:00:00Z'});
    expect(new Headers(executePosts(fetcher)[0][1]!.headers).get('X-Session-Token')).toBe(token);
    expect(writes(fetcher)).toHaveLength(1);
  });

  it('requires the original collaboration actor write permission and dispatches with its captured branch', async () => {
    collaboration(); const {fetcher} = http({collaboration: true}); render(panel());
    const {check, confirm} = await prepare(); fireEvent.click(check); fireEvent.click(confirm);
    await waitFor(() => expect(executePosts(fetcher)).toHaveLength(1));
    expect(new Headers(executePosts(fetcher)[0][1]!.headers).get('X-Branch-Id')).toBe(scope.branchId);
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/permissions')).length).toBeGreaterThan(0);
  });

  it.each([
    ['unreachable', {reachable: false}], ['unknown reachability', {reachable: undefined}], ['unconfigured', {configured: false}],
    ['unregistered', {registered: false}], ['disabled', {enabled: false}], ['unknown model', {default_model: 'other-model'}],
    ['unknown locality', {local: undefined}],
  ])('does not dispatch when the original provider is %s', async (_label, changes) => {
    host(); const {state, fetcher} = http(); state.providers = [provider(changes as Record<string, unknown>)];
    render(panel()); await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it.each([
    ['read only', {capabilities: {'domain.write': false}}], ['unknown write', {capabilities: {}}],
    ['foreign actor', {actor_id: 'another-author'}], ['wrong domain', {domain: 'IMAGE'}],
  ])('does not dispatch with a collaboration permission response that is %s', async (_label, changes) => {
    collaboration(); const {state, fetcher} = http({collaboration: true}); state.permission = permission(changes as Record<string, unknown>);
    render(panel()); await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it.each([401, 403])('does not dispatch after permission HTTP %s', async code => {
    collaboration(); const {fetcher} = http({collaboration: true, permissions: async () => json({detail: 'Fixture permission denied'}, code)});
    render(panel()); await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('does not infer execute authority for an unverified anonymous local client', async () => {
    const {fetcher} = http(); render(panel()); await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('does not dispatch to an old server that does not advertise the additive confirmation contract', async () => {
    host(); const {fetcher} = http({confirmationSupported: false}); render(panel());
    await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('rejects duplicate provider declarations rather than choosing one by array order', async () => {
    host(); const {state, fetcher} = http(); state.providers = [provider(), provider({endpoint: 'http://127.0.0.1:9999'})];
    render(panel()); await attemptConfirmation(); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it.each([
    ['prompt', {prompt: 'Changed server prompt'}], ['model', {model_id: 'changed-server-model'}],
    ['parameters', {parameters: {width: 768, height: 768, steps: 20, seed: 3}}],
    ['attempt', {attempt: 1}], ['time', {updated_at: '2026-10-23T15:02:00Z'}], ['digest', {request_sha256: 'b'.repeat(64)}],
    ['status', {status: 'RUNNING'}], ['project', {novel_id: 'other-execute-project'}],
  ])('retires confirmation when the final fresh original-job %s changed', async (_label, changes) => {
    host(); const {state, fetcher} = http(); render(panel()); const {check, confirm} = await prepare();
    fireEvent.click(check); state.jobs = [job(changes as Record<string, unknown>)]; fireEvent.click(confirm);
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('retires confirmation when provider capability changes after preparation', async () => {
    host(); const {state, fetcher} = http(); render(panel()); const {check, confirm} = await prepare();
    fireEvent.click(check); state.providers = [provider({reachable: false})]; fireEvent.click(confirm);
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('retires confirmation when collaboration write permission is revoked after preparation', async () => {
    collaboration(); const {state, fetcher} = http({collaboration: true}); render(panel()); const {check, confirm} = await prepare();
    fireEvent.click(check); state.permission = permission({capabilities: {'domain.write': false}}); fireEvent.click(confirm);
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('does not reuse a checked old confirmation during a same-batch verified Host A/B/A', async () => {
    host(); const {fetcher} = http(); render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    act(() => {host('another-local-author'); host(); fireEvent.click(confirm);});
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('retires the original confirmation after a same-batch width A/B/A before its old confirm callback runs', async () => {
    host(); const {fetcher} = http(); render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    const width = screen.getByLabelText('队列图片宽度') as HTMLInputElement;
    expect(width.value).toBe('1024');
    act(() => {
      fireEvent.change(width, {target: {value: '768'}});
      fireEvent.change(width, {target: {value: '1024'}});
      fireEvent.click(confirm);
    });
    await act(async () => {});
    expect((screen.getByLabelText('队列图片宽度') as HTMLInputElement).value).toBe('1024');
    expect(screen.queryByRole('region', {name: '执行原图片任务确认'})).toBeNull();
    expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('does not reuse a checked old confirmation when the exact API context object returns through A/B/A', async () => {
    collaboration(); const {fetcher} = http({collaboration: true}); render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    const original = getCollaborationContext();
    act(() => {setCollaborationContext({...original, sessionToken: 'fixture-transient-token'}); setCollaborationContext(original); fireEvent.click(confirm);});
    expect(getCollaborationContext()).toBe(original);
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it('sends a single execution POST for repeated clicks while the same dispatch is pending', async () => {
    host(); let finish!: (value: Response) => void;
    const {fetcher} = http({execute: () => new Promise(resolve => {finish = resolve;})});
    render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    act(() => {fireEvent.click(confirm); fireEvent.click(confirm); fireEvent.click(confirm);});
    await waitFor(() => expect(executePosts(fetcher)).toHaveLength(1));
    await act(async () => {finish(json(job({status: 'RUNNING', attempt: 1})));});
    expect(executePosts(fetcher)).toHaveLength(1); expect(writes(fetcher)).toHaveLength(1);
  });

  it('does not admit late provider metadata from a retired API-only A/B/A review', async () => {
    collaboration(); let finishProviders!: (value: Response) => void;
    const {fetcher} = http({collaboration: true, providers: () => new Promise(resolve => {finishProviders = resolve;})});
    render(panel()); await screen.findByText(`任务 ID：${jobId}`); fireEvent.click(screen.getByRole('button', {name: '执行任务'}));
    await waitFor(() => expect(finishProviders).toBeTypeOf('function'));
    const original = getCollaborationContext();
    act(() => {setCollaborationContext({...original, sessionToken: 'fixture-transient-token'}); setCollaborationContext(original);});
    await act(async () => {finishProviders(json({items: [provider()]}));});
    const check = screen.queryByRole('checkbox', {name: checkboxName}); if (check) fireEvent.click(check);
    const confirm = screen.queryByRole('button', {name: confirmName}); if (confirm) fireEvent.click(confirm);
    await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it.each(['network', 'timeout'])('writes a minimal marker before %s uncertainty and blocks blind re-dispatch across remount when GET still says QUEUED', async failure => {
    host(); let markerAtDispatch = '';
    const {fetcher} = http({execute: async () => {
      markerAtDispatch = stored();
      throw failure === 'network' ? new TypeError('Fixture execution network outcome unknown') : new DOMException('Fixture synthetic timeout', 'TimeoutError');
    }});
    let view = render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check); fireEvent.click(confirm);
    await waitFor(() => expect(executePosts(fetcher)).toHaveLength(1)); await act(async () => {});
    expect(markerAtDispatch).toContain(jobId); expect(markerAtDispatch).toContain('a'.repeat(64));
    expect(markerAtDispatch).not.toContain(token); expect(markerAtDispatch).not.toContain(prompt);
    view.unmount(); view = render(panel()); await attemptConfirmation();
    expect(executePosts(fetcher)).toHaveLength(1); expect(writes(fetcher)).toHaveLength(1);
  });

  it('fires the production 30000ms client abort timer and preserves uncertainty across a same-QUEUED remount', async () => {
    host(); let dispatchSignal!: AbortSignal;
    const {fetcher} = http({execute: () => new Promise((_resolve, reject) => {
      dispatchSignal = executePosts(fetcher)[0][1]!.signal as AbortSignal;
      dispatchSignal.addEventListener('abort', () => reject(new DOMException('Fixture fetch observes client abort', 'AbortError')), {once: true});
    })});
    let view = render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    // Keep preparation and final GETs on native timers. A native timer cannot be
    // migrated after creation, so install the test clock only when production
    // schedules its actual 30s abort callback, before returning that timer handle.
    const nativeSetTimeout = globalThis.setTimeout;
    const schedule = vi.spyOn(globalThis, 'setTimeout');
    let abortDelay = 0, clockInstalled = false;
    schedule.mockImplementation(((callback: (...args: unknown[]) => void, delay?: number, ...args: unknown[]) => {
      if (delay === 30_000) {
        abortDelay = delay; schedule.mockRestore(); vi.useFakeTimers(); clockInstalled = true;
        return globalThis.setTimeout(callback, delay, ...args);
      }
      return nativeSetTimeout(callback, delay, ...args);
    }) as typeof setTimeout);
    try {
      await act(async () => {fireEvent.click(confirm);});
      expect(executePosts(fetcher)).toHaveLength(1); expect(abortDelay).toBe(30_000);
      expect(dispatchSignal.aborted).toBe(false);
      await act(async () => {await vi.advanceTimersByTimeAsync(29_999);});
      expect(dispatchSignal.aborted).toBe(false);
      await act(async () => {await vi.advanceTimersByTimeAsync(1);});
      expect(dispatchSignal.aborted).toBe(true);
      expect(screen.getByText(/超时不代表模型未运行/)).toBeTruthy();
      expect(stored()).toContain(jobId); expect(executePosts(fetcher)).toHaveLength(1);
    } finally {if (!clockInstalled) schedule.mockRestore(); vi.useRealTimers();}
    view.unmount(); view = render(panel()); await attemptConfirmation();
    expect(executePosts(fetcher)).toHaveLength(1); expect(writes(fetcher)).toHaveLength(1);
  });

  it('does not dispatch if the required uncertainty marker cannot be stored and read back', async () => {
    host(); const {fetcher} = http(); render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {throw new Error('Fixture storage unavailable');});
    fireEvent.click(confirm); await act(async () => {}); expect(executePosts(fetcher)).toHaveLength(0);
  });

  it.each(['empty timestamp', 'unknown field', 'array-hash'])('preserves and blocks a corrupt %s pending marker instead of clearing it to admit execution', async corruption => {
    host(); const {fetcher} = http({execute: async () => {throw new TypeError('Fixture unknown execution outcome');}});
    let view = render(panel()); const {check, confirm} = await prepare(); fireEvent.click(check); fireEvent.click(confirm);
    await waitFor(() => expect(executePosts(fetcher)).toHaveLength(1)); await act(async () => {});
    const key = Array.from({length: localStorage.length}, (_, index) => localStorage.key(index))
      .find(value => value?.startsWith('poemseed.image.execute.pending.v1.'));
    if (!key) throw new Error('Expected the genuine dispatch uncertainty marker');
    const original = JSON.parse(localStorage.getItem(key)!);
    // The unknown-field case also differs from the current expectation, proving
    // corrupt records cannot be treated as valid obsolete markers and removed.
    const corrupt = JSON.stringify({...original, ...(corruption === 'empty timestamp'
      ? {updatedAt: ''} : corruption === 'array-hash' ? {requestSha256: [original.requestSha256]}
        : {updatedAt: '2026-10-23T15:03:00Z', unexpected_field: true})});
    localStorage.setItem(key, corrupt);
    view.unmount(); view = render(panel()); await attemptConfirmation();
    expect(executePosts(fetcher)).toHaveLength(1);
    expect(localStorage.getItem(key)).toBe(corrupt);
    expect(screen.queryByRole('region', {name: '执行原图片任务确认'})).toBeNull();
  });
});
