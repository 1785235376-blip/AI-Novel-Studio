// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 nav] en 主导航（独立工作区内容条：创作开始/任务中心/素材工作区/创作图/制作操作 + 界面模式）不含汉字；zh 文案不变。 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { projectedTask, tasksResponse, reviewInboxItem, reviewInboxResponse } from '../taskcenter/taskCenterFixtures';
import { setLocale } from '../i18n';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
const id = 'neutral-project', base = `/api/projects/${id}/studio`;
const sha = 'a'.repeat(64);
const overview = (): StudioOverview => ({ project: { id, title: '独立项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } });
const asset = (version = 1): StudioAsset => ({ id: 'image-1', novel_id: id, branch_id: null, filename: 'reference.png', kind: 'image', media_type: 'image/png', size: 3, sha256: sha, version, created_at: '2026-10-16T00:00:00Z', updated_at: '2026-10-16T00:00:00Z', deleted_at: null,
  provenance: { origin: version > 1 ? 'EXTERNAL_IMPORT' : 'UNDECLARED', version, digest: sha, integrity: 'VERIFIED', license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', operation: '外部文件导入', parents: [], sources: [], stale: false } });
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body, blob: async () => new Blob(['png'], { type: 'image/png' }) });
let fetchMock: ReturnType<typeof vi.fn>, saved: StudioAsset[];
type Override = (url: string, init: RequestInit) => unknown;
function server(options: { overview?: StudioOverview; override?: Override } = {}) {
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const changed = options.override?.(url, init); if (changed !== undefined) return await changed;
    if (url === base) return response(options.overview || overview());
    // Mounted Prompt/Asset browsers read the same original owners; these are
    // successful empty/library DTOs, independent of the mutation under test.
    if (url === `${base}/prompts` && init.method === 'GET') return response({ ...emptyPromptLibrary, project_id: id, scope: { mode: 'local', novel_id: id } });
    if (url === `${base}/assets` && init.method === 'GET') return response({ items: saved });
    if (url.startsWith(`${base}/assets?`)) return response({ items: saved });
    if (url === `${base}/production/jobs` && init.method === 'GET') return response({ items: [] });
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

beforeEach(() => {
  localStorage.clear(); saved = [];
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: '', actorId: '' });
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fixture') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  server();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); act(() => setLocale('zh-CN')); });
const HAN = /[\u4e00-\u9fff]/;
function han(root: Element): string[] {
  const out: string[] = []; if (HAN.test(root.textContent || '')) out.push(`text: ${root.textContent}`);
  [root, ...root.querySelectorAll('*')].forEach(el => ['aria-label', 'title'].forEach(a => { const v = el.getAttribute(a); if (v && HAN.test(v)) out.push(`@${a}: ${v}`); }));
  return out;
}
it('en main navigation has no Chinese', async () => {
  act(() => setLocale('en'));
  const { container } = mount();
  const bar = await waitFor(() => { const b = container.querySelector('.studio-graph-actions'); expect(b).toBeTruthy(); return b!; });
  expect(within(bar as HTMLElement).getByRole('button', { name: 'Start creating' })).toBeTruthy();
  expect(han(bar)).toEqual([]);
});
it('zh main navigation labels unchanged', async () => {
  const { container } = mount();
  const bar = await waitFor(() => { const b = container.querySelector('.studio-graph-actions'); expect(b).toBeTruthy(); return b!; });
  for (const n of ['创作开始', '任务中心', '素材工作区', '制作操作']) expect(within(bar as HTMLElement).getByRole('button', { name: n })).toBeTruthy();
});
