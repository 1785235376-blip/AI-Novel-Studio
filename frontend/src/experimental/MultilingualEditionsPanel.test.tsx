// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { MultilingualEditionsPanel } from './MultilingualEditionsPanel';
import type { LanguageEdition } from './multilingualEditionsClient';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'session', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const catalog = { chapters: [{ id: 'n:1', title: '甲章节', version: 2 }], branch_sources_available: true, translation: { available: false, reason: 'AUTHORIZED_TRANSLATION_ADAPTER_UNAVAILABLE', model_called: false } };
const makeEdition = (status: 'DRAFT' | 'REVIEW' | 'ACCEPTED' = 'DRAFT'): LanguageEdition => ({ id: 'edition', title: 'Arabic edition', version: 1, status, source_language: 'zh-Hant', target_language: 'ar', direction: 'rtl', font: 'serif', stale: false, content_withheld: false, rules: [], term_revision: 0, style_note: '', segments: [{ id: 'segment', chapter_id: 'n:1', source_version: 2, path: [0], from_pos: 1, to_pos: 8, source_text: '甲🙂é“原文”', target_text: status === 'DRAFT' ? '' : 'مرحبا🙂é', note: '', status, issues: [] }], checks: { missing: status === 'DRAFT' ? ['segment'] : [], pending: status !== 'ACCEPTED' ? ['segment'] : [], terminology: [], aligned: true, can_export: status === 'ACCEPTED' } });
function backend(row = makeEdition(), handler?: (url: string, init: RequestInit, row: LanguageEdition) => Response | Promise<Response> | undefined) {
  return vi.fn(async (url: string, init: RequestInit) => {
    const override = await handler?.(url, init, row); if (override) return override;
    if (url.endsWith('/catalog')) return reply(catalog);
    if (init.method === 'GET') return reply(url.endsWith('/edition') ? row : { items: [row], truncated: false });
    const body = JSON.parse(String(init.body));
    if (init.method === 'PUT') { row.version++; Object.assign(row.segments![0], { target_text: body.text, note: body.note, status: 'DRAFT' }); return reply(row); }
    if (url.endsWith('/preview')) return reply({ preview_digest: 'a'.repeat(64), can_accept: true, issues: [] });
    if (url.endsWith('/review')) { row.version++; row.segments![0].status = body.action === 'accept' ? 'ACCEPTED' : 'REVIEW'; return reply(row); }
    return reply(row);
  });
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: /Arabic edition · ar/ })); }

it('manual bilingual save→review→exact acceptance with RTL and no model calls', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />); await select();
  const input = screen.getByLabelText('第 1 段译文');
  expect(input.getAttribute('lang')).toBe('ar'); expect(input.getAttribute('dir')).toBe('rtl');
  fireEvent.compositionStart(input); fireEvent.change(input, { target: { value: 'مرحبا🙂é' } }); fireEvent.compositionEnd(input);
  expect((screen.getByRole('button', { name: '刷新当前语言版本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存本段草稿' })); await screen.findByText('译文草稿已保存，原稿未修改。');
  fireEvent.click(screen.getByRole('button', { name: '提交本段审核' })); await screen.findByText('本段已进入待审。');
  fireEvent.click(screen.getByRole('button', { name: '预检本段术语与版本' }));
  const accept = await screen.findByRole('button', { name: '确认仅接受本段译文' }); expect((accept as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已人工核对本段译文、术语与源版本')); fireEvent.click(accept);
  await screen.findByText('仅本段译文已接受。原稿仍保持原样。');
  const request = fetch.mock.calls.find(([url, init]) => url.endsWith('/review') && JSON.parse(String(init.body)).action === 'accept')!;
  expect(JSON.parse(String(request[1].body))).toEqual({ expected_version: 3, action: 'accept', preview_digest: 'a'.repeat(64) });
  expect(new Headers(request[1].headers).get('X-Branch-Id')).toBe('branch');
  expect(fetch.mock.calls.some(([url]) => /generate|chapters\//.test(url))).toBe(false);
});

it('preserves unsaved Unicode draft on conflict and explicitly restores saved value', async () => {
  const fetch = backend(makeEdition(), (_url, init) => init.method === 'PUT' ? reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) : undefined);
  vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('第 1 段译文'), { target: { value: '不能丢失🙂é' } });
  fireEvent.click(screen.getByRole('button', { name: '保存本段草稿' })); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect((screen.getByLabelText('第 1 段译文') as HTMLTextAreaElement).value).toBe('不能丢失🙂é');
  fireEvent.click(screen.getByRole('button', { name: '还原未保存输入' }));
  expect((screen.getByLabelText('第 1 段译文') as HTMLTextAreaElement).value).toBe('');
});

it('invalidates acceptance receipt immediately when the draft changes', async () => {
  const fetch = backend(makeEdition('REVIEW')); vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预检本段术语与版本' }));
  fireEvent.click(await screen.findByLabelText('已人工核对本段译文、术语与源版本'));
  fireEvent.change(screen.getByLabelText('第 1 段译文'), { target: { value: '新草稿' } });
  expect(screen.queryByRole('button', { name: '确认仅接受本段译文' })).toBeNull();
});

it('shows stale metadata without plaintext and requires alignment preview before recovery', async () => {
  const stale = { ...makeEdition(), stale: true, content_withheld: true, segments: undefined, rules: undefined, title: undefined };
  const fetch = backend(stale, (url, init) => url.endsWith('/refresh-preview') ? reply({ preview_digest: 'b'.repeat(64), retained_exact: 1, new_or_changed: 1, archived_old: 1, requires_review: 2 }) : url.endsWith('/refresh') ? reply(makeEdition()) : undefined);
  vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: /待更新语言版本 · ar/ }));
  expect(screen.queryByLabelText('第 1 段译文')).toBeNull(); expect(screen.queryByText('甲🙂é“原文”')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '预览重新对齐' }));
  fireEvent.click(await screen.findByRole('button', { name: '确认重新对齐并重新审核' }));
  await screen.findByLabelText('第 1 段译文');
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/refresh'))![1].body)).preview_digest).toBe('b'.repeat(64));
});

it('ignores late reads and mutations on scope navigation, including StrictMode', async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = backend(makeEdition(), (url, init) => init.method === 'PUT' ? new Promise<Response>(resolve => { finish = resolve; }) : url.includes('/other/') ? reply(url.endsWith('/catalog') ? catalog : { items: [], truncated: false }) : undefined);
  vi.stubGlobal('fetch', fetch); const view = render(<StrictMode><MultilingualEditionsPanel client={client()} /></StrictMode>); await select();
  fireEvent.change(screen.getByLabelText('第 1 段译文'), { target: { value: 'old private target' } });
  fireEvent.click(screen.getByRole('button', { name: '保存本段草稿' }));
  view.rerender(<StrictMode><MultilingualEditionsPanel client={client('other')} /></StrictMode>);
  finish(reply(makeEdition('ACCEPTED')));
  await waitFor(() => expect(screen.queryByLabelText('第 1 段译文')).toBeNull());
  expect(screen.queryByDisplayValue('old private target')).toBeNull();
});

it('displays approved rule conflicts and retains independent explicit rule approval', async () => {
  const row = makeEdition('REVIEW'); row.segments![0].issues = [{ code: 'TERM_REQUIRED', term: '甲', expected: 'Jia' }];
  row.rules = [{ id: 'rule', version: 1, source_term: '甲', preferred: 'Jia', source_aliases: ['阿甲'], target_aliases: ['Chia'], forbidden: ['BadJia'], strategy: 'transliteration', category: 'character', match: 'substring', note: '', status: 'DRAFT' }];
  const fetch = backend(row, url => url.endsWith('/preview') ? reply({ preview_digest: 'a'.repeat(64), can_accept: false, issues: [{ code: 'TERM_REQUIRED', term: '甲', expected: 'Jia' }] }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预检本段术语与版本' }));
  const check = await screen.findByLabelText('已人工核对本段译文、术语与源版本'); expect((check as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByRole('button', { name: '批准此术语规则' })).toBeTruthy();
  expect(screen.getAllByText('缺少批准译法：甲 → Jia').length).toBeGreaterThan(0);
});

it('creates UTF-8 Blob only after export preview and confirmation, revoking it on source view changes', async () => {
  const createObjectURL = vi.fn((_blob: Blob) => 'blob:edition'), revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  const row = makeEdition('ACCEPTED');
  const fetch = backend(row, url => url.endsWith('/export-preview') ? reply({ preview_digest: 'c'.repeat(64), can_export: true, checks: row.checks, format: 'html', encoding: 'UTF-8' }) : url.endsWith('/export') ? reply({ filename: 'edition-ar.html', mime: 'text/html; charset=utf-8', content: '<html lang="ar" dir="rtl">مرحبا🙂</html>', encoding: 'UTF-8', published: false }) : undefined);
  vi.stubGlobal('fetch', fetch); const view = render(<MultilingualEditionsPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('语言版本导出格式'), { target: { value: 'html' } });
  fireEvent.click(screen.getByRole('button', { name: '预检语言版本导出' }));
  const generate = await screen.findByRole('button', { name: '生成已审核语言文件' }); expect((generate as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对全部译文，确认生成本地下载')); fireEvent.click(generate);
  const link = await screen.findByRole('link', { name: '下载 edition-ar.html' }); expect(link.getAttribute('href')).toBe('blob:edition');
  expect(createObjectURL.mock.calls[0][0]).toBeInstanceOf(Blob); view.unmount(); expect(revokeObjectURL).toHaveBeenCalledWith('blob:edition');
});

it('empty/loading/error states are actionable without starting translation', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? { detail: { code: 'FORBIDDEN' } } : { items: [], truncated: false }, url.endsWith('/catalog') ? 403 : 200));
  vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />);
  expect(screen.getAllByText('正在读取…').length).toBeGreaterThan(0);
  await screen.findByText(/FORBIDDEN/); await screen.findByText('暂无记录');
  expect((screen.getByRole('button', { name: '创建语言版本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '刷新原稿章节' }));
  await waitFor(() => expect(fetch.mock.calls.length).toBe(3));
});

it('makes archived changed-paragraph drafts recoverable only as read-only manual candidates', async () => {
  const row = makeEdition(); row.archived_segments = [{ chapter_id: 'n:1', source_version: 1, path: [0], target_text: 'Old Arabic candidate 🙂', note: 'needs new review' }];
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  const old = screen.getByLabelText('归档译文 1') as HTMLTextAreaElement;
  expect(old.readOnly).toBe(true); expect(old.value).toBe('Old Arabic candidate 🙂');
  expect((screen.getByLabelText('第 1 段译文') as HTMLTextAreaElement).value).toBe('');
});

it('warns on browser navigation only while unsaved text is present and cleans up the listener', async () => {
  vi.stubGlobal('fetch', backend()); const view = render(<MultilingualEditionsPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('第 1 段译文'), { target: { value: 'Draft retained' } });
  const dirty = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(dirty); expect(dirty.defaultPrevented).toBe(true);
  view.unmount(); const clean = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
});
