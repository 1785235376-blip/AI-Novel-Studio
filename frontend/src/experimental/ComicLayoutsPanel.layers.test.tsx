// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { enableComicLayers } from './comicLayers';
import { saveOtioFile } from './timelineExchangeClient';
import type { ComicDocument, ComicRecord } from './comicLayoutsClient';
import fixture from '../../../tests/fixtures/comic_panel_duplicate.json';
vi.mock('./timelineExchangeClient', () => ({ saveOtioFile: vi.fn() }));
const source = { id: 'screenplay', title: 'Source', edit_version: 1, shots: [{ id: 'shot', number: 1, scene_id: 'scene' }] };
const preset = { width: 320, height: 640, safe_area: 8, segment_height: 320 };
const catalog = { screenplays: [source], characters: [{ id: 'alice', name: 'Alice' }], assets: [{ id: 'asset', filename: 'SYNTHETIC.png', version: 2, approved: true }], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted' });
function harness({ layers = false, status = 'DRAFT', intercept }: { layers?: boolean; status?: string; intercept?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined } = {}) {
  const document = structuredClone(fixture.document) as ComicDocument;
  let row: ComicRecord = { id: 'layout', version: 1, status, stale: false, document: layers ? enableComicLayers(document) : document, history_versions: [] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const special = intercept?.(url, init); if (special) return special;
    if (init.method === 'PUT') {
      const { expected_version, ...document } = JSON.parse(String(init.body)); row = { ...row, version: expected_version + 1, status: 'DRAFT', document }; return reply(row);
    }
    if (url.endsWith('/preflight')) return reply({ version: row.version, status: row.status, can_render: true, review_digest: 'digest', segments: [{ index: 0, width: 320, height: 640 }], issues: [] });
    if (url.includes('/segments/')) return new Response(new Blob(['SYNTHETIC PNG']));
    if (url.includes('/export-ora?')) return new Response(new Blob(['SYNTHETIC ORA'], { type: 'image/openraster' }));
    return reply(url.endsWith('/catalog') ? catalog : { items: [row] });
  }); vi.stubGlobal('fetch', fetch); return { fetch };
}
const open = async () => fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
const save = () => fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
const ora = () => screen.getByRole('button', { name: '下载已批准漫画图层（ORA）' }) as HTMLButtonElement;
const preflight = async () => { fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' })); const image = await screen.findByRole('img', { name: /漫画分段 1/ }); fireEvent.load(image); };
const clickHandler = (element: HTMLElement) => (element as unknown as Record<string, { onClick: () => void }>)[Object.keys(element).find(key => key.startsWith('__reactProps'))!].onClick;
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:layer-preview'); URL.revokeObjectURL = vi.fn(); vi.mocked(saveOtioFile).mockClear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('legacy save stays unlayered until explicit enable and never shows ORA export', async () => {
  const { fetch } = harness({ status: 'APPROVED' }); render(<ComicLayoutsPanel client={client()} />); await open(); await preflight();
  expect(screen.queryByRole('button', { name: /下载已批准漫画图层/ })).toBeNull();
  expect(screen.getByRole('button', { name: '下载已批准漫画分段' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: 'Edited legacy' } }); save();
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body))).not.toHaveProperty('layer_stack');
});
it('explicit enable and layer edits preserve canonical dialogue, save through CAS and remain undoable', async () => {
  const { fetch } = harness(); render(<ComicLayoutsPanel client={client()} />); await open();
  fireEvent.click(screen.getByRole('button', { name: '为当前草稿启用图层' }));
  expect((screen.getByLabelText('布局预设') as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('图层 1 名称'), { target: { value: '对白 👩🏽‍🚀' } });
  fireEvent.click(screen.getByLabelText('图层 1 可见'));
  fireEvent.change(screen.getByLabelText('图层 1 不透明度 (%)'), { target: { value: '42' } });
  fireEvent.click(screen.getByRole('button', { name: '下移图层 1' }));
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: '你好 é\n可编辑对白' } });
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect((screen.getByLabelText('格框 1 气泡 1 文字') as HTMLTextAreaElement).value).toBe(fixture.document.panels[0].bubbles[0].text);
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' })); save();
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.expected_version).toBe(1);
  expect(saved.layer_stack.items.map((layer: { kind: string }) => layer.kind)).toEqual(['PANEL_ART', 'PANEL_FRAME', 'BUBBLE_TEXT', 'BUBBLE_SHAPE']);
  expect(saved.layer_stack.items[2]).toMatchObject({ name: '对白 👩🏽‍🚀', visible: false, opacity_percent: 42, target_id: 'speech' });
  expect(saved.panels[0].bubbles[0].text).toBe('你好 é\n可编辑对白');
  expect(saved.layer_stack.items[2]).not.toHaveProperty('text');
  expect(fetch.mock.calls.some(([url]) => /approve|export-ora|generate/.test(url))).toBe(false);
});
it('structural add/remove preserves unrelated layer settings and exact undo coverage', async () => {
  const { fetch } = harness({ layers: true }); render(<ComicLayoutsPanel client={client()} />); await open();
  fireEvent.change(screen.getByLabelText('图层 4 名称'), { target: { value: '保留图片图层' } });
  fireEvent.change(screen.getByLabelText('图层 4 不透明度 (%)'), { target: { value: '37' } });
  fireEvent.click(screen.getByRole('button', { name: '添加格框 1 气泡' }));
  expect(within(screen.getByRole('list', { name: '图层叠放顺序（从上到下）' })).getAllByRole('listitem')).toHaveLength(6);
  fireEvent.click(screen.getByRole('button', { name: '移除格框 1 气泡 1' }));
  expect(within(screen.getByRole('list', { name: '图层叠放顺序（从上到下）' })).getAllByRole('listitem')).toHaveLength(4);
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect(within(screen.getByRole('list', { name: '图层叠放顺序（从上到下）' })).getAllByRole('listitem')).toHaveLength(6);
  save(); await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.layer_stack.items[0]).toMatchObject({ name: '保留图片图层', opacity_percent: 37 });
  expect(saved.layer_stack.items.filter((layer: { target_id: string }) => layer.target_id === 'speech')).toHaveLength(2);
});
it('ORA export needs approved loaded current pixels and admits a double click once', async () => {
  let finish: (value: Response) => void = () => {};
  const { fetch } = harness({ layers: true, status: 'APPROVED', intercept: url => url.includes('/export-ora?') ? new Promise(resolve => { finish = resolve; }) : undefined });
  render(<ComicLayoutsPanel client={client()} />); await open();
  fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  const image = await screen.findByRole('img', { name: /漫画分段 1/ }); expect(ora().disabled).toBe(true); fireEvent.load(image); expect(ora().disabled).toBe(false);
  const retained = clickHandler(ora()); act(() => { retained(); retained(); });
  expect(fetch.mock.calls.filter(([url]) => url.includes('/export-ora?expected_version=1'))).toHaveLength(1);
  expect(ora().disabled).toBe(true); expect(saveOtioFile).not.toHaveBeenCalled();
  await act(async () => { finish(new Response(new Blob(['ORA'], { type: 'image/openraster' }))); });
  expect(saveOtioFile).toHaveBeenCalledWith(expect.any(Blob), 'comic-layers.ora');
  expect(screen.getAllByText(/文字与形状.*栅格化/).length).toBeGreaterThan(0);
});
it('layer edits invalidate pixels and a retained ORA action cannot export unsaved changes', async () => {
  const { fetch } = harness({ layers: true, status: 'APPROVED' }); render(<ComicLayoutsPanel client={client()} />); await open(); await preflight();
  const retained = clickHandler(ora()); fireEvent.click(screen.getByLabelText('图层 1 可见')); act(retained);
  expect(screen.queryByRole('img', { name: /漫画分段 1/ })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.includes('/export-ora?'))).toBe(false);
});
it.each([403, 409, 500])('ORA failure %s preserves the authored native document', async status => {
  harness({ layers: true, status: 'APPROVED', intercept: url => url.includes('/export-ora?') ? reply({ detail: { code: 'ORA_DENIED' } }, status) : undefined });
  render(<ComicLayoutsPanel client={client()} />); await open(); await preflight(); fireEvent.click(ora());
  await screen.findByText(/ORA_DENIED/); expect(saveOtioFile).not.toHaveBeenCalled();
  expect((screen.getByLabelText('格框 1 气泡 1 文字') as HTMLTextAreaElement).value).toBe(fixture.document.panels[0].bubbles[0].text);
});
it('late ORA completion cannot download after owner replacement', async () => {
  let finish: (value: Response) => void = () => {};
  harness({ layers: true, status: 'APPROVED', intercept: url => url.includes('/export-ora?') ? new Promise(resolve => { finish = resolve; }) : undefined });
  const view = render(<ComicLayoutsPanel client={client()} />); await open(); await preflight(); fireEvent.click(ora());
  view.rerender(<ComicLayoutsPanel client={client('other')} />);
  await act(async () => { finish(new Response(new Blob(['ORA']))); }); expect(saveOtioFile).not.toHaveBeenCalled();
});
it('draft approval and failed preview continue to block ORA', async () => {
  harness({ layers: true }); render(<ComicLayoutsPanel client={client()} />); await open(); await preflight(); expect(ora().disabled).toBe(true);
  fireEvent.error(screen.getByRole('img', { name: /漫画分段 1/ })); expect(ora().disabled).toBe(true);
});
it('retained layer control cannot cross a later edit, repeated callback or undo generation', async () => {
  harness({ layers: true }); render(<ComicLayoutsPanel client={client()} />); await open();
  const button = screen.getByRole('button', { name: '下移图层 1' }), retained = clickHandler(button);
  act(() => { retained(); retained(); });
  expect((screen.getByLabelText('图层 1 名称') as HTMLInputElement).value).toMatch(/形状/);
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect((screen.getByLabelText('图层 1 名称') as HTMLInputElement).value).toMatch(/文字/);
  act(retained); expect((screen.getByLabelText('图层 1 名称') as HTMLInputElement).value).toMatch(/文字/);
});
