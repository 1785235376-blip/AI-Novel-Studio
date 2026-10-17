// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { comicPreset, type ComicDocument } from './comicLayoutsClient';
const source = { id: 'screenplay', title: 'Synthetic framing test', edit_version: 4, shot_status: 'APPROVED', checks: [], shots: [{ id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const catalog = { screenplays: [source], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400, segment_height: 1200 } }, renderer: { available: true }, font: { available: true } };
const reply = (value: unknown) => new Response(JSON.stringify(value));
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted' });
const field = (axis: '水平' | '垂直') => screen.getByLabelText(`格框 1 裁切${axis}位置 (%)`) as HTMLInputElement;
function harness(fit: 'CONTAIN' | 'COVER' = 'COVER', intercept?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  const document = comicPreset(source, 'PAGE', preset); document.panels[0].fit = fit;
  let row = { id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] as number[] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const custom = intercept?.(url, init); if (custom) return custom;
    if (init.method === 'PUT') {
      const { expected_version, ...saved } = JSON.parse(String(init.body));
      row = { ...row, version: expected_version + 1, document: saved as ComicDocument };
      return reply(row);
    }
    if (url.endsWith('/preflight')) return reply({ version: row.version, status: row.status, review_digest: 'framing-digest', can_render: true, segments: [{ index: 0 }], issues: [{ code: 'COMIC_POSITIONED_CROP', target: 'panel-1', severity: 'WARNING' }] });
    if (url.includes('/segments/')) return new Response(new Blob(['SYNTHETIC PNG'], { type: 'image/png' }));
    return reply(url.endsWith('/catalog') ? catalog : { items: [row] });
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:synthetic-framing'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('shows legacy center without injecting fields when opening and saving a legacy document', async () => {
  const fetch = harness('CONTAIN'); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  expect(field('水平').value).toBe('50'); expect(field('垂直').value).toBe('50');
  expect(field('水平').disabled).toBe(true); expect(field('垂直').disabled).toBe(true);
  expect(screen.getByText(/不识别画面主体/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.expected_version).toBe(1);
  expect(saved.panels[0]).not.toHaveProperty('cover_x_percent'); expect(saved.panels[0]).not.toHaveProperty('cover_y_percent');
});

it('uses original undo redo and CAS save while retaining inactive values through fit toggles', async () => {
  const fetch = harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(field('水平'), { target: { value: '0' } });
  fireEvent.change(field('垂直'), { target: { value: '100' } });
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(field('垂直').value).toBe('50');
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' })); expect(field('垂直').value).toBe('100');
  fireEvent.change(screen.getByLabelText('格框 1 图片缩放'), { target: { value: 'CONTAIN' } });
  expect(field('水平').disabled).toBe(true); expect(field('水平').value).toBe('0'); expect(field('垂直').value).toBe('100');
  fireEvent.change(screen.getByLabelText('格框 1 图片缩放'), { target: { value: 'COVER' } });
  expect(field('水平').disabled).toBe(false); expect(field('水平').value).toBe('0');
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved).toMatchObject({ expected_version: 1, panels: [{ fit: 'COVER', cover_x_percent: 0, cover_y_percent: 100, shot_id: 'shot', asset_id: null, expected_asset_version: null }] });
  expect(fetch.mock.calls.some(([url]) => /generate|execute|approve|export/.test(url))).toBe(false);
});

it('rejects empty fractional and out-of-range input without emitting a document edit', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  for (const value of ['', '-1', '101', '1.5']) {
    fireEvent.change(field('水平'), { target: { value } });
    expect(field('水平').value).toBe('50');
  }
  expect((screen.getByRole('button', { name: '撤销本地排版' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(field('水平'), { target: { value: '25' } }); expect(field('水平').value).toBe('25');
});

it('revokes displayed pixels warning consent and approval on framing edits', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  fireEvent.load(await screen.findByRole('img', { name: /漫画分段/ }));
  expect(screen.getByText(/按指定位置填满会裁切图片/)).toBeTruthy();
  const consent = screen.getByRole('checkbox', { name: /已核对图片、阅读顺序/ }); fireEvent.click(consent);
  expect((screen.getByRole('button', { name: '批准当前漫画布局' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(field('水平'), { target: { value: '100' } });
  expect(screen.queryByRole('img', { name: /漫画分段/ })).toBeNull();
  expect(screen.queryByRole('button', { name: '批准当前漫画布局' })).toBeNull();
  expect(vi.mocked(URL.revokeObjectURL).mock.calls.map(call => call[0])).toEqual(['blob:synthetic-framing']);
  expect((screen.getByRole('button', { name: '预检并渲染当前布局' }) as HTMLButtonElement).disabled).toBe(true);
});

it('drops pending old pixels on client replacement and starts new controls at the new document', async () => {
  let resolve: ((response: Response) => void) | undefined;
  harness('COVER', url => url.includes('/segments/') ? new Promise<Response>(done => { resolve = done; }) : undefined);
  const view = render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  await waitFor(() => expect(resolve).toBeTruthy());
  view.rerender(<ComicLayoutsPanel client={client('other')} />);
  resolve!(new Response(new Blob(['OLD SYNTHETIC PNG'])));
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  expect(field('水平').value).toBe('50');
  expect(screen.queryByRole('img', { name: /漫画分段/ })).toBeNull();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it('original vertical arrangement preserves framing values through apply and undo', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(field('水平'), { target: { value: '25' } });
  fireEvent.change(field('垂直'), { target: { value: '75' } });
  fireEvent.change(screen.getByLabelText('格框 1 横坐标'), { target: { value: '48' } });
  fireEvent.click(screen.getByRole('button', { name: '预览纵向排列' }));
  fireEvent.click(screen.getByRole('button', { name: '应用纵向排列到草稿' }));
  expect(field('水平').value).toBe('25'); expect(field('垂直').value).toBe('75');
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' }));
  expect(field('水平').value).toBe('25'); expect(field('垂直').value).toBe('75');
  expect((screen.getByLabelText('格框 1 横坐标') as HTMLInputElement).value).toBe('48');
});
