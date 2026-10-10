// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview, StudioReference } from './studioClient';

const id = 'relations-project', base = `/api/projects/${id}/studio`, digest = 'a'.repeat(64);
const reference: StudioReference = { kind: 'ASSET', id: 'target', label: 'target.png', version: 2, digest, deleted: false };
const makeAsset = (): StudioAsset => ({ id: 'source', novel_id: id, branch_id: null, filename: 'source.png', kind: 'image', media_type: 'image/png', size: 3, sha256: digest, version: 2, created_at: '', updated_at: '', relationships: [], provenance: { origin: 'EXTERNAL_IMPORT', version: 2, digest, integrity: 'VERIFIED', license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [], stale: false, operation: '外部文件导入' } });
const overview: StudioOverview = { project: { id, title: '关联项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { manual_import: true, manual_export: true, can_mutate: true, can_review: false, model_required: false, chapter_required: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } };
const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value, blob: async () => new Blob(['png']) });
let fetchMock: ReturnType<typeof vi.fn>, asset: StudioAsset, relationshipStatus: number;
beforeEach(() => {
  localStorage.clear(); asset = makeAsset(); relationshipStatus = 201;
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:relations') }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === base) return reply(overview);
    if (url.includes('/assets?')) return reply({ items: [asset] });
    if (url === `${base}/assets/source`) return reply(asset);
    if (url.endsWith('/download')) return reply({});
    if (url === `${base}/references?kind=ASSET`) return reply({ items: [reference], read_only: true, content_copied: false });
    if (url === `${base}/assets/source/relationships` && init.method === 'POST') {
      if (relationshipStatus !== 201) return reply({ code: relationshipStatus === 409 ? 'VERSION_CONFLICT' : 'FORBIDDEN' }, relationshipStatus);
      const body = JSON.parse(String(init.body)); asset = { ...asset, version: 3, relationships: [{ id: 'relation', type: body.type, state: 'CURRENT', expected: body.target, target: reference, reason: body.reason, created_by: 'local', created_at: '2026-10-09T12:00:00Z', semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' }] };
      return reply(asset, 201);
    }
    throw new Error(`Unexpected request ${url}`);
  }); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function mount() {
  const leave = vi.fn(); const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: '关联项目', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE" requestedAssetId="source" onModuleChange={leave} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  await screen.findByRole('region', { name: '独立资产来源' }); fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
  const option = await screen.findByRole('option', { name: 'target.png · v2' }) as HTMLOptionElement;
  return { leave, choose: () => fireEvent.change(screen.getByLabelText('关联目标'), { target: { value: option.value } }) };
}
describe('studio relationship ownership and draft integration', () => {
  it('keeps a relationship draft across navigation attempts and prevents other asset mutations', async () => {
    const { leave, choose } = await mount(); choose(); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '未保存关联理由' } });
    expect((screen.getByRole('button', { name: '保存来源声明' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '删除资产' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' })); expect(leave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '继续编辑' })); expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('未保存关联理由');
    fireEvent.click(screen.getByRole('button', { name: '放弃关联输入' }));
    await waitFor(() => expect((screen.getByRole('button', { name: '保存来源声明' }) as HTMLButtonElement).disabled).toBe(false));
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });

  it('saves through the original asset owner and refreshes the source version without copying a target', async () => {
    const { choose } = await mount(); choose(); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '构图参考' } }); fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await screen.findByText('关联已保存，原文件和引用内容未改变。');
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v3');
    const writes = fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET'); expect(writes).toHaveLength(1);
    expect(writes[0][0]).toBe(`${base}/assets/source/relationships`); expect(JSON.parse(writes[0][1].body)).toMatchObject({ expected_version: 2, target: { id: 'target', version: 2, digest } });
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); await screen.findByText('理由：构图参考');
  });

  it('preserves CAS-conflicted input and source version until an explicit reload', async () => {
    relationshipStatus = 409; const { choose } = await mount(); choose(); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '发生冲突仍保留' } }); fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await screen.findByRole('alert'); expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('发生冲突仍保留');
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v2'); expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
  });

  it('clears selected private content when saving the relationship is revoked', async () => {
    relationshipStatus = 403; const { choose } = await mount(); choose(); fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await screen.findByText('当前会话无权访问此项目'); expect(screen.queryByRole('region', { name: '资产关联' })).toBeNull(); expect(screen.queryByRole('region', { name: '独立资产来源' })).toBeNull();
  });

  it('prevents relation writes while a provenance draft is being edited', async () => {
    await mount(); fireEvent.change(screen.getByLabelText('许可使用备注'), { target: { value: '来源备注草稿' } });
    expect((screen.getByLabelText('关联目标') as HTMLSelectElement).disabled).toBe(true); expect(screen.getByText('请先保存或放弃来源声明，再修改关联。')).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  });
});
