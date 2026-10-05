// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {fireEvent} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from '../api';
import {localAiDiscoveryApi as api, type LocalDiscoverySnapshot, type LocalDiscoveryScan, type LocalModelCandidate, type LocalModelRegistration} from '../localAiDiscoveryApi';
import {LocalAiDiscovery} from './LocalAiDiscovery';

(globalThis as typeof globalThis & {IS_REACT_ACT_ENVIRONMENT: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
const candidate = (extra: Partial<LocalModelCandidate> = {}): LocalModelCandidate => ({id: 'candidate-qwen', display_name: 'Qwen3 local', model_id: 'qwen3:8b', family: 'QWEN', modality: 'TEXT', declared_capabilities: ['TEXT'], verified_capabilities: [], runtime_id: 'ollama', runtime_type: 'OLLAMA', source: 'OLLAMA', model_name: 'qwen3:8b', status: 'DISCOVERED', compatible: 'NOT_VERIFIED', verified: false, validation_notes: [], validated_at: null, evidence: {}, enable_eligible: false, ...extra});
const scan = (extra: Partial<LocalDiscoveryScan> = {}): LocalDiscoveryScan => ({id: 'scan-1', status: 'COMPLETED', runtimes: [{id: 'ollama', name: 'Ollama', type: 'OLLAMA', endpoint: 'http://127.0.0.1:11434', status: 'RUNNING', version: '0.9'}], candidates: [candidate()], errors: [], ...extra});
const snapshot = (extra: Partial<LocalDiscoverySnapshot> = {}): LocalDiscoverySnapshot => ({scan: null, registrations: [], settings: {scan_roots: [], runtimes: []}, hardware: {platform: 'Windows', architecture: 'AMD64', cpu: 'Local CPU', ram_bytes: 32 * 1024 ** 3, gpus: [{vendor: 'NVIDIA', name: 'RTX local', dedicated_vram_bytes: 16 * 1024 ** 3}], status: 'DETECTED', notes: []}, ...extra});
const registration = (extra: Partial<LocalModelRegistration> = {}): LocalModelRegistration => ({...candidate({validated_at: '2026-10-05', status: 'VALIDATION_REQUIRED', verified_capabilities: ['TEXT'], enable_eligible: true}), id: 'registration-qwen', candidate_id: 'candidate-qwen', enabled: false, ...extra});
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};};

describe('Local AI Discovery', () => {
  let host: HTMLDivElement, root: Root, mounted = false;
  const button = (label: string) => Array.from(host.querySelectorAll('button')).find(item => item.textContent === label)!;
  const click = async (label: string) => {await act(async () => {button(label).click();});};
  async function render(canMutate = true) {host = document.createElement('div'); document.body.append(host); root = createRoot(host); mounted = true; await act(async () => {root.render(<LocalAiDiscovery canMutate={canMutate}/>);});}
  beforeEach(() => {vi.spyOn(api, 'snapshot').mockResolvedValue(snapshot());});
  afterEach(() => {if (mounted) act(() => root.unmount()); mounted = false; host?.remove(); vi.restoreAllMocks(); vi.useRealTimers();});

  it('does not scan on mount and supports skipping without mutations', async () => {
    const start = vi.spyOn(api, 'scan');
    await render();
    expect(host.textContent).toContain('尚未开始扫描'); expect(host.textContent).toContain('Local CPU'); expect(host.textContent).toContain('16.0 GiB');
    expect(start).not.toHaveBeenCalled();
    await click('跳过 / 收起'); expect(button('展开本地 AI')).toBeTruthy(); expect(host.textContent).not.toContain('尚未开始扫描'); expect(start).not.toHaveBeenCalled();
  });

  it('keeps Detect, Validate, Register and explicit Enable separate', async () => {
    const detected = candidate({license_required: true, license_confirmed: false}), validated = candidate({validated_at: '2026-10-05', verified_capabilities: ['TEXT'], status: 'LICENSE_REQUIRED', license_required: true, license_confirmed: false, enable_eligible: false, enable_blockers: ['LICENSE_VALIDATION_REQUIRED']});
    const start = vi.spyOn(api, 'scan').mockResolvedValue(scan({candidates: [detected]}));
    const validate = vi.spyOn(api, 'validate').mockResolvedValue(validated);
    const register = vi.spyOn(api, 'register').mockResolvedValue(registration({license_required: true, license_confirmed: false, enable_eligible: false, enable_blockers: ['LICENSE_VALIDATION_REQUIRED']}));
    const configure = vi.spyOn(api, 'configureRegistration').mockResolvedValue(registration({license_required: true, license_confirmed: true, enable_eligible: true}));
    const enable = vi.spyOn(api, 'enable').mockResolvedValue(registration({enabled: true}));
    const disable = vi.spyOn(api, 'disable').mockResolvedValue(registration());
    await render(); await click('检测本机 AI 环境');
    expect(start).toHaveBeenCalledTimes(1); expect(button('注册').disabled).toBe(true); expect(validate).not.toHaveBeenCalled(); expect(register).not.toHaveBeenCalled(); expect(enable).not.toHaveBeenCalled();
    await click('验证'); expect(validate).toHaveBeenCalledWith(detected.id); expect(button('注册').disabled).toBe(false); expect(register).not.toHaveBeenCalled();
    await click('注册'); expect(register).toHaveBeenCalledWith(detected.id); expect(host.textContent).toContain('已注册 · 未启用'); expect(enable).not.toHaveBeenCalled();
    expect(button('启用').disabled).toBe(true); await click('配置接入条件');
    const license = host.querySelector<HTMLInputElement>('input[type=checkbox]')!; expect(license.checked).toBe(false);
    await act(async () => {fireEvent.click(license);});
    await act(async () => {fireEvent.submit(host.querySelector('form')!);});
    expect(configure).toHaveBeenCalledWith('registration-qwen', {workflow_adapter_id: '', license_confirmed: true}); expect(enable).not.toHaveBeenCalled();
    await click('启用'); expect(host.textContent).toContain('进入实际任务路由'); expect(enable).not.toHaveBeenCalled();
    await click('确认启用'); expect(enable).toHaveBeenCalledWith('registration-qwen'); expect(host.textContent).toContain('已启用');
    await click('停用'); expect(disable).toHaveBeenCalledWith('registration-qwen'); expect(host.textContent).toContain('已注册 · 未启用');
  });

  it('polls partial results and rejects an old running response after cancel', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'scan').mockResolvedValue(scan({status: 'RUNNING', candidates: []}));
    const pending = deferred<LocalDiscoveryScan>();
    const poll = vi.spyOn(api, 'scanStatus').mockReturnValue(pending.promise);
    const cancel = vi.spyOn(api, 'cancelScan').mockResolvedValue(scan({status: 'CANCELLED', candidates: [candidate()]}));
    await render(); await click('检测本机 AI 环境');
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); expect(poll).toHaveBeenCalledTimes(1);
    await click('取消扫描'); expect(cancel).toHaveBeenCalledWith('scan-1'); expect(host.textContent).toContain('扫描已取消');
    expect(poll.mock.calls[0][1]?.aborted).toBe(true);
    await act(async () => {pending.resolve(scan({status: 'RUNNING', candidates: [candidate({display_name: 'stale result'})]}));});
    expect(host.textContent).toContain('Qwen3 local'); expect(host.textContent).not.toContain('stale result'); expect(host.textContent).toContain('CANCELLED');
    await act(async () => {await vi.advanceTimersByTimeAsync(4000);}); expect(poll).toHaveBeenCalledTimes(1);
  });

  it('recovers polling after cancellation fails without discarding partial results', async () => {
    vi.useFakeTimers();
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan({status: 'RUNNING'})}));
    vi.spyOn(api, 'cancelScan').mockRejectedValue(new ApiError({status: 503, code: 'TEMPORARY_FAILURE', message: 'temporary'}));
    const poll = vi.spyOn(api, 'scanStatus').mockResolvedValue(scan({status: 'COMPLETED'}));
    await render(); await click('取消扫描');
    expect(host.textContent).toContain('TEMPORARY_FAILURE'); expect(host.textContent).toContain('Qwen3 local');
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    expect(poll).toHaveBeenCalledTimes(1); expect(host.textContent).toContain('COMPLETED');
  });

  it('retries a failed status read while keeping available results', async () => {
    vi.useFakeTimers();
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan({status: 'RUNNING'})}));
    const poll = vi.spyOn(api, 'scanStatus').mockRejectedValueOnce(new ApiError({status: 503, code: 'TEMPORARY_FAILURE', message: 'temporary'})).mockResolvedValue(scan());
    await render(); await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    expect(host.textContent).toContain('TEMPORARY_FAILURE'); expect(host.textContent).toContain('Qwen3 local');
    await act(async () => {await vi.advanceTimersByTimeAsync(3000);});
    expect(poll).toHaveBeenCalledTimes(2); expect(host.textContent).toContain('COMPLETED');
  });

  it('keeps newer scan results when a previous poll resolves late', async () => {
    vi.useFakeTimers(); const old = deferred<LocalDiscoveryScan>();
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan({status: 'RUNNING', candidates: []})}));
    vi.spyOn(api, 'scanStatus').mockReturnValue(old.promise);
    vi.spyOn(api, 'cancelScan').mockResolvedValue(scan({status: 'CANCELLED', candidates: []}));
    vi.spyOn(api, 'scan').mockResolvedValue(scan({id: 'scan-2', candidates: [candidate({display_name: 'new result'})]}));
    await render(); await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); await click('取消扫描'); await click('重新扫描');
    await act(async () => {old.resolve(scan({candidates: [candidate({display_name: 'old result'})]}));});
    expect(host.textContent).toContain('new result'); expect(host.textContent).not.toContain('old result');
  });

  it('polls to completion, groups utilities separately, and preserves unavailable Runtime results', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, 'scan').mockResolvedValue(scan({status: 'RUNNING'}));
    const poll = vi.spyOn(api, 'scanStatus').mockResolvedValue(scan({status: 'PARTIAL', candidates: [candidate(), candidate({id: 'rife', display_name: 'RIFE', modality: 'INTERPOLATION', declared_capabilities: ['INTERPOLATION']})], errors: [{runtime_id: 'a1111', code: 'NOT_FOUND'}]}));
    await render(); await click('检测本机 AI 环境'); expect(host.textContent).toContain('已显示当前部分结果');
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    expect(host.querySelector('[aria-label="Utilities 工具"]')?.textContent).toContain('RIFE'); expect(host.textContent).toContain('a1111 · NOT_FOUND'); expect(host.textContent).toContain('Qwen3 local');
    await act(async () => {await vi.advanceTimersByTimeAsync(4000);}); expect(poll).toHaveBeenCalledTimes(1);
  });

  it('shows request errors, preserves existing data and permits retry', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan()}));
    const validate = vi.spyOn(api, 'validate').mockRejectedValueOnce(new ApiError({status: 503, code: 'RUNTIME_UNAVAILABLE', message: 'secret-output'})).mockResolvedValue(candidate({validated_at: '2026-10-05'}));
    await render(); await click('验证');
    expect(host.querySelector('[role=alert]')?.textContent).toContain('RUNTIME_UNAVAILABLE'); expect(host.textContent).not.toContain('secret-output'); expect(host.textContent).toContain('Qwen3 local'); expect(button('验证').disabled).toBe(false);
    await click('验证'); expect(validate).toHaveBeenCalledTimes(2); expect(host.querySelector('[role=alert]')).toBeNull();
  });

  it('refreshes revoked server eligibility after failed enable without losing its error', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({license_confirmed: true})]}));
    vi.spyOn(api, 'enable').mockRejectedValue(new ApiError({status: 409, code: 'LOCAL_AI_ENABLE_BLOCKED', message: 'blocked'}));
    await render(); await click('启用');
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: false, enable_eligible: false, license_confirmed: false, enable_blockers: ['MODEL_OR_RUNTIME_NOT_FOUND', 'LICENSE_VALIDATION_REQUIRED']})]}));
    await click('确认启用');
    expect(host.querySelector('[role=alert]')?.textContent).toContain('LOCAL_AI_ENABLE_BLOCKED');
    expect(host.textContent).toContain('MODEL_OR_RUNTIME_NOT_FOUND'); expect(button('启用').disabled).toBe(true);
    expect(host.querySelector('[aria-label="确认启用模型"]')).toBeNull();
    await click('配置接入条件'); expect(host.querySelector<HTMLInputElement>('input[type=checkbox]')!.checked).toBe(false);
  });

  it.each(['validate', 'configure'] as const)('refreshes an enabled registration revoked during failed %s', async action => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: true, license_confirmed: true})]}));
    const operation = action === 'validate' ? vi.spyOn(api, 'validate') : vi.spyOn(api, 'configureRegistration');
    operation.mockRejectedValue(new ApiError({status: 409, code: 'MODEL_CHANGED', message: 'changed'}));
    await render();
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: false, enable_eligible: false, license_confirmed: false, enable_blockers: ['REVALIDATION_REQUIRED']})]}));
    if (action === 'validate') await click('验证');
    else {await click('配置接入条件'); await act(async () => {fireEvent.submit(host.querySelector('form')!);});}
    expect(host.querySelector('[role=alert]')?.textContent).toContain('MODEL_CHANGED');
    expect(host.textContent).toContain('已注册 · 未启用'); expect(button('启用').disabled).toBe(true); expect(button('停用')).toBeUndefined();
  });

  it('fails closed if recovery cannot read state, and permits an explicit safe reread', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: true})]}));
    vi.spyOn(api, 'validate').mockRejectedValue(new ApiError({status: 409, code: 'MODEL_CHANGED', message: 'changed'}));
    await render(); vi.mocked(api.snapshot).mockRejectedValue(new Error('private diagnostics'));
    await click('验证');
    expect(host.textContent).toContain('接入状态待确认'); expect(host.textContent).not.toContain('private diagnostics');
    expect(host.querySelector('[role=alert]')?.textContent).toContain('MODEL_CHANGED'); expect(button('验证').disabled).toBe(true); expect(button('停用').disabled).toBe(true);
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: false, enable_eligible: false})]}));
    await click('重新读取状态'); expect(host.textContent).toContain('已注册 · 未启用'); expect(host.textContent).not.toContain('接入状态待确认'); expect(button('验证').disabled).toBe(false);
  });

  it('ignores a recovery read that finishes after unmount', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enabled: true})]}));
    vi.spyOn(api, 'validate').mockRejectedValue(new ApiError({status: 409, code: 'MODEL_CHANGED', message: 'changed'}));
    await render(); const pending = deferred<LocalDiscoverySnapshot>(); vi.mocked(api.snapshot).mockReturnValue(pending.promise);
    await click('验证'); expect(host.textContent).toContain('接入状态待确认'); act(() => root.unmount()); mounted = false;
    await act(async () => {pending.resolve(snapshot());}); expect(host.textContent).toBe('');
  });

  it('fails closed on session expiry and does not send another mutation', async () => {
    const start = vi.spyOn(api, 'scan').mockRejectedValue(new ApiError({status: 401, code: 'INVALID_SESSION', message: 'expired'}));
    await render(); await click('检测本机 AI 环境'); expect(host.textContent).toContain('桌面会话已失效'); expect(button('检测本机 AI 环境').disabled).toBe(true);
    await click('检测本机 AI 环境'); expect(start).toHaveBeenCalledTimes(1);
  });

  it('ignores responses and stops polling after unmount', async () => {
    vi.useFakeTimers(); const pending = deferred<LocalDiscoveryScan>();
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan({status: 'RUNNING'})}));
    const poll = vi.spyOn(api, 'scanStatus').mockReturnValue(pending.promise);
    await render(); await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    act(() => root.unmount()); mounted = false; expect(poll.mock.calls[0][1]?.aborted).toBe(true);
    await act(async () => {pending.resolve(scan()); await vi.advanceTimersByTimeAsync(5000);});
    expect(host.textContent).toBe(''); expect(poll).toHaveBeenCalledTimes(1);
  });

  it('can revalidate a restored registration before enabling again', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({id: 'candidate-qwen', candidate_id: 'candidate-qwen', validated_at: null, enable_eligible: false, enable_blockers: ['REVALIDATION_REQUIRED']})]}));
    const validate = vi.spyOn(api, 'validate').mockResolvedValue(candidate({validated_at: '2026-10-05', verified_capabilities: ['TEXT'], enable_eligible: true, enable_blockers: []}));
    const enable = vi.spyOn(api, 'enable');
    await render(); expect(button('启用').disabled).toBe(true); await click('验证');
    expect(validate).toHaveBeenCalledWith('candidate-qwen'); expect(button('启用').disabled).toBe(false); expect(enable).not.toHaveBeenCalled();
  });

  it('refreshes hardware when a background scan completes', async () => {
    vi.useFakeTimers();
    vi.mocked(api.snapshot).mockResolvedValueOnce(snapshot({hardware: {status: 'NOT_VERIFIED'}, scan: scan({status: 'RUNNING'})})).mockResolvedValue(snapshot({scan: scan()}));
    vi.spyOn(api, 'scanStatus').mockResolvedValue(scan()); await render();
    expect(host.textContent).not.toContain('Local CPU');
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); expect(host.textContent).toContain('Local CPU'); expect(host.textContent).toContain('16.0 GiB');
  });

  it('keeps cancellation pending until the bounded server probe stops', async () => {
    vi.useFakeTimers(); vi.mocked(api.snapshot).mockResolvedValue(snapshot({scan: scan({status: 'RUNNING'})}));
    vi.spyOn(api, 'cancelScan').mockResolvedValue(scan({status: 'RUNNING'}));
    vi.spyOn(api, 'scanStatus').mockResolvedValue(scan({status: 'CANCELLED'}));
    await render(); await click('取消扫描'); expect(button('正在取消扫描…').disabled).toBe(true); expect(host.textContent).toContain('等待当前只读探测结束');
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); expect(host.textContent).toContain('扫描已取消');
  });

  it('requires authoritative eligibility and explicit removal without model deletion', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({enable_eligible: false, enable_blockers: ['WORKFLOW_REQUIRED']})]}));
    const remove = vi.spyOn(api, 'remove').mockResolvedValue(undefined), enable = vi.spyOn(api, 'enable');
    await render(); expect(button('启用').disabled).toBe(true); expect(host.textContent).toContain('WORKFLOW_REQUIRED'); expect(enable).not.toHaveBeenCalled();
    await click('移除注册'); expect(host.textContent).toContain('不删除真实模型文件'); expect(remove).not.toHaveBeenCalled();
    await click('确认移除注册'); expect(remove).toHaveBeenCalledWith('registration-qwen'); expect(host.textContent).not.toContain('Qwen3 local');
  });

  it('never confirms licensing or chooses a workflow implicitly', async () => {
    vi.mocked(api.snapshot).mockResolvedValue(snapshot({registrations: [registration({license_required: true, enable_eligible: false, enable_blockers: ['LICENSE_REQUIRED']})], workflow_adapters: [{id: 'sd-checkpoint', display_name: 'SD checkpoint', capability: 'IMAGE'}]}));
    const configure = vi.spyOn(api, 'configureRegistration').mockResolvedValue(registration({license_confirmed: true, workflow_adapter_id: 'sd-checkpoint'}));
    const enable = vi.spyOn(api, 'enable');
    await render(); await click('配置接入条件');
    const checkbox = host.querySelector<HTMLInputElement>('input[type=checkbox]')!;
    expect(checkbox.checked).toBe(false); expect((host.querySelector('select') as HTMLSelectElement).value).toBe(''); expect(configure).not.toHaveBeenCalled();
    await act(async () => {fireEvent.click(checkbox); fireEvent.change(host.querySelector('select')!, {target: {value: 'sd-checkpoint'}});});
    await act(async () => {fireEvent.submit(host.querySelector('form')!);});
    expect(configure).toHaveBeenCalledWith('registration-qwen', {workflow_adapter_id: 'sd-checkpoint', license_confirmed: true}); expect(enable).not.toHaveBeenCalled();
  });

  it('saves explicit custom roots without starting a scan', async () => {
    const save = vi.spyOn(api, 'settings').mockResolvedValue({scan_roots: ['D:\\AI\\models'], runtimes: []}), start = vi.spyOn(api, 'scan');
    await render(); await click('配置扫描目录');
    await act(async () => {fireEvent.change(host.querySelector('textarea')!, {target: {value: '  D:\\AI\\models\n\n'}});});
    await act(async () => {fireEvent.submit(host.querySelector('form')!);});
    expect(save).toHaveBeenCalledWith(['D:\\AI\\models']); expect(start).not.toHaveBeenCalled();
  });

  it('keeps local Runtime declarations distinct from verified capabilities', async () => {
    const save = vi.spyOn(api, 'saveRuntime').mockResolvedValue({id: 'custom'}), start = vi.spyOn(api, 'scan');
    await render(); await click('添加本地 Runtime');
    await act(async () => {
      const form = host.querySelector('form')!;
      fireEvent.change(form.querySelector('input')!, {target: {value: 'My local server'}});
      fireEvent.change(form.querySelector('select')!, {target: {value: 'CUSTOM_HTTP'}});
      fireEvent.submit(form);
    });
    expect(save).toHaveBeenCalledTimes(1); const payload = save.mock.calls[0][0];
    expect(payload.name).toBe('My local server'); expect(payload.type).toBe('CUSTOM_HTTP'); expect(payload.management).toBe('EXTERNAL'); expect(payload.modality).toBe('UNKNOWN'); expect(payload).not.toHaveProperty('verified_capabilities'); expect(start).not.toHaveBeenCalled();
  });

  it('keeps scan and configuration read-only without desktop mutation authorization', async () => {
    const start = vi.spyOn(api, 'scan'); await render(false);
    expect(button('检测本机 AI 环境').disabled).toBe(true); expect(button('添加本地 Runtime').disabled).toBe(true); expect(host.textContent).toContain('需要受信任的桌面会话'); await click('检测本机 AI 环境'); expect(start).not.toHaveBeenCalled();
  });
});
