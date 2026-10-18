// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import wire from './videoReferenceWire.testFixture.json';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
const { source, review, result } = wire;
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it.each([false, true])('saves through original VIDEO workspace and refreshes original assets, lost receipt %s', async lost => {
  vi.stubGlobal('crypto', webcrypto); localStorage.clear();
  useStudio.setState({ novelId: source.novel_id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: '', actorId: '' });
  vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:fixture'); static revokeObjectURL = vi.fn(); });
  const base = `/api/projects/${source.novel_id}/studio`; let saved = false, didLose = false;
  const overview = { project: { id: source.novel_id, title: 'Video project', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
    capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
  const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
  const fetch = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === base) return reply(overview);
    if (url === base + '/prompts') return reply({ ...emptyPromptLibrary, project_id: source.novel_id, scope: { mode: 'local', novel_id: source.novel_id } });
    if (url.startsWith(base + '/assets?') && init.method === 'GET') return reply({ items: saved ? [source, result.asset] : [source] });
    if (url === `${base}/assets/${source.id}/video-reference/preview` && init.method === 'POST') return reply(review);
    if (url === `${base}/assets/${source.id}/video-reference/save` && init.method === 'POST') {
      const replayed = saved; saved = true;
      if (lost && !didLose) { didLose = true; throw new Error('Lost response after original asset commit'); }
      return reply({ ...result, receipt: { ...result.receipt, replayed, asset_created: !replayed } }, replayed ? 200 : 201);
    }
    if (url === `${base}/assets/${result.asset.id}`) return reply(result.asset);
    if (url === `${base}/assets/${result.asset.id}/download`) return new Response(new Uint8Array([137, 80, 78, 71]), { headers: { 'Content-Type': 'image/png' } });
    throw new Error(`Unexpected request: ${init.method} ${url}`);
  }); vi.stubGlobal('fetch', fetch);
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={source.novel_id} context={{ sessionToken: '' }}
    scope={{ workspace: 'Local', project: 'Video project', storyline: 'Default', branch: 'Main' }} actor="Author" module="VIDEO" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  const picker = await screen.findByLabelText('视频参考原素材');
  await screen.findByRole('option', { name: 'source.mp4 · v1' });
  expect(fetch.mock.calls.some(([url]) => url.includes('/video-reference/'))).toBe(false);
  fireEvent.change(picker, { target: { value: source.id } });
  fireEvent.change(screen.getByLabelText('采样起点（毫秒，包含）'), { target: { value: String(review.in_ms) } });
  fireEvent.change(screen.getByLabelText('采样终点（毫秒，不包含）'), { target: { value: String(review.out_ms) } });
  fireEvent.change(screen.getByLabelText('采样帧数'), { target: { value: String(review.sample_count) } });
  fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' }));
  const selected = result.receipt.selected_index;
  fireEvent.load(await screen.findByRole('img', { name: `已校验采样帧 ${selected + 1}` }));
  fireEvent.click(screen.getByRole('button', { name: `选择第 ${selected + 1} 帧` }));
  const confirm = screen.getByLabelText('已查看所选采样帧，确认保存为派生图片素材'); fireEvent.click(confirm);
  const save = screen.getByRole('button', { name: '保存所选参考帧到素材库' }); fireEvent.click(save);
  if (lost) {
    await screen.findByText(/保存结果未确认。请先核对原素材库/);
    await waitFor(() => expect((confirm as HTMLInputElement).disabled).toBe(false));
    fireEvent.click(confirm); fireEvent.click(save);
  }
  await screen.findByText('所选帧已保存到原素材库。图片到视频需在现有入口另行明确操作。');
  const writes = fetch.mock.calls.filter(([, init]) => init.method === 'POST');
  expect(writes.map(([url]) => url)).toEqual([`${base}/assets/${source.id}/video-reference/preview`, `${base}/assets/${source.id}/video-reference/save`, ...(lost ? [`${base}/assets/${source.id}/video-reference/save`] : [])]);
  expect(fetch.mock.calls.filter(([url]) => url.startsWith(base + '/assets?')).length).toBeGreaterThan(1);
  expect(fetch.mock.calls.some(([url]) => /generate|execute|production\/jobs/.test(url))).toBe(false);
  const saves = writes.filter(([url]) => url.endsWith('/save')); const first = JSON.parse(String(saves[0][1].body));
  expect(first.reviewed_preview_digest).toBe(review.preview_digest); expect(first.reviewed_png_sha256).toBe(review.frames[selected].png_sha256);
  if (lost) expect(JSON.parse(String(saves[1][1].body))).toEqual(first);
});
