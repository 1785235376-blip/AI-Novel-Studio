// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, type Asset } from '../api';
import { useStudio } from '../store';
import { AssetLibraryPanel, type AssetLibraryAdapter } from './AssetLibraryPanel';

const row = (filename = 'current.txt'): Asset => ({ id: 'one', novel_id: 'n1', filename, kind: 'file',
  media_type: 'text/plain', size: 10, sha256: 'a'.repeat(64), created_at: '', updated_at: '' });
const scope = { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'branch-a' };
const clients: QueryClient[] = [];
beforeEach(() => useStudio.setState({ sessionToken: 'session-a',
  actor: { id: 'actor-a', workspaceId: 'w', displayName: 'A' }, scope }));
afterEach(() => { cleanup(); clients.splice(0).forEach(client => client.clear());
  vi.restoreAllMocks(); useStudio.getState().setCollaboration(''); });

type Props = Partial<Parameters<typeof AssetLibraryPanel>[0]>;
function mount(initial: Props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  const selected = vi.fn();
  const element = (props: Props) => <QueryClientProvider client={client}>
    <AssetLibraryPanel novelId="n1" requestedAssetId="one" onSelectAsset={selected} {...props}/>
  </QueryClientProvider>;
  const view = render(element(initial));
  return { ...view, client, selected, update: (props: Props) => view.rerender(element(props)) };
}
const search = () => screen.getByRole('searchbox', { name: '查找资产' }) as HTMLInputElement;
const hide = () => fireEvent.change(search(), { target: { value: 'missing' } });
const focusedTarget = async () => {
  const target = await screen.findByRole('article', { name: '资产 current.txt' });
  await waitFor(() => expect(document.activeElement).toBe(target));
};

it.each(['authority', 'branch'] as const)('reveals the same requested ID after a new %s owner read', async change => {
  const list = vi.spyOn(api, 'assets').mockResolvedValue([row()]);
  const view = mount();
  await focusedTarget(); hide();
  expect(screen.queryByRole('article')).toBeNull();
  act(() => useStudio.setState(change === 'authority'
    ? { sessionToken: 'session-b', actor: { id: 'actor-b', workspaceId: 'w', displayName: 'B' } }
    : { scope: { ...scope, branchId: 'branch-b' } }));
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  await focusedTarget();
  expect(search().value).toBe('');
  expect(view.selected).not.toHaveBeenCalled();
});

it('treats project, character and scene changes as fresh same-ID target navigation', async () => {
  const list = vi.spyOn(api, 'assets').mockImplementation(async novelId => [{ ...row(), novel_id: novelId }]);
  const view = mount();
  await focusedTarget();
  for (const props of [{ novelId: 'n2' }, { novelId: 'n2', characterId: 'character' },
    { novelId: 'n2', characterId: 'character', sceneId: 'scene' }]) {
    hide(); view.update(props);
    await focusedTarget(); expect(search().value).toBe('');
  }
  expect(list).toHaveBeenLastCalledWith('n2', undefined, 'character', 'scene');
  expect(view.selected).not.toHaveBeenCalled();
});

it('does not let an old owner callback clear current filters or replace the current target', async () => {
  let complete!: (assets: Asset[]) => void;
  const delayed = new Promise<Asset[]>(resolve => { complete = resolve; });
  const list = vi.spyOn(api, 'assets').mockReturnValueOnce(delayed).mockResolvedValue([row()]);
  const view = mount();
  await waitFor(() => expect(list).toHaveBeenCalledTimes(1)); hide();
  act(() => useStudio.setState({ scope: { ...scope, branchId: 'branch-b' } }));
  await focusedTarget();
  fireEvent.change(search(), { target: { value: 'current' } });
  await act(async () => complete([row('old-private.txt')]));
  expect(search().value).toBe('current');
  expect(screen.queryByRole('article', { name: '资产 old-private.txt' })).toBeNull();
  expect(screen.getByRole('article', { name: '资产 current.txt' })).toBeTruthy();
  expect(view.selected).not.toHaveBeenCalled();
});

it('preserves browsing filters and sort on ordinary refresh and callback rerenders', async () => {
  vi.spyOn(api, 'assets').mockResolvedValue([row()]);
  const view = mount(); await focusedTarget();
  fireEvent.change(screen.getByRole('combobox', { name: '类型筛选' }), { target: { value: 'file' } });
  fireEvent.change(screen.getByRole('combobox', { name: '资产排序' }), { target: { value: 'SIZE' } }); hide();
  await act(async () => { await view.client.invalidateQueries({ queryKey: ['assets', 'n1'] }); });
  view.update({ onSelectAsset: vi.fn() });
  expect(search().value).toBe('missing');
  expect((screen.getByRole('combobox', { name: '类型筛选' }) as HTMLSelectElement).value).toBe('file');
  expect((screen.getByRole('combobox', { name: '资产排序' }) as HTMLSelectElement).value).toBe('SIZE');
});

it('preserves filters across scope changes without an explicit target', async () => {
  vi.spyOn(api, 'assets').mockResolvedValue([row()]);
  mount({ requestedAssetId: undefined });
  await screen.findByRole('article'); hide();
  fireEvent.change(screen.getByRole('combobox', { name: '类型筛选' }), { target: { value: 'file' } });
  act(() => useStudio.setState({ scope: { ...scope, branchId: 'branch-b' } }));
  expect(search().value).toBe('missing');
  expect((screen.getByRole('combobox', { name: '类型筛选' }) as HTMLSelectElement).value).toBe('file');
});

it('binds adapter navigation to its owner key, never to callback references or a retired owner', async () => {
  const adapter: AssetLibraryAdapter = { cacheKey: 'owner-a', canMutate: false, isCurrent: () => true,
    list: vi.fn().mockResolvedValue([row()]), upload: vi.fn(), download: vi.fn(), remove: vi.fn(),
    trash: vi.fn(), restore: vi.fn() };
  const view = mount({ adapter }); await focusedTarget(); hide();
  view.update({ adapter: { ...adapter, cacheKey: 'owner-b' } });
  await focusedTarget(); expect(search().value).toBe(''); hide();
  view.update({ adapter: { ...adapter, cacheKey: 'owner-b', isCurrent: () => true } });
  expect(search().value).toBe('missing');
  view.update({ adapter: { ...adapter, cacheKey: 'retired', isCurrent: () => false } });
  expect(search().value).toBe('missing');
  expect(view.selected).not.toHaveBeenCalled();
});
