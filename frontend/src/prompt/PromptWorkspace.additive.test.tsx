// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
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

describe('Prompt history finder', () => {
  it('exposes authored change reasons and searches only loaded revision records', async () => {
    const { transport, calls } = transportWith({});
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    const search = await screen.findByRole('searchbox', { name: '搜索版本记录' });
    expect(screen.getByText('修改原因：合成调整')).toBeTruthy();
    expect(screen.getByText('修改原因：合成第一版')).toBeTruthy();
    const before = calls.length;
    fireEvent.change(search, { target: { value: '合成调整' } });
    expect(document.querySelectorAll('.prompt-version-list li')).toHaveLength(1);
    expect(screen.getByText('修改原因：合成调整')).toBeTruthy();
    expect(screen.queryByText('修改原因：合成第一版')).toBeNull();
    expect(screen.getByText(/当前显示 1 条/)).toBeTruthy();
    expect(calls).toHaveLength(before);
    fireEvent.click(screen.getByRole('button', { name: '清除版本搜索' }));
    expect(document.querySelectorAll('.prompt-version-list li')).toHaveLength(2);
  });

  it('offers a recoverable no-match message while preserving the complete history warning', async () => {
    const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
    detail.history_complete = false;
    const { transport } = transportWith({ detail });
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    fireEvent.change(await screen.findByRole('searchbox', { name: '搜索版本记录' }), { target: { value: '找不到的修改原因' } });
    expect(screen.getByText('已加载记录中没有匹配的版本')).toBeTruthy();
    expect(screen.getByText(/修订链\*\*不完整\*\*/)).toBeTruthy();
    expect(screen.getByRole('button', { name: '清除版本搜索' })).toBeTruthy();
  });

  it('selects a comparison from history without reading bodies or writing until explicitly requested', async () => {
    const { transport, calls } = transportWith({});
    const detail = fixture('detail.json') as { versions: { asset_id: string }[] };
    renderWorkspace(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    await screen.findByRole('searchbox', { name: '搜索版本记录' });
    const before = calls.length;
    fireEvent.click(screen.getByRole('button', { name: '将修订 2 选作旧版' }));
    fireEvent.click(screen.getByRole('button', { name: '将修订 1 选作新版' }));
    expect((screen.getByLabelText('对比旧版') as HTMLSelectElement).value).toBe(detail.versions[1].asset_id);
    expect((screen.getByLabelText('与新版') as HTMLSelectElement).value).toBe(detail.versions[0].asset_id);
    expect(calls).toHaveLength(before);
    fireEvent.click(screen.getByRole('button', { name: '比较正文' }));
    await waitFor(() => expect(calls.filter(call => call.url.endsWith('/body'))).toHaveLength(2));
    expect(calls.every(call => call.method === 'GET')).toBe(true);
  });
});

describe('Prompt editor correction across interface modes', () => {
  it('reveals an invalid advanced field in novice mode and keeps correction editable until explicit save', async () => {
    const { transport, calls } = transportWith({ onPost: () => ({ status: 201, payload: {
      family_id: 'fam-correction', asset_id: 'asset-correction', revision: 1, asset_version: 1,
      text_digest: 'd'.repeat(64), idempotent_replay: false, previous_asset_id: null,
      payload_digest: 'p'.repeat(64),
    } }) });
    const view = renderWorkspace(transport);
    fireEvent.click(await screen.findByRole('button', { name: '新建 Prompt' }));
    fireEvent.change(screen.getByLabelText('正文'), { target: { value: '保留创作正文' } });
    fireEvent.change(screen.getByLabelText('参数（JSON，不会执行）'), { target: { value: '{unfinished' } });
    view.rerender(<PromptWorkspace projectId="p1" actor="author-a" transport={transport} mode="NOVICE" writable denied={false} />);
    expect(screen.queryByLabelText('参数（JSON，不会执行）')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '保存为新 Prompt' }));
    const parameters = await screen.findByLabelText('参数（JSON，不会执行）') as HTMLTextAreaElement;
    expect(parameters.value).toBe('{unfinished');
    expect(document.activeElement).toBe(parameters);
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0);
    fireEvent.change(parameters, { target: { value: '{"steps":2}' } });
    expect((screen.getByLabelText('参数（JSON，不会执行）') as HTMLTextAreaElement).value).toBe('{"steps":2}');
    expect(calls.filter(call => call.method === 'POST')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: '保存为新 Prompt' }));
    await waitFor(() => expect(calls.filter(call => call.method === 'POST')).toHaveLength(1));
    expect(calls.find(call => call.method === 'POST')?.body).toMatchObject({ text: '保留创作正文', parameters: { steps: 2 } });
  });
});

describe('Prompt field error attribution', () => {
  it('does not carry a failed field correction from family A into valid family B', async () => {
    const library = structuredClone(fixture('library.json')) as Record<string, unknown>;
    const original = (library.entries as Record<string, unknown>[])[0];
    library.entries = ['editor-A', 'editor-B'].map(id => ({ ...original, family_id: id, head_asset_id: `${id}-a2`, revision: 2 }));
    library.prompt_count = 2; library.projected_families = 2; library.revision_count = 4;
    const calls: string[] = [];
    const transport: StudioGraphTransport = { async json<T>(url: string, method = 'GET'): Promise<T> {
      calls.push(method);
      if (method !== 'GET') throw new Error('Unexpected write');
      if (url.endsWith('/prompts')) return library as T;
      const id = url.includes('/editor-A') ? 'editor-A' : 'editor-B';
      const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
      detail.family_id = id; detail.head_asset_id = `${id}-a2`; detail.revision = 2;
      const versions = detail.versions as Record<string, unknown>[];
      versions[0] = { ...versions[0], asset_id: `${id}-a1`, revision: 1 };
      versions[1] = { ...versions[1], asset_id: `${id}-a2`, revision: 2, previous_asset_id: `${id}-a1` };
      detail.body = { ...(detail.body as Record<string, unknown>), state: 'COMPLETE', value: `${id} body`, truncated: false, decodable: true };
      (detail.fields as Record<string, unknown>[])[0] = { field: 'text', label: '提示词', value: `${id} body`, authored: true, state: 'KNOWN' };
      return detail as T;
    } };
    const view = renderWorkspace(transport, { actor: 'editor-attribution' });
    await waitFor(() => expect(document.querySelectorAll('.prompt-list-item')).toHaveLength(2));
    const [familyA, familyB] = Array.from(document.querySelectorAll<HTMLButtonElement>('.prompt-list-item'));
    fireEvent.click(familyA);
    await waitFor(() => expect((screen.getByLabelText('正文') as HTMLTextAreaElement).value).toBe('editor-A body'));
    fireEvent.change(screen.getByLabelText('参数（JSON，不会执行）'), { target: { value: '{unfinished' } });
    view.rerender(<PromptWorkspace projectId="p1" actor="editor-attribution" transport={transport} mode="NOVICE" writable denied={false} />);
    fireEvent.click(screen.getByRole('button', { name: '保存新版本' }));
    expect(document.activeElement).toBe(screen.getByLabelText('参数（JSON，不会执行）'));
    familyB.focus();
    fireEvent.click(familyB);
    await waitFor(() => expect((screen.getByLabelText('正文') as HTMLTextAreaElement).value).toBe('editor-B body'));
    expect(screen.queryByLabelText('参数（JSON，不会执行）')).toBeNull();
    expect(screen.queryByText(/参数不是合法 JSON/)).toBeNull();
    expect(document.activeElement).toBe(familyB);
    expect(calls.every(method => method === 'GET')).toBe(true);
  });
});

describe('Prompt visible draft rescue', () => {
  it('copies an edited body without submitting or persisting that body', async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    const copied: string[] = [];
    Object.defineProperty(navigator, 'clipboard', { configurable: true,
      value: { writeText: async (text: string) => { copied.push(text); } } });
    try {
      const { transport, calls } = transportWith({ library: fixture('empty-library.json') });
      renderWorkspace(transport, { actor: 'copy-rescue-author' });
      await screen.findByText('还没有 Prompt');
      const text = '  手工保留正文🙂\n第二行\n';
      fireEvent.change(screen.getByLabelText('正文'), { target: { value: text } });
      expect(copied).toEqual([]);
      fireEvent.click(screen.getByRole('button', { name: '复制当前正文' }));
      await screen.findByText(/当前正文已复制到剪贴板/);
      expect(copied).toEqual([text]);
      expect(screen.getByText('有未保存修改')).toBeTruthy();
      expect(calls.every(call => call.method === 'GET')).toBe(true);
      const stored = Array.from({ length: localStorage.length }, (_, index) =>
        localStorage.getItem(localStorage.key(index)!)).join('');
      expect(stored).not.toContain(text);
    } finally {
      if (original) Object.defineProperty(navigator, 'clipboard', original);
      else Reflect.deleteProperty(navigator, 'clipboard');
    }
  });
});
