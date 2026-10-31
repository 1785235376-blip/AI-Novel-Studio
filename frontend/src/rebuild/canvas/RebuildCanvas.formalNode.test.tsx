// @vitest-environment jsdom
// Local selection fences only; no backend, provider or media operation.
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RebuildCanvas, type CvNode } from './RebuildCanvas';

const nodes: CvNode[] = ['node-a', 'node-b'].map((id, index) => ({ id, t: 'image_generate', title: id, prompt: 'Light', x: index * 200, y: 0 }));
let guards: (() => boolean)[];
function select(id: string) {
  const element = document.querySelector(`[data-node-id="${id}"]`)!;
  fireEvent.pointerDown(element, { button: 0, clientX: 40, clientY: 40 });
  fireEvent.pointerUp(element, { button: 0, clientX: 40, clientY: 40 });
}
function mount() {
  return render(<RebuildCanvas kind="image" scope="formal-project" seed={{ nodes, edges: [] }}
    renderImageTaskBinding={(_node, _current, _revision, formal) => { if (formal) guards.push(formal); return null; }} />);
}
beforeEach(() => { localStorage.clear(); guards = []; vi.stubGlobal('PointerEvent', MouseEvent); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('retires a retained formal selection on A/B/A without changing the legacy source guard', () => {
  mount(); select('node-a'); const first = guards.at(-1)!; expect(first()).toBe(true);
  select('node-b'); select('node-a'); expect(first()).toBe(false); expect(guards.at(-1)!()).toBe(true);
});
it('retires formal prompt confirmation after prompt A/B/A', () => {
  const view = mount(); select('node-a'); const first = guards.at(-1)!;
  const input = view.getByLabelText('本次提示词');
  fireEvent.change(input, { target: { value: 'Other' } }); fireEvent.change(input, { target: { value: 'Light' } });
  expect(first()).toBe(false); expect(guards.at(-1)!()).toBe(true);
});
it('retires a captured position after dragging and after unmount', () => {
  const view = mount(); select('node-a'); const first = guards.at(-1)!;
  const svg = view.getByRole('application'); const node = document.querySelector('[data-node-id="node-a"]')!;
  fireEvent.pointerDown(node, { button: 0, clientX: 40, clientY: 40 });
  fireEvent.pointerMove(svg, { clientX: 80, clientY: 80 }); fireEvent.pointerUp(svg);
  expect(first()).toBe(false); const next = guards.at(-1)!; expect(next()).toBe(true);
  view.unmount(); expect(next()).toBe(false);
});
