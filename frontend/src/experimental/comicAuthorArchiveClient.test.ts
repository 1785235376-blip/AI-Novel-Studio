// @vitest-environment jsdom
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { readAuthorAttempt, saveAuthorAttempt, withAuthorAttempt } from './comicAuthorArchiveClient';
beforeEach(() => { localStorage.clear(); });
afterEach(() => vi.restoreAllMocks());
it('holds cross-tab admission through restore and rereads durable identity under the lock', async () => {
  const tails = new Map<string, Promise<unknown>>();
  const request = vi.fn((name: string, work: () => Promise<unknown>) => { const result = (tails.get(name) || Promise.resolve()).then(work); tails.set(name, result.catch(() => {})); return result; });
  Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
  let finish: () => void = () => {}; const hold = new Promise<void>(resolve => { finish = resolve; });
  const keys: string[] = [];
  const first = withAuthorAttempt('a'.repeat(64), '1'.repeat(32), undefined, () => true, async key => { keys.push(key); await hold; return 'first'; });
  const second = withAuthorAttempt('a'.repeat(64), '2'.repeat(32), undefined, () => true, async key => { keys.push(key); return 'replay'; });
  await vi.waitFor(() => expect(keys).toEqual(['1'.repeat(32)]));
  expect(readAuthorAttempt('a'.repeat(64))?.status).toBe('PENDING'); finish();
  expect(await Promise.all([first, second])).toEqual(['first', 'replay']); expect(keys).toEqual(['1'.repeat(32), '1'.repeat(32)]);
  expect(readAuthorAttempt('a'.repeat(64))?.status).toBe('COMPLETED');
  expect(request.mock.calls.some(([name]) => name === `comic-author-restore:${'a'.repeat(64)}`)).toBe(true);
});
it('does not dispatch a queued restore after its owner is retired', async () => {
  Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: (_name: string, work: () => Promise<unknown>) => Promise.resolve().then(work) } });
  const work = vi.fn(); await expect(withAuthorAttempt('a'.repeat(64), '1'.repeat(32), undefined, () => false, work)).rejects.toThrow(/范围已变化/); expect(work).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0);
});

it('rejects stale explicit new-copy intent after another tab has persisted an unknown attempt', async () => {
  const tails = new Map<string, Promise<unknown>>();
  Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: (name: string, work: () => Promise<unknown>) => { const result = (tails.get(name) || Promise.resolve()).then(work); tails.set(name, result.catch(() => {})); return result; } } });
  const digest = 'a'.repeat(64), prior = '1'.repeat(32), tabBKey = '2'.repeat(32), tabAKey = '3'.repeat(32);
  saveAuthorAttempt(digest, prior, 'COMPLETED');
  // Both tabs inspected this completed identity; B submits first and loses its response.
  let lose: () => void = () => {}; const lost = new Promise<void>(resolve => { lose = resolve; });
  const tabB = withAuthorAttempt(digest, tabBKey, prior, () => true, async () => { await lost; throw new Error('Lost acknowledgement'); });
  const rejectedB = expect(tabB).rejects.toThrow('Lost acknowledgement');
  await vi.waitFor(() => expect(readAuthorAttempt(digest)).toMatchObject({ request_key: tabBKey, status: 'PENDING' }));
  const tabAPost = vi.fn();
  const tabA = withAuthorAttempt(digest, tabAKey, prior, () => true, tabAPost);
  const rejectedA = expect(tabA).rejects.toThrow(/已有恢复尝试已变化或结果未知/);
  lose(); await Promise.all([rejectedB, rejectedA]);
  expect(tabAPost).not.toHaveBeenCalled();
  expect(readAuthorAttempt(digest)).toMatchObject({ request_key: tabBKey, status: 'PENDING' });
});
it('rejects stale explicit new-copy intent when another tab completed a different predecessor', async () => {
  Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: (_name: string, work: () => Promise<unknown>) => Promise.resolve().then(work) } });
  const digest = 'a'.repeat(64), inspectedPrior = '1'.repeat(32), changedPrior = '2'.repeat(32);
  saveAuthorAttempt(digest, changedPrior, 'COMPLETED');
  const post = vi.fn();
  await expect(withAuthorAttempt(digest, '3'.repeat(32), inspectedPrior, () => true, post)).rejects.toThrow(/已有恢复尝试已变化或结果未知/);
  expect(post).not.toHaveBeenCalled(); expect(readAuthorAttempt(digest)).toMatchObject({ request_key: changedPrior, status: 'COMPLETED' });
});
