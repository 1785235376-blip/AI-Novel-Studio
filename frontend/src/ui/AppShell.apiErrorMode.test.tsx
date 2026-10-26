// @vitest-environment jsdom
// [HERMIA-FE-20261025 P1-ERR] AppShell 将外壳模式同步给 apiErrorView：只有专业模式返回技术详情
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { AppShell } from './AppShell';
import { ApiError, apiErrorView } from '../api';
import { getApiErrorShellMode, setApiErrorShellMode } from '../apiErrorMode';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => setApiErrorShellMode('basic'));
const props = { onModuleChange: vi.fn(), scope: { workspace: 'w', project: 'p', storyline: 's', branch: 'b' }, actor: '作者', sidebar: 'n', main: 'm', inspector: 'i', status: 's', module: 'NOVEL' as any };
const err = new ApiError({ status: 500, code: 'HTTP_ERROR', message: '服务暂时出错，请稍后重试', message_source: 'fallback', raw_text: 'boom trace' });

it('syncs shell mode and gates technical details', () => {
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  act(() => root.render(<AppShell {...props} shellMode="pro" />));
  expect(getApiErrorShellMode()).toBe('pro');
  expect(apiErrorView(err).technical).toBe('boom trace');
  act(() => root.render(<AppShell {...props} shellMode="basic" />));
  expect(getApiErrorShellMode()).toBe('basic');
  expect(apiErrorView(err).technical).toBeUndefined();
  expect(apiErrorView(err).message).not.toMatch(/boom/);
  act(() => root.unmount()); host.remove();
});
