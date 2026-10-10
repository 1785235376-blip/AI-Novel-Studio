// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorldPanel } from './WorldPanel';
import { experimentalClient } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('world continuity result accessibility', () => {
  it('exposes successful deterministic findings as a named native region', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/world/continuity') ? { verification: 'DETERMINISTIC_RULES', items: [] } : { items: [] }), { status: 200 })));
    render(<WorldPanel client={experimentalClient('novel', { sessionToken: '' })} />);
    await waitFor(() => expect((screen.getByRole('button', { name: '检查世界连续性' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '检查世界连续性' }));
    const region = await screen.findByRole('region', { name: '世界连续性结果' });
    expect(region.tagName).toBe('SECTION'); expect(region.textContent).toContain('DETERMINISTIC_RULES'); expect(region.textContent).toContain('0 项发现');
    expect(screen.getByText('确定性检查已完成')).toBeTruthy();
  });
});
