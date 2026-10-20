// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
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

  it.each(['same-version', 'failed'] as const)('keeps refresh inputs visible until %s read settles, then retires the old relationship view', async outcome => {
    mount(); await screen.findByRole('region', { name: '独立资产来源' });
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
    await screen.findByText('当前没有可选引用；可以保持独立创作。');
    const finish = deferredRead(); fireEvent.click(screen.getByRole('button', { name: '重新读取当前资产' }));
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).disabled).toBe(true);
    await act(async () => finish(outcome === 'same-version' ? reply(makeAsset()) : { ...reply({ code: 'READ_FAILED' }), ok: false, status: 500 }));
    expect(screen.queryByLabelText('关联理由')).toBeNull();
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v2');
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).disabled).toBe(false);
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('');
    expect(fetchMock.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false);
  });

  it.each([401, 403])('removes the retained refresh form when the original asset read returns %s', async status => {
    mount(); await screen.findByRole('region', { name: '独立资产来源' });
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' }));
    await screen.findByText('当前没有可选引用；可以保持独立创作。');
    const finish = deferredRead(); fireEvent.click(screen.getByRole('button', { name: '重新读取当前资产' }));
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).disabled).toBe(true);
    await act(async () => finish({ ...reply({ code: 'PROJECT_SCOPE_FORBIDDEN' }), ok: false, status }));
    expect(screen.queryByLabelText('关联理由')).toBeNull();
    expect(screen.queryByRole('region', { name: '独立资产来源' })).toBeNull();
    expect(screen.queryByRole('region', { name: '资产关联' })).toBeNull();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false);
  });
});
