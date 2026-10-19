// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { api, type Asset } from '../api';
import { AssetLibraryPanel, type AssetLibraryAdapter } from './AssetLibraryPanel';

const rows: Asset[] = [
  { id: 'one', novel_id: 'n1', filename: 'Scene10.TXT', kind: 'file', media_type: 'text/plain', size: 10,
    created_at: '2026-10-18T12:00:00Z', updated_at: '', sha256: 'a'.repeat(64) },
  { id: 'two', novel_id: 'n1', filename: 'scene2.txt', kind: 'file', media_type: 'text/plain', size: 20,
    created_at: '2026-10-19T12:00:00Z', updated_at: '', sha256: 'b'.repeat(64) },
];
const view = (props: Partial<Parameters<typeof AssetLibraryPanel>[0]> = {}) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><AssetLibraryPanel novelId="n1" {...props}/></QueryClientProvider>);
};
const names = () => screen.getAllByRole('article').map(article => article.getAttribute('aria-label'));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('exposes filename search in the original entry and preserves hidden selection and owner order', async () => {
  const list = vi.spyOn(api, 'assets').mockResolvedValue(rows);
  const selected = vi.fn();
  view({ selectedAssetId: 'one', onSelectAsset: selected });
  await screen.findByRole('button', { name: '检查资产 Scene10.TXT' });
  fireEvent.change(screen.getByRole('searchbox', { name: '查找资产' }), { target: { value: ' SCENE2 ' } });
  expect(names()).toEqual(['资产 scene2.txt']);
  expect(screen.getByText('显示 1 / 2 项资产')).toBeTruthy();
  expect(screen.getByText(/已选资产被当前查找隐藏/)).toBeTruthy();
  expect(selected).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '清除查找' }));
  expect(document.activeElement).toBe(screen.getByRole('searchbox', { name: '查找资产' }));
  expect(screen.getByRole('button', { name: '检查资产 Scene10.TXT' }).getAttribute('aria-pressed')).toBe('true');
  fireEvent.change(screen.getByRole('combobox', { name: '资产排序' }), { target: { value: 'NAME' } });
  expect(names()).toEqual(['资产 scene2.txt', '资产 Scene10.TXT']);
  fireEvent.change(screen.getByRole('combobox', { name: '资产排序' }), { target: { value: 'OWNER' } });
  expect(names()).toEqual(['资产 Scene10.TXT', '资产 scene2.txt']);
  expect(list).toHaveBeenCalledTimes(1);
  expect(selected).not.toHaveBeenCalled();
});

it('uses the original file-kind API filter with character and scene constraints intact', async () => {
  const list = vi.spyOn(api, 'assets').mockResolvedValue(rows);
  view({ characterId: 'character', sceneId: 'scene' });
  await screen.findByRole('article', { name: '资产 Scene10.TXT' });
  fireEvent.change(screen.getByRole('combobox', { name: '类型筛选' }), { target: { value: 'file' } });
  await waitFor(() => expect(list).toHaveBeenLastCalledWith('n1', 'file', 'character', 'scene'));
  fireEvent.change(screen.getByRole('searchbox', { name: '查找资产' }), { target: { value: 'missing' } });
  expect(screen.getByText('当前查找没有匹配资产。')).toBeTruthy();
  expect(screen.queryByText('暂无资产')).toBeNull();
});

it('clears a stale search before focusing an explicitly requested original asset', async () => {
  vi.spyOn(api, 'assets').mockResolvedValue(rows);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const props = (requestedAssetId?: string) => <QueryClientProvider client={client}>
    <AssetLibraryPanel novelId="n1" requestedAssetId={requestedAssetId}/></QueryClientProvider>;
  const rendered = render(props());
  await screen.findByRole('article', { name: '资产 Scene10.TXT' });
  fireEvent.change(screen.getByRole('searchbox', { name: '查找资产' }), { target: { value: 'missing' } });
  rendered.rerender(props('one'));
  const target = await screen.findByRole('article', { name: '资产 Scene10.TXT' });
  await waitFor(() => expect(document.activeElement).toBe(target));
  expect((screen.getByRole('searchbox', { name: '查找资产' }) as HTMLInputElement).value).toBe('');
});

it('keeps the adapter read-only while browsing and never uploads, removes, restores or downloads', async () => {
  const adapter: AssetLibraryAdapter = { cacheKey: 'read-only', canMutate: false, isCurrent: () => true,
    list: vi.fn().mockResolvedValue(rows), upload: vi.fn(), download: vi.fn(), remove: vi.fn(),
    trash: vi.fn(), restore: vi.fn() };
  view({ adapter });
  await screen.findByRole('article', { name: '资产 Scene10.TXT' });
  fireEvent.change(screen.getByRole('searchbox', { name: '查找资产' }), { target: { value: 'scene' } });
  fireEvent.change(screen.getByRole('combobox', { name: '资产排序' }), { target: { value: 'NEWEST' } });
  expect(names()).toEqual(['资产 scene2.txt', '资产 Scene10.TXT']);
  expect((screen.getByRole('button', { name: '上传资产' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getAllByRole('button', { name: '删除资产' }).every(button => (button as HTMLButtonElement).disabled)).toBe(true);
  for (const operation of [adapter.upload, adapter.download, adapter.remove, adapter.trash, adapter.restore]) {
    expect(operation).not.toHaveBeenCalled();
  }
});
