// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import type { ComicRecord } from './comicLayoutsClient';
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const catalog = { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } };
const reply = (value: unknown) => new Response(JSON.stringify(value));
const button = (name: string) => screen.getByRole('button', { name });
const number = (name: string) => Number((screen.getByLabelText(name) as HTMLInputElement).value);
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:original-preview'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('blank two-panel text page geometry uses original undo, explicit save, reopen and authoritative preview', async () => {
  let row: ComicRecord | undefined;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/records') && init.method === 'POST') { row = { id: 'saved', version: 1, status: 'DRAFT', stale: false, document: JSON.parse(String(init.body)) }; return reply(row); }
    if (url.endsWith('/preflight')) return reply({ version: 1, status: 'DRAFT', can_render: true, review_digest: 'digest', segments: [{ index: 0, ...preset }], issues: [] });
    if (url.includes('/segments/')) return new Response(new Blob(['SYNTHETIC original renderer response']));
    return reply({ items: row ? [row] : [] });
  }); vi.stubGlobal('fetch', fetch);
  render(<ComicLayoutsPanel client={experimentalClient('novel', { sessionToken: 'trusted' })} />);
  await waitFor(() => expect((button('新建空白漫画页') as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button('新建空白漫画页'));
  fireEvent.click(button('添加格框（手工定位）')); fireEvent.click(button('添加格框（手工定位）'));
  fireEvent.click(button('添加格框 1 气泡'));
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: '你好，几何 👩🏽‍🚀' } });
  fireEvent.change(screen.getByLabelText('格框 2 纵坐标'), { target: { value: '384' } });
  fireEvent.keyDown(button('移动示意格框 2'), { key: 'ArrowDown', shiftKey: true });
  expect(number('格框 2 纵坐标')).toBe(394);
  fireEvent.keyDown(button('调整示意格框 1大小'), { key: 'ArrowDown', shiftKey: true });
  expect(number('格框 1 高度')).toBe(330);
  fireEvent.keyDown(button('移动示意格框 1 气泡 1'), { key: 'ArrowDown' });
  expect(number('格框 1 气泡 1 纵坐标')).toBe(41);
  fireEvent.click(button('撤销本地排版')); expect(number('格框 1 气泡 1 纵坐标')).toBe(40);
  fireEvent.click(button('重做本地排版')); expect(number('格框 1 气泡 1 纵坐标')).toBe(41);
  expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(0);
  fireEvent.click(button('保存漫画布局草稿'));
  await waitFor(() => expect((screen.getByRole('button', { name: /打开布局/ }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: /打开布局/ }));
  expect(number('格框 2 纵坐标')).toBe(394); expect(number('格框 1 高度')).toBe(330);
  expect((screen.getByLabelText('格框 1 气泡 1 文字') as HTMLInputElement).value).toBe('你好，几何 👩🏽‍🚀');
  expect(row?.document?.panels.every(p => p.artwork_mode === 'BLANK')).toBe(true);
  fireEvent.click(button('预检并渲染当前布局'));
  await screen.findByRole('img', { name: /漫画分段 1/ });
  fireEvent.keyDown(button('移动示意格框 2'), { key: 'ArrowDown' });
  expect(screen.queryByRole('img', { name: /漫画分段 1/ })).toBeNull();
  expect((button('预检并渲染当前布局') as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.some(([url]) => /approve|generate|export/.test(url))).toBe(false);
});

it('group translation is one original undo entry and saves both panels and bubbles through the existing owner', async () => {
  let row: ComicRecord | undefined;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/records') && init.method === 'POST') { row = { id: 'group-page', version: 1, status: 'DRAFT', stale: false, document: JSON.parse(String(init.body)) }; return reply(row); }
    return reply({ items: row ? [row] : [] });
  }); vi.stubGlobal('fetch', fetch);
  const ownerDirty = vi.fn(); render(<ComicLayoutsPanel client={experimentalClient('novel', { sessionToken: 'trusted' })} onDirtyChange={ownerDirty} />);
  await waitFor(() => expect((button('新建空白漫画页') as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button('新建空白漫画页'));
  fireEvent.click(button('添加格框（手工定位）')); fireEvent.click(button('添加格框（手工定位）'));
  fireEvent.click(button('添加格框 1 气泡'));
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: '保留对白 👩🏽‍🚀' } });
  fireEvent.change(screen.getByLabelText('格框 2 纵坐标'), { target: { value: '384' } });
  fireEvent.click(screen.getByLabelText('整体移动格框 1')); fireEvent.click(screen.getByLabelText('整体移动格框 2'));
  fireEvent.click(button('所选格框下移'));
  expect(number('格框 1 纵坐标')).toBe(34); expect(number('格框 2 纵坐标')).toBe(394); expect(number('格框 1 气泡 1 纵坐标')).toBe(50);
  expect(ownerDirty).toHaveBeenCalledWith(true); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(button('撤销本地排版'));
  expect(number('格框 1 纵坐标')).toBe(24); expect(number('格框 2 纵坐标')).toBe(384); expect(number('格框 1 气泡 1 纵坐标')).toBe(40);
  fireEvent.click(button('重做本地排版')); fireEvent.click(button('保存漫画布局草稿'));
  await waitFor(() => expect(row?.document?.panels[0].y).toBe(34));
  expect(row?.document?.panels.map(panel => panel.y)).toEqual([34, 394]);
  expect(row?.document?.panels[0].bubbles[0]).toMatchObject({ y: 50, text: '保留对白 👩🏽‍🚀' });
  expect(row?.status).toBe('DRAFT'); expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => /approve|generate|execute|export/.test(url))).toBe(false);
});
