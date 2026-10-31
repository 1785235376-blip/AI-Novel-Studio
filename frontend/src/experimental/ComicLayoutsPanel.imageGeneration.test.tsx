// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel, type ComicImageGenerationHost } from './ComicLayoutsPanel';
import type { ComicRecord } from './comicLayoutsClient';
import type { ExperimentalClient } from './api';
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const page: ComicRecord = { id: 'page', version: 1, status: 'DRAFT', stale: false, document: { title: 'Original', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', ...preset, panels: [{ id: 'panel', shot_id: null, artwork_mode: 'IMAGE', order: 1, x: 24, y: 24, width: 512, height: 512, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', bubbles: [], image_brief: 'scene', appearance_references: [] }] } };
const catalog = { screenplays: [], characters: [], assets: [{ id: 'manual', version: 1, approved: true, filename: 'Manual image' }], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } };
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:fixture'); URL.revokeObjectURL = vi.fn(); });
afterEach(cleanup);
async function mount() {
  let host!: ComicImageGenerationHost;
  const client = { get: vi.fn(async (path: string) => path.endsWith('/catalog') ? catalog : { items: path.endsWith('/records') ? [page] : [] }), post: vi.fn(), put: vi.fn(), blob: vi.fn(), postBlob: vi.fn() } as unknown as ExperimentalClient;
  const dirty = vi.fn(), busy = vi.fn();
  render(<ComicLayoutsPanel client={client} onDirtyChange={dirty} onBusyChange={busy} renderImageGeneration={next => { host = next; return <p>Generation host v{next.page.version}</p>; }} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开布局 Original' }));
  await screen.findByText('Generation host v1'); return { getHost: () => host, client, dirty, busy };
}
it('locks manual page edits and navigation synchronously while generation input owns the saved page', async () => {
  const { getHost, dirty } = await mount(); const host = getHost();
  const title = screen.getByLabelText('漫画布局名称') as HTMLInputElement;
  await act(async () => { host.onDirtyChange(true); fireEvent.change(title, { target: { value: 'must not change' } }); });
  expect(title.value).toBe('Original'); expect(dirty).toHaveBeenLastCalledWith(true);
  expect((screen.getByRole('button', { name: '新建空白漫画页' }) as HTMLButtonElement).disabled).toBe(true);
  expect(host.isCurrent()).toBe(true);
  act(() => getHost().onDirtyChange(false));
  fireEvent.change(screen.getByLabelText('格框 1 已批准图片'), { target: { value: 'manual' } });
  expect((screen.getByLabelText('格框 1 已批准图片') as HTMLSelectElement).value).toBe('manual');
});
it('rejects retained adoption after a local edit, even when the panel ID is unchanged', async () => {
  const { getHost } = await mount(); const original = getHost();
  fireEvent.change(screen.getByLabelText('格框 1 图片简报'), { target: { value: 'new brief' } });
  expect(original.isCurrent()).toBe(false);
  act(() => original.onAdopt({ ...page, version: 2 }));
  expect((screen.getByLabelText('格框 1 图片简报') as HTMLTextAreaElement).value).toBe('new brief');
  expect(screen.queryByText('Generation host v2')).toBeNull();
});
it('accepts only the same page next DRAFT version and refreshes original records', async () => {
  const { getHost, client } = await mount();
  act(() => getHost().onAdopt({ ...page, id: 'another', version: 2 })); expect(screen.queryByText('Generation host v2')).toBeNull();
  act(() => getHost().onAdopt({ ...page, version: 2, status: 'APPROVED' })); expect(screen.queryByText('Generation host v2')).toBeNull();
  act(() => getHost().onAdopt({ ...page, version: 2 }));
  await waitFor(() => expect(screen.getByText('Generation host v2')).toBeTruthy());
  expect(client.get).toHaveBeenCalledWith('/comic-layouts/records', expect.any(AbortSignal));
});
