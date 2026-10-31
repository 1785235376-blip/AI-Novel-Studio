// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3] IndependentStudioWorkspace 的 denied EmptyState（title/detail 取自源码原文）在 en 下无中文。 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { setLocale } from '../i18n';
import { EmptyState } from '../ui/primitives';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });

it('denied EmptyState copy from the source is English in en and unchanged in zh', () => {
  const src = readFileSync(resolve(process.cwd(), 'src/creative/IndependentStudioWorkspace.tsx'), 'utf8');
  const m = src.match(/\{denied \? <EmptyState title="([^"]+)" detail="([^"]+)" \/>/);
  expect(m).toBeTruthy();
  const [, title, detail] = m!;
  const zh = render(<EmptyState title={title} detail={detail} />);
  expect(zh.container.textContent).toBe(title + detail);
  zh.unmount();
  act(() => setLocale('en'));
  const { container } = render(<EmptyState title={title} detail={detail} />);
  expect(container.textContent).not.toMatch(/[\u4e00-\u9fff]/);
});
