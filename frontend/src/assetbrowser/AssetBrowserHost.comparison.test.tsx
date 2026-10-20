// @vitest-environment jsdom
import { Blob as NodeBlob } from 'node:buffer';
import { createHash, webcrypto } from 'node:crypto';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from '../creative/IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from '../creative/studioClient';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';

// Keep the complete host, browser, comparison surface, and verified-byte helper mounted.
// Only the original HTTP owner and browser media APIs are fixture substitutes.
const projectId = 'comparison-host-project', base = `/api/projects/${projectId}/studio`;
const bytes = 'original comparison audio', digest = createHash('sha256').update(bytes).digest('hex');
const payload = new NodeBlob([bytes], { type: 'audio/wav' }) as Blob;
const hostToken = 'fixture-original-host-token';
const overview = (): StudioOverview => ({
  project: { id: projectId, title: 'Comparison host', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false,
    chapter_required: false, intent_is_permission: false, media_validator_configured: true,
    asset_kinds: ['image', 'video', 'audio'] },
});
const assets: StudioAsset[] = ['asset-left', 'asset-right'].map((id, index) => ({
  id, novel_id: projectId, branch_id: null, filename: 'comparison.wav', kind: 'audio', media_type: 'audio/wav',
  size: bytes.length, sha256: digest, version: index + 1, created_at: '2026-10-16T00:00:00Z',
  updated_at: '2026-10-16T00:00:00Z', deleted_at: null,
}));
const response = (body: unknown) => ({ ok: true, status: 200, json: async () => body, blob: async () => payload });
let fetchMock: ReturnType<typeof vi.fn>;
const createUrl = vi.fn(), revokeUrl = vi.fn();

function props(): IndependentStudioProps {
  return { projectId, context: { sessionToken: '' },
    scope: { workspace: '本机作品', project: 'Comparison host', storyline: '默认故事线', branch: '主线' },
    actor: '作者', module: 'IMAGE', onModuleChange: vi.fn(), onProjectChoice: vi.fn() };
}
async function openLoadedComparison(patch: Partial<IndependentStudioProps> = {}) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const initialProps = { ...props(), ...patch };
  const element = (value = initialProps) => <QueryClientProvider client={query}><IndependentStudioWorkspace {...value}/></QueryClientProvider>;
  const view = render(element());
  await screen.findByRole('button', { name: '上传资产' });
  const choices = await screen.findAllByRole('button', { name: '选择素材 comparison.wav' });
  fireEvent.click(choices[0]);
  await waitFor(() => expect((screen.getByRole('button', { name: '打开版本对比' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '打开版本对比' }));
  fireEvent.change(screen.getByRole('combobox', { name: '选择对比版本' }), { target: { value: 'asset-right' } });
  const comparison = await screen.findByRole('region', { name: '版本对比' });
  await waitFor(() => expect(comparison.querySelector('[data-slot="RIGHT"]')).toBeTruthy());
  const right = () => within(comparison.querySelector('[data-slot="RIGHT"]') as HTMLElement);
  expect(fetchMock.mock.calls.filter(([url]) => url === `${base}/assets/asset-right/download`)).toHaveLength(0);
  fireEvent.click(right().getByRole('button', { name: /读取音频预览/ }));
  const media = await right().findByLabelText('comparison.wav 音频预览') as HTMLAudioElement;
  return { ...view, initialProps, element, comparison, right, media };
}

beforeEach(() => {
  localStorage.clear();
  useStudio.setState({ novelId: projectId, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: hostToken, actorId: 'fixture-host', epoch: 0 });
  createUrl.mockReset(); revokeUrl.mockReset();
  createUrl.mockImplementation(() => `blob:host-comparison-${createUrl.mock.calls.length}`);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createUrl });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeUrl });
  vi.stubGlobal('crypto', webcrypto);
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (init.method !== 'GET') throw new Error(`Unexpected write: ${init.method} ${url}`);
    if (url === base) return response(overview());
    if (url === `${base}/prompts`) return response({ ...emptyPromptLibrary, project_id: projectId, scope: { mode: 'local', novel_id: projectId } });
    if (url === `${base}/assets` || url.startsWith(`${base}/assets?`)) return response({ items: assets });
    if (url.endsWith('/download')) return response({});
    const asset = assets.find(value => url === `${base}/assets/${value.id}`);
    if (asset) return response(asset);
    throw new Error(`Unexpected request: ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('actual independent workspace comparison preview lifecycle', () => {
  it('keeps loaded comparison and playback across an unrelated host draft rerender without another comparison read', async () => {
    const view = await openLoadedComparison(), src = view.media.src;
    fireEvent.play(view.media);
    const comparisonReads = () => fetchMock.mock.calls.filter(([url]) => url.startsWith(`${base}/assets/asset-right`));
    const callsBefore = comparisonReads().length;
    const pause = vi.spyOn(view.media, 'pause'); pause.mockClear();
    fireEvent.change(screen.getByLabelText('自定义意图'), { target: { value: 'Unrelated local preference draft' } });
    await screen.findByText('创作偏好未保存 · 基于 v1。');
    expect(view.right().getByLabelText('comparison.wav 音频预览')).toBe(view.media);
    expect(view.media.src).toBe(src);
    expect(view.comparison.querySelector('[data-slot="RIGHT"]')?.getAttribute('data-active')).toBe('true');
    expect(pause).not.toHaveBeenCalled(); expect(revokeUrl).not.toHaveBeenCalledWith(src);
    expect(comparisonReads().length).toBe(callsBefore);
    const download = fetchMock.mock.calls.find(([url]) => url === `${base}/assets/asset-right/download`)!;
    expect((download[1].headers as Record<string, string>)['X-Session-Token']).toBe(hostToken);
    expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  });

  it('clears a decoder failure in the real mounted right slot and permits explicit retry', async () => {
    const view = await openLoadedComparison(), src = view.media.src;
    fireEvent.play(view.media); fireEvent.error(view.media);
    expect(view.right().queryByLabelText('comparison.wav 音频预览')).toBeNull();
    expect(view.right().getByRole('alert').textContent).toContain('预览读取失败');
    expect(revokeUrl).toHaveBeenCalledWith(src);
    expect(view.comparison.querySelector('[data-slot="RIGHT"]')?.getAttribute('data-active')).toBe('false');
    fireEvent.click(view.right().getByRole('button', { name: /读取音频预览/ }));
    const replacement = await view.right().findByLabelText('comparison.wav 音频预览') as HTMLAudioElement;
    expect(replacement.src).not.toBe(src);
    expect(fetchMock.mock.calls.filter(([url]) => url === `${base}/assets/asset-right/download`)).toHaveLength(2);
  });

  it.each(['studio credentials', 'host credentials', 'host epoch'] as const)(
    'retires visible private comparison on %s ABA even when credentials return within one batch', async change => {
      const view = await openLoadedComparison(), src = view.media.src;
      fireEvent.play(view.media);
      const pause = vi.spyOn(view.media, 'pause'); pause.mockClear();
      const callsBefore = fetchMock.mock.calls.length;
      act(() => {
        if (change === 'studio credentials') {
          useStudio.setState({ sessionToken: 'fixture-new-studio-token' });
          useStudio.setState({ sessionToken: '' });
        } else if (change === 'host credentials') {
          useLocalHostSession.setState({ token: 'fixture-new-host-token' });
          useLocalHostSession.setState({ token: hostToken });
        } else {
          useLocalHostSession.setState({ epoch: 1 });
          useLocalHostSession.setState({ epoch: 0 });
        }
      });
      expect(screen.queryByRole('region', { name: '版本对比' })).toBeNull();
      expect(pause).toHaveBeenCalled(); expect(revokeUrl).toHaveBeenCalledWith(src);
      expect(fetchMock.mock.calls.length).toBe(callsBefore);
    });

  it('uses new credentials after a real keyed workspace replacement and does not retain the old preview', async () => {
    const view = await openLoadedComparison(), src = view.media.src;
    const callsBefore = fetchMock.mock.calls.length;
    act(() => { useStudio.setState({ sessionToken: 'fixture-replacement-session' }); });
    view.rerender(view.element({ ...view.initialProps, context: { sessionToken: 'fixture-replacement-session' } }));
    await screen.findByRole('button', { name: '上传资产' });
    expect(screen.queryByRole('region', { name: '版本对比' })).toBeNull();
    expect(revokeUrl).toHaveBeenCalledWith(src);
    const newReads = fetchMock.mock.calls.slice(callsBefore);
    expect(newReads.length).toBeGreaterThan(0);
    expect(newReads.every(([, init]) => (init.headers as Record<string, string>)['X-Session-Token'] === 'fixture-replacement-session')).toBe(true);
  });

  it('retires loaded comparison when the explicit localHostToken prop changes and uses the replacement override', async () => {
    const view = await openLoadedComparison({ context: { sessionToken: '', localHostToken: 'fixture-explicit-old' } });
    const src = view.media.src, callsBefore = fetchMock.mock.calls.length;
    const oldDownload = fetchMock.mock.calls.find(([url]) => url === `${base}/assets/asset-right/download`)!;
    expect((oldDownload[1].headers as Record<string, string>)['X-Session-Token']).toBe('fixture-explicit-old');
    view.rerender(view.element({ ...view.initialProps, context: { sessionToken: '', localHostToken: 'fixture-explicit-new' } }));
    await waitFor(() => expect(view.comparison.querySelector('[data-slot="RIGHT"]')).toBeTruthy());
    expect(view.comparison.querySelector('audio')).toBeNull();
    expect(view.media.isConnected).toBe(false);
    expect(revokeUrl).toHaveBeenCalledWith(src);
    fireEvent.click(view.right().getByRole('button', { name: /读取音频预览/ }));
    const replacement = await view.right().findByLabelText('comparison.wav 音频预览') as HTMLAudioElement;
    expect(replacement.src).not.toBe(src);
    const newReads = fetchMock.mock.calls.slice(callsBefore).filter(([url]) => url.startsWith(`${base}/assets/asset-right`));
    expect(newReads.length).toBeGreaterThan(0);
    expect(newReads.every(([, init]) => (init.headers as Record<string, string>)['X-Session-Token'] === 'fixture-explicit-new')).toBe(true);
    expect(newReads.filter(([url]) => url.endsWith('/download'))).toHaveLength(1);
    // Returning to the original explicit credential starts another preview epoch.
    view.rerender(view.element(view.initialProps));
    await waitFor(() => expect(view.comparison.querySelector('[data-slot="RIGHT"]')).toBeTruthy());
    expect(view.comparison.querySelector('audio')).toBeNull();
    expect(revokeUrl).toHaveBeenCalledWith(replacement.src);
  });
});
