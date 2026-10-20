// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MediaCanvasMiniMap } from './MediaCanvasMiniMap';
import { mediaOverview } from './mediaCanvasGeometry';
import type { CanvasDefinition } from './studioCanvasViewClient';
const definition = (): CanvasDefinition => ({ schema_version: 1, title: 'Map', cards: Array.from({ length: 1000 }, (_, i) => ({ id: `Card_${i}`, position: { x: i * 80, y: i * 60 } })), viewport: { x: 0, y: 0, zoom: 1 } });
const ctx = { clearRect: vi.fn(), fillRect: vi.fn(), strokeRect: vi.fn(), fillStyle: '', strokeStyle: '', lineWidth: 1 };
beforeEach(() => { vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as any); vi.clearAllMocks(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function props() { return { definition: definition(), size: { width: 800, height: 480 }, owner: {}, disabled: false, isCurrent: () => true, onChange: vi.fn() }; }
it('draws all 1000 bounded locations into one bitmap and outlines the current camera', () => { const p = props(); render(<MediaCanvasMiniMap {...p} />); expect(ctx.fillRect).toHaveBeenCalledTimes(1001); expect(ctx.strokeRect).toHaveBeenCalledTimes(1); expect(document.querySelectorAll('canvas')).toHaveLength(1); expect(mediaOverview(p.definition, 800, 480).right).toBeGreaterThan(79920); });
it('maps pointer location to world center and supports explicit keyboard navigation', () => { const p = props(); render(<MediaCanvasMiniMap {...p} />); const map = screen.getByLabelText('媒体画布缩略导航'); vi.spyOn(map, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 200, height: 120 } as DOMRect);
 fireEvent.click(map, { clientX: 100, clientY: 60 }); const view = p.onChange.mock.calls[0][0].viewport, bounds = mediaOverview(p.definition, 800, 480); expect(view.x).toBeCloseTo(400 - (bounds.left + bounds.right) / 2); expect(view.y).toBeCloseTo(240 - (bounds.top + bounds.bottom) / 2);
 fireEvent.keyDown(map, { key: 'Enter' }); expect(p.onChange.mock.calls[1][0].viewport).toEqual(view);
});
it('rejects a retained navigation callback after disabled ABA and unmount', () => { const p = props(); const v = render(<MediaCanvasMiniMap {...p} />); const node = screen.getByLabelText('媒体画布缩略导航'), key = Object.keys(node).find(k => k.startsWith('__reactProps$'))!, retained = (node as any)[key].onKeyDown;
 v.rerender(<MediaCanvasMiniMap {...p} disabled />); v.rerender(<MediaCanvasMiniMap {...p} />); retained({ key: 'Enter', preventDefault() {} }); v.unmount(); retained({ key: 'Enter', preventDefault() {} }); expect(p.onChange).not.toHaveBeenCalled();
});
