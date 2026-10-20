// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MediaCanvasGroupTools } from './MediaCanvasGroupTools';
import type { CanvasDefinition } from './studioCanvasViewClient';
afterEach(cleanup);
function props() { const definition: CanvasDefinition = { schema_version: 1, title: 'Display', cards: [{ id: 'Card', position: { x: 0, y: 0 } }], viewport: { x: 0, y: 0, zoom: 1 }, groups: [{ id: 'Group', name: 'Group', card_ids: [], collapsed: false }] }; return { definition, selectedCard: 'Card', owner: {}, disabled: false, isCurrent: () => true, onChange: vi.fn() }; }
it('assigns a selected card and explicitly changes collapse without starting any execution', () => { const p = props(); render(<MediaCanvasGroupTools {...p} />); fireEvent.change(screen.getByLabelText('当前显示组'), { target: { value: 'Group' } }); fireEvent.click(screen.getByText('将当前卡片移入所选组')); expect(p.onChange.mock.calls[0][0].groups[0].card_ids).toEqual(['Card']); fireEvent.click(screen.getByText('折叠所选组')); expect(p.onChange.mock.calls[1][0].groups[0].collapsed).toBe(true); });
it('keeps cards when dissolving and rejects stale selection callbacks after owner change', () => { const p = props(), v = render(<MediaCanvasGroupTools {...p} />); fireEvent.change(screen.getByLabelText('当前显示组'), { target: { value: 'Group' } }); const button = screen.getByText('解散所选组，保留卡片'), key = Object.keys(button).find(k => k.startsWith('__reactProps$'))!, retained = (button as any)[key].onClick;
 fireEvent.click(button); expect(p.onChange.mock.calls[0][0].cards).toEqual(p.definition.cards); expect(p.onChange.mock.calls[0][0]).not.toHaveProperty('groups'); p.onChange.mockClear(); v.rerender(<MediaCanvasGroupTools {...p} owner={{}} />); retained(); expect(p.onChange).not.toHaveBeenCalled(); });
