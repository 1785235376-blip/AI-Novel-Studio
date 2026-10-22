// [HERMIA-FE-20261022 U2] 分格模板 / 气泡样式 / 双画布
// @vitest-environment jsdom
import {describe, it, expect, vi} from 'vitest';
import {render, screen, fireEvent} from '@testing-library/react';
import {ComicView, bubbleBounds} from './ComicView';
import {COMIC_TEMPLATES, remapCells} from './comicTemplates';
import {DualCanvas} from '../canvas/DualCanvas';

describe('comic templates', () => {
  it('has varied, non-identical layouts', () => {
    expect(COMIC_TEMPLATES.length).toBeGreaterThanOrEqual(9);
    expect(new Set(COMIC_TEMPLATES.map(t => t.rows + t.cols + t.panels.map(p => p.area + (p.clip || '') + (p.cls || '')).join())).size).toBe(COMIC_TEMPLATES.length);
    expect(COMIC_TEMPLATES.some(t => t.panels.some(p => p.clip))).toBe(true);
    expect(COMIC_TEMPLATES.some(t => t.panels.some(p => p.cls === 'inset'))).toBe(true);
  });
  it('remap keeps bubbles when panels shrink', () => {
    const b = (id: string) => ({id, text: id, x: 0, y: 0, w: 40, kind: 'speech' as const, tail: 'bl' as const});
    expect(remapCells([[b('a')], [b('b')], [b('c')]], 2).flat().map(x => x.id)).toEqual(['a', 'b', 'c']);
  });
});

describe('ComicView', () => {
  it('switches template per page, adds styled bubble, edits and deletes it without fetch', () => {
    const f = vi.spyOn(globalThis, 'fetch' as any);
    const {container} = render(<ComicView chrome={null} onBack={() => {}} onGen={() => {}} />);
    fireEvent.click(container.querySelector('[data-tpl="irregular6"]')!);
    expect(container.querySelectorAll('.comic-cell').length).toBe(6);
    fireEvent.change(screen.getByLabelText('新气泡样式'), {target: {value: 'thought'}});
    fireEvent.click(container.querySelector('#comicBubble')!);
    expect(container.querySelector('.bub--thought')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: '喊叫'}));
    expect(container.querySelector('.bub--shout')).toBeTruthy();
    fireEvent.click(container.querySelector('[data-tail="r"]')!);
    expect(container.querySelector('.bub-tail--r')).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/竖排文字/));
    expect(container.querySelector('.bub--v')).toBeTruthy();
    fireEvent.click(container.querySelector('[data-bubble-delete]')!);
    expect(container.querySelector('.bub')).toBeNull();
    expect(f).not.toHaveBeenCalled();
  });
});

describe('DualCanvas', () => {
  it('shows creation + execution side by side and toggles', () => {
    render(<DualCanvas scope="t-dual" />);
    expect(screen.getByLabelText('创作画布', {selector: 'div.dual-cv__pane'})).toBeTruthy();
    expect(screen.getByLabelText('执行画布', {selector: 'div.dual-cv__pane'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: '执行画布'}));
    expect(document.querySelector('[data-dual-mode="execution"]')).toBeTruthy();
  });
});

describe('bubble clamp (Vera must-fix)', () => {
  it('clamps by real bubble size so wide bubbles stay inside the cell', () => {
    expect(bubbleBounds(200, 100, 150, 40)).toEqual({maxX: 25, maxY: 60});
    expect(bubbleBounds(100, 100, 120, 20).maxX).toBe(0);
  });
  it('keyboard nudge stops at cell edge minus bubble width', () => {
    const {container} = render(<ComicView chrome={null} onBack={() => {}} onGen={() => {}} />);
    fireEvent.click(container.querySelector('#comicBubble')!);
    const cell = container.querySelector('.comic-cell') as HTMLElement, bub = container.querySelector('.bub') as HTMLElement;
    cell.getBoundingClientRect = () => ({width: 200, height: 100, left: 0, top: 0, right: 200, bottom: 100, x: 0, y: 0, toJSON() {}}) as DOMRect;
    bub.getBoundingClientRect = () => ({width: 150, height: 40, left: 0, top: 0, right: 150, bottom: 40, x: 0, y: 0, toJSON() {}}) as DOMRect;
    for (let i = 0; i < 40; i++) fireEvent.keyDown(bub, {key: 'ArrowRight'});
    expect(parseFloat(bub.style.left)).toBeLessThanOrEqual(25);
  });
});
