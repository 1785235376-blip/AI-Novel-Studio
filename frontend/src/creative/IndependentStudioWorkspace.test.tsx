// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api';
import { projectedTask, tasksResponse, reviewInboxItem, reviewInboxResponse } from '../taskcenter/taskCenterFixtures';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';

const id = 'neutral-project', base = `/api/projects/${id}/studio`;
const sha = 'a'.repeat(64);
const overview = (): StudioOverview => ({ project: { id, title: '独立项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } });
const asset = (version = 1): StudioAsset => ({ id: 'image-1', novel_id: id, branch_id: null, filename: 'reference.png', kind: 'image', media_type: 'image/png', size: 3, sha256: sha, version, created_at: '', updated_at: '', deleted_at: null,
  provenance: { origin: version > 1 ? 'EXTERNAL_IMPORT' : 'UNDECLARED', version, digest: sha, integrity: 'VERIFIED', license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', operation: '外部文件导入', parents: [], sources: [], stale: false } });
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body, blob: async () => new Blob(['png'], { type: 'image/png' }) });
let fetchMock: ReturnType<typeof vi.fn>, saved: StudioAsset[];
type Override = (url: string, init: RequestInit) => unknown;
function server(options: { overview?: StudioOverview; override?: Override } = {}) {
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const changed = options.override?.(url, init); if (changed !== undefined) return await changed;
    if (url === base) return response(options.overview || overview());
    if (url.startsWith(`${base}/assets?`)) return response({ items: saved });
    if (url === `${base}/assets` && init.method === 'POST') { saved = [asset()]; return response(saved[0], 201); }
    if (url.endsWith('/lineage')) { saved = [asset(2)]; return response(saved[0]); }
    if (url.endsWith('/download')) return response({});
    if (url === `${base}/assets/image-1`) return response(saved[0] || asset());
    if (url.endsWith('/preferences')) return response({ ...JSON.parse(String(init.body)), version: 2 });
    throw new Error(`Unexpected request: ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
}
function props(patch: Partial<IndependentStudioProps> = {}): IndependentStudioProps {
  return { projectId: id, context: { sessionToken: '' }, scope: { workspace: '本机作品', project: '独立项目', storyline: '默认故事线', branch: '主线' }, actor: '作者', module: 'IMAGE', onModuleChange: vi.fn(), onProjectChoice: vi.fn(), ...patch };
}
function mount(patch: Partial<IndependentStudioProps> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><IndependentStudioWorkspace {...props(patch)} /></QueryClientProvider>);
}
async function ready() { await waitFor(() => expect(screen.getByRole('button', { name: '上传资产' })).toBeTruthy()); }
function upload(read: () => Promise<ArrayBuffer> = async () => new Uint8Array([1, 2, 3]).buffer) {
  const file = new File(['png'], 'reference.png', { type: 'image/png' });
  Object.defineProperty(file, 'arrayBuffer', { value: read });
  fireEvent.change(screen.getByLabelText('选择要上传的资产文件'), { target: { files: [file] } });
}
beforeEach(() => {
  localStorage.clear(); saved = [];
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fixture') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  server();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('independent studio original owner integration', () => {
  it('imports once and saves source provenance without chapters, models, or the legacy asset API', async () => {
    const oldUpload = vi.spyOn(api, 'uploadAsset');
    mount(); await ready(); upload();
    await screen.findByText('资产与外部导入来源已保存。');
    expect(oldUpload).not.toHaveBeenCalled();
    expect(screen.getByRole('navigation', { name: '当前创作范围' }).textContent).toContain('项目：独立项目');
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v2');
    const writes = fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET');
    expect(writes.map(([url]) => url)).toEqual([`${base}/assets`, `${base}/assets/image-1/lineage`]);
    expect(JSON.parse(writes[1][1].body)).toMatchObject({ expected_version: 1, origin: 'EXTERNAL_IMPORT', chapter_ids: [], parent_asset_ids: [], license: { label: 'UNSPECIFIED' } });
    expect(screen.getAllByRole('tab')).toHaveLength(8);
  });

  it('retains uploaded v1 after a declaration failure and retries only the declaration', async () => {
    let declarations = 0;
    server({ override: url => url.endsWith('/lineage') && ++declarations === 1 ? response({ code: 'VERSION_CONFLICT' }, 409) : undefined });
    mount(); await ready(); upload();
    await screen.findByText('文件已保存，来源声明尚未保存。可仅重试声明，无需重新上传。');
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v1');
    fireEvent.click(screen.getByRole('button', { name: '仅重试外部导入声明' }));
    await screen.findByText('资产与外部导入来源已保存。');
    expect(fetchMock.mock.calls.filter(([url, init]) => url === `${base}/assets` && init.method === 'POST')).toHaveLength(1);
    expect(declarations).toBe(2);
  });

  it('rejects a delayed file read after the selected project changes', async () => {
    let finish!: (value: ArrayBuffer) => void;
    const bytes = new Promise<ArrayBuffer>(resolve => { finish = resolve; });
    mount(); await ready(); upload(() => bytes);
    useStudio.setState({ novelId: 'other-project' });
    await act(async () => finish(new Uint8Array([1, 2, 3]).buffer));
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });

  it('does not interpret a readable legacy project as a neutral project', async () => {
    const value = overview(); value.project.entry_kind = 'LEGACY'; server({ overview: value }); mount();
    await screen.findByText('当前项目尚未启用独立工作区，请返回项目列表重新选择。');
    expect(screen.queryByRole('button', { name: '上传资产' })).toBeNull();
    expect(screen.getByRole('navigation', { name: '当前创作范围' }).textContent).toContain('小说：独立项目');
    expect(fetchMock.mock.calls).toHaveLength(1);
  });

  it('keeps preview/export available in readonly mode while preventing all writes', async () => {
    const value = overview(); value.capabilities.can_mutate = false; saved = [asset(2)]; server({ overview: value });
    mount(); await ready();
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(await screen.findByRole('button', { name: '检查资产 reference.png' }));
    await screen.findByRole('region', { name: '独立资产来源' });
    expect((screen.getByRole('button', { name: '下载原始文件' }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole('button', { name: '保存来源声明' }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });

  it('disables only import when media validation is unavailable, with truthful capability text', async () => {
    const value = overview(); value.capabilities.media_validator_configured = false; saved = [asset(2)]; server({ overview: value });
    mount(); await ready();
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('图片、视频和音频导入需要 FFmpeg / ffprobe 校验工具。当前可查看和导出已保存资产，未调用模型。')).toBeTruthy();
    expect((await screen.findByRole('button', { name: '删除资产' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('preserves a preference draft on CAS conflict and does not hide modules or run jobs', async () => {
    server({ override: (url, init) => url.endsWith('/preferences') && init.method === 'PUT' ? response({ code: 'VERSION_CONFLICT' }, 409) : undefined });
    const leave = vi.fn(); mount({ onModuleChange: leave }); await ready();
    fireEvent.click(screen.getByText('创作意图与推荐布局'));
    fireEvent.click(screen.getByLabelText('图片设计'));
    fireEvent.click(screen.getByRole('button', { name: '保存创作偏好' }));
    expect((await screen.findByText('版本或来源已经变化。当前草稿已保留，请核对服务端版本。')).getAttribute('role')).toBe('alert');
    expect((screen.getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
    expect(screen.getAllByRole('tab')).toHaveLength(8);
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '小说' }));
    expect(leave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' }));
    expect((screen.getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET').map(([url]) => url)).toEqual([`${base}/preferences`]);
  });

  it('clears private selected data when the authoritative download is denied', async () => {
    saved = [asset(2)]; server({ override: url => url.endsWith('/download') ? response({ code: 'FORBIDDEN' }, 403) : undefined });
    mount({ requestedAssetId: 'image-1' });
    await screen.findByText('当前会话无权访问此项目');
    expect(screen.queryByRole('region', { name: '独立资产来源' })).toBeNull();
    expect(screen.queryByRole('button', { name: '检查资产 reference.png' })).toBeNull();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});

describe('mounted original asset browser to timeline handoff', () => {
  async function sendFixture(target = '时间线模块') {
    saved = [{ ...asset(2), kind: target === '图片模块' ? 'image' : 'video', filename: 'handoff.mp4', media_type: target === '图片模块' ? 'image/png' : 'video/mp4', created_at: '2026-10-16T00:00:00Z', updated_at: '2026-10-16T00:00:00Z' }];
    server({ override: (url, init) => {
      if (url === `${base}/assets` && init.method === 'GET') return response({ items: saved });
      if (url.endsWith('/timelines')) return response({ items: [] });
      return undefined;
    } });
    mount(); await ready(); fireEvent.click(await screen.findByRole('button', { name: '选择素材 handoff.mp4' }));
    await screen.findByRole('button', { name: target }); fireEvent.click(screen.getByRole('button', { name: target }));
  }
  it('routes a real browser reference into the original timeline preview and exact draft only after explicit acceptance', async () => {
    await sendFixture(); fireEvent.click(screen.getByRole('button', { name: '生成引用（不执行目标模块）' }));
    await screen.findByRole('region', { name: '素材引用交接到时间线' });
    await waitFor(() => expect((screen.getByRole('button', { name: '添加视频轨道' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '添加视频轨道' })); fireEvent.click(screen.getByRole('button', { name: '核对交接素材版本' }));
    const select = await screen.findByLabelText('交接目标轨道'); fireEvent.change(select, { target: { value: (select as HTMLSelectElement).options[1].value } });
    expect(screen.getByText(/未保存 · 1 条轨道 · 0 个片段/)).toBeTruthy(); fireEvent.click(screen.getByRole('button', { name: '明确加入原时间线草稿' }));
    await screen.findByText(/已把核对的原素材版本加入/); expect(screen.getByText(/未保存 · 1 条轨道 · 1 个片段/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });
  it.each([['时间线模块', '素材引用交接到时间线'], ['图片模块', '素材引用交接到图片制作'], ['视频模块', '素材引用交接到视频制作']])('keeps dirty-navigation cancel for %s', async (target, region) => {
    await sendFixture(target); fireEvent.change(screen.getByLabelText('自定义意图'), { target: { value: 'keep my draft' } });
    fireEvent.click(screen.getByRole('button', { name: '生成引用（不执行目标模块）' }));
    expect(screen.queryByRole('region', { name: region })).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '继续编辑' }));
    expect((screen.getByLabelText('自定义意图') as HTMLInputElement).value).toBe('keep my draft');
    fireEvent.click(screen.getByRole('button', { name: '生成引用（不执行目标模块）' })); fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); fireEvent.click(screen.getByRole('button', { name: '确认离开' }));
    await screen.findByRole('region', { name: region }); expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });
});


describe('mounted asset browser to original image draft', () => {
  it.each([['图片', 'm5.image.i2i'], ['视频', 'm7.video.i2v']])('requires an explicit %s operation choice and two metadata reads without dispatch', async (kind, operation) => {
    saved = [{ ...asset(2), created_at: '2026-10-16T00:00:00Z', updated_at: '2026-10-16T00:00:00Z' }];
    server({ override: (url, init) => {
      if (url === `${base}/assets` && init.method === 'GET') return response({ items: saved });
      if (url.endsWith('/timelines') || url.endsWith('/providers')) return response({ items: [] });
      return undefined;
    } });
    mount(); await ready(); fireEvent.click(await screen.findByRole('button', { name: '选择素材 reference.png' }));
    fireEvent.click(await screen.findByRole('button', { name: `${kind}模块` })); fireEvent.click(screen.getByRole('button', { name: '生成引用（不执行目标模块）' }));
    await screen.findByRole('region', { name: `素材引用交接到${kind}制作` });
    expect((screen.getByRole('button', { name: `核对${kind}交接版本` }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('操作'), { target: { value: operation } });
    await waitFor(() => expect((screen.getByRole('button', { name: `核对${kind}交接版本` }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: `核对${kind}交接版本` })); fireEvent.click(await screen.findByRole('button', { name: `明确加入${kind}制作草稿` }));
    await screen.findByText(new RegExp(`已加入原${kind}制作草稿`)); expect(screen.getByText(/已绑定来源 reference.png/)).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });
});


describe('mounted TaskCenter original owner routing', () => {
  it('opens exact original media task, deduplicates repeated opens and clears on leaving', async () => {
    server({ override: url => url.includes('/workspace/tasks?') ? response(tasksResponse())
      : url.endsWith('/experimental/media/tasks') ? response({ items: [{ id: 'media-task-1', version: 4, status: 'RUNNING', novel_id: id, scope: { mode: 'local', novel_id: id } }] }) : undefined });
    mount(); await ready(); fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
    fireEvent.click(await screen.findByRole('button', { name: '定位原任务结果' }));
    await screen.findByText('原记录 media-task-1 · v4 · RUNNING');
    fireEvent.click(screen.getByRole('button', { name: '定位原任务结果' }));
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/experimental/media/tasks'))).toHaveLength(1);
    expect(screen.getByRole('button', { name: '任务中心' }).getAttribute('aria-pressed')).toBe('true');
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/production/jobs'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '素材工作区' }));
    expect(screen.queryByLabelText('原任务与候选记录')).toBeNull();
    expect(fetchMock.mock.calls.some(([, init]) => init.method !== 'GET')).toBe(false);
  });
  it('shows unsupported owner honestly without claiming location or reading another service', async () => {
    server({ override: url => url.includes('/workspace/tasks?') ? response(tasksResponse({ items: [projectedTask({ authority: 'images' })] })) : undefined });
    mount(); await ready(); fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
    fireEvent.click(await screen.findByRole('button', { name: '定位原任务结果' }));
    await screen.findByText(/此来源没有接入/);
    expect(fetchMock.mock.calls.some(([url]) => url.includes('/experimental/media/') || url.includes('/production/jobs'))).toBe(false);
  });
});


describe('mounted original candidate reopening', () => {
  it('reads the exact original candidate and refuses newer revisions', async () => {
    server({ override: url => url.includes('/workspace/tasks?') ? response(tasksResponse())
      : url.endsWith('/review-inbox') ? response(reviewInboxResponse({ items: [reviewInboxItem({ novel_id: id, project: id, scope: { mode: 'local', novel_id: id } })] }))
      : url.endsWith('/experimental/media/proposals') ? response({ items: [{ id: 'candidate-1', version: 4, task_id: 'media-task-1', status: 'PENDING_REVIEW', novel_id: id, scope: { mode: 'local', novel_id: id } }] }) : undefined });
    mount(); await ready(); fireEvent.click(screen.getByRole('button', { name: '任务中心' }));
    fireEvent.click(await screen.findByRole('tab', { name: '审核收件箱' }));
    fireEvent.click(await screen.findByRole('button', { name: '查看候选详情' }));
    fireEvent.click(screen.getByRole('button', { name: '定位原审核项' }));
    await screen.findByText(/原候选版本或来源已变化/);
    expect(screen.queryByLabelText('已核对原媒体记录')).toBeNull();
    expect(fetchMock.mock.calls.some(([, init]) => init.method !== 'GET')).toBe(false);
  });
});
