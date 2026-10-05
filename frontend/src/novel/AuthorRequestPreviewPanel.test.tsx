// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthorRequestPreviewPanel } from './AuthorRequestPreviewPanel';
import { AiWritingPanel } from './AiWritingPanel';
import { authorContextRequest, type AuthorRequestBody } from './authorContextClient';

const body: AuthorRequestBody = { novel_id: 'n', chapter_id: 'n:1', chapter_version: 2, operation: 'continue', instruction: '', style: '', profile: 'LOCAL_ONLY', provider_id: 'fixture', model_id: 'model', source: 'saved selection', selected_text: 'saved selection' };
const context = { sessionToken: 'session' };
const response = { contract: 'AUTHOR_REQUEST_V1', preview_digest: 'a'.repeat(64), chapter_id: 'n:1', chapter_version: 2, target: 'local', provider_id: 'fixture', model_id: 'model', prompt_characters: 40, source_characters: 15, source_strategy: 'EXACT_SAVED_SELECTION', truncation: 'NONE', token_count: null, context_sections: [{ name: 'characters', characters: 2, included_in_adapter_request: true }], privacy_omissions: [], creation_records: [], request: { prompt: 'Real source prompt', context: { characters: [] }, parameters: {}, system_instruction: null } };
function fetcher() { return vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => response } as Response); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Author actual request preflight', () => {
  it('does not fetch automatically and reads exact request with scope headers', async () => {
    const fetch = fetcher(), receipt = vi.fn();
    render(<AuthorRequestPreviewPanel body={body} context={context} saved disabled={false} onReceipt={receipt} />);
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
    expect(await screen.findByText('请求已预检')).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith('/api/novels/n/experimental/author-context/preview', expect.objectContaining({ headers: { 'Content-Type': 'application/json', 'X-Session-Token': 'session' }, body: JSON.stringify(body) }));
    expect((screen.getByLabelText('准确生成 Prompt') as HTMLTextAreaElement).value).toBe('Real source prompt');
    expect(screen.getByText('40 字符；Token 数未知')).toBeTruthy();
    expect(receipt).toHaveBeenLastCalledWith(expect.objectContaining({ previewDigest: 'a'.repeat(64), chapterVersion: 2, requestId: expect.any(String) }));
  });
  it('blocks dirty edits and invalidates a receipt on changed version or input', async () => {
    fetcher(); const receipt = vi.fn();
    const view = render(<AuthorRequestPreviewPanel body={body} context={context} saved disabled={false} onReceipt={receipt} />);
    fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' })); await screen.findByText('请求已预检');
    view.rerender(<AuthorRequestPreviewPanel body={{ ...body, chapter_version: 3 }} context={context} saved={false} disabled={false} onReceipt={receipt} />);
    expect(screen.queryByText('请求已预检')).toBeNull();
    expect((screen.getByRole('button', { name: '检查真实生成请求' }) as HTMLButtonElement).disabled).toBe(true);
    expect(receipt).toHaveBeenLastCalledWith(undefined);
  });
  it('permission failures are recoverable and never supply a receipt', async () => {
    const fetch = fetcher(); fetch.mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({ detail: { code: 'FORBIDDEN' } }) } as Response);
    const receipt = vi.fn(); render(<AuthorRequestPreviewPanel body={body} context={context} saved disabled={false} onReceipt={receipt} />);
    fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(receipt).toHaveBeenLastCalledWith(undefined);
    fireEvent.click(screen.getByRole('button', { name: '重试真实请求预检' })); await screen.findByText('请求已预检');
  });
  it('a late request cannot restore a previous session result', async () => {
    let finish: (value: Response) => void = () => {};
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const receipt = vi.fn();
    const view = render(<AuthorRequestPreviewPanel body={body} context={context} saved disabled={false} onReceipt={receipt} />);
    fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
    view.rerender(<AuthorRequestPreviewPanel body={body} context={{ sessionToken: 'other-session' }} saved disabled={false} onReceipt={receipt} />);
    finish({ ok: true, json: async () => response } as Response);
    await waitFor(() => expect(screen.queryByText('请求已预检')).toBeNull());
    expect(receipt).toHaveBeenLastCalledWith(undefined);
  });
  it('generation client uses the stable receipt request id for retry', async () => {
    const fetch = fetcher();
    for (let i = 0; i < 2; i++) await authorContextRequest('n', 'generate', { ...body, preview_digest: 'a'.repeat(64), generation_request_id: 'same-attempt' }, context);
    for (const call of fetch.mock.calls) expect(call[1]?.headers).toMatchObject({ 'Idempotency-Key': 'same-attempt' });
  });
  it('writing UI requires the matching preview before sending and invalidates changed style', async () => {
    fetcher(); const generate = vi.fn();
    render(<AiWritingPanel novelId="n" chapterNumber={1} models={[{ provider_id: 'fixture', model_id: 'model', display_name: 'Fixture', available: true }]} selection={{ providerId: 'fixture', modelId: 'model' }} readiness={{ diagnostics_contract_version: '1', read_only: true, provider_id: 'fixture', model_id: 'model', state: 'READY', state_label: 'Ready', explanation: '', author_action: '', safe_capabilities: [] }} onGenerate={generate} onAccept={vi.fn()} onReject={vi.fn()} authorPreview={{ enabled: true, chapterId: 'n:1', chapterVersion: 2, source: 'saved selection', profile: 'LOCAL_ONLY', context, saved: true }} />);
    const button = screen.getByRole('button', { name: '生成创作下一章草稿' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' })); await screen.findByText('请求已预检');
    expect(button.disabled).toBe(false); fireEvent.click(button);
    expect(generate).toHaveBeenCalledWith('continue', '', '', expect.objectContaining({ previewDigest: 'a'.repeat(64) }));
    fireEvent.change(screen.getByLabelText('写作风格（可选）'), { target: { value: 'changed style' } });
    expect(button.disabled).toBe(true);
  });
});
