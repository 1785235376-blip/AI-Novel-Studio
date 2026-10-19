import { samePin, type AssetPin } from '../experimental/studioUsageEvidence';
import type { FactTarget, FactUse } from './storyFactClient';
export type FactAsset = FactUse['assets'][number];
export const factAssetPin = (asset: FactAsset): AssetPin => ({ kind: 'ASSET', id: asset.asset_id, version: asset.version, digest: asset.digest, asset_kind: asset.kind });
export const sameTarget = (a: FactTarget, b: FactTarget) => a.document_id === b.document_id && a.document_version === b.document_version
  && a.document_digest === b.document_digest && a.scene_id === b.scene_id && a.shot_id === b.shot_id
  && a.shot_version === b.shot_version && a.shot_digest === b.shot_digest;
const pin = (p: FactUse['fact']) => [p.id, p.version, p.digest];
// Compare the selected path, not unrelated assets or the order of the owner's list.
export const factPathKey = (row: FactUse, asset: FactAsset) => JSON.stringify([row.id, row.version, pin(row.fact),
  pin(row.current_fact), row.current_fact.status, row.state, [...row.blockers].sort(), row.purpose, row.rationale,
  row.target.document_id, row.target.document_version, row.target.document_digest, row.target.scene_id,
  row.target.shot_id, row.target.shot_version, row.target.shot_digest, factAssetPin(asset)]);
export function revalidateFactPath(rows: FactUse[], expected: FactUse, asset: FactAsset, target: FactTarget): FactUse {
  const found = rows.filter(row => row.id === expected.id);
  if (found.length !== 1 || !sameTarget(found[0].target, target)) throw new Error('事实或镜头上下文已变化');
  const row = found[0], assets = row.assets.filter(a => a.asset_id === asset.asset_id);
  if (assets.length !== 1 || !samePin(factAssetPin(assets[0]), factAssetPin(asset))
    || factPathKey(row, assets[0]) !== factPathKey(expected, asset)) throw new Error('事实、镜头或素材证据已变化');
  return row;
}
