// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview, StudioStorage } from './studioClient';

const id = 'read-fence-project', base = `/api/projects/${id}/studio`, digest = 'a'.repeat(64);
const makeAsset = (name = 'source', version = 2): StudioAsset => ({ id: name, novel_id: id, filename: `${name}.png`, kind: 'image', media_type: 'image/png', size: 3, sha256: digest, version, created_at: '', updated_at: '', branch_id: null, relationships: [], provenance: { origin: 'EXTERNAL_IMPORT', version, digest, integrity: 'VERIFIED', license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [], stale: false } });
const makeOverview = (): StudioOverview => ({ project: { id, title: '读取保护项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, can_review: false, manual_import: true, manual_export: true, model_required: false, chapter_required: false, media_validator_configured: true, asset_kinds: ['image', 'audio', 'video'], intent_is_permission: false } });
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value, blob: async () => new Blob(['png']) });
let overview: StudioOverview, storage: StudioStorage, nextRead: Promise<ReturnType<typeof reply>> | undefined, fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  localStorage.clear(); nextRead = undefined; overview = makeOverview();
  storage = { assets: { count: 2, bytes: 6 }, trash: { count: 0, bytes: 0 }, limits: { asset_bytes: 25, project_asset_bytes: 100, project_assets: 10 }, model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER', export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false };
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:read-fence') }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetchMock = vi.fn(async (url: string) => {
    if (url === base) return reply(overview);
    if (url.includes('/assets?')) return reply({ items: [makeAsset(), makeAsset('target')] });
    if (url === `${base}/assets/source`) { const value = nextRead; nextRead = undefined; return value ? await value : reply(makeAsset()); }
    if (url.endsWith('/download')) return reply({});
    if (url.includes('/references?')) return reply({ items: [], read_only: true, content_copied: false });
    if (url.endsWith('/storage')) return reply(storage);
    throw new Error(`Unexpected ${url}`);
  }); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const leave = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: '读取保护项目', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE" requestedAssetId="source" onModuleChange={leave} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  return leave;
}
function deferredRead() { let finish!: (value: ReturnType<typeof reply>) => void; nextRead = new Promise(resolve => { finish = resolve; }); return finish; }

describe('independent asset read fences and truthful capability labels', () => {
  it('locks mutation inputs during explicit refresh and preserves the next draft after the read finishes', async () => {
    const leave = mount(); await screen.findByRole('region', { name: '独立资产来源' });
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); await screen.findByText('当前没有可选引用；可以保持独立创作。');
    const finish = deferredRead(); fireEvent.click(screen.getByRole('button', { name: '重新读取当前资产' }));
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).disabled).toBe(true); expect((screen.getByLabelText('许可使用备注') as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' })); expect(leave).not.toHaveBeenCalled();
    await act(async () => finish(reply(makeAsset('source', 3))));
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v3');
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '刷新后新草稿' } });
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' }));
    await screen.findByText('有未保存的偏好、来源声明或资产关联。可以继续编辑，或确认放弃后离开。');
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('刷新后新草稿'); expect(leave).not.toHaveBeenCalled();
  });

  it('ignores delayed recovery after the author explicitly selects a different asset and starts a draft', async () => {
    const finish = deferredRead(); mount();
    fireEvent.click(await screen.findByRole('button', { name: '检查资产 target.png' }));
    await screen.findByRole('region', { name: '独立资产来源' }); fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
    fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '较新的目标资产草稿' } });
    await act(async () => finish(reply(makeAsset('source', 3))));
    const inspector = screen.getByRole('region', { name: '资产检查面板' });
    expect(inspector.querySelector('header strong')?.textContent).toBe('target.png');
    expect(within(inspector).getByText('资产 ID').nextElementSibling?.textContent).toBe('target');
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v2');
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('较新的目标资产草稿');
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('labels review-only authority accurately while asset files remain readonly', async () => {
    overview.capabilities.can_mutate = false; overview.capabilities.can_review = true; mount(); await screen.findByRole('region', { name: '独立资产来源' });
    expect(screen.getByText('仅审核与读取 · 不需要模型')).toBeTruthy(); expect(screen.getByText('资产文件当前只读，可以查看和导出已有资产。')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); expect((screen.getByRole('option', { name: '审核适用' }) as HTMLOptionElement).disabled).toBe(false);
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('describes presets as saved preferences without implying an active layout change', async () => {
    mount(); await screen.findByRole('region', { name: '独立资产来源' }); fireEvent.click(screen.getByText('创作意图与推荐布局'));
    expect(screen.getByText(/布局选项仅保存偏好，当前不会调整界面/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('布局偏好（仅保存）'), { target: { value: 'VIDEO' } });
    expect(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '图片' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getAllByRole('tab')).toHaveLength(8); expect(fetchMock.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false);
  });

  it.each([
    ['READY', 50, '当前可导入容量估算：50 字节；已扣除安全预留空间和项目配额。'],
    ['LOW_SPACE_OR_QUOTA', 0, '空间或项目配额不足，当前无法继续导入。已有资产仍可查看和导出。'],
    ['UNAVAILABLE', null, '当前无法确认存储容量，导入将由服务端安全校验。'],
  ] as const)('shows safe %s storage state without filesystem paths or cleanup controls', async (state, available, message) => {
    const capacity = state === 'UNAVAILABLE' ? { state, available_import_bytes: null } as const : { state, available_import_bytes: available ?? 0 } as const;
    storage.admission = { ...capacity, reserve_bytes: 64, measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA', paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' }, external_model_scan: false, automatic_cleanup: false, automatic_migration: false };
    mount(); await screen.findByRole('region', { name: '独立资产来源' }); fireEvent.click(screen.getByText('项目存储')); fireEvent.click(screen.getByText('刷新存储统计'));
    await screen.findByText(message); expect(screen.getByText('以上为查询时估算；实际上传会再次校验。回收站仍占用空间，不会自动清理。')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /清理|迁移|删除模型/ })).toBeNull(); expect(document.body.textContent).not.toContain('EXISTING_ASSET_LIBRARY');
  });
});
