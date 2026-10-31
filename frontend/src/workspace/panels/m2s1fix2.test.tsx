// @vitest-environment jsdom
// [HERMIA-FE-20261024 M2-s1fix2] sent reference nodes form a non-overlapping grid; the first ones stay in view.
import {cleanup, render} from '@testing-library/react';
import {afterEach, beforeEach, expect, it} from 'vitest';
import {ExecutionCanvasPanel} from './studioPreviewPanels';
import {linkToExecution, LINK_DX} from '../../rebuild/canvas/DualCanvas';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
beforeEach(() => localStorage.clear());
afterEach(cleanup);
const node: CvNode = {id: 'a', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const W = 186, H = 60; // rendered node box (180 + border/port), measured in Chrome (m2s1fix-browser.json)

it('9 sends: pairwise non-overlapping (with ≥10px gaps); first 3 inside 320×280; first 9 inside a 750×449 real panel (1366 layout)', () => {
  expect(LINK_DX).toBeGreaterThanOrEqual(W + 10);
  for (let i = 0; i < 9; i++) linkToExecution('n1', {...node, id: `a${i}`});
  const g = JSON.parse(localStorage.getItem(canvasStorageKey('video', 'n1'))!);
  render(<ExecutionCanvasPanel novelId="n1" revision={1} />);
  const [, vx, vy, k] = /translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+)\)/.exec(document.querySelector('svg g[transform]')!.getAttribute('transform')!)!.map(Number);
  const rects = [...document.querySelectorAll('[data-node-id]')].map(el => {
    const [, x, y] = /translate\(([-\d.]+),([-\d.]+)\)/.exec(el.getAttribute('transform')!)!.map(Number);
    return {l: vx + x * k, t: vy + y * k, r: vx + x * k + W * k, b: vy + y * k + H * k};
  });
  expect(rects).toHaveLength(9); expect(g.nodes).toHaveLength(9);
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], c = rects[j];
    const overlap = a.l < c.r + 10 && c.l < a.r + 10 && a.t < c.b + 10 && c.t < a.b + 10;
    expect(overlap, `nodes ${i} and ${j} overlap`).toBe(false);
  }
  const inside = (r: typeof rects[0], w: number, h: number) => r.l >= 0 && r.t >= 0 && r.r <= w && r.b <= h;
  rects.slice(0, 3).forEach(r => expect(inside(r, 320, 280)).toBe(true));
  rects.forEach(r => expect(inside(r, 750, 449)).toBe(true));
});
