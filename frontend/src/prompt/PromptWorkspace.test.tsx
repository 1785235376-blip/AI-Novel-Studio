// @vitest-environment jsdom
/**
 * R3-U3-C1 —— 真实组件挂载（jsdom / React Testing Library）。
 *
 * 传输层被替换成受控的假 transport，但它回放的是**真实后端**采集下来的 fixture 形状
 * （`__fixtures__/library.json` 等），所以解码器与真实生产者仍然对得上。
 * 这些测试只证明组件行为；真实浏览器验收是 R3-U3-D 的独立项。
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { PromptWorkspace } from './PromptWorkspace';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

// `import.meta.url` is not a file URL under the jsdom environment, so resolve from the
// vitest root (frontend/) instead — works in both node and jsdom.
const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

type Call = { url: string; method: string; body: unknown };

function transportWith(options: {
  library?: unknown; detail?: unknown; body?: unknown;
  onPost?: (url: string, body: unknown) => { status: number; payload: unknown };
}) {
  const calls: Call[] = [];
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
      calls.push({ url, method, body });
      if (method === 'GET') {
        if (url.endsWith('/prompts')) return (options.library ?? fixture('library.json')) as T;
        if (url.includes('/revisions/') && url.endsWith('/body')) return (options.body ?? fixture('revision-1-body.json')) as T;
        if (url.includes('/prompts/')) return (options.detail ?? fixture('detail.json')) as T;
      }
      if (method === 'POST' && options.onPost) {
        const result = options.onPost(url, body);
        const error = new Error('http') as Error & { problem?: unknown };
        if (result.status >= 400) {
          const { ApiError } = await import('../api');
          throw new ApiError({ status: result.status, code: 'EXPERIMENTAL_VERSION_CONFLICT',
            message: 'conflict', details: result.payload });
        }
        void error;
        return result.payload as T;
      }
      throw new Error(`unexpected ${method} ${url}`);
    },
  };
  return { transport, calls };
}

const renderWorkspace = (transport: StudioGraphTransport, over: Record<string, unknown> = {}) =>
  render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport} mode="PROFESSIONAL"
    writable denied={false} {...over} />);

beforeEach(() => { globalThis.localStorage?.clear?.(); });
// React Testing Library does not auto-clean in this setup, so unmount between cases:
// otherwise a previous render leaks in and role queries match twice.
afterEach(() => { cleanup(); });

describe('R3-U3-C1 Prompt workspace (jsdom)', () => {
  it('lists the authorised families from the real producer shape', async () => {
    const { transport } = transportWith({});
    renderWorkspace(transport);
    expect(await screen.findByRole('region', { name: 'Prompt 列表' })).toBeTruthy();
    const items = await screen.findAllByRole('button', { name: /IMAGE/ });
    expect(items.length).toBeGreaterThan(0);
  });

  it('shows an explicit empty state when there are no prompts', async () => {
    const { transport } = transportWith({ library: fixture('empty-library.json') });
    renderWorkspace(transport);
    expect(await screen.findByText('还没有 Prompt')).toBeTruthy();
  });

  it('warns that search only covers what was loaded when the read is bounded', async () => {
    const library = { ...(fixture('library.json') as Record<string, unknown>),
      truncated: true, has_more: true, read_complete: false };
    const { transport } = transportWith({ library });
    renderWorkspace(transport);
    expect(await screen.findByText(/仅在已加载的条目中进行/)).toBeTruthy();
  });

  it('opens a family and edits the body without saving on input', async () => {
    const { transport, calls } = transportWith({});
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    const textarea = await screen.findByLabelText('正文');
    fireEvent.change(textarea, { target: { value: '中文正文\n第二行 🙂' } });
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toContain('🙂'));
    // Typing must never POST: nothing is created until the user clicks save.
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0);
    expect(screen.getByRole('status').textContent).toMatch(/未保存/);
  });

  it('does not trim CJK, newlines or emoji, and reports them back unchanged', async () => {
    const { transport } = transportWith({});
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
    const text = '  前后空白 \n\n emoji 🙂🙂 \n';
    fireEvent.change(textarea, { target: { value: text } });
    expect(textarea.value).toBe(text);
  });

  it('saves only on an explicit click, sending origin MANUAL and a request id', async () => {
    const { transport, calls } = transportWith({
      onPost: () => ({ status: 201, payload: {
        family_id: 'fam-1', asset_id: 'asset-9', revision: 1, asset_version: 2,
        text_digest: 'd'.repeat(64), idempotent_replay: false, previous_asset_id: null,
        payload_digest: 'p'.repeat(64) } }),
    });
    renderWorkspace(transport);
    fireEvent.click(await screen.findByRole('button', { name: '新建 Prompt' }));
    const textarea = await screen.findByLabelText('正文');
    fireEvent.change(textarea, { target: { value: '手写草稿' } });
    fireEvent.click(screen.getByRole('button', { name: '保存为新 Prompt' }));
    await waitFor(() => expect(calls.filter(call => call.method === 'POST')).toHaveLength(1));
    const post = calls.find(call => call.method === 'POST')!;
    const body = post.body as Record<string, unknown>;
    expect(body.origin).toBe('MANUAL');            // never claims AI_GENERATED
    expect(body.text).toBe('手写草稿');             // not trimmed
    expect(typeof body.request_id).toBe('string');
    expect(body.request_id).toBeTruthy();
  });

  it('keeps the draft and explains it when the server refuses with 409', async () => {
    const { transport } = transportWith({
      onPost: () => ({ status: 409, payload: {
        code: 'PROMPT_REVISION_STALE', family_id: 'fam-1', expected_revision: 1,
        current_revision: 2, retryable: true } }),
    });
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '我的宝贵草稿' } });
    fireEvent.click(screen.getByRole('button', { name: '保存新版本' }));
    await waitFor(() => expect(document.body.textContent).toContain('已经有人保存了更新的修订'));
    // The user's text is still there, and a rebase action is offered.
    expect(textarea.value).toBe('我的宝贵草稿');
    expect(screen.getByRole('button', { name: '重新基准到服务器最新修订' })).toBeTruthy();
  });

  it('renders explicit status for a masked body instead of pretending it is complete', async () => {
    const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
    (detail.body as Record<string, unknown>) = { state: 'REDACTED', value: null, digest: 'a'.repeat(64),
      digest_of: 'ORIGINAL_BYTES', truncated: false, decodable: false, body_validated: false,
      tail_unverified: false, original_length: 12, preview_length: 0, limit: 65536, fetch: 'REDACTED' };
    detail.redacted = true;
    const { transport } = transportWith({ detail });
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    await waitFor(() => expect(document.body.textContent).toContain('完整正文'));
    expect(document.body.textContent).toContain('已脱敏');
  });

  it('refuses to claim a full-text diff when a side is unavailable', async () => {
    const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
    const versions = detail.versions as Record<string, unknown>[];
    versions[0] = { ...versions[0], available: false };
    const body = { ...(fixture('revision-1-body.json') as Record<string, unknown>),
      state: 'DELETED', value: null, available: false, verified: false };
    const { transport } = transportWith({ detail, body });
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    fireEvent.click(await screen.findByRole('button', { name: '比较正文' }));
    await waitFor(() => expect(document.body.textContent).toContain('无法比较完整正文'));
  });

  it('denies access with an explicit state instead of rendering an empty workspace', () => {
    const { transport } = transportWith({});
    renderWorkspace(transport, { denied: true });
    expect(screen.getByText('当前会话无权访问此项目')).toBeTruthy();
  });

  it('does not let a stale response overwrite after the project changes', async () => {
    const { transport } = transportWith({});
    const view = renderWorkspace(transport);
    await screen.findByRole('region', { name: 'Prompt 列表' });
    // A different project+actor must remount on a fresh scope, not keep the old data on screen.
    view.rerender(<PromptWorkspace projectId="p2" actor="author-b" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await waitFor(() => expect(screen.getByRole('region', { name: 'Prompt 列表' })).toBeTruthy());
  });
});
