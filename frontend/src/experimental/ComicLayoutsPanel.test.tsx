// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { comicPreset } from './comicLayoutsClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const source = { id: 'screenplay', title: 'Synthetic test comic', edit_version: 4, shot_status: 'APPROVED', checks: [], shots: [{ id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const document = comicPreset(source, 'PAGE', preset);
const record = { id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] };
const asset = { id: 'asset', filename: 'SYNTHETIC-TEST-ASSET.png', version: 1, approved: false, manual_review_available: true };
const catalog = { screenplays: [source], characters: [{ id: 'alice', name: 'Alice' }], assets: [asset], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400, segment_height: 1200 } }, renderer: { available: true }, font: { available: true } };
const report = { issues: [], segments: [{ index: 0, width: 800, height: 1120, y: 0 }], can_render: true, review_digest: 'a'.repeat(64), version: 1, status: 'DRAFT' };
const client = (nid = 'novel') => experimentalClient(nid, { sessionToken: 'trusted' });
function fetcher(mutation?: (url: string, init: RequestInit) => Response | Promise<Response>, sourceCatalog = catalog) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(record, 201);
    if (/segments\/|images\//.test(url)) return new Response(new Blob(['TEST PNG BYTES'], { type: 'image/png' }));
    return reply(url.endsWith('/catalog') ? sourceCatalog : { items: [record] });
  });
}
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:synthetic-test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('mount is read-only; hand-edited numeric geometry reuses original source IDs and supports undo', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); render(<StrictMode><ComicLayoutsPanel client={client()} /></StrictMode>);
  await screen.findByRole('option', { name: /Synthetic test comic/ }); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: 'screenplay' } });
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('24');
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' })); expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1));
  const body = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'POST')![1].body));
  expect(body).toMatchObject({ screenplay_id: 'screenplay', expected_screenplay_version: 4, panels: [{ x: 48, shot_id: 'shot', asset_id: null }] });
  expect(fetch.mock.calls.some(([url]) => /generate|execute|approve/.test(url))).toBe(false);
});

it('explicit raster preview is required for image review and double clicks submit once', async () => {
  let finish: (value: Response) => void = () => {};
  const fetch = fetcher(() => new Promise(resolve => { finish = resolve; })); vi.stubGlobal('fetch', fetch); render(<ComicLayoutsPanel client={client()} />);
  await screen.findByRole('option', { name: /SYNTHETIC-TEST-ASSET/ }); fireEvent.change(screen.getByLabelText('待核对的原图片'), { target: { value: 'asset' } });
  expect((screen.getByRole('button', { name: '批准此用户图片' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '查看原图片像素' })); const image = await screen.findByRole('img', { name: /待审原图片/ }); fireEvent.load(image);
  fireEvent.click(screen.getByLabelText('已查看此用户图片，并确认可用于漫画排版'));
  const button = screen.getByRole('button', { name: '批准此用户图片' }); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/approve'))).toHaveLength(1));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/approve'))![1].body))).toEqual({ expected_version: 1 });
  finish(reply({ id: 'asset', version: 2 })); await screen.findByText(/已记录原图库图片/);
});

it('preflight blockers are displayed and do not fetch fake preview pixels', async () => {
  const fetch = fetcher(() => reply({ ...report, can_render: false, issues: [{ code: 'COMIC_MISSING_APPROVED_IMAGE', target: 'panel-1', severity: 'BLOCKER' }] })); vi.stubGlobal('fetch', fetch);
  render(<ComicLayoutsPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: /打开布局/ })); fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  await screen.findByText(/缺少已批准图片/); expect(fetch.mock.calls.some(([url]) => /segments\//.test(url))).toBe(false);
  expect((screen.getByRole('button', { name: '批准当前漫画布局' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '下载已批准漫画分段' }) as HTMLButtonElement).disabled).toBe(true);
});

it('approved-review ticket clears when geometry changes; preview widths do not rerender geometry', async () => {
  const fetch = fetcher(() => reply(report)); vi.stubGlobal('fetch', fetch); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ })); fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  await screen.findByRole('img', { name: /漫画分段 1/ }); const calls = fetch.mock.calls.length;
  fireEvent.change(screen.getByLabelText('漫画预览屏宽'), { target: { value: '320' } }); expect(fetch.mock.calls.length).toBe(calls);
  const preview = screen.getByLabelText('实际漫画分段像素'); expect(preview.style.width).toBe('320px');
  fireEvent.click(screen.getByLabelText('已核对图片、阅读顺序、所有裁切与分段警告，并批准此布局版本'));
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '40' } });
  expect(screen.queryByRole('button', { name: '批准当前漫画布局' })).toBeNull(); expect(screen.queryByRole('img', { name: /漫画分段 1/ })).toBeNull();
  expect(URL.revokeObjectURL).toHaveBeenCalled();
});

it('preserves draft on version conflict and clears private draft on captured-scope replacement', async () => {
  const fetch = fetcher(() => reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); vi.stubGlobal('fetch', fetch);
  const view = render(<ComicLayoutsPanel client={client()} />); await screen.findByRole('option', { name: /Synthetic test comic/ });
  fireEvent.change(screen.getByLabelText('漫画来源剧本'), { target: { value: 'screenplay' } }); fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: '保留本地排版' } });
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' })); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect((screen.getByLabelText('漫画布局名称') as HTMLInputElement).value).toBe('保留本地排版');
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<ComicLayoutsPanel client={client('other')} />);
  expect(screen.queryByDisplayValue('保留本地排版')).toBeNull(); expect(screen.queryByText(document.title)).toBeNull();
});

it('late preflight completion cannot resurrect pixels after switching project', async () => {
  let finish: (value: Response) => void = () => {};
  const fetch = fetcher(() => new Promise(resolve => { finish = resolve; })); vi.stubGlobal('fetch', fetch);
  const view = render(<ComicLayoutsPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: /打开布局/ })); fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  view.rerender(<ComicLayoutsPanel client={client('other')} />); finish(reply(report));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => /segments\//.test(url))).toBe(false));
  expect(screen.queryByRole('img', { name: /漫画分段/ })).toBeNull();
});

it('preset produces bounded nonoverlapping source-linked page and vertical geometry', () => {
  const many = { ...source, shots: Array.from({ length: 8 }, (_, i) => ({ ...source.shots[0], id: `shot-${i}`, number: i + 1 })) };
  for (const kind of ['PAGE', 'WEBTOON'] as const) {
    const doc = comicPreset(many, kind, catalog.presets[kind]); expect(doc.panels.length).toBe(kind === 'PAGE' ? 4 : 6);
    doc.panels.forEach((panel, index) => { expect(panel.shot_id).toBe(`shot-${index}`); expect(panel.y + panel.height).toBeLessThanOrEqual(doc.height - doc.safe_area); if (index) expect(panel.y).toBeGreaterThan(doc.panels[index - 1].y + doc.panels[index - 1].height); });
  }
});

it('approves only displayed current pixels with exact digest and downloads only the approved version', async () => {
  let current = { ...record }; const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/records') && init.method === 'GET') return reply({ items: [current] });
    if (url.endsWith('/preflight')) return reply({ ...report, version: current.version, status: current.status });
    if (url.endsWith('/approve')) { current = { ...current, version: 2, status: 'APPROVED' }; return reply(current); }
    return new Response(new Blob(['TEST-ONLY-BYTES']));
  }); vi.stubGlobal('fetch', fetch); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ })); fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  const preview = await screen.findByRole('img', { name: /漫画分段 1/ });
  const acknowledge = screen.getByLabelText('已核对图片、阅读顺序、所有裁切与分段警告，并批准此布局版本') as HTMLInputElement;
  expect(acknowledge.disabled).toBe(true); fireEvent.load(preview); expect(acknowledge.disabled).toBe(false); fireEvent.click(acknowledge);
  const approve = screen.getByRole('button', { name: '批准当前漫画布局' }); fireEvent.click(approve); fireEvent.click(approve);
  await screen.findByText(/此布局版本已显式批准/);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/approve'))).toHaveLength(1);
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/approve'))![1].body))).toEqual({ expected_version: 1, review_digest: report.review_digest, acknowledge_warnings: true });
  fireEvent.click(await screen.findByRole('button', { name: '预检并渲染当前布局' })); fireEvent.load(await screen.findByRole('img', { name: /已批准布局/ }));
  fireEvent.click(screen.getByRole('button', { name: '下载已批准漫画分段' })); await waitFor(() => expect(anchorClick).toHaveBeenCalledTimes(1));
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/export?expected_version=2'))).toBe(true); anchorClick.mockRestore();
});
