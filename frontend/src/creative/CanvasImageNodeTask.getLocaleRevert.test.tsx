// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3] 行为测试：若渲染改回 getLocale()，切到 en 后标题仍为中文 → 本测试变红。
 * getLocale 被冻结为 'zh-CN'，只有响应式 useLocale() 能让标题变成英文。 */
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
vi.mock('../i18n', async orig => ({ ...(await orig<typeof import('../i18n')>()), getLocale: () => 'zh-CN' as const }));
vi.mock('./StudioMediaExecutionPanel', () => ({ StudioMediaExecutionPanel: () => <p>panel fixture</p> }));
import { setLocale } from '../i18n';
import { CanvasImageNodeTask, type CanvasImageNodeTaskProps } from './CanvasImageNodeTask';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); localStorage.clear(); });

it('title switches to English even when getLocale() is stuck at zh-CN', () => {
  const props = { projectId: 'p', node: { id: 'n1', title: '新生成图片', prompt: 'x', x: 1, y: 2 }, client: {}, production: {},
    canMutate: false, canReview: false, isCurrent: () => true, read: async <T,>(f: () => Promise<T>) => f(), mutate: async <T,>(f: () => Promise<T>) => f() } as unknown as CanvasImageNodeTaskProps;
  render(<CanvasImageNodeTask {...props} />);
  act(() => setLocale('en'));
  expect(screen.getByText(/New generated image/)).toBeTruthy();
});
