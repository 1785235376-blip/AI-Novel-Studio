// @vitest-environment jsdom
/**
 * R3-U3-C2 P0-C —— 异步读取不得取消真实的保存回执。
 *
 * 已定位风险：`epoch` 同时服务 refresh / selectFamily / submit / rebase / compare。
 * 保存仍在途中时，任何另一个操作都会让 epoch 增加，把真正成功的回执当成过时结果丢弃，
 * 草稿永久停在 SUBMITTING。
 *
 * 这些用例用**可控延迟**的 transport 制造真实交错，而不是猜测。
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

function deferred<T = void>() {
  let resolveFn: (value: T) => void = () => {};
  const promise = new Promise<T>(resolve => { resolveFn = resolve; });
  return { promise, resolve: resolveFn };
}

const receipt = (familyId: string, assetId: string, revision: number) => ({
  family_id: familyId, asset_id: assetId, revision, asset_version: 1,
  text_digest: 'd'.repeat(64), idempotent_replay: false,
  previous_asset_id: revision > 1 ? 'asset-0' : null, payload_digest: 'p'.repeat(64),
});

function harness(options: {
  library?: unknown; detail?: unknown;
  postGate?: Promise<void>;
  postResult?: { status: number; payload: unknown } | 'NETWORK';
  libraryFailsAfterPost?: boolean;
} = {}) {
  const calls: Call[] = [];
  let posted = false;
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
      calls.push({ url, method, body: body as Record<string, unknown> | undefined });
      if (method === 'GET') {
        if (url.endsWith('/prompts')) {
          if (posted && options.libraryFailsAfterPost) {
            throw new ApiError({ status: 500, code: 'HTTP_500', message: 'list failed' });
          }
          return (options.library ?? fixture('library.json')) as T;
        }
        if (url.includes('/revisions/') && url.endsWith('/body')) return fixture('revision-1-body.json') as T;
        if (url.includes('/prompts/')) return (options.detail ?? fixture('detail.json')) as T;
      }
      if (method === 'POST') {
        if (options.postGate) await options.postGate;
        posted = true;
        const result = options.postResult ?? { status: 201, payload: receipt('fam-1', 'asset-1', 1) };
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

const postsOf = (calls: Call[]) => calls.filter(call => call.method === 'POST');
const getsOf = (calls: Call[]) => calls.filter(call => call.method === 'GET');

beforeEach(() => { globalThis.localStorage?.clear?.(); });
afterEach(() => { cleanup(); });

async function startSave() {
  fireEvent.click(await screen.findByRole('button', { name: '新建 Prompt' }));
  const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
  fireEvent.change(textarea, { target: { value: '交错保存的正文' } });
  fireEvent.click(screen.getByRole('button', { name: '保存为新 Prompt' }));
  return textarea;
}

describe('P0-C a read must not cancel a real save receipt', () => {
  it('keeps the receipt when the user refreshes the library mid-save', async () => {
    const gate = deferred();
    const { transport, calls } = harness({ postGate: gate.promise });
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await startSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));

    // The user refreshes while the POST is still in flight.
    fireEvent.click(screen.getByRole('button', { name: '重新读取' }));
    await waitFor(() => expect(getsOf(calls).length).toBeGreaterThan(1));
    gate.resolve();

    // The genuine 201 must land: SAVED, not a draft stuck in SUBMITTING.
    await waitFor(() => expect(document.body.textContent).toMatch(/已保存/), { timeout: 3000 });
    expect(document.body.textContent).not.toMatch(/正在提交/);
    expect(postsOf(calls)).toHaveLength(1);
  });

  it('keeps the receipt when the user compares two revisions mid-save', async () => {
    const gate = deferred();
    const { transport, calls } = harness({ postGate: gate.promise });
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    // Open a family first so the compare controls exist.
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    await screen.findByRole('button', { name: '比较正文' });
    const textarea = (await screen.findByLabelText('正文')) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '比较期间保存' } });
    fireEvent.click(screen.getByRole('button', { name: '保存新版本' }));
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));

    fireEvent.click(screen.getByRole('button', { name: '比较正文' }));
    gate.resolve();
    await waitFor(() => expect(document.body.textContent).toMatch(/已保存/), { timeout: 3000 });
    expect(postsOf(calls)).toHaveLength(1);
  });

  it('survives a host rerender that hands over a new transport object', async () => {
    const gate = deferred();
    const first = harness({ postGate: gate.promise });
    const view = render(<PromptWorkspace projectId="p1" actor="author-a"
      transport={first.transport} mode="PROFESSIONAL" writable denied={false} />);
    await startSave();
    await waitFor(() => expect(postsOf(first.calls)).toHaveLength(1));

    // React sees a brand-new transport identity on an unrelated parent re-render.
    view.rerender(<PromptWorkspace projectId="p1" actor="author-a"
      transport={{ json: first.transport.json.bind(first.transport) }}
      mode="PROFESSIONAL" writable denied={false} />);
    gate.resolve();
    await waitFor(() => expect(document.body.textContent).toMatch(/已保存|已确认/), { timeout: 3000 });
  });

  it('marks a save whose list refresh failed as saved, never as unknown', async () => {
    const gate = deferred();
    const { transport, calls } = harness({ postGate: gate.promise, libraryFailsAfterPost: true });
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await startSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));
    gate.resolve();
    // The write succeeded; the follow-up read did not. That must not undo the success.
    await waitFor(() => expect(document.body.textContent).toMatch(/已保存/), { timeout: 3000 });
    expect(document.body.textContent).not.toMatch(/结果未知/);
  });

  it('does not apply an old receipt to a different draft the user moved to', async () => {
    const gate = deferred();
    const { transport, calls } = harness({ postGate: gate.promise });
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await startSave();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));
    // The user starts another brand-new prompt while the first save is still in flight.
    fireEvent.click(screen.getByRole('button', { name: '新建 Prompt' }));
    gate.resolve();
    await waitFor(() => expect(postsOf(calls)).toHaveLength(1));
    // Whatever the screen shows, it must not claim the NEW empty draft was saved.
    const textarea = screen.getByLabelText('正文') as HTMLTextAreaElement;
    expect(textarea.value).toBe('');
    expect(document.body.textContent).not.toMatch(/已保存（服务器已确认）/);
  });

  it('reconciles a draft left SUBMITTING by an earlier mount instead of hanging forever', async () => {
    const gate = deferred();
    const { transport } = harness({ postGate: gate.promise });
    const view = render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await startSave();
    // Unmount while the POST is still in flight: the receipt can never arrive here.
    view.unmount();
    gate.resolve();

    cleanup();
    const second = harness({});
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={second.transport}
      mode="PROFESSIONAL" writable denied={false} />);
    // It must resolve to an explicit "outcome to be verified" state, not a permanent
    // "submitting" lock, and it must not silently fire a brand-new request.
    await waitFor(() => expect(document.body.textContent).toMatch(/待核对|结果未知/), { timeout: 3000 });
    expect(postsOf(second.calls)).toHaveLength(0);
  });
});
