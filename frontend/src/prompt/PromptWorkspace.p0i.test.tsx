// @vitest-environment jsdom
/**
 * R3-U3 P0-I —— 默认比较界面不得悄悄展示已标记「展示遮罩」的修订原文。
 *
 * 已实测：Library/Detail 会把 `redacted` 的修订遮罩，而单修订正文路由仍然返回 COMPLETE
 * （见 tests/test_round3u_redaction_consistency.py）。redacted 是**展示遮罩**，不是权限，
 * 所以修复是前端默认行为，而不是改 owner 的授权读取契约。
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { PromptWorkspace } from './PromptWorkspace';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

function harness(detail: unknown) {
  const calls: { url: string; method: string }[] = [];
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET'): Promise<T> {
      calls.push({ url, method });
      if (url.endsWith('/prompts')) return fixture('library.json') as T;
      if (url.includes('/revisions/') && url.endsWith('/body')) return fixture('revision-1-body.json') as T;
      if (url.includes('/prompts/')) return detail as T;
      throw new Error(`unexpected ${method} ${url}`);
    },
  };
  return { transport, calls };
}

const maskedDetail = () => {
  const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
  const versions = detail.versions as Record<string, unknown>[];
  // Revision 1 is display-masked; revision 2 is not.
  versions[0] = { ...versions[0], redacted: true };
  versions[1] = { ...versions[1], redacted: false };
  return detail;
};

beforeEach(() => { globalThis.localStorage?.clear?.(); });
afterEach(() => { cleanup(); });

describe('P0-I masked revisions do not enter plaintext comparison by default', () => {
  it('refuses to compare a masked revision and says why', async () => {
    const { transport, calls } = harness(maskedDetail());
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    const from = await screen.findByLabelText('对比旧版');
    // Default selection is the two newest revisions; force the masked one on the left.
    fireEvent.change(from, { target: { value: (maskedDetail().versions as Record<string, unknown>[])[0].asset_id as string } });
    fireEvent.click(screen.getByRole('button', { name: '比较正文' }));
    await waitFor(() => expect(document.body.textContent).toMatch(/展示遮罩/));
    expect(document.body.textContent).toMatch(/默认不参与明文比较/);
    // No body fetch was made for the masked comparison.
    expect(calls.filter(call => call.url.endsWith('/body'))).toHaveLength(0);
  });

  it('still compares two unmasked revisions normally', async () => {
    const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
    (detail.versions as Record<string, unknown>[]).forEach(row => { row.redacted = false; });
    const { transport, calls } = harness(detail);
    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    fireEvent.click((await screen.findAllByRole('button', { name: /IMAGE/ }))[0]);
    fireEvent.click(await screen.findByRole('button', { name: '比较正文' }));
    await waitFor(() => expect(calls.filter(call => call.url.endsWith('/body')).length).toBe(2));
    expect(document.body.textContent).not.toMatch(/默认不参与明文比较/);
  });
});
