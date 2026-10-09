// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { readLocalStudioSelection, readLocalWorkspaceSelection, rememberLocalStudioSelection, rememberLocalWorkspaceSelection, type LocalStudioModule } from './workspaceSelection';
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

it('keeps the studio hint separate from the unchanged original workspace hint', () => {
  expect(readLocalStudioSelection('project-b')).toEqual({ state: 'EMPTY' });
  expect(rememberLocalWorkspaceSelection('project-a')).toBe(true);
  expect(rememberLocalStudioSelection('project-b', 'IMAGE', 'asset-b')).toBe(true);
  expect(readLocalWorkspaceSelection()).toEqual({ state: 'SAVED', projectId: 'project-a' });
  expect(readLocalStudioSelection('project-b')).toEqual({ state: 'SAVED', projectId: 'project-b', module: 'IMAGE', assetId: 'asset-b' });
  expect(localStorage.length).toBe(2);
  expect(JSON.parse(localStorage.getItem('studio.workspace-selection.v1:local-author:file')!)).toEqual({ schema: 1, mode: 'local', actor: 'local-author', project_id: 'project-a' });
});

it.each<LocalStudioModule>(['IMAGE', 'ASSETS', 'VIDEO', 'AUDIO'])('stores a bounded %s module hint without requiring a selected asset', module => {
  const setItem = vi.fn();
  expect(rememberLocalStudioSelection('project-b', module, undefined, { setItem })).toBe(true);
  const [key, value] = setItem.mock.calls[0];
  expect(key).toBe('studio.studio-selection.v1:local-author:file');
  expect(JSON.parse(value)).toEqual({ schema: 1, mode: 'local', actor: 'local-author', project_id: 'project-b', module });
  expect(readLocalStudioSelection('project-b', { getItem: () => value })).toEqual({ state: 'SAVED', projectId: 'project-b', module });
});

it('returns a studio hint only for the exact requested project and clears an omitted asset on the next save', () => {
  expect(rememberLocalStudioSelection('project-b', 'ASSETS', 'asset-b')).toBe(true);
  expect(readLocalStudioSelection('project-B')).toEqual({ state: 'EMPTY' });
  expect(readLocalStudioSelection('another-project')).toEqual({ state: 'EMPTY' });
  expect(rememberLocalStudioSelection('project-b', 'VIDEO')).toBe(true);
  expect(readLocalStudioSelection('project-b')).toEqual({ state: 'SAVED', projectId: 'project-b', module: 'VIDEO' });
});

it('rejects studio hints with unknown schema, owner, modules, malformed IDs, or private fields', () => {
  const valid = { schema: 1, mode: 'local', actor: 'local-author', project_id: 'project-b', module: 'IMAGE' };
  const records = [null, [], 'project-b', 1,
    { ...valid, schema: 2 }, { ...valid, mode: 'shared' }, { ...valid, actor: 'other' },
    { ...valid, module: 'NOVEL' }, { ...valid, module: 'image' }, { ...valid, module: '' },
    { ...valid, project_id: '' }, { ...valid, project_id: ' ' }, { ...valid, project_id: 'x'.repeat(161) },
    { ...valid, asset_id: '' }, { ...valid, asset_id: null }, { ...valid, asset_id: 'x'.repeat(161) },
    { ...valid, asset_id: 'invalid\nline' }, { ...valid, session: 'forbidden' },
    { ...valid, token: 'forbidden' }, { ...valid, title: 'private-title' },
    { ...valid, content_base64: 'private-bytes' }, { ...valid, branch_id: 'branch-b' },
  ];
  for (const record of records) expect(readLocalStudioSelection('project-b', { getItem: () => JSON.stringify(record) })).toEqual({ state: 'INVALID' });
  expect(readLocalStudioSelection('project-b', { getItem: () => '{invalid' })).toEqual({ state: 'INVALID' });
  expect(readLocalStudioSelection('project-b', { getItem: () => 'x'.repeat(1025) })).toEqual({ state: 'INVALID' });
});

it('rejects unbounded studio writes and invalid module values without touching storage', () => {
  const setItem = vi.fn(), storage = { setItem };
  for (const projectId of ['', ' ', 'x'.repeat(161), 'invalid\nline']) {
    expect(rememberLocalStudioSelection(projectId, 'IMAGE', undefined, storage)).toBe(false);
  }
  for (const assetId of ['', ' ', 'x'.repeat(161), 'invalid\u0000id']) {
    expect(rememberLocalStudioSelection('project-b', 'IMAGE', assetId, storage)).toBe(false);
  }
  expect(rememberLocalStudioSelection('project-b', 'NOVEL' as LocalStudioModule, undefined, storage)).toBe(false);
  expect(setItem).not.toHaveBeenCalled();
});

it('permits bounded opaque studio IDs without making them authority', () => {
  const id = '项目 / asset:one';
  expect(rememberLocalStudioSelection(id, 'AUDIO', 'a'.repeat(160))).toBe(true);
  expect(readLocalStudioSelection(id)).toEqual({ state: 'SAVED', projectId: id, module: 'AUDIO', assetId: 'a'.repeat(160) });
});

it('fails closed when studio hint storage is blocked and does not inspect storage for an invalid project', () => {
  const getItem = vi.fn(() => { throw new Error('blocked'); });
  expect(readLocalStudioSelection('', { getItem })).toEqual({ state: 'INVALID' });
  expect(getItem).not.toHaveBeenCalled();
  expect(readLocalStudioSelection('project-b', { getItem })).toEqual({ state: 'UNAVAILABLE' });
  expect(rememberLocalStudioSelection('project-b', 'IMAGE', 'asset-b', { setItem: () => { throw new Error('quota'); } })).toBe(false);
});
