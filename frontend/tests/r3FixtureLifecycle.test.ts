import { EventEmitter } from 'node:events';
import type { Page, Request, Response, Route } from '@playwright/test';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createPageQuiescer } from './e2e/r3-fixture-lifecycle';

afterEach(() => vi.useRealTimers());
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function pageFixture() {
  const events = new EventEmitter(), context = new EventEmitter(), order: string[] = [];
  let closed = false;
  const page = Object.assign(events, {
    context: () => context,
    isClosed: () => closed,
    route: vi.fn(async (_pattern: string, _handler: (route: Route) => Promise<void>) => { order.push('block-new-api'); }),
    close: vi.fn(async () => { order.push('close-page'); closed = true; }),
  });
  return { page, context, order };
}
const request = (path: string, method = 'GET') => ({ url: () => 'http://127.0.0.1:5176' + path,
  method: () => method, response: vi.fn(async () => null) }) as unknown as Request;
function response(request: Request, done = deferred<null>()) {
  const value = { request: () => request, status: () => 200, finished: vi.fn(() => done.promise) } as unknown as Response;
  return { value, done };
}

describe('R3 disposable browser fixture lifecycle (event-contract tests, not browser latency)', () => {
  it('drains existing API readers and closes the page before exact-owned-ID cleanup', async () => {
    const { page, order } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page);
    const pending = request('/api/novels/owned-1/experimental/world/records');
    page.emit('request', pending);
    expect(page.route).not.toHaveBeenCalled();
    let complete = false;
    const cleanup = (async () => { await quiesce(); for (const id of ['owned-1', 'owned-2']) order.push(`delete:${id}`); complete = true; })();
    await Promise.resolve();
    expect(page.route).toHaveBeenCalledWith('**/api/**', expect.any(Function));
    expect(page.close).not.toHaveBeenCalled(); expect(complete).toBe(false);
    page.emit('requestfinished', request('/assets/app.js'));
    expect(page.close).not.toHaveBeenCalled();
    order.push('reader-finished'); page.emit('requestfinished', pending);
    await cleanup;
    expect(order).toEqual(['block-new-api', 'reader-finished', 'close-page', 'delete:owned-1', 'delete:owned-2']);
    expect(page.close).toHaveBeenCalledWith({ runBeforeUnload: false });
    expect(page.listenerCount('request')).toBe(0); expect(page.listenerCount('requestfinished')).toBe(0);
  });
  it('blocks cleanup on timeout, retaining sanitized method/path/status/age diagnostics', async () => {
    vi.useFakeTimers();
    const { page, context, order } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page, 100);
    const pending = request('/api/novels/private-title/chapters?q=secret-text&token=private-token#private-fragment', 'PUT');
    page.emit('request', pending); page.emit('response', response(pending).value);
    const cleanup = quiesce().then(() => { order.push('delete:owned-1'); });
    const failed = expect(cleanup).rejects.toThrow('page API requests did not drain');
    await vi.advanceTimersByTimeAsync(101); await failed;
    const diagnostic = quiesce.diagnostics();
    expect(diagnostic.pending[0]).toMatchObject({ method: 'PUT', path: '/api/novels/:id/chapters', status: 200, phase: 'awaiting_response_end', age_ms: 101 });
    expect(JSON.stringify(diagnostic)).not.toMatch(/private-|secret-text|127\.0\.0\.1|token=/);
    expect(page.close).not.toHaveBeenCalled(); expect(order).not.toContain('delete:owned-1');
    expect(page.listenerCount('request')).toBe(0); expect(context.listenerCount('requestfinished')).toBe(0);
  });
  it('requires page close to succeed before cleanup continues', async () => {
    const { page, order } = pageFixture();
    page.close.mockRejectedValueOnce(new Error('page close failed'));
    const quiesce = createPageQuiescer(page as unknown as Page);
    await expect(quiesce().then(() => { order.push('delete:owned-1'); })).rejects.toThrow('page close failed');
    expect(order).not.toContain('delete:owned-1');
  });
  it('reconciles a reload request whose completion is emitted on Context without a Page association', async () => {
    const { page, context } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page);
    const oldDocument = request('/api/novels/owned/chapters'); page.emit('request', oldDocument);
    const cleanup = quiesce(); await Promise.resolve();
    context.emit('requestfinished', oldDocument);
    await cleanup;
    expect(quiesce.diagnostics().pending_count).toBe(0);
    expect(page.close).toHaveBeenCalledOnce(); expect(context.listenerCount('requestfinished')).toBe(0);
  });
  it('does not let another page request with the same URL retire the tracked reader', async () => {
    const { page, context } = pageFixture();
    const quiesce = createPageQuiescer(page as unknown as Page);
    const tracked = request('/api/novels/owned/chapters'); page.emit('request', tracked);
    const cleanup = quiesce(); await Promise.resolve();
    context.emit('requestfinished', request('/api/novels/owned/chapters'));
    expect(quiesce.diagnostics().pending_count).toBe(1); expect(page.close).not.toHaveBeenCalled();
    context.emit('requestfinished', tracked); await cleanup;
  });
  it('waits for full response completion, not just headers, when reconciling a missing Page event', async () => {
    const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page);
    const pending = request('/api/novels/owned/chapters'), complete = response(pending);
    vi.mocked(pending.response).mockResolvedValue(complete.value);
    page.emit('request', pending);
    const cleanup = quiesce(); await Promise.resolve(); await Promise.resolve();
    expect(page.close).not.toHaveBeenCalled();
    complete.done.resolve(null); await cleanup;
    expect(page.close).toHaveBeenCalledOnce();
  });
  it('passively drains before a deliberate reload without intercepting business requests or closing', async () => {
    const { page, context } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page);
    const pending = request('/api/novels/owned/chapters'); page.emit('request', pending);
    let canReload = false; const drain = quiesce.drain().then(() => { canReload = true; });
    await Promise.resolve(); expect(canReload).toBe(false);
    expect(page.route).not.toHaveBeenCalled(); expect(page.close).not.toHaveBeenCalled();
    context.emit('requestfinished', pending); await drain;
    expect(canReload).toBe(true); await quiesce();
  });
  it('does not mistake a browser-side request abort for server completion', async () => {
    vi.useFakeTimers(); const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page, 100);
    const pending = request('/api/novels/owned/chapters'); page.emit('request', pending); page.emit('requestfailed', pending);
    const cleanup = quiesce(), failed = expect(cleanup).rejects.toThrow('server_completion_unknown');
    await vi.advanceTimersByTimeAsync(101); await failed;
    expect(page.close).not.toHaveBeenCalled();
  });
  it('retires a newly intercepted request only after its abort acknowledgement', async () => {
    const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page);
    const prior = request('/api/novels/owned/chapters'); page.emit('request', prior);
    const cleanup = quiesce(); await Promise.resolve();
    const late = request('/api/novels/owned/media-tasks'), aborted = deferred<void>();
    page.emit('request', late);
    const route = { request: () => late, abort: vi.fn(() => aborted.promise) } as unknown as Route;
    const abort = page.route.mock.calls[0][1](route);
    page.emit('requestfailed', late); page.emit('requestfinished', prior);
    await Promise.resolve(); expect(page.close).not.toHaveBeenCalled();
    aborted.resolve(); await abort; await cleanup;
    expect(route.abort).toHaveBeenCalledWith('aborted');
    expect(quiesce.diagnostics().blocked_before_dispatch).toBe(1);
  });
  it('handles request events arriving after an acknowledged pre-dispatch abort', async () => {
    const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page);
    const prior = request('/api/novels/owned/chapters'); page.emit('request', prior);
    const cleanup = quiesce(); await Promise.resolve();
    const late = request('/api/novels/owned/media-tasks');
    const route = { request: () => late, abort: vi.fn(async () => {}) } as unknown as Route;
    await page.route.mock.calls[0][1](route);
    page.emit('request', late); page.emit('requestfailed', late);
    expect(quiesce.diagnostics().pending_count).toBe(1);
    page.emit('requestfinished', prior); await cleanup;
    expect(page.close).toHaveBeenCalledOnce();
  });
  it('retains a failed response-completion probe as a blocker', async () => {
    vi.useFakeTimers(); const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page, 100);
    const pending = request('/api/novels/owned/chapters'), result = response(pending);
    page.emit('request', pending); page.emit('response', result.value);
    const cleanup = quiesce(), failed = expect(cleanup).rejects.toThrow('server_completion_unknown');
    result.done.reject(new Error('target closed with private URL'));
    await vi.advanceTimersByTimeAsync(101); await failed;
    expect(page.close).not.toHaveBeenCalled(); expect(JSON.stringify(quiesce.diagnostics())).not.toContain('private URL');
  });
  it('bounds diagnostics while retaining every unresolved request', async () => {
    vi.useFakeTimers(); const { page } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page, 100);
    for (let n = 0; n < 25; n++) page.emit('request', request(`/api/novels/private-${n}/chapters`));
    const cleanup = quiesce(), failed = expect(cleanup).rejects.toThrow('did not drain');
    await vi.advanceTimersByTimeAsync(101); await failed;
    expect(quiesce.diagnostics()).toMatchObject({ pending_count: 25, diagnostics_truncated: true });
    expect(quiesce.diagnostics().pending).toHaveLength(20);
  });
  it('shares one teardown promise and counts duplicate Page/Context completions once', async () => {
    const { page, context } = pageFixture(); const quiesce = createPageQuiescer(page as unknown as Page);
    const pending = request('/api/novels/owned/chapters'); page.emit('request', pending);
    const first = quiesce(); expect(quiesce()).toBe(first);
    context.emit('requestfinished', pending); page.emit('requestfinished', pending);
    await first;
    expect(page.route).toHaveBeenCalledOnce(); expect(page.close).toHaveBeenCalledOnce();
    expect(quiesce.diagnostics().completed_requests).toBe(1);
  });
  it('rejects an invalid unbounded timeout', () => {
    const { page } = pageFixture();
    for (const timeout of [0, -1, Infinity, NaN]) expect(() => createPageQuiescer(page as unknown as Page, timeout)).toThrow('positive and bounded');
  });
});
