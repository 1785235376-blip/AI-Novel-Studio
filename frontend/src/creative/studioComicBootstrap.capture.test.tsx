// @vitest-environment jsdom
// The JSON below is emitted by the real mounted File API, not a hand-built DTO.
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { studioClient } from './studioClient';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { useStudio } from '../store';
import captured from './studioComicBootstrapWire.testFixture.json';

// The capture has no Actor DTO. Supply a synthetic, resolved frontend identity;
// this is not an actor recovered from the File capture or a new credential.
const actor = { id: 'synthetic-bootstrap-author', displayName: '合成测试作者', workspaceId: captured.scope.workspaceId };
const context = { sessionToken: 'synthetic-bootstrap-session', actor, scope: captured.scope };
const base = `/api/projects/${captured.project_id}/studio`;
const comics = `/api/novels/${captured.project_id}/experimental/comic-layouts`;
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(body) });
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:comic'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it('the original client decodes the actual mounted Comic bootstrap and preserves captured headers', async () => {
  const fetcher = vi.fn(async () => response(captured.bootstrap)); vi.stubGlobal('fetch', fetcher);
  expect(captured.capture_contract).toBe('actual-mounted-comic-bootstrap/1');
  expect(await studioClient(captured.project_id, context).comicWorkspace()).toEqual(captured.bootstrap);
  expect(fetcher).toHaveBeenCalledWith(`${base}/comic-workspace`, expect.objectContaining({ method: 'GET',
    headers: expect.objectContaining({ 'X-Session-Token': context.sessionToken, 'X-Branch-Id': captured.branch_id }) }));
});

it.each(['project', 'contract', 'source_free', 'can_mutate', 'can_review'])('rejects malformed captured %s without granting workspace permissions', async field => {
  const value = structuredClone(captured.bootstrap);
  if (field === 'project') value.project.id = 'other-project';
  else if (field === 'contract') value.contract = 'wrong';
  else if (field === 'source_free') (value as Record<string, unknown>).source_free = 'true';
  else (value.capabilities as Record<string, unknown>)[field] = 'true';
  vi.stubGlobal('fetch', vi.fn(async () => response(value)));
  await expect(studioClient(captured.project_id, context).comicWorkspace()).rejects.toMatchObject({ status: 403 });
});

it('actual mounted bootstrap/catalog/page responses pass through IndependentStudioWorkspace to StudioComicPanel', async () => {
  useStudio.setState({ novelId: captured.project_id, chapterId: '', sessionToken: context.sessionToken, actor: context.actor, scope: captured.scope });
  const fetcher = vi.fn(async (url: string) => {
    if (url === base) return response({ detail: { code: 'PERMISSION_DENIED' } }, 403);
    if (url === `${base}/comic-workspace`) return response(captured.bootstrap);
    if (url === `${comics}/catalog`) return response(captured.catalog);
    if (url === `${comics}/records`) return response(captured.records);
    if (url === `${comics}/books`) return response(captured.books);
    throw new Error(`Unexpected request ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={captured.project_id} context={context} module="IMAGE" actor="合成测试作者"
    scope={{ workspace: '测试工作区', project: captured.bootstrap.project.title, storyline: '测试故事线', branch: '测试分支' }} onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: '打开漫画制作' }));
  fireEvent.click(await screen.findByRole('button', { name: `打开布局 ${captured.page.document.title}` }));
  expect((screen.getByLabelText('漫画布局名称') as HTMLInputElement).value).toBe(captured.page.document.title);
  expect(screen.queryByRole('button', { name: '素材工作区' })).toBeNull();
  expect(screen.queryByText('为已保存格框生成图片')).toBeNull();
  expect(new Set(fetcher.mock.calls.map(([url]) => url))).toEqual(new Set([base, `${base}/comic-workspace`, `${comics}/catalog`, `${comics}/records`, `${comics}/books`]));
});

it('an in-flight captured bootstrap cannot remount Comic after session retirement', async () => {
  useStudio.setState({ novelId: captured.project_id, chapterId: '', sessionToken: context.sessionToken, actor: context.actor, scope: captured.scope });
  let resolve!: (value: ReturnType<typeof response>) => void;
  const fetcher = vi.fn(async (url: string) => url === base ? response({ detail: { code: 'PERMISSION_DENIED' } }, 403) : new Promise<ReturnType<typeof response>>(done => { resolve = done; }));
  vi.stubGlobal('fetch', fetcher);
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={captured.project_id} context={context} module="IMAGE" actor="作者"
    scope={{ workspace: '测试工作区', project: '测试项目', storyline: '测试故事线', branch: '测试分支' }} onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await act(async () => { useStudio.setState({ sessionToken: 'replacement' }); resolve(response(captured.bootstrap)); });
  expect(screen.queryByRole('button', { name: '打开漫画制作' })).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(2);
});
