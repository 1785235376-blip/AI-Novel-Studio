// @vitest-environment jsdom
// [HERMIA-FE-20261025 VERA-097 W8] 三个面板的错误块：专业模式渲染技术详情，普通模式不渲染，且主文案不含原文
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it } from 'vitest';
import '../i18n';
import { ApiError } from '../api';
import { setApiErrorShellMode } from '../apiErrorMode';
import { AssetError } from './AssetLibraryPanel';
import { ImportError } from './NovelImportPanel';
import { ExportError } from './ExportPanel';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => setApiErrorShellMode('basic'));
const err = () => new ApiError({ status: 404, code: 'HTTP_404', message: '请求的内容不存在或已被删除', message_source: 'fallback', raw_text: 'Not found: /home/u/SECRET.key' });
const render = (el: JSX.Element) => { const h = document.createElement('div'); document.body.append(h); const r = createRoot(h); act(() => r.render(el)); return { h, done: () => { act(() => r.unmount()); h.remove(); } }; };

describe.each([['AssetError', AssetError], ['ImportError', ImportError], ['ExportError', ExportError]] as const)('%s', (_n, C) => {
  it('pro renders technical details', () => {
    setApiErrorShellMode('pro');
    const { h, done } = render(<C error={err()} fallback="失败" />);
    expect(h.querySelector('.api-error-technical')?.textContent).toBe('技术详情：Not found: /home/u/SECRET.key');
    expect(h.querySelector('.novel-error')?.textContent).toBe('请求的内容不存在或已被删除');
    done();
  });
  it('basic hides technical details', () => {
    const { h, done } = render(<C error={err()} fallback="失败" />);
    expect(h.querySelector('.api-error-technical')).toBeNull();
    expect(h.textContent).not.toContain('SECRET');
    done();
  });
});
