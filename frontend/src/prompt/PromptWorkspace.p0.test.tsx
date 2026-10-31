// @vitest-environment jsdom
/**
 * R3-U3-C2 P0 —— 用户会写错、丢稿或误报成功的回归。
 *
 * 每一项都是指导书里的**待证假设**：先复现，再最小修复。若某项无法复现，就在这里记为
 * FALSE POSITIVE，而不是去改正确的代码。
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { PromptWorkspace } from './PromptWorkspace';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { ApiError } from '../api';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

type Call = { url: string; method: string; body: Record<string, unknown> | undefined };

function harness(options: {
  library?: unknown;
  detail?: unknown;
  /** Return a status + payload, or a thrown transport error to simulate a lost response. */
  onPost?: (url: string, body: unknown) => { status: number; payload: unknown } | 'NETWORK';
  gate?: Promise<void>;
} = {}) {
  const calls: Call[] = [];
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
      calls.push({ url, method, body: body as Record<string, unknown> | undefined });
      if (method === 'GET') {
        if (url.endsWith('/prompts')) return (options.library ?? fixture('library.json')) as T;
        if (url.includes('/revisions/') && url.endsWith('/body')) return fixture('revision-1-body.json') as T;
        if (url.includes('/prompts/')) return (options.detail ?? fixture('detail.json')) as T;
      }
      if (method === 'POST') {
        if (options.gate) await options.gate;
        const result = options.onPost?.(url, body)
          ?? { status: 201, payload: receipt('fam-1', 'asset-1', 1) };
        if (result === 'NETWORK') throw new TypeError('network down');
        if (result.status >= 400) {
          throw new ApiError({ status: result.status, code: `HTTP_${result.status}`,
            message: 'rejected', details: result.payload });
        }
        return result.payload as T;
      }
      throw new Error(`unexpected ${method} ${url}`);
    },
  };
  return { transport, calls };
}

const receipt = (familyId: string, assetId: string, revision: number) => ({
  family_id: familyId, asset_id: assetId, revision, asset_version: 1,
  text_digest: 'd'.repeat(64), idempotent_replay: false,
  previous_asset_id: revision > 1 ? 'asset-0' : null, payload_digest: 'p'.repeat(64),
});

const postsOf = (calls: Call[]) => calls.filter(call => call.method === 'POST');
const renderWs = (transport: StudioGraphTransport) => render(
  <PromptWorkspace projectId="p1" actor="author-a" transport={transport} mode="PROFESSIONAL"
    writable denied={false} />);

beforeEach(() => { globalThis.localStorage?.clear?.(); });
afterEach(() => { cleanup(); });

/** Start a brand-new prompt and fill its body — it must NOT save; each test clicks save
 *  itself, after any parameter/seed input, so the assertion covers the real request. */
async function createPromptWith(text: string) {
  fireEvent.click(await screen.findByRole('button', { name: '新建 Prompt' }));
  const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
  fireEvent.change(textarea, { target: { value: text } });
  return textarea;
}

const clickSave = (name = '保存为新 Prompt') =>
  fireEvent.click(screen.getByRole('button', { name }));

describe('P0-A invalid parameters and seed must not be silently replaced', () => {
  it('sends no POST at all when the parameter JSON is invalid', async () => {
    const { transport, calls } = harness();
    renderWs(transport);
    await createPromptWith('正文');
    fireEvent.change(screen.getByLabelText(/参数/), { target: { value: '{ not json' } });
    clickSave();
    await waitFor(() => expect(document.body.textContent).toMatch(/JSON/));
    expect(postsOf(calls)).toHaveLength(0);
  });

  it('sends no POST when the parameters are a JSON array instead of an object', async () => {
    const { transport, calls } = harness();
    renderWs(transport);
    await createPromptWith('正文');
    fireEvent.change(screen.getByLabelText(/参数/), { target: { value: '[1,2,3]' } });
    clickSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(0));
  });

  it('sends no POST for a negative, fractional or non-numeric seed, and keeps the typed value', async () => {
    for (const bad of ['-1', '1.5', 'abc']) {
      cleanup();
      const { transport, calls } = harness();
      renderWs(transport);
      await createPromptWith('正文');
      const seed = screen.getByLabelText('Seed') as HTMLInputElement;
      fireEvent.change(seed, { target: { value: bad } });
      clickSave();
      await waitFor(() => expect(document.body.textContent).toMatch(/Seed/));
      expect(postsOf(calls), `seed=${bad} must not POST`).toHaveLength(0);
      // The user's raw input is preserved, never coerced to a default.
      expect((screen.getByLabelText('Seed') as HTMLInputElement).value).toBe(bad);
    }
  });

  it('still sends a precise request for valid parameters and seed', async () => {
    const { transport, calls } = harness();
    renderWs(transport);
    await createPromptWith('正文');
    fireEvent.change(screen.getByLabelText(/参数/), { target: { value: '{"steps":28}' } });
    fireEvent.change(screen.getByLabelText('Seed'), { target: { value: '7' } });
    clickSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));
    expect(postsOf(calls)[0].body?.parameters).toEqual({ steps: 28 });
    expect(postsOf(calls)[0].body?.seed).toBe(7);
  });
});

describe('P0-B creating twice must produce two families', () => {
  it('saves the second new prompt as a create, not as a revision of the first', async () => {
    let created = 0;
    const { transport, calls } = harness({
      onPost: url => {
        if (url.endsWith('/prompts')) {
          created += 1;
          return { status: 201, payload: receipt(`fam-${created}`, `asset-${created}`, 1) };
        }
        return { status: 201, payload: receipt('fam-1', 'asset-9', 2) };
      },
    });
    renderWs(transport);
    await createPromptWith('第一份');
    clickSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));

    // Same page, no reload: start another brand-new prompt.
    await createPromptWith('第二份');
    clickSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(2));
    const second = postsOf(calls)[1];
    expect(second.url.endsWith('/prompts'), `expected a create, got ${second.url}`).toBe(true);
    expect(second.body?.text).toBe('第二份');
    expect(second.body?.expected_previous_asset_id).toBeUndefined();
  });
});

describe('P0-D an incomplete baseline must not become a new revision', () => {
  it('refuses to save a revision when the head body is only a preview', async () => {
    const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
    detail.body = { state: 'TRUNCATED', value: '只有预览', digest: 'a'.repeat(64),
      digest_of: 'ORIGINAL_BYTES', truncated: true, decodable: true, body_validated: false,
      tail_unverified: true, original_length: 9999, preview_length: 12, limit: 12, fetch: 'ASSET_BYTES' };
    const { transport, calls } = harness({ detail });
    renderWs(transport);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    await screen.findByLabelText('正文');
    clickSave('保存新版本');
    await waitFor(() => expect(document.body.textContent).toMatch(/预览|不完整/));
    expect(postsOf(calls)).toHaveLength(0);
  });
});

describe('P0-F a definite HTTP rejection is not an unknown outcome', () => {
  it('does not lock the draft as UNKNOWN when the server answers 422', async () => {
    const { transport } = harness({ onPost: () => ({ status: 422, payload: { code: 'EXPERIMENTAL_INVALID' } }) });
    renderWs(transport);
    await createPromptWith('正文');
    clickSave();
    await waitFor(() => expect(document.body.textContent).toMatch(/拒绝|不接受|校验/));
    // A validation refusal is definitive: it must not read as "the result is unknown".
    expect(document.body.textContent).not.toMatch(/结果未知/);
    expect(screen.getByRole('button', { name: '保存为新 Prompt' })).toBeTruthy();
  });

  it('treats a lost response as genuinely unknown', async () => {
    const { transport } = harness({ onPost: () => 'NETWORK' });
    renderWs(transport);
    await createPromptWith('正文');
    clickSave();
    await waitFor(() => expect(document.body.textContent).toMatch(/结果未知/));
    expect(screen.getByRole('button', { name: '用同一请求重试' })).toBeTruthy();
  });

  it('treats a 5xx as unknown rather than as definitely unsaved', async () => {
    const { transport } = harness({ onPost: () => ({ status: 503, payload: { code: 'BUSY' } }) });
    renderWs(transport);
    await createPromptWith('正文');
    clickSave();
    await waitFor(() => expect(document.body.textContent).toMatch(/结果未知/));
  });
});

describe('P0-H duplicate submits', () => {
  it('sends at most one request when save is clicked repeatedly in the same batch', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>(resolveGate => { release = resolveGate; });
    const { transport, calls } = harness({ gate });
    renderWs(transport);
    fireEvent.click(await screen.findByRole('button', { name: '新建 Prompt' }));
    const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '只应提交一次' } });
    const save = screen.getByRole('button', { name: '保存为新 Prompt' });
    fireEvent.click(save);
    fireEvent.click(save);
    fireEvent.click(save);
    release();
    await waitFor(() => expect(postsOf(calls).length).toBeGreaterThan(0));
    expect(postsOf(calls)).toHaveLength(1);
  });
});
