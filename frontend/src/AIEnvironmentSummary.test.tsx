// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from './api';
import {AIEnvironmentSummary} from './AIEnvironmentSummary';
import {localAiDiscoveryApi, type AIEnvironmentReport} from './localAiDiscoveryApi';
vi.mock('./localAiDiscoveryApi', () => ({localAiDiscoveryApi: {environment: vi.fn(), scan: vi.fn()}}));
const report = (status: AIEnvironmentReport['status'] = 'NOT_SCANNED'): AIEnvironmentReport => ({
  schema_version:2, execution_scope:'BACKEND_HOST', inference_status:'NOT_RUN', windows_acceptance:'NOT_RUN',
  scan_id:null, status, started_at:null, finished_at:null,
  hardware:{platform:'Synthetic',architecture:'x86_64',cpu:'Fixture CPU',logical_cpu_count:8,ram_bytes:16*1024**3,
    gpus:[{vendor:'NVIDIA',name:'Fixture GPU',dedicated_vram_bytes:8*1024**3}],status:'DETECTED',notes:[],
    cuda:{status:'COMPONENT_FOUND_NOT_VERIFIED',source:'fixture',inference_verified:false},
    directml:{status:'NOT_RUN',source:'fixture',inference_verified:false}},
  services:[], model_files:[], roots:[], errors:[], notes:[],
  limits:{scan_budget_seconds:45,request_timeout_seconds:2,max_services:20,max_models_per_service:512,max_response_bytes:4194304,max_roots:32,max_entries:5000,max_files:2000,max_depth:3,max_metadata_bytes:262144},
});
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(accept => {resolve = accept;}); return {promise, resolve};};

describe('V2 passive environment inspector', () => {
  beforeEach(() => {vi.mocked(localAiDiscoveryApi.environment).mockReset(); vi.mocked(localAiDiscoveryApi.scan).mockReset();});
  afterEach(() => {cleanup(); vi.useRealTimers();});
  it('does no fetch when disabled', () => {
    const view = render(<AIEnvironmentSummary enabled={false} onOpenModels={vi.fn()}/>);
    expect(view.container.textContent).toBe(''); expect(localAiDiscoveryApi.environment).not.toHaveBeenCalled();
  });
  it('shows NOT_SCANNED and routes deliberate detection to existing Model Center', async () => {
    vi.mocked(localAiDiscoveryApi.environment).mockResolvedValue(report()); const open = vi.fn();
    render(<AIEnvironmentSummary enabled onOpenModels={open}/>);
    expect(await screen.findByText('尚未检测')).toBeTruthy();
    expect(screen.getByText(/云端结果不代表你的电脑/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name:'打开模型中心'})); expect(open).toHaveBeenCalledOnce();
    expect(localAiDiscoveryApi.scan).not.toHaveBeenCalled();
  });
  it('shows partial observations and component-only GPU evidence honestly', async () => {
    const data = report('PARTIAL'); data.services = [{id:'lm',name:'LM Studio',type:'OPENAI_COMPATIBLE_LOCAL',endpoint:'http://127.0.0.1:1234',status:'RUNNING',version:null,notes:[],available_models:['qwen'],candidate_ids:[],inference_verified:false}];
    vi.mocked(localAiDiscoveryApi.environment).mockResolvedValue(data);
    render(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>);
    expect(await screen.findByText('部分结果')).toBeTruthy(); expect(screen.getByText('16.0 GiB')).toBeTruthy();
    expect(screen.getByText('发现组件，未实测')).toBeTruthy(); expect(screen.getByText(/真实推理：NOT_RUN/)).toBeTruthy();
    expect(screen.queryByText('http://127.0.0.1:1234')).toBeNull();
  });
  it('does not apply an old response after disable and re-enable', async () => {
    const old = deferred<AIEnvironmentReport>(); vi.mocked(localAiDiscoveryApi.environment).mockReturnValueOnce(old.promise).mockResolvedValueOnce(report());
    const view = render(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>);
    const signal = vi.mocked(localAiDiscoveryApi.environment).mock.calls[0][0];
    view.rerender(<AIEnvironmentSummary enabled={false} onOpenModels={vi.fn()}/>); expect(signal?.aborted).toBe(true);
    view.rerender(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>); await screen.findByText('尚未检测');
    await act(async () => old.resolve(report('COMPLETED')));
    expect(screen.queryByText('Fixture CPU')).toBeNull();
  });
  it('clears private observations on permission failure and allows explicit read retry', async () => {
    vi.mocked(localAiDiscoveryApi.environment).mockResolvedValueOnce(report('COMPLETED')).mockRejectedValueOnce(new ApiError({status:401,code:'SESSION_REQUIRED',message:'PRIVATE RAW ERROR'})).mockResolvedValueOnce(report());
    render(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>); await screen.findByText('Fixture CPU');
    fireEvent.click(screen.getByRole('button',{name:'重新读取'})); await screen.findByRole('alert');
    expect(screen.queryByText('Fixture CPU')).toBeNull(); expect(screen.queryByText('PRIVATE RAW ERROR')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'重新读取'})); await screen.findByText('尚未检测');
  });
  it('polls an existing running scan and stops after terminal status', async () => {
    vi.useFakeTimers(); vi.mocked(localAiDiscoveryApi.environment).mockResolvedValueOnce(report('RUNNING')).mockResolvedValueOnce(report('CANCELLED'));
    render(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>);
    await act(async () => {}); expect(screen.getByText('检测中')).toBeTruthy();
    await act(async () => vi.advanceTimersByTimeAsync(1500)); expect(screen.getByText('已取消')).toBeTruthy();
    await act(async () => vi.advanceTimersByTimeAsync(5000)); expect(localAiDiscoveryApi.environment).toHaveBeenCalledTimes(2);
    expect(localAiDiscoveryApi.scan).not.toHaveBeenCalled();
  });
  it('aborts and clears pending polls on unmount', async () => {
    vi.mocked(localAiDiscoveryApi.environment).mockResolvedValue(report('RUNNING'));
    const view = render(<AIEnvironmentSummary enabled onOpenModels={vi.fn()}/>);
    await waitFor(() => expect(screen.getByText('检测中')).toBeTruthy());
    const signal = vi.mocked(localAiDiscoveryApi.environment).mock.calls[0][0]; view.unmount(); expect(signal?.aborted).toBe(true);
  });
});
