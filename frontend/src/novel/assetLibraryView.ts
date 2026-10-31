import type { Asset } from '../api';

export const ASSET_LIBRARY_SORTS = [
  ['OWNER', '原目录顺序'],
  ['NAME', '文件名'],
  ['NEWEST', '创建时间（最新优先）'],
  ['SIZE', '文件大小（最大优先）'],
] as const;
export type AssetLibrarySort = typeof ASSET_LIBRARY_SORTS[number][0];

const names = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' });
const created = (asset: Asset) => {
  const value = Date.parse(asset.created_at);
  return Number.isFinite(value) ? value : -Infinity;
};

/** Only the current owner response is searched; preserve its objects and order on ties. */
export function assetLibraryView(assets: readonly Asset[], query: string, sort: AssetLibrarySort): Asset[] {
  const term = query.trim().toLocaleLowerCase();
  const rows = assets.filter(asset => !term || asset.filename.toLocaleLowerCase().includes(term));
  if (sort === 'NAME') rows.sort((left, right) => names.compare(left.filename, right.filename));
  if (sort === 'NEWEST') rows.sort((left, right) => {
    const a = created(left), b = created(right);
    return a === b ? 0 : a > b ? -1 : 1;
  });
  if (sort === 'SIZE') rows.sort((left, right) => right.size - left.size);
  return rows;
}
