// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { drafts, conflicts, conflictResolutionDrafts, exportDraftText } from './drafts';

const ids = new Set<string>();
function draft(content = '中文，👩🏽‍🚀 e\u0301 <script>literal</script>') {
  const id = crypto.randomUUID(); ids.add(id);
  return { chapterId: id, content, baseVersion: 7, updatedAt: '2026-10-05T00:00:00Z' };
}
afterEach(() => {
  vi.restoreAllMocks(); vi.unstubAllGlobals();
  ids.forEach(id => { drafts.remove(id); conflicts.remove(id); conflicts.clearHistory(id); conflictResolutionDrafts.remove(id); });
  ids.clear(); localStorage.clear();
});
it('retains the latest candidate over an older durable snapshot after quota failure, then flushes on recovery', () => {
  const first = draft('older'); expect(drafts.save(first).durability).toBe('durable');
  const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError'); });
  const latest = { ...first, content: '最新候选 👩🏽‍🚀' };
  expect(drafts.save(latest).durability).toBe('memory');
  expect(drafts.load(first.chapterId)).toEqual(latest);
  expect(drafts.durability(first.chapterId)).toBe('memory');
  write.mockRestore();
  expect(drafts.save(latest).durability).toBe('durable');
  expect(drafts.durability(first.chapterId)).toBe('durable');
});
it('survives blocked storage access and keeps conflict candidates and the manual resolution', () => {
  const value = draft();
  vi.stubGlobal('localStorage', { getItem() { throw new DOMException('Blocked', 'SecurityError'); }, setItem() { throw new DOMException('Blocked', 'SecurityError'); }, removeItem() { throw new Error('blocked'); } });
  expect(drafts.save(value).durability).toBe('memory');
  const conflict = { chapterId: value.chapterId, local: value, server: { content: 'server', version: 8 }, detectedAt: 'now' };
  expect(conflicts.save(conflict).durability).toBe('memory');
  conflictResolutionDrafts.save({ chapterId: value.chapterId, content: '合并', serverVersion: 8, sourceConflictDetectedAt: 'now', updatedAt: 'now' });
  expect(drafts.load(value.chapterId)?.content).toBe(value.content);
  expect(conflicts.load(value.chapterId)).toEqual(conflict);
  expect(conflictResolutionDrafts.load(value.chapterId)?.content).toBe('合并');
});
it('does not call silently rejected writes durable or resurrect a deleted draft in this session', () => {
  const first = draft('old'); drafts.save(first);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => undefined);
  expect(drafts.save({ ...first, content: 'new' }).durability).toBe('memory');
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('denied'); });
  drafts.remove(first.chapterId);
  expect(drafts.load(first.chapterId)).toBeUndefined();
  expect(drafts.durability(first.chapterId)).toBe('none');
});
it('recovers a durable versioned snapshot in a fresh module and rejects corrupt or mismatched records', async () => {
  const value = draft(); drafts.save(value);
  vi.resetModules(); const fresh = (await import('./drafts')).drafts;
  expect(fresh.load(value.chapterId)).toEqual(value);
  localStorage.setItem(`ai-novel-studio:draft:file:${value.chapterId}`, '{invalid');
  expect(fresh.load(value.chapterId)).toBeUndefined();
  localStorage.setItem(`ai-novel-studio:draft:file:${value.chapterId}`, JSON.stringify({ ...value, chapterId: 'different' }));
  expect(fresh.load(value.chapterId)).toBeUndefined();
});
it('exports the exact Unicode candidate as a user-triggered text file, never HTML', async () => {
  const value = draft();
  const create = vi.fn((_blob: Blob) => 'blob:local-recovery');
  vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.download).toBe('writing-recovery.txt'); expect(this.href).toBe('blob:local-recovery');
  });
  exportDraftText(value.content);
  const blob = create.mock.calls[0][0] as Blob;
  const text = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
  expect(text).toBe(value.content); expect(blob.type).toBe('text/plain;charset=utf-8'); expect(click).toHaveBeenCalledOnce();
});
it('distinguishes an invalid retained record from an empty journal without deleting raw bytes', () => {
  const value = draft(); const key = `ai-novel-studio:draft:file:${value.chapterId}`;
  for (const raw of ['', 'null', '[]', '{broken', JSON.stringify({ ...value, document: '<unsafe>' })]) {
    localStorage.setItem(key, raw);
    expect(drafts.inspect(value.chapterId)).toEqual({ state: 'CORRUPT', raw });
    expect(drafts.load(value.chapterId)).toBeUndefined(); expect(localStorage.getItem(key)).toBe(raw);
  }
  drafts.remove(value.chapterId); expect(drafts.inspect(value.chapterId)).toEqual({ state: 'EMPTY' });
});
