import type { ComicAsset, comicLayoutsClient } from './comicLayoutsClient';

export type ComicFramingPosition = { x: number; y: number };
const percent = (value: number) => Math.max(0, Math.min(100, Math.round(value)));
/** Drag the artwork, rather than the crop window; only overflowing axes move. */
export function panComicFraming(source: { width: number; height: number }, frame: { width: number; height: number }, start: ComicFramingPosition, dx: number, dy: number): ComicFramingPosition {
  if (![source.width, source.height, frame.width, frame.height].every(value => Number.isFinite(value) && value > 0)
    || ![start.x, start.y, dx, dy].every(Number.isFinite) || start.x < 0 || start.x > 100 || start.y < 0 || start.y > 100) return start;
  const scale = Math.max(frame.width / source.width, frame.height / source.height);
  const overflowX = source.width * scale - frame.width, overflowY = source.height * scale - frame.height;
  return { x: overflowX > 0.001 ? percent(start.x - dx / overflowX * 100) : start.x, y: overflowY > 0.001 ? percent(start.y - dy / overflowY * 100) : start.y };
}

/** Original Comic thumbnail reads only; source-free catalogs cannot admit a source. */
export async function readComicFramingImage(api: Pick<ReturnType<typeof comicLayoutsClient>, 'catalog' | 'image'>, source: ComicAsset, isCurrent: () => boolean) {
  const current = () => { if (!isCurrent()) throw new Error('当前页面或取景输入已变化，请重新读取。'); };
  if (source.approved !== true || !source.id || !Number.isSafeInteger(source.version) || source.version < 1) throw new Error('取景需要版本明确的已批准图片。');
  const checked = (items: ComicAsset[]) => {
    const matches = items.filter(asset => asset.id === source.id);
    if (matches.length !== 1 || matches[0].approved !== true || matches[0].version !== source.version)
      throw new Error('图片版本或批准状态已变化，请重新核对漫画来源。');
  };
  current(); const before = await api.catalog(); current(); checked(before.assets);
  const blob = await api.image(source.id); current();
  if (blob.type.split(';')[0].toLowerCase() !== 'image/png' || blob.size < 33 || blob.size > 4 * 1024 * 1024) throw new Error('原漫画缩略图格式或大小不符合预览边界。');
  const header = new Uint8Array(await blob.slice(0, 24).arrayBuffer()); current();
  if (![137, 80, 78, 71, 13, 10, 26, 10].every((value, index) => header[index] === value) || new DataView(header.buffer).getUint32(8) !== 13 || String.fromCharCode(...header.slice(12, 16)) !== 'IHDR') throw new Error('无法核对原漫画 PNG 缩略图。');
  const view = new DataView(header.buffer), width = view.getUint32(16), height = view.getUint32(20);
  if (!width || !height || width > 800 || height > 800) throw new Error('原漫画缩略图超出 800 × 800 像素边界。');
  const after = await api.catalog(); current(); checked(after.assets);
  return { blob, width, height };
}
