// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MediaCardViewport } from './MediaCardViewport';
import type { CanvasDefinition } from './studioCanvasViewClient';
class TestPointerEvent extends MouseEvent { readonly pointerId: number; constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; } }
beforeEach(() => vi.stubGlobal('PointerEvent', TestPointerEvent));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const definition = (): CanvasDefinition => ({ schema_version: 1, title: 'Media', cards: [{ id: 'Card', position: { x: 10, y: 20 } }], viewport: { x: 0, y: 0, zoom: 2 } });
function props() { return { definition: definition(), states: new Map(), selected: '', query: '', owner: {}, disabled: false, isCurrent: () => true, onSelect: vi.fn(), onChange: vi.fn(), onSize: vi.fn() }; }
const area = () => screen.getByLabelText('媒体卡片视口');
function down(target: Element, x = 0, y = 0) { fireEvent.pointerDown(target, { button: 0, pointerId: 1, clientX: x, clientY: y }); }
function move(x: number, y: number) { fireEvent.pointerMove(area(), { pointerId: 1, clientX: x, clientY: y }); }
function up() { fireEvent.pointerUp(area(), { pointerId: 1 }); }
it('previews card movement at zoom and commits exactly once on release', () => {
 const p = props(), original = structuredClone(p.definition); render(<MediaCardViewport {...p} />); down(screen.getByText('Card')); move(100, 60);
 expect(p.onChange).not.toHaveBeenCalled(); expect((document.querySelector('[data-media-card]') as HTMLElement).style.left).toBe('120px');
 up(); up(); expect(p.onChange).toHaveBeenCalledTimes(1); expect(p.onChange.mock.calls[0][0].cards[0].position).toEqual({ x: 60, y: 50 }); expect(p.definition).toEqual(original);
});
it('pans blank space in screen coordinates and supports keyboard movement', () => { const p = props(); render(<MediaCardViewport {...p} />); down(area()); move(50, -40); up(); expect(p.onChange.mock.calls[0][0].viewport).toEqual({ x: 50, y: -40, zoom: 2 });
 fireEvent.keyDown(screen.getByText('Card'), { key: 'ArrowRight', shiftKey: true }); expect(p.onChange.mock.calls[1][0].cards[0].position.x).toBe(74);
 fireEvent.keyDown(area(), { key: 'ArrowDown' }); expect(p.onChange.mock.calls[2][0].viewport.y).toBe(16);
});
it.each(['escape', 'cancel', 'capture loss', 'permission ABA', 'source', 'owner', 'current', 'unmount'])('cancels in-flight gestures across %s', mode => {
 const p = props(); let current = true; p.isCurrent = () => current; const view = render(<MediaCardViewport {...p} />); down(screen.getByText('Card')); move(100, 60);
 if (mode === 'escape') fireEvent.keyDown(area(), { key: 'Escape' });
 if (mode === 'cancel') fireEvent.pointerCancel(area(), { pointerId: 1 });
 if (mode === 'capture loss') fireEvent.lostPointerCapture(area(), { pointerId: 1 });
 if (mode === 'permission ABA') { view.rerender(<MediaCardViewport {...p} disabled />); view.rerender(<MediaCardViewport {...p} />); }
 if (mode === 'source') view.rerender(<MediaCardViewport {...p} definition={definition()} />);
 if (mode === 'owner') view.rerender(<MediaCardViewport {...p} owner={{}} />);
 if (mode === 'current') current = false;
 if (mode === 'unmount') view.unmount(); else up(); expect(p.onChange).not.toHaveBeenCalled();
});
it('captures only explicit Ctrl-wheel and preserves the anchor using original zoom geometry', () => { const p = props(); render(<MediaCardViewport {...p} />);
 const ordinary = new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: -10, clientX: 100, clientY: 80 }); fireEvent(area(), ordinary); expect(ordinary.defaultPrevented).toBe(false); expect(p.onChange).not.toHaveBeenCalled();
 const zoom = new WheelEvent('wheel', { bubbles: true, cancelable: true, ctrlKey: true, deltaY: -10, clientX: 100, clientY: 80 }); fireEvent(area(), zoom); expect(zoom.defaultPrevented).toBe(true);
 const viewport = p.onChange.mock.calls[0][0].viewport; expect(viewport.zoom).toBeCloseTo(2.2); expect((100 - viewport.x) / viewport.zoom).toBeCloseTo(50); expect((80 - viewport.y) / viewport.zoom).toBeCloseTo(40);
});

// These owner/gesture tests do not exercise bitmap pixels; the dedicated minimap test checks drawing calls.
beforeEach(() => { vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null); });
afterEach(() => vi.restoreAllMocks());
