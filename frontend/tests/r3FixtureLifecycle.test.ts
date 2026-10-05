import { EventEmitter } from 'node:events';
import type { Page, Request } from '@playwright/test';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createPageQuiescer } from './e2e/r3-fixture-lifecycle';
afterEach(() => vi.useRealTimers());
function pageFixture() {
  const events = new EventEmitter(), order: string[] = [];
  let closed = false;
  const page = Object.assign(events, {
    isClosed: () => closed,
    route: vi.fn(async () => { order.push('block-new-api'); }),
    close: vi.fn(async () => { order.push('close-page'); closed = true; }),
  });
  return { page, order };
}
const request = (path: string) => ({ url: () => 'http://127.0.0.1:5176' + path }) as Request;
describe('R3 disposable browser fixture lifecycle', () => {
  it('drains existing API readers and closes the page before exact-owned-ID cleanup', async () => {
    const { page, order } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page);
    const pending = request('/api/novels/owned-1/experimental/world/records');
    page.emit('request', pending);
    expect(page.route).not.toHaveBeenCalled(); // No business-request interception.
    let complete = false;
    const cleanup = (async () => {
      await quiesce();
      for (const id of ['owned-1', 'owned-2']) order.push(`delete:${id}`);
      complete = true;
    })();
    await Promise.resolve();
    expect(page.route).toHaveBeenCalledWith('**/api/**', expect.any(Function));
    expect(page.close).not.toHaveBeenCalled(); expect(complete).toBe(false);
    const unrelated = request('/assets/app.js');
    page.emit('requestfinished', unrelated);
    expect(page.close).not.toHaveBeenCalled();
    order.push('reader-finished'); page.emit('requestfinished', pending);
    await cleanup;
    expect(order).toEqual(['block-new-api', 'reader-finished', 'close-page', 'delete:owned-1', 'delete:owned-2']);
    expect(page.close).toHaveBeenCalledWith({ runBeforeUnload: false });
    expect(page.listenerCount('request')).toBe(0); expect(page.listenerCount('requestfinished')).toBe(0);
  });
  it('blocks cleanup on a drain timeout rather than deleting under live readers', async () => {
    vi.useFakeTimers();
    const { page, order } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page, 100);
    page.emit('request', request('/api/novels/owned-1/chapters'));
    const cleanup = quiesce().then(() => { order.push('delete:owned-1'); });
    const failed = expect(cleanup).rejects.toThrow('page API requests did not drain');
    await vi.advanceTimersByTimeAsync(101); await failed;
    expect(page.close).not.toHaveBeenCalled(); expect(order).not.toContain('delete:owned-1');
    expect(page.listenerCount('request')).toBe(0);
  });
  it('requires the page close to succeed before cleanup continues', async () => {
    const { page, order } = pageFixture();
    page.close.mockRejectedValueOnce(new Error('page close failed'));
    const quiesce = createPageQuiescer(page as unknown as Page);
    await expect(quiesce().then(() => { order.push('delete:owned-1'); })).rejects.toThrow('page close failed');
    expect(order).not.toContain('delete:owned-1');
  });
});
