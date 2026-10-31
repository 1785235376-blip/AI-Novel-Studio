// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-EN P3] 节点说明行的默认标题随语言切换响应式重渲染；不得在渲染中读非响应式 getLocale()。 */
import { act, cleanup, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { setLocale } from '../i18n';
import { CanvasImageNodeTask, type CanvasImageNodeTaskProps } from './CanvasImageNodeTask';
vi.mock('./StudioMediaExecutionPanel', () => ({ StudioMediaExecutionPanel: () => <p>panel fixture</p> }));
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); localStorage.clear(); });

it('source uses the reactive locale hook, not getLocale()', () => {
  const src = readFileSync(resolve(process.cwd(), 'src/creative/CanvasImageNodeTask.tsx'), 'utf8');
  expect(src).not.toMatch(/\bgetLocale\s*\(/);
  expect(src).toMatch(/useLocale\(\)/);
});

it('default node title follows a locale switch after mount', () => {
  const props = { projectId: 'p', node: { id: 'n1', title: '新生成图片', prompt: 'x', x: 1, y: 2 }, client: {}, production: {},
    canMutate: false, canReview: false, isCurrent: () => true, read: async <T,>(f: () => Promise<T>) => f(), mutate: async <T,>(f: () => Promise<T>) => f() } as unknown as CanvasImageNodeTaskProps;
  render(<CanvasImageNodeTask {...props} />);
  expect(screen.getByText(/新生成图片/)).toBeTruthy();
  act(() => setLocale('en'));
  expect(screen.getByText(/New generated image/)).toBeTruthy();
  expect(screen.queryByText(/新生成图片/)).toBeNull();
});
