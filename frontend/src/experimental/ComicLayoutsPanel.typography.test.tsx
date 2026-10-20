// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { comicPreset, type ComicDocument } from './comicLayoutsClient';

const source = { id: 'screenplay', title: 'Synthetic typography', edit_version: 4, shot_status: 'APPROVED', checks: [], shots: [{ id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5 }] };
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const catalog = { screenplays: [source], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400, segment_height: 1200 } }, renderer: { available: true }, font: { available: true } };
const reply = (value: unknown) => new Response(JSON.stringify(value));
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted' });
const align = (panel = 1, bubble = 1) => screen.getByLabelText(`格框 ${panel} 气泡 ${bubble} 文字对齐`) as HTMLSelectElement;
const spacing = () => screen.getByLabelText('格框 1 气泡 1 行距 (%)') as HTMLInputElement;
function harness(intercept?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  const document = comicPreset(source, 'PAGE', preset);
  document.panels[0].height = 400;
  document.panels[0].bubbles = [1, 2].map(i => ({ id: `bubble-${i}`, kind: 'DIALOGUE', text: '天地\n日', character_id: null, font_size: 32, x: i * 100, y: 50, width: 180, height: 160 }));
  document.panels.push({ ...document.panels[0], id: 'other-panel', order: 2, y: 500,
    bubbles: [{ ...document.panels[0].bubbles[0], id: 'other-bubble', y: 550 }] });
  let row = { id: 'layout', version: 1, status: 'DRAFT', stale: false, document, history_versions: [] as number[] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    const custom = intercept?.(url, init); if (custom) return custom;
    if (init.method === 'PUT') {
      const { expected_version, ...saved } = JSON.parse(String(init.body));
      row = { ...row, version: expected_version + 1, document: saved as ComicDocument };
      return reply(row);
    }
    if (url.endsWith('/preflight')) return reply({ version: row.version, status: row.status, review_digest: 'typography-digest', can_render: true, segments: [{ index: 0 }], issues: [] });
    if (url.includes('/segments/')) return new Response(new Blob(['SYNTHETIC PNG'], { type: 'image/png' }));
    return reply(url.endsWith('/catalog') ? catalog : { items: [row] });
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, document };
}
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:typography'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('displays legacy defaults without adding them to an unchanged save', async () => {
  const { fetch } = harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  expect(align().value).toBe('LEFT'); expect(spacing().value).toBe('150');
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.panels[0].bubbles[0]).not.toHaveProperty('text_align');
  expect(saved.panels[0].bubbles[0]).not.toHaveProperty('line_height_percent');
});

it('edits one bubble, undoes and redoes, then saves and reopens the exact authored fields', async () => {
  const { fetch, document } = harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.change(align(), { target: { value: 'CENTER' } });
  fireEvent.change(spacing(), { target: { value: '200' } });
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(spacing().value).toBe('150');
  fireEvent.click(screen.getByRole('button', { name: '撤销本地排版' })); expect(align().value).toBe('LEFT');
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' }));
  fireEvent.click(screen.getByRole('button', { name: '重做本地排版' }));
  expect(align().value).toBe('CENTER'); expect(spacing().value).toBe('200');
  expect(align(1, 2).value).toBe('LEFT'); expect(align(2, 1).value).toBe('LEFT');
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved).toMatchObject({ expected_version: 1 });
  expect(saved.panels[0].bubbles[0]).toEqual({ ...document.panels[0].bubbles[0], text_align: 'CENTER', line_height_percent: 200 });
  expect(saved.panels[0].bubbles[1]).toEqual(document.panels[0].bubbles[1]);
  expect(saved.panels[1]).toEqual(document.panels[1]);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  expect(align().value).toBe('CENTER'); expect(spacing().value).toBe('200');
  expect(fetch.mock.calls.some(([url]) => /generate|execute|approve|export/.test(url))).toBe(false);
});

it('rejects empty fractional and out-of-range spacing without changing the draft', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  for (const value of ['', '99', '251', '150.5']) {
    fireEvent.change(spacing(), { target: { value } }); expect(spacing().value).toBe('150');
  }
  expect((screen.getByRole('button', { name: '撤销本地排版' }) as HTMLButtonElement).disabled).toBe(true);
});

it('retires preview pixels and review consent after a typography edit', async () => {
  harness(); render(<ComicLayoutsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /打开布局/ }));
  fireEvent.click(screen.getByRole('button', { name: '预检并渲染当前布局' }));
  fireEvent.load(await screen.findByRole('img', { name: /漫画分段/ }));
  fireEvent.click(screen.getByRole('checkbox', { name: /已核对图片、阅读顺序/ }));
  expect((screen.getByRole('button', { name: '批准当前漫画布局' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(align(), { target: { value: 'RIGHT' } });
  expect(screen.queryByRole('img', { name: /漫画分段/ })).toBeNull();
  expect(screen.queryByRole('button', { name: '批准当前漫画布局' })).toBeNull();
  expect(vi.mocked(URL.revokeObjectURL).mock.calls.map(call => call[0])).toEqual(['blob:typography']);
});
