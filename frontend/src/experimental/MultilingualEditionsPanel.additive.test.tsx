// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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

it('locates the exact duplicate Unicode segment, shows rule versions, then saves through the original owner', async () => {
  const row = makeEdition('REVIEW');
  row.rules = [{ id: 'locked', version: 4, source_term: '甲', preferred: 'Jia', source_aliases: [], target_aliases: ['Chia'], forbidden: [], strategy: 'transliteration', category: 'character', match: 'word', note: '', status: 'APPROVED', locked: true }];
  row.term_revision = 7;
  row.segments!.push({ ...row.segments![0], id: 'duplicate-second', path: [1], target_text: 'Chia🙂é مرحبا Chia', issues: [{ code: 'LOCKED_TERM_VARIANT', rule_id: 'locked', rule_version: 4, term: '甲', expected: 'Jia', found: 'Chia' }] });
  const fetch = backend(row, (url, init) => init.method === 'PUT' && url.endsWith('/duplicate-second') ? reply({ ...row, version: 2, segments: row.segments!.map(s => s.id === 'duplicate-second' ? { ...s, target_text: JSON.parse(String(init.body)).text, issues: [], status: 'DRAFT' } : s) }) : undefined);
  vi.stubGlobal('fetch', fetch); render(<MultilingualEditionsPanel client={client()} />); await select();
  const calls = fetch.mock.calls.length;
  fireEvent.click(screen.getByRole('button', { name: '定位第 2 段术语问题' }));
  const input = screen.getByLabelText('第 2 段译文') as HTMLTextAreaElement;
  expect(document.activeElement).toBe(input); expect(input.value).toBe('Chia🙂é مرحبا Chia');
  expect(fetch.mock.calls.length).toBe(calls);
  expect(screen.getByText(/规则 locked · v4 · APPROVED · 已锁定/)).toBeTruthy();
  fireEvent.change(input, { target: { value: 'Jia🙂é مرحبا Jia' } });
  expect((screen.getByRole('button', { name: '定位第 2 段术语问题' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存本段草稿' }));
  await screen.findByText('译文草稿已保存，原稿未修改。');
  expect(screen.queryByRole('button', { name: '定位第 2 段术语问题' })).toBeNull();
  expect(JSON.parse(String(fetch.mock.calls.find(([url, init]) => url.endsWith('/duplicate-second') && init.method === 'PUT')![1].body))).toEqual({ expected_version: 1, text: 'Jia🙂é مرحبا Jia', note: '' });
  expect(fetch.mock.calls.some(([url]) => /translations|translation-preview|\/rules\//.test(url))).toBe(false);
});

it('never substitutes a changed rule version for issue evidence', async () => {
  const row = makeEdition('REVIEW');
  row.segments![0].issues = [{ code: 'TERM_REQUIRED', rule_id: 'rule', rule_version: 99, expected: 'old' }];
  row.rules = [{ id: 'rule', version: 1, source_term: '甲', preferred: 'new', source_aliases: [], target_aliases: [], forbidden: [], strategy: 'meaning', category: 'term', match: 'word', note: '', status: 'APPROVED' }];
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  expect(screen.getByText(/规则 rule 的精确版本不可用/)).toBeTruthy();
});

it('withholds issue navigation and text when content is withheld independently of stale', async () => {
  const row = makeEdition('REVIEW'); row.content_withheld = true;
  row.segments![0].issues = [{ code: 'TERM_REQUIRED', expected: 'private' }];
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  expect(screen.queryByLabelText('已保存术语问题导航')).toBeNull();
  expect(screen.queryByLabelText('第 1 段译文')).toBeNull();
});
it('does not select a matching rule version from duplicate IDs', async () => {
  const row = makeEdition('REVIEW');
  row.segments![0].issues = [{ code: 'TERM_REQUIRED', rule_id: 'duplicate', rule_version: 1 }];
  const rule = { id: 'duplicate', version: 1, source_term: '甲', preferred: 'Jia', source_aliases: [], target_aliases: [], forbidden: [], strategy: 'meaning' as const, category: 'term' as const, match: 'word' as const, note: '', status: 'APPROVED' as const };
  row.rules = [rule, { ...rule, version: 2 }];
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  expect(screen.getByText(/规则 duplicate 的精确版本不可用/)).toBeTruthy();
});
it('labels legitimate unversioned conflict rules as same-edition snapshot evidence', async () => {
  const row = makeEdition('REVIEW');
  row.segments![0].issues = [{ code: 'RULE_CONFLICT', rule_id: 'first', other_rule_id: 'second' }];
  row.rules = ['first', 'second'].map((id, index) => ({ id, version: index + 1, source_term: '甲', preferred: id, source_aliases: [], target_aliases: [], forbidden: [], strategy: 'meaning', category: 'term', match: 'word', note: '', status: 'APPROVED' }));
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  expect(screen.getAllByText(/冲突依据来自同一已保存语言版本/)).toHaveLength(2);
  expect(screen.getByText(/规则 first · v1/)).toBeTruthy(); expect(screen.getByText(/规则 second · v2/)).toBeTruthy();
});
it('keeps the composing original textarea mounted before its first change event', async () => {
  const row = makeEdition('REVIEW'); row.segments!.push({ ...row.segments![0], id: 'other', path: [1], issues: [{ code: 'TERM_REQUIRED' }] });
  vi.stubGlobal('fetch', backend(row)); render(<MultilingualEditionsPanel client={client()} />); await select();
  const input = screen.getByLabelText('第 1 段译文'); fireEvent.compositionStart(input);
  const navigate = screen.getByRole('button', { name: '定位第 2 段术语问题' });
  expect((navigate as HTMLButtonElement).disabled).toBe(true); fireEvent.click(navigate);
  expect(screen.getByLabelText('第 1 段译文')).toBe(input);
  expect((input as HTMLTextAreaElement).disabled).toBe(false);
  fireEvent.compositionEnd(input); fireEvent.click(navigate);
  expect(screen.getByLabelText('第 2 段译文')).toBeTruthy();
});
