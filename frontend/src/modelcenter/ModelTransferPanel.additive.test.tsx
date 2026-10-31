// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ModelTransferPanel } from './ModelTransferPanel';
import { ModelCenterPanel } from './ModelCenterPanel';
import { createModelTransferClient } from './modelTransferClient';
import { checkedModelTransferCatalog, checkedModelTransferCleanupPreview, checkedModelTransferPreview, checkedModelTransferTask,
  type ModelTransferCatalog, type ModelTransferSource, type ModelTransferTask } from './modelTransferContract';
import { modelCenterCatalog, modelCenterStorage } from './modelCenterContract';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import type { ModelCenterPanelProps } from './modelCenterTypes';

const base = '/api/model-center/transfers';
const source: ModelTransferSource = { id: 'reviewed-source', model_id: 'fixture/model', display_name: 'Reviewed model', publisher: 'Fixture publisher',
  license_name: 'Fixture license', license_url: 'https://example.org/license', model_card_url: 'https://example.org/model',
  url: 'https://example.org/model/revision/file.gguf', revision: 'immutable-revision', size_bytes: 4096, sha256: 'a'.repeat(64) };
const task: ModelTransferTask = { id: 'owned-task', source_id: source.id, model_id: source.model_id, display_name: source.display_name,
  state: 'TRANSFERRING', version: 1, bytes_received: 512, total_bytes: 4096, error_code: null, can_resume: false };
const catalog = (items: ModelTransferTask[] = []): ModelTransferCatalog => ({ contract: 'studio-model-transfers/1', configured: true,
  platform_supported: true, blockers: [], sources: [structuredClone(source)], items });
const preview = () => ({ contract: 'studio-model-transfer-preview/1' as const, preview_id: 'preview-1', preview_digest: 'b'.repeat(64), expires_at: Date.now() / 1000 + 600,
  source: structuredClone(source), destination: '/controlled/owned/model.gguf', required_bytes: 4096, available_bytes: 16384, reserve_bytes: 1024 });
const cleanupPreview = (t: ModelTransferTask) => ({ contract: 'studio-model-transfer-cleanup/1' as const, preview_id: 'cleanup-1', preview_digest: 'c'.repeat(64),
  expires_at: Date.now() / 1000 + 600, task_id: t.id, version: t.version, bytes: t.bytes_received });
function setup(answer: (url: string, method?: string, body?: unknown, signal?: AbortSignal) => unknown = () => catalog()) {
  const json = vi.fn(async (url: string, method?: string, body?: unknown, signal?: AbortSignal) => answer(url, method, body, signal));
  const transport = { json } as unknown as StudioGraphTransport;
  // Record admission separately: vi.fn erases a generic implementation's
  // result type, so the prop wrappers must preserve each callback's own T.
  const read = vi.fn<(work: () => Promise<unknown>) => void>();
  const mutate = vi.fn<(work: () => Promise<unknown>) => void>();
  const props: ModelCenterPanelProps = { projectId: 'project', scope: { projectId: 'project', workspaceId: 'w', storylineId: 's', branchId: 'b' },
    transport, identity: 'original', active: true, denied: false, busy: false, isCurrent: () => true,
    read: <T,>(work: () => Promise<T>): Promise<T> => { read(work); return work(); },
    mutate: <T,>(work: () => Promise<T>): Promise<T> => { mutate(work); return work(); } };
  return { props, json, read, mutate };
}
async function load() { fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' })); await screen.findByText(/已读取当前传输状态/); }
async function chooseAndPreview() {
  await load(); fireEvent.change(screen.getByLabelText('已审核下载来源'), { target: { value: source.id } });
  fireEvent.click(screen.getByRole('button', { name: '预览下载与目标目录' })); await screen.findByLabelText('下载确认预览');
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('closed transfer wire contract', () => {
  it('copies the accepted catalog and rejects unknown keys, duplicates, invalid bytes and unsolicited credentials', () => {
    const wire = catalog([task]), checked = checkedModelTransferCatalog(wire); wire.sources[0].publisher = 'changed';
    expect(checked.sources[0].publisher).toBe(source.publisher);
    for (const invalid of [ { ...catalog(), secret: 'never-show' }, { ...catalog(), sources: [source, source] }, { ...catalog(), items: [task, task] },
      { ...catalog(), configured: 'yes' }, { ...catalog(), sources: [{ ...source, size_bytes: 0 }] },
      { ...catalog(), sources: [{ ...source, size_bytes: Number.MAX_SAFE_INTEGER + 1 }] },
      { ...catalog(), sources: [{ ...source, sha256: 'A'.repeat(64) }] }, { ...catalog(), sources: [{ ...source, api_key: 'never-show' }] },
      { ...catalog(), sources: [{ ...source, url: 'http://example.org/file' }] }, { ...catalog(), sources: [{ ...source, url: 'https://user:pass@example.org/file' }] },
      { ...catalog(), sources: [{ ...source, license_url: 'javascript:alert(1)' }] },
      ...['https://example.org/model?token=value', 'https://example.org:8443/model', 'https://example.org/model#fragment', 'https://example.org/a/../file.gguf', 'https://example.org/%2e/file.gguf'].map(url => ({ ...catalog(), sources: [{ ...source, url }] })) ]) expect(() => checkedModelTransferCatalog(invalid)).toThrow();
  });
  it('rejects task contradictions, foreign receipts and preview source substitution', () => {
    for (const invalid of [{ ...task, state: 'READY' }, { ...task, version: 0 }, { ...task, bytes_received: 4097 }, { ...task, state: 'COMPLETED' },
      { ...task, can_resume: true }, { ...task, error_code: 'secret\nvalue' }, { ...task, destination: '/unowned' }]) expect(() => checkedModelTransferTask(invalid)).toThrow();
    expect(() => checkedModelTransferTask({ ...task, id: 'foreign' }, task)).toThrow();
    expect(() => checkedModelTransferPreview({ ...preview(), source: { ...source, url: 'https://other.example/file' } }, source)).toThrow();
    expect(() => checkedModelTransferPreview({ ...preview(), expires_at: Number.MAX_VALUE }, source)).toThrow();
    expect(() => checkedModelTransferCleanupPreview({ ...cleanupPreview(task), task_id: 'foreign' }, task)).toThrow();
    expect(() => checkedModelTransferCleanupPreview({ ...cleanupPreview(task), version: 2 }, task)).toThrow();
    expect(checkedModelTransferTask({ ...task, state: 'PAUSING' }).state).toBe('PAUSING');
    expect(checkedModelTransferTask({ ...task, state: 'CANCELLING' }).state).toBe('CANCELLING');
  });
});

describe('captured transfer client', () => {
  it('fences every request with captured scope and never starts or cleans from a read', async () => {
    const { props, json } = setup(); const scope = { ...props.scope! };
    const client = createModelTransferClient('project', props.transport, scope); scope.projectId = 'changed';
    await client.list(); expect(json).toHaveBeenCalledWith(base, 'GET', undefined, undefined);
    const foreign = createModelTransferClient('other', props.transport, props.scope);
    await expect(foreign.list()).rejects.toThrow(); await expect(foreign.start(preview())).rejects.toThrow();
    await expect(foreign.preview(source)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1);
  });
  it('uses exact preview bindings and versioned POST commands with no automatic follow-up request', async () => {
    const { props, json } = setup((_url, _method, body) => ({ ...task, version: typeof body === 'object' && body && 'expected_version' in body ? 2 : 1 }));
    const client = createModelTransferClient('project', props.transport, props.scope), p = preview();
    await client.start(p); expect(json).toHaveBeenLastCalledWith(`${base}/start`, 'POST', { preview_id: p.preview_id, preview_digest: p.preview_digest, confirmed: true }, undefined);
    await client.pause(task); expect(json).toHaveBeenLastCalledWith(`${base}/${task.id}/pause`, 'POST', { expected_version: 1 }, undefined);
    await client.resume({ ...task, state: 'PAUSED', can_resume: true });
    expect(json).toHaveBeenLastCalledWith(`${base}/${task.id}/resume`, 'POST', { expected_version: 1, confirmed: true }, undefined);
    expect(json).toHaveBeenCalledTimes(3);
  });
  it('rejects expired previews, insufficient space, stale write receipts and foreign task responses', async () => {
    const { props, json } = setup(() => task), client = createModelTransferClient('project', props.transport, props.scope);
    await expect(client.start({ ...preview(), expires_at: 1 })).rejects.toThrow();
    await expect(client.start({ ...preview(), available_bytes: 1 })).rejects.toThrow(); expect(json).not.toHaveBeenCalled();
    await expect(client.pause(task)).rejects.toThrow(); json.mockResolvedValueOnce({ ...task, id: 'foreign', version: 2 });
    await expect(client.cancel(task)).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(2);
  });
});

describe('manual controlled transfer panel', () => {
  it('does no mount traffic and honestly explains production with no reviewed sources or destination', async () => {
    const { props, json, mutate } = setup(() => ({ ...catalog(), configured: false, sources: [], blockers: ['REVIEWED_SOURCES_NOT_CONFIGURED'] }));
    render(<ModelTransferPanel {...props} />); expect(json).not.toHaveBeenCalled(); expect(screen.getByText(/生产默认未配置/)).toBeTruthy();
    await load(); expect(screen.getByText(/尚未配置已审核来源和受控目标目录/)).toBeTruthy();
    expect(screen.getByText('没有已审核的下载来源')).toBeTruthy(); expect(mutate).not.toHaveBeenCalled();
    expect(json).toHaveBeenCalledTimes(1); expect(screen.queryByRole('button', { name: /开始下载/ })).toBeNull();
  });
  it('mounts additively without making the model registry downloadable or calling the transfer API', async () => {
    const { props, json } = setup();
    const storage = modelCenterStorage({ assets: { count: 0, bytes: 0 }, trash: { count: 0, bytes: 0 }, limits: { asset_bytes: 1024, project_asset_bytes: 4096, project_assets: 10 },
      model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER', export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false });
    render(<ModelCenterPanel {...props} catalog={modelCenterCatalog({ items: [] }, { items: [] })} storage={storage} />);
    expect(screen.getByLabelText('受控模型文件传输')).toBeTruthy(); expect(json).not.toHaveBeenCalled();
    expect((screen.getByRole('button', { name: /下载模型/ }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('shows exact source/license/digest/bytes/destination before explicit start and requires explicit state reread', async () => {
    const { props, json, read, mutate } = setup(url => url === base ? catalog() : url.endsWith('/preview') ? preview() : task);
    render(<ModelTransferPanel {...props} />); await chooseAndPreview();
    expect((screen.getByLabelText('审核后的下载来源 URL') as HTMLTextAreaElement).value).toBe(source.url);
    expect((screen.getByLabelText('预期 SHA-256') as HTMLTextAreaElement).value).toBe(source.sha256);
    expect(screen.getByText(/精确文件大小：4096 bytes/)).toBeTruthy(); expect(screen.getByRole('link', { name: 'Fixture license' }).getAttribute('href')).toBe(source.license_url);
    expect((screen.getByLabelText('确认的目标目录 / 文件') as HTMLTextAreaElement).value).toBe(preview().destination);
    expect(mutate).not.toHaveBeenCalled(); expect(json).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('button', { name: '确认来源、许可证与目标并开始下载' }));
    await screen.findByText(/已收到操作回执/); expect(mutate).toHaveBeenCalledTimes(1); expect(read).toHaveBeenCalledTimes(2);
    expect(json).toHaveBeenCalledTimes(3); expect((screen.getByRole('button', { name: '暂停传输' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /开始下载/ })).toBeNull();
  });
  it('blocks malformed previews without exposing unknown fields', async () => {
    const { props, json } = setup(url => url === base ? catalog() : { ...preview(), credential: 'should-never-render' });
    render(<ModelTransferPanel {...props} />); await load(); fireEvent.change(screen.getByLabelText('已审核下载来源'), { target: { value: source.id } });
    fireEvent.click(screen.getByRole('button', { name: '预览下载与目标目录' })); await screen.findByText(/传输读取失败或回执无效/);
    expect(screen.queryByRole('button', { name: /开始下载/ })).toBeNull(); expect(screen.queryByText('should-never-render')).toBeNull(); expect(json).toHaveBeenCalledTimes(2);
  });
  it('never retries an unknown write outcome and disables repeat writes until an explicit successful read', async () => {
    const { props, json } = setup(url => { if (url.endsWith('/start')) throw new Error('network outcome unknown'); return url === base ? catalog() : preview(); });
    render(<ModelTransferPanel {...props} />); await chooseAndPreview();
    fireEvent.click(screen.getByRole('button', { name: /确认来源、许可证与目标并开始下载/ })); await screen.findByText(/写入结果未知，未自动重试/);
    expect(json).toHaveBeenCalledTimes(3); expect((screen.getByRole('button', { name: '预览下载与目标目录' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: /开始下载/ })).toBeNull();
    await load(); expect(json).toHaveBeenCalledTimes(4); expect((screen.getByRole('button', { name: '预览下载与目标目录' }) as HTMLButtonElement).disabled).toBe(false);
  });
  it('labels asynchronous pause/cancel requests honestly and does not poll', async () => {
    const { props, json } = setup(url => url === base ? catalog([task]) : { ...task, state: 'PAUSING', version: 2 });
    render(<ModelTransferPanel {...props} />); await load(); fireEvent.click(screen.getByRole('button', { name: '暂停传输' }));
    await screen.findByText('正在请求暂停（尚未停止）'); expect(screen.queryByText('已暂停')).toBeNull(); expect(json).toHaveBeenCalledTimes(2);
  });
  it('shows original-source/destination resume confirmation and versions the explicit resume', async () => {
    const paused = { ...task, state: 'PAUSED' as const, can_resume: true };
    const { props, json } = setup(url => url === base ? catalog([paused]) : { ...task, version: 2 });
    render(<ModelTransferPanel {...props} />); await load(); expect(screen.getByText(/恢复将继续该任务原先确认的来源和目标目录/)).toBeTruthy();
    expect(json).toHaveBeenCalledTimes(1); fireEvent.click(screen.getByRole('button', { name: '确认原来源与目标并恢复' })); await screen.findByText(/已收到操作回执/);
    expect(json.mock.calls[1].slice(0, 3)).toEqual([`${base}/${task.id}/resume`, 'POST', { expected_version: 1, confirmed: true }]);
  });
  it('previews cleanup separately and confirms only owned partial bytes, with no completed-file deletion', async () => {
    const cancelled = { ...task, state: 'CANCELLED' as const }, completed = { ...task, id: 'complete-task', state: 'COMPLETED' as const, bytes_received: 4096 };
    const { props, json, mutate } = setup(url => url === base ? catalog([cancelled, completed]) : url.endsWith('/cleanup-preview') ? cleanupPreview(cancelled) : { ...cancelled, state: 'CLEANED', version: 2, bytes_received: 0 });
    render(<ModelTransferPanel {...props} />); await load(); expect(screen.getAllByRole('button', { name: '预览清理本任务部分文件' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '预览清理本任务部分文件' })); await screen.findByLabelText('部分文件清理确认');
    expect(mutate).not.toHaveBeenCalled(); expect(screen.getByText(/仅清理本任务拥有的部分文件：512 bytes/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '确认清理 512 bytes 部分文件' })); await screen.findByText('已清理本任务部分文件');
    expect(mutate).toHaveBeenCalledTimes(1); expect(json.mock.calls[2].slice(0, 3)).toEqual([`${base}/${task.id}/cleanup`, 'POST', { expected_version: 1, preview_id: 'cleanup-1', preview_digest: 'c'.repeat(64), confirmed: true }]);
  });
  it.each(['identity', 'transport', 'scope', 'inactive', 'denied'] as const)('retires late reads on %s changes without issuing another request', async kind => {
    let finish!: (value: unknown) => void, signal: AbortSignal | undefined;
    const { props, json } = setup((_url, _method, _body, s) => { signal = s; return new Promise(resolve => { finish = resolve; }); });
    const view = render(<ModelTransferPanel {...props} />); fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' }));
    const changed = { ...props, ...(kind === 'identity' ? { identity: 'other' } : kind === 'transport' ? { transport: { json: vi.fn() } as unknown as StudioGraphTransport }
      : kind === 'scope' ? { scope: { ...props.scope!, branchId: 'other' } } : kind === 'inactive' ? { active: false } : { denied: true }) };
    view.rerender(<ModelTransferPanel {...changed} />); expect(signal?.aborted).toBe(true);
    await act(async () => finish(catalog([task]))); expect(screen.queryByLabelText('已审核下载来源')).toBeNull(); expect(json).toHaveBeenCalledTimes(1);
  });
  it('retires a late write without applying it or retrying after identity changes', async () => {
    let finish!: (value: unknown) => void;
    const { props, json } = setup(url => url === base ? catalog([task]) : new Promise(resolve => { finish = resolve; }));
    const view = render(<ModelTransferPanel {...props} />); await load(); fireEvent.click(screen.getByRole('button', { name: '暂停传输' }));
    view.rerender(<ModelTransferPanel {...props} identity="other" />); await act(async () => finish({ ...task, state: 'PAUSING', version: 2 }));
    expect(screen.queryByText('正在请求暂停（尚未停止）')).toBeNull(); expect(json).toHaveBeenCalledTimes(2);
  });
  it('captures a deferred wrapper and never dispatches its command after retirement', async () => {
    const { props, json } = setup(() => catalog([task])); let deferred!: () => Promise<unknown>;
    const mutate = <T,>(work: () => Promise<T>) => { deferred = work; return new Promise<T>(() => {}); };
    const view = render(<ModelTransferPanel {...props} mutate={mutate} />); await load(); fireEvent.click(screen.getByRole('button', { name: '暂停传输' }));
    view.rerender(<ModelTransferPanel {...props} mutate={mutate} identity="other" />);
    await expect(async () => deferred()).rejects.toThrow(); expect(json).toHaveBeenCalledTimes(1);
  });
  it('retains its valid mutation receipt when the workspace wrapper sets busy', async () => {
    let finish!: (value: unknown) => void;
    const { props } = setup(url => url === base ? catalog([task]) : new Promise(resolve => { finish = resolve; }));
    const view = render(<ModelTransferPanel {...props} />); await load(); fireEvent.click(screen.getByRole('button', { name: '暂停传输' }));
    view.rerender(<ModelTransferPanel {...props} busy />); await act(async () => finish({ ...task, state: 'PAUSING', version: 2 }));
    expect(screen.getByText('正在请求暂停（尚未停止）')).toBeTruthy();
  });
  it('blocks invalid project context, inactive admission and live isCurrent revocation', async () => {
    const { props, json } = setup(); const view = render(<ModelTransferPanel {...props} projectId="" />);
    expect((screen.getByRole('button', { name: '明确读取传输状态' }) as HTMLButtonElement).disabled).toBe(true);
    view.rerender(<ModelTransferPanel {...props} scope={{ ...props.scope!, projectId: 'other' }} />);
    fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' })); expect(json).not.toHaveBeenCalled();
    let valid = true; view.rerender(<ModelTransferPanel {...props} isCurrent={() => valid} />); valid = false;
    fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' })); expect(json).not.toHaveBeenCalled();
  });
});


it('invalidates a download preview immediately when its source selection changes', async () => {
  const { props, json } = setup(url => url === base ? catalog() : preview());
  render(<ModelTransferPanel {...props} />); await chooseAndPreview();
  fireEvent.change(screen.getByLabelText('已审核下载来源'), { target: { value: '' } });
  expect(screen.queryByLabelText('下载确认预览')).toBeNull(); expect(json).toHaveBeenCalledTimes(2);
});
it('checks preview expiry again at confirmation time without sending a write', async () => {
  const clock = Date.now(), { props, json, mutate } = setup(url => url === base ? catalog() : { ...preview(), expires_at: clock / 1000 + 60 });
  render(<ModelTransferPanel {...props} />); await chooseAndPreview();
  vi.spyOn(Date, 'now').mockReturnValue(clock + 61000);
  fireEvent.click(screen.getByRole('button', { name: /确认来源、许可证与目标并开始下载/ }));
  await screen.findByText('下载预览已过期，请重新预览并确认。'); expect(json).toHaveBeenCalledTimes(2); expect(mutate).not.toHaveBeenCalled();
});
it('keeps unsupported-platform and failed-read states closed', async () => {
  const { props, json } = setup(() => ({ ...catalog([task]), platform_supported: false }));
  render(<ModelTransferPanel {...props} />); await load();
  expect((screen.getByRole('button', { name: '预览下载与目标目录' }) as HTMLButtonElement).disabled).toBe(true);
  json.mockRejectedValueOnce(new ApiError({ status: 403, code: 'DENIED', message: 'private diagnostic' }));
  fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' })); await screen.findByText(/传输读取被拒绝/);
  expect((screen.getByRole('button', { name: '暂停传输' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByText('private diagnostic')).toBeNull();
});
it('rejects completed-file cleanup and foreign cleanup previews without any destructive request', async () => {
  const { props, json } = setup(() => cleanupPreview(task)), client = createModelTransferClient('project', props.transport, props.scope);
  const complete = { ...task, state: 'COMPLETED' as const, bytes_received: 4096 };
  await expect(client.cleanupPreview(complete)).rejects.toThrow();
  await expect(client.cleanup(complete, cleanupPreview(complete))).rejects.toThrow();
  await expect(client.cleanup({ ...task, state: 'CANCELLED' }, { ...cleanupPreview(task), task_id: 'foreign' })).rejects.toThrow();
  expect(json).not.toHaveBeenCalled();
});
it('retires an in-flight read on unmount', async () => {
  let finish!: (value: unknown) => void, signal: AbortSignal | undefined;
  const { props, json } = setup((_url, _method, _body, s) => { signal = s; return new Promise(resolve => { finish = resolve; }); });
  const view = render(<ModelTransferPanel {...props} />); fireEvent.click(screen.getByRole('button', { name: '明确读取传输状态' }));
  view.unmount(); expect(signal?.aborted).toBe(true); await act(async () => finish(catalog([task]))); expect(json).toHaveBeenCalledTimes(1);
});

it('treats available bytes as already net of reserve, without double-counting the reserve', async () => {
  const { props, json } = setup(() => task), client = createModelTransferClient('project', props.transport, props.scope);
  await client.start({ ...preview(), required_bytes: 4096, available_bytes: 4096, reserve_bytes: 1024 });
  expect(json).toHaveBeenCalledTimes(1);
});
