// @vitest-environment jsdom
import {fireEvent,render,screen} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AssetLibraryPanel} from './AssetLibraryPanel';
import {api} from '../api';
import {vi,it,expect} from 'vitest';

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
