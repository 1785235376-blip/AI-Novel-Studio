// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AssetLibraryPanel} from './AssetLibraryPanel';
import {api} from '../api';
import {afterEach,vi,it,expect} from 'vitest';

afterEach(()=>{cleanup();vi.restoreAllMocks();});

it('renders image preview and asset metadata', async()=>{
  vi.spyOn(api,'assets').mockResolvedValue([{id:'a1',novel_id:'n1',filename:'cover.png',kind:'image',media_type:'image/png',size:1024,sha256:'abcdef1234567890',created_at:'',updated_at:''}]);
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={client}><AssetLibraryPanel novelId="n1"/></QueryClientProvider>);
  expect(await screen.findByAltText('cover.png')).toBeTruthy();
  expect(screen.getByText('image/png · abcdef123456')).toBeTruthy();
});

it('publishes the selected real asset to the workspace inspector',async()=>{
  const asset={id:'a2',novel_id:'n1',filename:'reference.png',kind:'image',media_type:'image/png',size:2048,sha256:'1234567890abcdef',created_at:'',updated_at:''};
  vi.spyOn(api,'assets').mockResolvedValue([asset]);
  const selected=vi.fn();
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={client}><AssetLibraryPanel novelId="n1" onSelectAsset={selected}/></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'检查资产 reference.png'}));
  expect(selected).toHaveBeenCalledWith(asset);
});

it('deletes within the selected novel and preserves selection on failure',async()=>{
  const asset={id:'delete-1',novel_id:'n1',filename:'remove.txt',kind:'file',media_type:'text/plain',size:8,sha256:'1234567890abcdef',created_at:'',updated_at:''};
  vi.spyOn(api,'assets').mockResolvedValue([asset]);
  vi.spyOn(api,'deleteAsset').mockRejectedValue(new Error('删除失败，请重试'));
  const selected=vi.fn();
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  render(<QueryClientProvider client={client}><AssetLibraryPanel novelId="n1" selectedAssetId="delete-1" onSelectAsset={selected}/></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'删除资产'}));
  await screen.findByText('删除失败，请重试');
  expect(api.deleteAsset).toHaveBeenCalledWith('delete-1','n1');
  expect(selected).not.toHaveBeenCalled();
});

it('rediscovers and restores deleted assets from the server recycle bin',async()=>{
  const asset={id:'restore-1',novel_id:'n1',filename:'restore.png',kind:'image',media_type:'image/png',size:8,sha256:'1234567890abcdef',created_at:'',updated_at:''};
  vi.spyOn(api,'assets').mockResolvedValue([]);
  vi.spyOn(api,'assetTrash').mockResolvedValue({items:[asset],total:1});
  vi.spyOn(api,'restoreAsset').mockResolvedValue(asset);
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={client}><AssetLibraryPanel novelId="n1"/></QueryClientProvider>);
  fireEvent.click(screen.getByRole('button',{name:'回收站'}));
  fireEvent.click(await screen.findByRole('button',{name:'恢复资产'}));
  await waitFor(()=>expect(api.restoreAsset).toHaveBeenCalledWith('n1','restore-1'));
});
