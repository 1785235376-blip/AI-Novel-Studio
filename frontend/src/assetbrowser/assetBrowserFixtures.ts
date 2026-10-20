import { assetBrowserRelationships, assetBrowserList } from './assetBrowserContract';
import type { AssetBrowserAsset, AssetBrowserRelationshipGraph } from './assetBrowserTypes';

/**
 * 夹具刻意复刻**真实 owner** 的响应形状：
 * - 资产行 = `workspace.py::_view()` → `asset_library_service.py::public()` +
 *   `lineage.asset(include_impact=False)` / `_production_provenance()`；
 * - 关系图 = `workspace_relationships.py::graph()`。
 *
 * 这里绝不"顺手"补上 owner 不会返回的字段（例如 `tags`）：没有就是没有，
 * 这样测试才能证明界面把"未披露"当作未核实而不是默认值。
 */

export const FIXTURE_PROJECT = 'novel-ux03';
const HEX = (seed: string): string => seed.repeat(64).slice(0, 64);
const DIGEST_A = HEX('a'), DIGEST_B = HEX('b'), DIGEST_C = HEX('c'), DIGEST_D = HEX('d');

/** `lineage.asset()` 的 `provenance`（真实投影的键集合）。 */
export function provenance(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'asset-a', label: 'cover.png', kind: 'image', version: 3, digest: DIGEST_A, deleted: false,
    integrity: 'VERIFIED', origin: 'EXTERNAL_IMPORT',
    license: { label: 'UNSPECIFIED', source: '', note: '' },
    license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION',
    operation: '', parents: [], sources: [], stale: false,
    producer: { declared_by: 'author-1', provider_id: null, model_id: null },
    generation: null, declaration_history_versions: [], source_task_id: null,
    ...overrides,
  };
}

/** 一行真实的 `StudioAsset`（`studioClient.ts::assets()` 的元素）。 */
export function assetRow(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'asset-a', novel_id: FIXTURE_PROJECT, filename: 'cover.png', kind: 'image', media_type: 'image/png',
    size: 2048, sha256: DIGEST_A, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-02T00:00:00Z',
    version: 3, branch_id: null, deleted_at: null,
    provenance: provenance(), relationships: [], parameters: {},
    ...overrides,
  };
}

export function listEnvelope(items: unknown[]): Record<string, unknown> {
  return { items };
}

/** 解码一行 / 一批行；测试与视图都只使用解码后的类型。 */
export function decodeRow(overrides: Record<string, unknown> = {}, project = FIXTURE_PROJECT): AssetBrowserAsset {
  return assetBrowserList(listEnvelope([assetRow(overrides)]), project)[0];
}
export function decodeRows(overrides: Record<string, unknown>[] = [{}], project = FIXTURE_PROJECT): AssetBrowserAsset[] {
  return assetBrowserList(listEnvelope(overrides.map(row => assetRow(row))), project);
}

/** 供视图测试使用的三行样本：图片 / 音频 / 视频，版本与来源各不相同。 */
export function sampleAssets(): AssetBrowserAsset[] {
  return decodeRows([
    { id: 'asset-a', filename: 'cover.png', kind: 'image', media_type: 'image/png', version: 3, sha256: DIGEST_A,
      created_at: '2026-10-14T01:00:00Z', tags: ['character'] },
    { id: 'asset-b', filename: 'theme.mp3', kind: 'audio', media_type: 'audio/mpeg', version: 1, sha256: DIGEST_B,
      created_at: '2026-09-20T01:00:00Z', parameters: { tags: ['environment'] },
      provenance: provenance({ id: 'asset-b', label: 'theme.mp3', kind: 'audio', version: 1, digest: DIGEST_B,
        origin: 'GENERATED_RESULT', stale: true, integrity: 'CONTENT_UNAVAILABLE',
        license: { label: 'CC0', source: 'author note', note: '' },
        parents: [{ id: 'asset-a', label: 'cover.png', version: 3, digest: DIGEST_A, state: 'STALE' }] }) },
    { id: 'asset-c', filename: 'shot.mp4', kind: 'video', media_type: 'video/mp4', version: 2, sha256: DIGEST_C,
      created_at: '2026-08-01T01:00:00Z' },
  ]);
}

/**
 * 真实的 `StudioRelationshipsGraph` 响应体（`workspace_relationships.py::graph()`
 * 原样写出的形状）：三个节点、四条边（三条声明关系 + 一条原始来源边）。
 * `asset-a` 被 `asset-b` 引用两次。**未解码**——测试自己调用
 * `assetBrowserRelationships()`，从而同时覆盖"服务端原文能解码"这件事。
 */
export function relationshipGraphPayload(): Record<string, unknown> {
  return {
    graph_kind: 'ASSET_RELATIONSHIPS',
    nodes: [
      { id: 'asset-a', kind: 'ASSET', asset_kind: 'image', label: 'cover.png', version: 3, digest: DIGEST_A },
      { id: 'asset-b', kind: 'ASSET', asset_kind: 'audio', label: 'theme.mp3', version: 1, digest: DIGEST_B },
      { id: 'asset-c', kind: 'ASSET', asset_kind: 'video', label: 'shot.mp4', version: 2, digest: DIGEST_C },
    ],
    edges: [
      { id: 'rel-1', from: 'asset-b', type: 'REFERENCES', state: 'CURRENT',
        target: { kind: 'ASSET', id: 'asset-a', version: 3, digest: DIGEST_A, label: 'cover.png', deleted: false },
        expected: { kind: 'ASSET', id: 'asset-a', version: 3, digest: DIGEST_A },
        reason: '作为封面参考', created_by: 'author-1', created_at: '2026-10-03T00:00:00Z',
        semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' },
      { id: 'rel-2', from: 'asset-c', type: 'USED_IN', state: 'CURRENT',
        target: { kind: 'SCREENPLAY', id: 'script-1', version: 4, digest: DIGEST_D, label: '第一幕', deleted: false },
        expected: { kind: 'SCREENPLAY', id: 'script-1', version: 4, digest: DIGEST_D },
        reason: '用于分镜', created_by: 'author-1', created_at: '2026-10-03T00:00:00Z',
        semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' },
      { id: 'rel-3', from: 'asset-a', type: 'REFERENCES', state: 'UNAVAILABLE',
        target: { label: '关联内容不可用或无权访问' } },
      { id: 'lineage-1', from: 'asset-b', type: 'DERIVED_FROM', owner: 'ASSET_LINEAGE', state: 'STALE',
        target: { kind: 'ASSET', id: 'asset-a', version: 3, digest: DIGEST_A, label: 'cover.png', deleted: false } },
    ],
    executable: false, knowledge_graph: false, automatic_regeneration: false,
  };
}

/** 解码后的关系图；服务端原文经同一份严格契约。 */
export function relationshipGraph(overrides: Record<string, unknown> = {}): AssetBrowserRelationshipGraph {
  return assetBrowserRelationships({ ...relationshipGraphPayload(), ...overrides });
}
