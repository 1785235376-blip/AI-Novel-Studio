// @vitest-environment jsdom
/**
 * R3-U3-D —— StrictMode 根因复现。
 *
 * 真实浏览器现象：`GET /studio/prompts` 两次都返回 200，但界面永远停在“正在读取…”，
 * `library=null`、`loading=true`。
 *
 * 根因（静态定位 + 本用例复现）：`main.tsx` 使用 `<React.StrictMode>`。开发模式下 Effect
 * 会经历 setup → cleanup → setup 的重放；而
 * `useEffect(() => () => { alive.current = false; }, [])`
 * 只在 cleanup 里置 false，**下一次 setup 没有恢复 true**。于是重放之后 `alive.current`
 * 永远为 false，所有**已经成功返回**的读取结果都被 `!alive.current` 丢弃。
 *
 * 这些用例把组件包在 StrictMode 里；修复前必须失败。
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { StrictMode } from 'react';

import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PromptWorkspace } from './PromptWorkspace';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

function harness(options: {library?: unknown; detail?: unknown} = {}) {
  const calls: string[] = [];
  const transport: StudioGraphTransport = {
    async json<T>(url: string, method = 'GET'): Promise<T> {
      calls.push(`${method} ${url}`);
      if (url.endsWith('/prompts')) return (options.library ?? fixture('library.json')) as T;
      if (url.includes('/revisions/') && url.endsWith('/body')) return fixture('revision-1-body.json') as T;
      if (url.includes('/prompts/')) return (options.detail ?? fixture('detail.json')) as T;
      throw new Error(`unexpected ${method} ${url}`);
    },
  };
  return {transport, calls};
}

const renderStrict = (transport: StudioGraphTransport) => render(
  <StrictMode>
    <PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />
  </StrictMode>,
);

afterEach(() => { cleanup(); });

describe('StrictMode effect replay must not discard a successful read', () => {
  it('renders the loaded library under StrictMode', async () => {
    const {transport, calls} = harness();
    renderStrict(transport);

    // The backend really was asked and really answered.
    await waitFor(() => expect(calls.filter(call => call.endsWith('/prompts'))).not.toHaveLength(0));

    // ...so the panel must leave the loading state and show the loaded entries.
    await waitFor(() => {
      expect(document.body.textContent).not.toContain('正在读取 Prompt 列表…');
    }, {timeout: 3000});
    await waitFor(() => {
      expect(screen.getAllByRole('button', {name: /IMAGE/}).length).toBeGreaterThan(0);
    }, {timeout: 3000});
  });

  it('shows the explicit empty state under StrictMode', async () => {
    const {transport} = harness({library: fixture('empty-library.json')});
    renderStrict(transport);
    await waitFor(() => expect(screen.getByText('还没有 Prompt')).toBeTruthy(), {timeout: 3000});
  });

  it('still ignores a read that resolves after the component really unmounts', async () => {
    // The safety property the original cleanup existed for must survive the fix.
    let release: (value: unknown) => void = () => {};
    const gate = new Promise(resolveGate => { release = resolveGate; });
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (url.endsWith('/prompts')) { await gate; return fixture('library.json') as T; }
        throw new Error(`unexpected ${method} ${url}`);
      },
    };
    const view = render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    view.unmount();
    release(undefined);
    await new Promise(resolveTick => setTimeout(resolveTick, 20));
    // No React warning about setting state on an unmounted component, and nothing rendered.
    expect(document.body.textContent).not.toContain('IMAGE ·');
  });
});
