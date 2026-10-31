// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 zoom] 节点图缩放按钮/读数用固定键：en 为 Zoom out graph / Graph zoom / Zoom in graph；zh 不变。 */
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { setLocale } from '../i18n';
import { GraphCanvas, type GraphCanvasProps } from './GraphCanvas';
import { modelCatalog } from './studioGraphModel.testFixtures';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });
const props = { definition: { schema_version: 1, title: 'g', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } }, nodeDefinitions: [], selectedNodeIds: [],
  removalDefinitions: modelCatalog().definitions, onDefinitionChange: () => {}, onSelectionChange: () => {} } as unknown as GraphCanvasProps;
const names = (c: HTMLElement) => [...c.querySelectorAll('.graph-canvas__toolbar > [aria-label]')].map(e => e.getAttribute('aria-label')).filter(v => /zoom|缩|放大/i.test(v!));
it.each([['en', ['Zoom out graph', 'Graph zoom', 'Zoom in graph']], ['zh-CN', ['缩小节点图', '节点图缩放', '放大节点图']]] as const)('%s graph zoom labels', (loc, want) => {
  act(() => setLocale(loc));
  const { container } = render(<GraphCanvas {...props} />);
  expect(names(container)).toEqual(want);
});
