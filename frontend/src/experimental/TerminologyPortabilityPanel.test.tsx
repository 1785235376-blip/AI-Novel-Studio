// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TerminologyPortabilityPanel } from './TerminologyPortabilityPanel';
import { parseGlossary, readGlossaryFile, MAX_GLOSSARY_BYTES, glossaryAdmissionToken, startGlossaryAdmission, clearGlossaryAdmission, type GlossaryPreview } from './terminologyPortability';
import { experimentalClient } from './api';
import type { LanguageEdition, TermInput } from './multilingualEditionsClient';
const edition: LanguageEdition = { id: 'edition', version: 4, source_language: 'zh-Hant', target_language: 'ar', direction: 'rtl', status: 'DRAFT', stale: false, content_withheld: false };
const rule: TermInput = { source_term: '甲🙂é', source_aliases: [], preferred: 'تشينغ', target_aliases: [], forbidden: [], strategy: 'meaning', category: 'term', match: 'substring', note: '<b>literal</b>' };
const document = JSON.stringify({ schema: 'language-terminology-v1', source_language: 'zh-Hant', target_language: 'ar', rules: [rule] });
const preview: GlossaryPreview = { preview_digest: 'a'.repeat(64), edition_version: 4, remaining_capacity: 99, draft_only: true, entries: [{ index: 0, rule, duplicates: [], conflicts: [], eligible: true }] };
const response = (value: unknown) => new Response(JSON.stringify(value));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const file = (text = document, size?: number) => ({ name: 'terms.json', size: size ?? new TextEncoder().encode(text).length, arrayBuffer: async () => new TextEncoder().encode(text).buffer }) as File;
function setup(fetch: any) {
  vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('n1', { sessionToken: 'host' });
  const perform = vi.fn(async (fn: () => Promise<LanguageEdition>) => { try { await fn(); } catch { /* Parent exposes failed action. */ } });
  return { client, edition, blocked: false, perform };
}
async function chooseAndPreview() {
  fireEvent.change(screen.getByLabelText('选择本地术语 JSON 文件'), { target: { files: [file()] } });
  await screen.findByText(/已在本地读取/);
  fireEvent.click(screen.getByRole('button', { name: '检查术语导入预览' }));
  await screen.findByRole('region', { name: '术语导入预览' });
}
it('locally reads first, previews literal rows, requires explicit selection and consent, sends exact CAS once', async () => {
  const fetch = vi.fn(async (url: string) => response(url.endsWith('/preview') ? preview : { ...edition, version: 5, rules: [{ ...rule, id: 'new', version: 1, status: 'DRAFT' }] }));
  const props = setup(fetch); render(<TerminologyPortabilityPanel {...props} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('选择本地术语 JSON 文件'), { target: { files: [file()] } });
  await screen.findByText(/已在本地读取/); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '检查术语导入预览' }));
  await screen.findByText(/备注：<b>literal<\/b>/);
  const save = screen.getByRole('button', { name: '确认导入所选术语草稿' }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  fireEvent.click(screen.getByRole('checkbox', { name: /第 1 行/ })); expect(save.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对所选行，仅新增为待批准术语草稿')); fireEvent.click(save); fireEvent.click(save);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(String((fetch.mock.calls as unknown as [string, RequestInit][])[1][1].body))).toEqual({ expected_version: 4, document, preview_digest: preview.preview_digest, selected_indices: [0] });
  expect(props.perform).toHaveBeenCalledTimes(1);
});
it('shows duplicate and alias conflicts, blocks ineligible rows and exceeds no capacity', async () => {
  const result = { ...preview, remaining_capacity: 0, entries: [preview.entries[0], { ...preview.entries[0], index: 1, eligible: false, duplicates: [{ kind: 'existing', index: 2 }], conflicts: [{ kind: 'file', index: 0 }] }] };
  const fetch = vi.fn(async () => response(result)); const props = setup(fetch); render(<TerminologyPortabilityPanel {...props} />);
  await chooseAndPreview();
  expect((screen.getByRole('checkbox', { name: /第 2 行/ }) as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByText(/完全重复：当前术语第 3 行/)).toBeTruthy(); expect(screen.getByText(/源词或别名冲突：文件第 1 行/)).toBeTruthy();
  fireEvent.click(screen.getByRole('checkbox', { name: /第 1 行/ }));
  expect((screen.getByLabelText('已核对所选行，仅新增为待批准术语草稿') as HTMLInputElement).disabled).toBe(true);
  expect(fetch).toHaveBeenCalledTimes(1);
});
it('discards late private previews through blocked-to-unblocked', async () => {
  let finish: (value: Response) => void = () => {};
  const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })); const props = setup(fetch);
  const view = render(<TerminologyPortabilityPanel {...props} />);
  fireEvent.change(screen.getByLabelText('选择本地术语 JSON 文件'), { target: { files: [file()] } }); await screen.findByText(/已在本地读取/);
  fireEvent.click(screen.getByRole('button', { name: '检查术语导入预览' }));
  view.rerender(<TerminologyPortabilityPanel {...props} blocked />); view.rerender(<TerminologyPortabilityPanel {...props} />);
  finish(response(preview)); await waitFor(() => expect((screen.getByRole('button', { name: '检查术语导入预览' }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.queryByRole('region', { name: '术语导入预览' })).toBeNull();
  expect(props.perform).not.toHaveBeenCalled();
});
it('invalidates a preview after selection changes or a saved edition refresh', async () => {
  const fetch = vi.fn(async () => response(preview)); const props = setup(fetch); const view = render(<TerminologyPortabilityPanel {...props} />);
  await chooseAndPreview(); fireEvent.click(screen.getByRole('checkbox', { name: /第 1 行/ })); fireEvent.click(screen.getByLabelText('已核对所选行，仅新增为待批准术语草稿'));
  fireEvent.click(screen.getByRole('checkbox', { name: /第 1 行/ })); expect((screen.getByLabelText('已核对所选行，仅新增为待批准术语草稿') as HTMLInputElement).checked).toBe(false);
  view.rerender(<TerminologyPortabilityPanel {...props} edition={{ ...edition, version: 5 }} />);
  expect(screen.queryByRole('region', { name: '术语导入预览' })).toBeNull(); expect(props.perform).not.toHaveBeenCalled();
});
it('never automatically retries an unknown write, asks to reopen, and removes the old receipt', async () => {
  const fetch = vi.fn(async (url: string) => { if (url.endsWith('/preview')) return response(preview); if (url.endsWith('/edition')) return response({ ...edition, version: 5, rules: [{ ...rule, status: 'DRAFT' }] }); throw new Error('lost receipt'); });
  const props = setup(fetch); const view = render(<TerminologyPortabilityPanel {...props} />); await chooseAndPreview();
  fireEvent.click(screen.getByRole('checkbox', { name: /第 1 行/ })); fireEvent.click(screen.getByLabelText('已核对所选行，仅新增为待批准术语草稿')); fireEvent.click(screen.getByRole('button', { name: '确认导入所选术语草稿' }));
  await screen.findByText(/保存结果未确认/); expect(fetch).toHaveBeenCalledTimes(2); expect(screen.queryByRole('region', { name: '术语导入预览' })).toBeNull();
  expect((screen.getByRole('button', { name: '检查术语导入预览' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('选择本地术语 JSON 文件'), { target: { files: [file()] } });
  expect(fetch).toHaveBeenCalledTimes(2); expect(screen.queryByText(/已在本地读取/)).toBeNull();
  view.rerender(<TerminologyPortabilityPanel {...props} edition={{ ...edition, version: 5 }} />);
  expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(true);
  view.unmount(); render(<TerminologyPortabilityPanel {...props} />);
  expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '重新读取并核对术语保存结果' }));
  await waitFor(() => expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(false));
  expect(fetch).toHaveBeenCalledTimes(3);
});
it('exports only on demand and revokes the download when blocked or closed', async () => {
  const create = vi.fn(() => 'blob:local-download'), revoke = vi.fn();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
  const fetch = vi.fn(async () => response({ filename: 'terminology-v1.json', mime: 'application/json', content: document, rule_count: 1, published: false, draft_only: true }));
  const props = setup(fetch); const view = render(<TerminologyPortabilityPanel {...props} />); expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '生成可复用术语 JSON 下载' }));
  expect((await screen.findByRole('link', { name: '下载术语 JSON 文件' })).getAttribute('download')).toBe('terminology-v1.json');
  expect((fetch.mock.calls as unknown as [string, RequestInit][])[0][0]).toMatch(/\/glossary\/export$/);
  view.rerender(<TerminologyPortabilityPanel {...props} blocked />); expect(screen.queryByRole('link')).toBeNull(); expect(revoke).toHaveBeenCalledWith('blob:local-download');
});
it('validates closed schema, exact Unicode, field bounds and literal formula-looking text', async () => {
  expect(parseGlossary(document).rules[0]).toEqual(rule);
  const base = JSON.parse(document); base.rules[0].preferred = '=1+2'; expect(parseGlossary(JSON.stringify(base)).rules[0].preferred).toBe('=1+2');
  for (const replacement of [{ locked: true }, { source_term: ' padded ' }, { source_term: '\ud800' }, { preferred: 'x'.repeat(161) }, { forbidden: ['تشينغ'] }, { source_aliases: ['same', 'same'] }]) {
    const value = JSON.parse(document); Object.assign(value.rules[0], replacement); expect(() => parseGlossary(JSON.stringify(value))).toThrow();
  }
  expect(() => parseGlossary(document + ' '.repeat(MAX_GLOSSARY_BYTES))).toThrow();
  await expect(readGlossaryFile(file(document, MAX_GLOSSARY_BYTES + 1))).rejects.toThrow();
  await expect(readGlossaryFile({ ...file(), arrayBuffer: async () => new Uint8Array([0xc3, 0x28]).buffer } as File)).rejects.toThrow();
});

it.each(['blocked', 'edition', 'client', 'close'])('discards a late local file read after %s changes', async mode => {
  let finish: (value: ArrayBuffer) => void = () => {};
  const delayed = { ...file(), arrayBuffer: () => new Promise<ArrayBuffer>(resolve => { finish = resolve; }) } as File;
  const fetch = vi.fn(); const props = setup(fetch); const view = render(<TerminologyPortabilityPanel {...props} />);
  fireEvent.change(screen.getByLabelText('选择本地术语 JSON 文件'), { target: { files: [delayed] } });
  if (mode === 'blocked') { view.rerender(<TerminologyPortabilityPanel {...props} blocked />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'edition') { view.rerender(<TerminologyPortabilityPanel {...props} edition={{ ...edition, id: 'other' }} />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'client') { view.rerender(<TerminologyPortabilityPanel {...props} client={experimentalClient('other', { sessionToken: 'other' })} />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'close') { view.unmount(); render(<TerminologyPortabilityPanel {...props} />); }
  finish(new TextEncoder().encode(document).buffer);
  await waitFor(() => expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(false));
  expect(screen.queryByText(/已在本地读取/)).toBeNull(); expect(fetch).not.toHaveBeenCalled();
});
it.each(['blocked', 'edition', 'close'])('discards a late export response after %s changes', async mode => {
  let finish: (value: Response) => void = () => {};
  const create = vi.fn(() => 'blob:late'), revoke = vi.fn();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create }); Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
  const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  const props = setup(fetch); const view = render(<TerminologyPortabilityPanel {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '生成可复用术语 JSON 下载' }));
  if (mode === 'blocked') { view.rerender(<TerminologyPortabilityPanel {...props} blocked />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'edition') view.rerender(<TerminologyPortabilityPanel {...props} edition={{ ...edition, version: 5 }} />);
  if (mode === 'close') { view.unmount(); render(<TerminologyPortabilityPanel {...props} />); }
  finish(response({ filename: 'terminology-v1.json', mime: 'application/json', content: document }));
  await waitFor(() => expect((screen.getByRole('button', { name: '生成可复用术语 JSON 下载' }) as HTMLButtonElement).disabled).toBe(false));
  expect(create).not.toHaveBeenCalled(); expect(screen.queryByRole('link')).toBeNull();
});

it('round-trips literal FEFF and rejects Unicode NEL without normalization', () => {
  const value = JSON.parse(document); value.rules[0].source_term = '\ufeffExact';
  expect(parseGlossary(JSON.stringify(value)).rules[0].source_term).toBe('\ufeffExact');
  value.rules[0].source_term = '\u0085Trimmed'; expect(() => parseGlossary(JSON.stringify(value))).toThrow();
});

it.each(['blocked', 'edition', 'client', 'close'])('does not clear UNKNOWN after late reconciliation across %s', async mode => {
  let finish: (value: Response) => void = () => {};
  const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })); const props = setup(fetch);
  const admission = startGlossaryAdmission(props.client, edition.id);
  const view = render(<TerminologyPortabilityPanel {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '重新读取并核对术语保存结果' }));
  if (mode === 'blocked') { view.rerender(<TerminologyPortabilityPanel {...props} blocked />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'edition') { view.rerender(<TerminologyPortabilityPanel {...props} edition={{ ...edition, id: 'other' }} />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'client') { view.rerender(<TerminologyPortabilityPanel {...props} client={experimentalClient('other', { sessionToken: 'other' })} />); view.rerender(<TerminologyPortabilityPanel {...props} />); }
  if (mode === 'close') { view.unmount(); render(<TerminologyPortabilityPanel {...props} />); }
  finish(response({ ...edition, rules: [] }));
  await waitFor(() => expect((screen.getByRole('button', { name: '重新读取并核对术语保存结果' }) as HTMLButtonElement).disabled).toBe(false));
  expect(glossaryAdmissionToken(props.client, edition.id)).toBe(admission); expect(props.perform).not.toHaveBeenCalled();
  expect((screen.getByLabelText('选择本地术语 JSON 文件') as HTMLInputElement).disabled).toBe(true);
});
it('a stale success or reconciliation token cannot clear a newer unknown admission', () => {
  const client = experimentalClient('n1', { sessionToken: 'host' });
  const old = startGlossaryAdmission(client, edition.id);
  expect(clearGlossaryAdmission(client, edition.id, old)).toBe(true);
  const newer = startGlossaryAdmission(client, edition.id);
  expect(clearGlossaryAdmission(client, edition.id, old)).toBe(false);
  expect(glossaryAdmissionToken(client, edition.id)).toBe(newer);
});
