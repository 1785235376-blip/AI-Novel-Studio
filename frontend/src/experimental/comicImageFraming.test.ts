import { Blob as NodeBlob } from 'node:buffer';
import { expect, it, vi } from 'vitest';
import { panComicFraming, readComicFramingImage } from './comicImageFraming';
import type { ComicAsset, ComicCatalog } from './comicLayoutsClient';
const source: ComicAsset = { id: 'art', version: 2, approved: true, filename: 'art.png', manual_review_available: false };
export function framingPng(width = 800, height = 100): Blob {
  const bytes = Buffer.alloc(33); Buffer.from([137,80,78,71,13,10,26,10]).copy(bytes); bytes.writeUInt32BE(13,8); bytes.write('IHDR',12); bytes.writeUInt32BE(width,16); bytes.writeUInt32BE(height,20);
  return new NodeBlob([bytes], { type: 'image/png' }) as unknown as Blob;
}
const catalog = (asset = source) => ({ assets: [asset] }) as ComicCatalog;
it('pans artwork in screen pixels, clamps percentages and preserves inactive axes', () => {
  expect(panComicFraming({ width:200,height:100 },{ width:100,height:100 },{x:50,y:75},10,100)).toEqual({x:40,y:75});
  expect(panComicFraming({ width:100,height:200 },{ width:100,height:100 },{x:25,y:50},100,-100)).toEqual({x:25,y:100});
  expect(panComicFraming({ width:100,height:100 },{ width:100,height:100 },{x:25,y:75},100,100)).toEqual({x:25,y:75});
});
it('does not guess invalid geometry or nonfinite movement', () => {
  const start={x:50,y:50}; expect(panComicFraming({width:0,height:100},{width:100,height:100},start,1,1)).toBe(start);
  expect(panComicFraming({width:200,height:100},{width:100,height:100},start,NaN,1)).toBe(start);
});
it('reads one original thumbnail between two matching approval/version checks', async () => {
  const api = { catalog:vi.fn(async()=>catalog()), image:vi.fn(async()=>framingPng()) };
  expect(await readComicFramingImage(api,source,()=>true)).toMatchObject({width:800,height:100});
  expect(api.catalog).toHaveBeenCalledTimes(2);
  expect(api.image).toHaveBeenCalledWith('art'); expect(api.image).toHaveBeenCalledTimes(1);
});
it('rejects source/version/approval changes without returning a preview', async () => {
  const api={catalog:vi.fn(async()=>catalog()),image:vi.fn(async()=>framingPng())};
  await expect(readComicFramingImage(api,{...source,approved:false},()=>true)).rejects.toThrow(); expect(api.catalog).not.toHaveBeenCalled();
  api.catalog.mockResolvedValueOnce(catalog({...source,version:3})); await expect(readComicFramingImage(api,source,()=>true)).rejects.toThrow(); expect(api.image).not.toHaveBeenCalled();
  api.catalog.mockResolvedValueOnce(catalog()).mockResolvedValueOnce(catalog({...source,approved:false})); await expect(readComicFramingImage(api,source,()=>true)).rejects.toThrow();
});
it('rejects invalid thumbnails and retired reads', async () => {
  const api={catalog:vi.fn(async()=>catalog()),image:vi.fn(async()=>framingPng(801,100))};
  await expect(readComicFramingImage(api,source,()=>true)).rejects.toThrow(/800/);
  let active=true; api.image.mockImplementationOnce(async()=>{active=false;return framingPng();});
  await expect(readComicFramingImage(api,source,()=>active)).rejects.toThrow(/变化/);
});
