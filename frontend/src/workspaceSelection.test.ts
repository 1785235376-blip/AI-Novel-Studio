// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { readLocalWorkspaceSelection, rememberLocalWorkspaceSelection } from './workspaceSelection';
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });
it('persists only the bounded local-author project hint', () => {
  expect(readLocalWorkspaceSelection()).toEqual({ state: 'EMPTY' });
  expect(rememberLocalWorkspaceSelection('project-b')).toBe(true);
  expect(readLocalWorkspaceSelection()).toEqual({ state: 'SAVED', projectId: 'project-b' });
  const value = JSON.parse(localStorage.getItem(localStorage.key(0)!)!);
  expect(value).toEqual({ schema: 1, mode: 'local', actor: 'local-author', project_id: 'project-b' });
  expect(rememberLocalWorkspaceSelection('x'.repeat(161))).toBe(false);
});
it('rejects unknown schema, actor or extra data instead of using a private reference', () => {
  for (const value of [{ schema: 2 }, { schema: 1, mode: 'local', actor: 'other', project_id: 'b' }, { schema: 1, mode: 'local', actor: 'local-author', project_id: 'b', session: 'forbidden-extra' }]) {
    expect(readLocalWorkspaceSelection({ getItem: () => JSON.stringify(value) })).toEqual({ state: 'INVALID' });
  }
});
it('handles blocked browser storage without an availability claim', () => {
  expect(readLocalWorkspaceSelection({ getItem: () => { throw new Error('blocked'); } })).toEqual({ state: 'UNAVAILABLE' });
  expect(rememberLocalWorkspaceSelection('b', { setItem: () => { throw new Error('quota'); } })).toBe(false);
});
