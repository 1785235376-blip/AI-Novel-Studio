// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';

const id = 'sequential-import-project', base = `/api/projects/${id}/studio`, sha = 'a'.repeat(64);
const reply = (value: unknown, status = 200) => ({ ok: status < 300, status, json: async () => value, blob: async () => new Blob(['png'], { type: 'image/png' }) });
const overview: StudioOverview = { project: { id, title: '连续导入项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const makeAsset = (filename: string, version = 1): StudioAsset => ({ id: filename.replace('.png', ''), novel_id: id, branch_id: null, filename, kind: 'image', media_type: 'image/png', size: 3, sha256: sha, version, created_at: '', updated_at: '', deleted_at: null, provenance: { origin: version === 1 ? 'UNDECLARED' : 'EXTERNAL_IMPORT', version, digest: sha, integrity: 'VERIFIED', license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [], stale: false } });
let fetchMock: ReturnType<typeof vi.fn>, assets: StudioAsset[], releaseList: (() => void) | undefined;
let deferNextList: boolean;
beforeEach(() => {
  localStorage.clear(); assets = []; releaseList = undefined; deferNextList = false;
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:sequential') }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === base) return reply(overview);
    if (url.startsWith(`${base}/assets?`)) {
      if (deferNextList) { deferNextList = false; await new Promise<void>(resolve => { releaseList = resolve; }); }
      return reply({ items: assets });
    }
    if (url === `${base}/assets` && init.method === 'POST') { const asset = makeAsset(JSON.parse(String(init.body)).filename); assets.push(asset); return reply(asset, 201); }
    if (url.endsWith('/lineage') && init.method === 'PUT') {
      const asset = assets.find(value => url === `${base}/assets/${value.id}/lineage`)!;
      const saved = makeAsset(asset.filename, 2); assets = assets.map(value => value.id === saved.id ? saved : value); return reply(saved);
    }
    if (url.endsWith('/download')) return reply({});
    throw new Error(`Unexpected request: ${init.method} ${url}`);
  }); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: '连续导入项目', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
function upload(filename: string) {
  const file = new File(['png'], filename, { type: 'image/png' }); Object.defineProperty(file, 'arrayBuffer', { value: async () => new Uint8Array([1, 2, 3]).buffer });
  fireEvent.change(screen.getByLabelText('选择要上传的资产文件'), { target: { files: [file] } });
}
async function ready() {
  await waitFor(() => expect((screen.getByLabelText('选择要上传的资产文件') as HTMLInputElement).disabled).toBe(false));
  expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(false);
}
const imports = () => fetchMock.mock.calls.filter(([url, init]) => url === `${base}/assets` && init.method === 'POST');
const declarations = () => fetchMock.mock.calls.filter(([url, init]) => url.endsWith('/lineage') && init.method === 'PUT');

describe('independent studio sequential import readiness', () => {
  it('does not advertise readiness at lineage completion while the asset list refresh is still pending, then imports the next file once', async () => {
    mount(); await ready(); deferNextList = true; upload('source.png');
    await screen.findByText('资产与外部导入来源已保存。'); await waitFor(() => expect(releaseList).toBeTypeOf('function'));
    expect((screen.getByLabelText('选择要上传的资产文件') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '上传中…' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('region', { name: '独立资产来源' })).toBeNull();
    await act(async () => releaseList!()); await ready();
    expect(screen.getByRole('region', { name: '资产检查面板' }).querySelector('header strong')?.textContent).toBe('source.png');
    upload('target.png'); await ready();
    await waitFor(() => expect(screen.getByRole('region', { name: '资产检查面板' }).querySelector('header strong')?.textContent).toBe('target.png'));
    expect(screen.getByRole('region', { name: '独立资产来源' }).textContent).toContain('版本 v2');
    expect(imports()).toHaveLength(2); expect(declarations()).toHaveLength(2);
    expect(imports().map(([, init]) => JSON.parse(String(init.body)).filename)).toEqual(['source.png', 'target.png']);
    expect(within(screen.getByRole('region', { name: '资产检查面板' })).getByText('资产 ID').nextElementSibling?.textContent).toBe('target');
  });

  it('rejects a synthetic change sent to the disabled input instead of silently queueing another upload', async () => {
    mount(); await ready(); deferNextList = true; upload('source.png'); await waitFor(() => expect(releaseList).toBeTypeOf('function'));
    expect((screen.getByLabelText('选择要上传的资产文件') as HTMLInputElement).disabled).toBe(true);
    upload('premature.png'); await act(async () => Promise.resolve()); expect(imports()).toHaveLength(1);
    await act(async () => releaseList!()); await ready();
    expect(imports()).toHaveLength(1); expect(declarations()).toHaveLength(1);
    expect(screen.getByRole('region', { name: '资产检查面板' }).querySelector('header strong')?.textContent).toBe('source.png');
  });
});
