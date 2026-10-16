// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.resetModules(); });
it('AUDIT permits application-store initialization when browser reads are denied', async () => {
  vi.resetModules();
  vi.stubGlobal('localStorage', { getItem() { throw new DOMException('Blocked', 'SecurityError'); }, setItem() { throw new DOMException('Blocked', 'SecurityError'); }, removeItem() { throw new DOMException('Blocked', 'SecurityError'); } });
  await expect(import('./store')).resolves.toBeTruthy();
});
it('permits cold-start when accessing the storage property itself throws', async () => {
  vi.resetModules();
  const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new DOMException('Denied', 'SecurityError'); } });
  try {
    const { useStudio } = await import('./store');
    expect(useStudio.getState().sessionToken).toBe('');
    expect(() => useStudio.getState().setCollaboration('ephemeral-only')).not.toThrow();
    expect(useStudio.getState().sessionToken).toBe('ephemeral-only');
  } finally { if (original) Object.defineProperty(globalThis, 'localStorage', original); }
});
it('changes in-memory collaboration scope when durable writes fail', async () => {
  vi.resetModules();
  vi.stubGlobal('localStorage', { getItem: () => null, setItem() { throw new DOMException('Full', 'QuotaExceededError'); }, removeItem() { throw new DOMException('Denied', 'SecurityError'); } });
  const { useStudio } = await import('./store');
  const scope = { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'b' };
  expect(() => useStudio.getState().setCollaboration('session', { id: 'actor', displayName: 'Writer', workspaceId: 'w' }, scope)).not.toThrow();
  expect(useStudio.getState().scope).toEqual(scope);
  expect(() => useStudio.getState().setCollaboration('')).not.toThrow();
  expect(useStudio.getState().sessionToken).toBe('');
});
it('never reads or persists browser session credentials in packaged hosts', async () => {
  vi.resetModules();
  window.__AI_NOVEL_PACKAGED_HOST__ = true;
  const getItem = vi.fn(() => 'private-old-session'), setItem = vi.fn(), removeItem = vi.fn();
  vi.stubGlobal('localStorage', { getItem, setItem, removeItem });
  try {
    const { useStudio } = await import('./store');
    expect(useStudio.getState().sessionToken).toBe('');
    useStudio.getState().setCollaboration('ephemeral-host-session');
    expect(getItem).not.toHaveBeenCalled(); expect(setItem).not.toHaveBeenCalled(); expect(removeItem).not.toHaveBeenCalled();
  } finally { delete window.__AI_NOVEL_PACKAGED_HOST__; }
});
