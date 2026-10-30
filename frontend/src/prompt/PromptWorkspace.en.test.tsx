// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-EN] en 下 Prompt 工作台（列表/空态/无权/编辑器/历史/比较/变量）界面文案不显示中文。
 *  fixture 中的用户内容（标题、正文、变量值）是数据，不在检查范围内。 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it } from 'vitest';
import { setLocale } from '../i18n';
import { PromptWorkspace } from './PromptWorkspace';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

const raw = (name: string) => readFileSync(resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8');
const fixture = (name: string): unknown => JSON.parse(raw(name)) as unknown;
const USER = [...new Set(['library.json', 'detail.json', 'revision-1-body.json', 'revision-2-body.json']
  .flatMap(n => [...raw(n).matchAll(/"((?:[^"\\]|\\.)*[\u4e00-\u9fff](?:[^"\\]|\\.)*)"/g)].map(m => JSON.parse(`"${m[1]}"`) as string)))]
  .flatMap(s => [s, ...s.split('\n')]).filter(Boolean).sort((a, b) => b.length - a.length);
const HAN = /[\u4e00-\u9fff]+/g;
function chinese(root: HTMLElement): string[] {
  const out: string[] = [];
  const scrub = (s: string) => USER.reduce((acc, u) => acc.split(u).join(''), s);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.parentElement?.closest('textarea')) continue;
    const s = scrub(n.textContent || ''); if (s.match(HAN)) out.push(`text: ${s.trim()}`);
  }
  root.querySelectorAll('*').forEach(el => { for (const a of ['aria-label', 'title', 'placeholder']) { const v = el.getAttribute(a); if (v && scrub(v).match(HAN)) out.push(`${a}: ${v}`); } });
  return out;
}
function transport(library?: unknown): StudioGraphTransport {
  return { async json<T>(url: string, method = 'GET'): Promise<T> {
    if (method === 'GET') {
      if (url.endsWith('/prompts')) return (library ?? fixture('library.json')) as T;
      if (url.includes('/revisions/') && url.endsWith('/body')) return fixture(url.includes('revision-1') || url.includes('/1/') ? 'revision-1-body.json' : 'revision-2-body.json') as T;
      if (url.includes('/prompts/')) return fixture('detail.json') as T;
    }
    throw new Error(`unexpected ${method} ${url}`);
  } };
}
const view = (t: StudioGraphTransport, over: Record<string, unknown> = {}) =>
  render(<PromptWorkspace projectId="p1" actor="author-a" transport={t} mode="PROFESSIONAL" writable denied={false} {...over} />);
beforeEach(() => { localStorage.clear(); act(() => setLocale('en')); });
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });

it('denied project message is English', () => {
  const { container } = view(transport(), { denied: true });
  expect(container.textContent).not.toContain('当前会话无权访问此项目');
  expect(chinese(container)).toEqual([]);
});
it('library list and bounded-read warning are English', async () => {
  const library = { ...(fixture('library.json') as Record<string, unknown>), truncated: true, has_more: true, read_complete: false };
  const { container } = view(transport(library));
  await screen.findAllByRole('button', { name: /IMAGE/ });
  expect(chinese(container)).toEqual([]);
});
it('empty library is English', async () => {
  const { container } = view(transport(fixture('empty-library.json')));
  await waitFor(() => expect(container.querySelector('.prompt-workspace, section, [role="region"]')).toBeTruthy());
  await act(async () => {});
  expect(chinese(container)).toEqual([]);
});
it('opened family (editor, history, compare, variables, unsaved status) is English', async () => {
  const { container } = view(transport());
  fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
  const area = await waitFor(() => { const a = container.querySelector('textarea'); if (!a) throw new Error('no editor'); return a; });
  fireEvent.change(area, { target: { value: 'edited body' } });
  await act(async () => {});
  expect(chinese(container)).toEqual([]);
});
it('read-only (not writable) family view is English', async () => {
  const { container } = view(transport(), { writable: false });
  fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
  await waitFor(() => { if (!container.querySelector('textarea')) throw new Error('no editor'); });
  await act(async () => {});
  expect(chinese(container)).toEqual([]);
});
