// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AuthorSourcePicker } from './AuthorSourceItems';
import { AuthorRequestPreviewPanel } from './AuthorRequestPreviewPanel';
import { defaultAuthorRequestScope, type AuthorRequestBody, type AuthorRequestScope } from './authorContextClient';
const body: AuthorRequestBody = { novel_id: 'n', chapter_id: 'n:1', chapter_version: 1, operation: 'continue', instruction: '', style: '', profile: 'LOCAL_ONLY', provider_id: 'mock', model_id: 'mock-writer', source: '', selected_text: '', request_scope: { ...defaultAuthorRequestScope, source_mode: 'NONE' } };
const row = { kind: 'RESEARCH', id: 'archive', key: 'key', version: 2, source_digest: 'a'.repeat(64), label: 'Synthetic archive', privacy_level: 'LOCAL_ONLY', preview: 'REFERENCE_CANARY', characters: 900, preview_truncated: true, citation: { source_id: 'archive', source_version: 2, paragraph: 3, quote_sha256: 'b'.repeat(64) } };
const response = (value: unknown) => ({ ok: true, json: async () => value }) as Response;
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('reads explicitly, pins original IDs/citations without client text, edits/excludes/removes existing scope', async () => {
 const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ items: [row], truncated: false, branch_sources_available: true })), changes = vi.fn();
 function Harness() { const [scope, setScope] = useState<AuthorRequestScope>(body.request_scope!); return <AuthorSourcePicker body={{ ...body, request_scope: scope }} context={{ sessionToken: 'session' }} disabled={false} onChange={value => { changes(value); setScope(value); }} />; }
 render(<Harness />); expect(fetch).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('添加来源类型'), { target: { value: 'RESEARCH' } }); fireEvent.click(screen.getByRole('button', { name: '读取可添加来源' }));
 fireEvent.click(await screen.findByRole('button', { name: '添加并固定 Synthetic archive' }));
 expect(changes.mock.calls[0][0].added_sources[0]).toEqual({ kind: row.kind, id: row.id, version: 2, source_digest: row.source_digest, citation: row.citation, include: true, max_characters: 4000 });
 fireEvent.change(screen.getByLabelText('来源字符上限 archive'), { target: { value: '256' } }); fireEvent.click(screen.getByLabelText('包含手动来源 archive'));
 expect(changes).toHaveBeenLastCalledWith(expect.objectContaining({ source_mode: 'NONE', added_sources: [expect.objectContaining({ include: false, max_characters: 256 })] }));
 fireEvent.click(screen.getByRole('button', { name: '移除手动来源 archive' })); expect(changes).toHaveBeenLastCalledWith(expect.objectContaining({ added_sources: [] })); expect(fetch).toHaveBeenCalledTimes(1);
});
it('discards a late catalogue after session change', async () => {
 let finish: (value: Response) => void = () => {};
 vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(resolve => { finish = resolve; }));
 const props = { body, disabled: false, onChange: vi.fn() };
 const view = render(<AuthorSourcePicker {...props} context={{ sessionToken: 'session-a' }} />); fireEvent.click(screen.getByRole('button', { name: '读取可添加来源' }));
 view.rerender(<AuthorSourcePicker {...props} context={{ sessionToken: 'session-b' }} />); finish(response({ items: [row], truncated: false, branch_sources_available: true }));
 await waitFor(() => expect((screen.getByRole('button', { name: '读取可添加来源' }) as HTMLButtonElement).disabled).toBe(false)); expect(screen.queryByText('Synthetic archive')).toBeNull();
});
it('invalidates the real receipt when adding a source without automatically sending a model request', async () => {
 const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => String(url).endsWith('/sources') ? response({ items: [row], truncated: false, branch_sources_available: true }) : response({ preview_digest: 'c'.repeat(64), chapter_id: 'n:1', chapter_version: 1, provider_id: 'mock', model_id: 'mock-writer', target: 'local', source_strategy: 'NO_MANUSCRIPT', source_characters: 0, prompt_characters: 20, context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: 'Actual original payload', context: {}, parameters: {}, system_instruction: null } }));
 const receipt = vi.fn();
 function Harness() { const [scope, setScope] = useState(body.request_scope!); return <AuthorRequestPreviewPanel body={{ ...body, request_scope: scope }} context={{ sessionToken: '' }} saved disabled={false} onScopeChange={setScope} onReceipt={receipt} />; }
 render(<Harness />); fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' })); await screen.findByText('请求已预检'); fireEvent.click(screen.getByRole('button', { name: '读取可添加来源' })); fireEvent.click(await screen.findByRole('button', { name: '添加并固定 Synthetic archive' }));
 await waitFor(() => expect(screen.queryByText('请求已预检')).toBeNull()); expect(receipt).toHaveBeenLastCalledWith(undefined); expect(fetch).toHaveBeenCalledTimes(2); expect(fetch.mock.calls.every(([url]) => !String(url).endsWith('/generate'))).toBe(true);
});
it('isolates character-only requests and displays branch source unavailability', async () => {
 const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ items: [], truncated: false, branch_sources_available: false }));
 const view = render(<AuthorRequestPreviewPanel body={{ ...body, character_id: 'alice' }} context={{ sessionToken: '' }} saved disabled={false} onScopeChange={vi.fn()} onReceipt={vi.fn()} />);
 expect(screen.queryByRole('region', { name: '添加原始上下文来源' })).toBeNull(); expect(fetch).not.toHaveBeenCalled(); view.unmount();
 render(<AuthorSourcePicker body={body} context={{ sessionToken: '' }} disabled={false} onChange={vi.fn()} />); fireEvent.click(screen.getByRole('button', { name: '读取可添加来源' })); await screen.findByText(/当前分支没有原始章节读取能力/); expect(screen.queryByRole('button', { name: /添加并固定/ })).toBeNull();
});

it('never resurrects source pins after switching project authority and returning', async () => {
 const { AiWritingPanel } = await import('./AiWritingPanel');
 vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ items: [row], truncated: false, branch_sources_available: true }));
 const props = { novelId: 'n', chapterNumber: 1, models: [{ provider_id: 'mock', model_id: 'mock-writer', display_name: 'Fixture', available: true }], selection: { providerId: 'mock', modelId: 'mock-writer' }, onGenerate: vi.fn(), onAccept: vi.fn(), onReject: vi.fn() };
 const options = { enabled: true, chapterId: 'n:1', chapterVersion: 1, source: '', profile: 'LOCAL_ONLY' as const, context: { sessionToken: 'session-a' }, saved: true };
 const view = render(<AiWritingPanel {...props} authorPreview={options} />);
 fireEvent.click(screen.getByRole('button', { name: '读取可添加来源' })); fireEvent.click(await screen.findByRole('button', { name: '添加并固定 Synthetic archive' }));
 expect(screen.getByLabelText('包含手动来源 archive')).toBeTruthy();
 view.rerender(<AiWritingPanel {...props} authorPreview={{ ...options, context: { sessionToken: 'session-b' } }} />);
 expect(screen.queryByLabelText('包含手动来源 archive')).toBeNull();
 view.rerender(<AiWritingPanel {...props} authorPreview={options} />);
 expect(screen.queryByLabelText('包含手动来源 archive')).toBeNull();
});
