// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FirstUsePanel } from './FirstUsePanel';
import { SampleJourneyGuide } from './SampleJourneyGuide';
import { firstUseClient, type FirstUseReceipt } from './firstUseClient';
import * as flagsModule from '../experimental/api';
vi.mock('./firstUseClient', () => ({ firstUseClient: vi.fn() }));
const enabled = { experimental: true, default_enabled: false as const, features: { 'experimental.workspace_tools_v2': true } };
const receipt: FirstUseReceipt = { id: 'receipt', version: 6, stage: 'READY', project_id: 'sample-project', chapter_id: 'sample-project:1', seed_version: 2, path: null, synthetic: true, sample_version: 1, availability: 'AVAILABLE', can_open: true, can_recover: false };
const chapter = { id: 'sample-project:1', novel_id: 'sample-project', title: '练习', version: 3 } as any;
let api: { read: ReturnType<typeof vi.fn>; start: ReturnType<typeof vi.fn>; recover: ReturnType<typeof vi.fn> };
beforeEach(() => {
  api = { read: vi.fn().mockResolvedValue({ item: null, model_calls: 0 }), start: vi.fn().mockResolvedValue({ item: receipt, model_calls: 0 }), recover: vi.fn() };
  vi.mocked(firstUseClient).mockReturnValue(api as any);
  vi.spyOn(flagsModule, 'experimentalFeatures').mockResolvedValue(enabled);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
describe('FirstUsePanel', () => {
  it('keeps default-off entries hidden without reading or creating samples', async () => {
    vi.mocked(flagsModule.experimentalFeatures).mockResolvedValue({ ...enabled, features: {} });
    const view = render(<FirstUsePanel sessionToken="" onOpenLocal={vi.fn()} />);
    await waitFor(() => expect(flagsModule.experimentalFeatures).toHaveBeenCalled());
    expect(view.container.textContent).toBe(''); expect(api.read).not.toHaveBeenCalled(); expect(api.start).not.toHaveBeenCalled();
  });
  it('explains five scenarios, skips and reopens without a write', async () => {
    const writing = vi.fn(), importing = vi.fn();
    render(<FirstUsePanel sessionToken="" onOpenLocal={vi.fn()} onChooseWriting={writing} onChooseImport={importing} />);
    await screen.findByRole('button', { name: '创建独立练习（不需要 Key）' });
    for (const text of ['纯写作', '导入长篇', '做剧本与分镜', '有声书', '本地模型']) expect(screen.getByText(text)).toBeTruthy();
    expect(screen.getByText(/有声书实验功能未启用/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '填写新小说名称' })); expect(writing).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: '选择导入文件' })); expect(importing).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: '跳过指引' })); expect(screen.queryByText('纯写作')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重新打开首次使用指引' })); expect(screen.getByText('纯写作')).toBeTruthy(); expect(api.start).not.toHaveBeenCalled();
  });
  it('single-flights creation and requires a separate reauthorized open', async () => {
    let finish!: (value: any) => void;
    api.start.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const open = vi.fn(); render(<FirstUsePanel sessionToken="" onOpenLocal={open} />);
    const button = await screen.findByRole('button', { name: '创建独立练习（不需要 Key）' });
    fireEvent.click(button); fireEvent.click(button); expect(api.start).toHaveBeenCalledOnce();
    await act(async () => { finish({ item: receipt }); }); expect(open).not.toHaveBeenCalled();
    api.read.mockResolvedValue({ item: receipt }); fireEvent.click(screen.getByRole('button', { name: '打开独立练习' }));
    await waitFor(() => expect(open).toHaveBeenCalledWith('sample-project')); expect(api.read).toHaveBeenCalledTimes(2);
  });
  it('retains unknown create and never exposes blind retry', async () => {
    api.start.mockRejectedValue(new TypeError('Network unavailable'));
    render(<FirstUsePanel sessionToken="" onOpenLocal={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '创建独立练习（不需要 Key）' })); await screen.findByText(/请求结果未知/);
    expect(screen.queryByRole('button', { name: '创建独立练习（不需要 Key）' })).toBeNull();
    api.read.mockResolvedValue({ item: { ...receipt, stage: 'CREATING_PROJECT', project_id: null, chapter_id: null, can_open: false } });
    fireEvent.click(screen.getByRole('button', { name: '核对练习状态' })); await screen.findByText(/项目创建结果尚未确认/);
    expect(screen.queryByRole('button', { name: '继续已确认的练习步骤' })).toBeNull(); expect(api.start).toHaveBeenCalledOnce();
  });
  it('offers only explicit continuation and original-project open for a known partial state', async () => {
    api.read.mockResolvedValue({ item: { ...receipt, stage: 'CHAPTER_CREATED', can_recover: true } }); api.recover.mockResolvedValue({ item: receipt });
    render(<FirstUsePanel sessionToken="" onOpenLocal={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '继续已确认的练习步骤' })); await screen.findByRole('button', { name: '打开独立练习' });
    expect(api.recover).toHaveBeenCalledOnce(); expect(api.start).not.toHaveBeenCalled();
  });
  it('does not open a stale response after changing workspace', async () => {
    const path = { workspace_id: 'workspace-a', project_id: 'sample-project', storyline_id: 'story', branch_id: 'branch' };
    api.read.mockResolvedValue({ item: { ...receipt, path } }); const open = vi.fn();
    const view = render(<FirstUsePanel sessionToken="session-a" workspaceId="workspace-a" onOpenScoped={open} />);
    await screen.findByRole('button', { name: '打开独立练习' }); let finish!: (value: any) => void;
    api.read.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    fireEvent.click(screen.getByRole('button', { name: '打开独立练习' }));
    view.rerender(<FirstUsePanel sessionToken="session-b" workspaceId="workspace-b" onOpenScoped={open} />);
    await act(async () => { finish({ item: { ...receipt, path } }); }); expect(open).not.toHaveBeenCalled();
    expect(firstUseClient).toHaveBeenCalledWith({ sessionToken: 'session-b' }, 'workspace-b');
  });
});
describe('SampleJourneyGuide', () => {
  it('uses exact project and save evidence while preserving dirty buffers', async () => {
    api.read.mockResolvedValue({ item: receipt }); const navigate = vi.fn();
    const view = render(<SampleJourneyGuide novelId="sample-project" context={{ sessionToken: '' }} chapter={chapter} saved={false} onNavigate={navigate} />);
    await screen.findByRole('heading', { name: '独立练习 · 写作到导出' });
    expect((screen.getByRole('button', { name: '打开练习导出中心' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText(/当前已保存自己的版本/)).toBeNull();
    view.rerender(<SampleJourneyGuide novelId="sample-project" context={{ sessionToken: '' }} chapter={chapter} saved onNavigate={navigate} />);
    expect(screen.getByText(/当前已保存自己的版本 v3/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '打开练习导出中心' })); expect(navigate).toHaveBeenCalledWith('exports');
    fireEvent.click(screen.getByRole('button', { name: '收起练习指引' })); fireEvent.click(screen.getByRole('button', { name: '重新打开独立练习指引' }));
    expect(screen.getByRole('heading', { name: '独立练习 · 写作到导出' })).toBeTruthy(); expect(api.start).not.toHaveBeenCalled(); expect(api.recover).not.toHaveBeenCalled();
  });
  it('does not apply instructions to an unrelated project', async () => {
    api.read.mockResolvedValue({ item: receipt }); const view = render(<SampleJourneyGuide novelId="real-manuscript" context={{ sessionToken: '' }} chapter={chapter} saved />);
    await waitFor(() => expect(api.read).toHaveBeenCalled()); expect(view.container.textContent).toBe('');
  });
});
