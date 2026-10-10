// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ApiError, setCollaborationContext} from '../api';
import {localAiDiscoveryApi as discovery, type LocalDiscoverySnapshot, type LocalDiscoveryScan, type LocalModelRegistration} from '../localAiDiscoveryApi';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {LocalAiDiscovery} from './LocalAiDiscovery';
const context = {sessionToken: ''};
const registration = (): LocalModelRegistration => ({id: 'private-registration', display_name: 'private-model', model_id: 'private-model-id', family: 'QWEN', modality: 'TEXT', declared_capabilities: ['TEXT'], verified_capabilities: [], runtime_id: 'private-runtime', runtime_type: 'LLAMA_CPP', source: 'CONFIGURED', model_name: 'private-model.gguf', local_path: '/private/model.gguf', status: 'VALIDATION_REQUIRED', compatible: 'NOT_VERIFIED', verified: false, validation_notes: [], validated_at: '2026-10-09', evidence: {}, enable_eligible: true, enabled: false});
const scan = (status = 'COMPLETED'): LocalDiscoveryScan => ({id: 'scan-1', status, runtimes: [], candidates: [], errors: []});
const snapshot = (): LocalDiscoverySnapshot => ({scan: null, registrations: [registration()], settings: {scan_roots: ['/private/models'], runtimes: [{id: 'private-runtime', name: 'private-runtime', type: 'LLAMA_CPP', endpoint: 'http://127.0.0.1:19191', executable: '/private/llama', model_path: '/private/model.gguf', credential_required: false, management: 'EXTERNAL'}]}, hardware: {cpu: 'private-cpu', gpus: []}, workflow_adapters: [{id: 'private-adapter', display_name: 'private-adapter'}]});
const cleanSnapshot = (): LocalDiscoverySnapshot => ({scan: null, registrations: [], settings: {scan_roots: [], runtimes: []}, hardware: {cpu: 'current-cpu', gpus: []}});
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};};
const button = (name: string) => screen.getByRole('button', {name}) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const bind = () => bindLocalHostSession('original-host', {session_mode: 'LOCAL_HOST', actor_id: 'host'});
const flush = async () => {await act(async () => {});};
const assertPrivateGone = () => {expect(document.body.textContent).not.toContain('private-'); expect(document.body.textContent).not.toContain('/private/'); expect(screen.queryByRole('form', {name: '扫描目录配置'})).toBeNull(); expect(screen.queryByRole('form', {name: '本地 Runtime 配置'})).toBeNull(); expect(screen.queryByRole('form', {name: 'private-model 接入条件'})).toBeNull(); expect(screen.queryByLabelText('确认启用模型')).toBeNull(); for (const input of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea')) expect(input.value).not.toContain('/private/');};
beforeEach(() => {setCollaborationContext(context); useStudio.setState({sessionToken: '', novelId: 'project', actor: undefined, scope: undefined}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); bind(); vi.spyOn(discovery, 'snapshot').mockResolvedValue(snapshot());});
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});});
describe('all-mode discovery private view ownership', () => {
  it.each([false, true])('purges snapshot and copied forms on each observed denial (V2=%s)', async v2 => {
    for (const [status, code] of [[401, 'INVALID_SESSION'], [403, 'FORBIDDEN'], [403, 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE']] as const) {
      const denial = new ApiError({status, code, message: 'private-response'});
      vi.spyOn(discovery, 'validate').mockRejectedValue(denial);
      vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/validate') ? {detail: {code}} : snapshot()), {status: url.endsWith('/validate') ? status : 200})));
      render(<LocalAiDiscovery canMutate onboarding={v2 ? {context, projectId: 'project'} : undefined}/>); await screen.findByText('private-cpu');
      click(v2 ? '高级：配置扫描目录' : '配置扫描目录'); click('配置 Runtime'); click('配置接入条件'); click('启用');
      expect(screen.getByDisplayValue('/private/models')).toBeTruthy(); expect(screen.getByDisplayValue('/private/model.gguf')).toBeTruthy(); expect(screen.getByLabelText('确认启用模型')).toBeTruthy();
      click('验证'); await flush(); assertPrivateGone(); expect(button(v2 ? '预览 AI 检测范围' : '检测本机 AI 环境').disabled).toBe(true); expect(button('重试读取').disabled).toBe(true); cleanup();
    }
  });
  it('retains the authorized initial read-only view but purges an actual true → false permission revocation', async () => {
    const view = render(<LocalAiDiscovery canMutate={false}/>); await screen.findByText('private-cpu'); expect(button('检测本机 AI 环境').disabled).toBe(true);
    view.rerender(<LocalAiDiscovery canMutate/>); click('配置扫描目录'); click('配置 Runtime'); click('配置接入条件'); click('启用');
    view.rerender(<LocalAiDiscovery canMutate={false}/>); await flush(); assertPrivateGone();
    view.rerender(<LocalAiDiscovery canMutate/>); await flush(); expect(button('检测本机 AI 环境').disabled).toBe(true); assertPrivateGone();
  });
  it('clears legacy private state on same-mount owner invalidation and never revives it on project ABA', async () => {
    render(<LocalAiDiscovery canMutate/>); await screen.findByText('private-cpu'); click('配置扫描目录'); click('配置 Runtime');
    act(() => {useStudio.setState({novelId: 'other'}); useStudio.setState({novelId: 'project'});}); await flush(); assertPrivateGone(); expect(discovery.snapshot).toHaveBeenCalledTimes(1);
  });
  it.each(['snapshot', 'scan', 'poll'] as const)('rejects a late legacy %s result after same-mounted host ABA', async operation => {
    const oldRead = deferred<LocalDiscoverySnapshot>(), oldScan = deferred<LocalDiscoveryScan>();
    if (operation === 'snapshot') vi.mocked(discovery.snapshot).mockReturnValueOnce(oldRead.promise);
    else if (operation === 'scan') vi.spyOn(discovery, 'scan').mockReturnValue(oldScan.promise);
    else {vi.useFakeTimers(); vi.mocked(discovery.snapshot).mockResolvedValue({...snapshot(), scan: scan('RUNNING')}); vi.spyOn(discovery, 'scanStatus').mockReturnValue(oldScan.promise);}
    render(<LocalAiDiscovery canMutate/>); await flush();
    if (operation === 'scan') {click('检测本机 AI 环境'); await flush();}
    if (operation === 'poll') await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    vi.mocked(discovery.snapshot).mockResolvedValue(cleanSnapshot()); act(() => {clearLocalHostSession(); bind();}); await flush();
    await act(async () => {oldRead.resolve(snapshot()); oldScan.resolve({...scan(), candidates: [registration()]});});
    assertPrivateGone(); expect(screen.getByText('current-cpu')).toBeTruthy();
    if (operation === 'poll') {await act(async () => {await vi.advanceTimersByTimeAsync(4000);}); expect(discovery.scanStatus).toHaveBeenCalledTimes(1);}
  });
  it.each(['snapshot', 'scan', 'poll'] as const)('ignores late %s after permission revocation without refetching private data', async operation => {
    const pendingRead = deferred<LocalDiscoverySnapshot>(), pendingScan = deferred<LocalDiscoveryScan>();
    if (operation === 'snapshot') vi.mocked(discovery.snapshot).mockReturnValueOnce(pendingRead.promise);
    else if (operation === 'scan') vi.spyOn(discovery, 'scan').mockReturnValue(pendingScan.promise);
    else {vi.useFakeTimers(); vi.mocked(discovery.snapshot).mockResolvedValue({...snapshot(), scan: scan('RUNNING')}); vi.spyOn(discovery, 'scanStatus').mockReturnValue(pendingScan.promise);}
    const view = render(<LocalAiDiscovery canMutate/>); await flush();
    if (operation === 'scan') {click('检测本机 AI 环境'); await flush();}
    if (operation === 'poll') await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    view.rerender(<LocalAiDiscovery canMutate={false}/>); await flush();
    await act(async () => {pendingRead.resolve(snapshot()); pendingScan.resolve({...scan(), candidates: [registration()]});}); assertPrivateGone();
    if (operation === 'poll') {await act(async () => {await vi.advanceTimersByTimeAsync(4000);}); expect(discovery.scanStatus).toHaveBeenCalledTimes(1);}
    expect(discovery.snapshot).toHaveBeenCalledTimes(1);
  });
  it('purges a previously authorized read-only snapshot when its owner is invalidated', async () => {
    render(<LocalAiDiscovery canMutate={false}/>); await screen.findByText('private-cpu');
    act(() => {useStudio.setState({novelId: 'other'});}); await flush(); assertPrivateGone(); expect(discovery.snapshot).toHaveBeenCalledTimes(1);
  });
  it('checks legacy ownership before retry-read dispatch during an uncommitted React transition', async () => {
    vi.mocked(discovery.snapshot).mockRejectedValueOnce(new ApiError({status: 503, code: 'TEMPORARY_FAILURE', message: 'temporary'}));
    render(<LocalAiDiscovery canMutate/>); await screen.findByRole('button', {name: '重试读取'}); const retry = button('重试读取');
    vi.mocked(discovery.snapshot).mockResolvedValue(cleanSnapshot());
    act(() => {clearLocalHostSession(); retry.click();}); await flush();
    // The newly mounted owner gets one read; the old retry must not dispatch.
    expect(discovery.snapshot).toHaveBeenCalledTimes(2); expect(screen.getByText('current-cpu')).toBeTruthy();
  });
  it('checks legacy ownership before a queued poll dispatch during an uncommitted React transition', async () => {
    vi.useFakeTimers(); vi.mocked(discovery.snapshot).mockResolvedValue({...snapshot(), scan: scan('RUNNING')}); const poll = vi.spyOn(discovery, 'scanStatus');
    render(<LocalAiDiscovery canMutate/>); await flush(); vi.mocked(discovery.snapshot).mockResolvedValue(cleanSnapshot());
    act(() => {clearLocalHostSession(); vi.advanceTimersByTime(1000);}); await flush(); expect(poll).not.toHaveBeenCalled(); expect(screen.getByText('current-cpu')).toBeTruthy();
  });
  it('checks legacy ownership before mutation dispatch during an uncommitted React transition', async () => {
    const start = vi.spyOn(discovery, 'scan'); render(<LocalAiDiscovery canMutate/>); await screen.findByText('private-cpu'); const oldButton = button('检测本机 AI 环境');
    act(() => {clearLocalHostSession(); oldButton.click();}); await flush(); expect(start).not.toHaveBeenCalled();
  });
});
