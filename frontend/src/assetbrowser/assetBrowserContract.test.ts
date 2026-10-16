import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import {
  assetBrowserAsset, assetBrowserIndexRow, assetBrowserList, assetBrowserQuery, assetBrowserReadTarget,
  assetBrowserRelationships, withReviewState,
} from './assetBrowserContract';
import { ASSET_BROWSER_ERROR_CODES } from './assetBrowserTypes';
import { FIXTURE_PROJECT, assetRow, listEnvelope, provenance, relationshipGraph, relationshipGraphPayload } from './assetBrowserFixtures';

/** 严格解码器用机器码报错：断言码，不断言文案。 */
function rejectionCode(run: () => unknown): string | undefined {
  try {
    run();
    return undefined;
  } catch (error) {
    return error instanceof ApiError ? error.problem.code : `NOT_AN_API_ERROR:${String(error)}`;
  }
}
const single = (value: unknown, project = FIXTURE_PROJECT) => assetBrowserAsset(value, project);
const many = (value: unknown, project = FIXTURE_PROJECT) => assetBrowserList(value, project);

describe('asset browser contract against real asset projections', () => {
  it('accepts the real list envelope and keeps owner disclosure verbatim', () => {
    const [asset] = many(listEnvelope([assetRow()]));
    expect(asset.id).toBe('asset-a');
    expect(asset.version).toBe(3);
    expect(asset.media_kind).toBe('image');
    expect(asset.digest).toBe(assetRow().sha256);
    expect(asset.provenance?.integrity).toBe('VERIFIED');
    expect(asset.provenance?.stale).toBe(false);
    expect(asset.provenance?.license_verification).toBe('AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION');
  });

  it('never invents a review conclusion the owner strips in public()', () => {
    // `public()` 剥掉 `_text_result_review`，所以目录投影里**没有**审核标记。
    const asset = single(assetRow());
    expect(asset.review_state).toBe('UNREVIEWED');
    // 只有调用方显式注入 owner 自己的索引行时才会覆盖。
    const injected = withReviewState(asset, 'APPROVED');
    expect(injected.review_state).toBe('APPROVED');
    expect(rejectionCode(() => withReviewState(asset, 'MADE_UP' as 'APPROVED')))
      .toBe(ASSET_BROWSER_ERROR_CODES.readLocalInvalid);
  });

  it('reads the owner review marker only from the owner index projection', () => {
    expect(assetBrowserIndexRow({ id: 'asset-a', kind: 'image', version: 3, review_status: null,
      source_job_id: null, deleted: false, created_at: '2026-10-01T00:00:00Z' }).review_status).toBe('UNREVIEWED');
    expect(assetBrowserIndexRow({ id: 'asset-a', kind: 'image', version: 3, review_status: 'DRAFT',
      source_job_id: null, deleted: false, created_at: '2026-10-01T00:00:00Z' }).review_status).toBe('DRAFT');
    expect(rejectionCode(() => assetBrowserIndexRow({ id: 'asset-a', kind: 'image', version: 3,
      review_status: 'PENDING', source_job_id: null, deleted: false, created_at: '2026-10-01T00:00:00Z' })))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('rejects a foreign project instead of rendering another project library', () => {
    expect(rejectionCode(() => single(assetRow({ novel_id: 'other-project' }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.scopeMismatch);
    // 缺失 / 非字符串的 `novel_id` 是形状问题，不是"别的项目"。
    expect(rejectionCode(() => many(listEnvelope([assetRow({ novel_id: null })]))))
      .toBe(ASSET_BROWSER_ERROR_CODES.listInvalid);
    expect(rejectionCode(() => single(assetRow({ novel_id: 7 }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('rejects unknown keys at every level rather than dropping them silently', () => {
    expect(rejectionCode(() => single({ ...assetRow(), hidden_flag: true })))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ provenance: { ...provenance(), secret: 1 } }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ provenance: provenance({ parents: [{ state: 'CURRENT', extra: 1 }] }) }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => many({ items: [], total: 0 })))
      .toBe(ASSET_BROWSER_ERROR_CODES.listInvalid);
    // owner 已剥掉的内部标记若真的出现，同样拒绝：那是越权投影。
    expect(rejectionCode(() => single(assetRow({ _text_result_review: { status: 'APPROVED' } }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ parameters: { _origin_provenance: {} } }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ parameters: { asset_relationships_v2: { items: [] } } }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('rejects an unbounded, control-character or non-string field', () => {
    expect(rejectionCode(() => single(assetRow({ filename: 'x'.repeat(300) }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ filename: 'bad\u0000name' }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ filename: '   ' }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ size: -1 }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ sha256: 'not-a-digest' }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ created_at: 'not-a-date' }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('refuses a coerced or missing asset version instead of defaulting it', () => {
    // `workspace.py::_row()` 明确要求 `version` 是 ≥1 的真实 int。
    expect(rejectionCode(() => single(assetRow({ version: 0 }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    expect(rejectionCode(() => single(assetRow({ version: 2.5 }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
    const withoutVersion = { ...assetRow() };
    delete (withoutVersion as Record<string, unknown>).version;
    expect(rejectionCode(() => single(withoutVersion)))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('keeps UNVERIFIED source states and undeclared provenance as unknown, never as true/false', () => {
    const asset = single(assetRow({
      provenance: provenance({ integrity: undefined, stale: undefined,
        parents: [{ state: 'UNVERIFIED', label: '来源未核实' }] }),
    }));
    expect(asset.provenance?.integrity).toBeNull();
    expect(asset.provenance?.stale).toBeNull();
    expect(asset.provenance?.parents[0].state).toBe('UNVERIFIED');
    expect(asset.provenance?.parents[0].id).toBeNull();
    // 没有 provenance 时是 null，而不是一个"默认可信"的对象。
    expect(single(assetRow({ provenance: null })).provenance).toBeNull();
  });

  it('bound the declared parameters and keep them raw', () => {
    const asset = single(assetRow({ parameters: { note: 'a', nested: { list: [1, 2, 'three'] } } }));
    expect(asset.parameters).toEqual({ note: 'a', nested: { list: [1, 2, 'three'] } });
    expect(rejectionCode(() => single(assetRow({ parameters: { blob: 'x'.repeat(3000) } }))))
      .toBe(ASSET_BROWSER_ERROR_CODES.detailInvalid);
  });

  it('rejects a duplicated asset row instead of presenting a shorter library', () => {
    expect(rejectionCode(() => many(listEnvelope([assetRow(), assetRow()]))))
      .toBe(ASSET_BROWSER_ERROR_CODES.listInvalid);
  });

  it('rejects an oversized list instead of truncating it into a false complete library', () => {
    const items = Array.from({ length: 501 }, (_, index) => assetRow({ id: `asset-${index}` }));
    expect(rejectionCode(() => many(listEnvelope(items)))).toBe(ASSET_BROWSER_ERROR_CODES.listInvalid);
  });

  it('validates the local read target and the local search term before any request', () => {
    expect(assetBrowserReadTarget(FIXTURE_PROJECT)).toEqual({ project_id: FIXTURE_PROJECT, asset_id: null });
    expect(assetBrowserReadTarget(FIXTURE_PROJECT, 'asset-a').asset_id).toBe('asset-a');
    expect(rejectionCode(() => assetBrowserReadTarget('../etc/passwd')))
      .toBe(ASSET_BROWSER_ERROR_CODES.readLocalInvalid);
    expect(rejectionCode(() => assetBrowserReadTarget(FIXTURE_PROJECT, 'a/b')))
      .toBe(ASSET_BROWSER_ERROR_CODES.readLocalInvalid);
    expect(assetBrowserQuery('  cover  ')).toBe('cover');
    expect(assetBrowserQuery('co\u0000ver')).toBe('cover');
    expect(rejectionCode(() => assetBrowserQuery('x'.repeat(200))))
      .toBe(ASSET_BROWSER_ERROR_CODES.queryLocalInvalid);
  });
});

describe('asset browser relationship contract', () => {
  it('accepts the real graph projection and its owner facts', () => {
    const graph = relationshipGraph();
    expect(graph.nodes).toHaveLength(3);
    expect(graph.edges).toHaveLength(4);
    expect(graph.executable).toBe(false);
    expect(graph.knowledge_graph).toBe(false);
    expect(graph.automatic_regeneration).toBe(false);
  });

  it('keeps an UNAVAILABLE relationship free of hidden target identity', () => {
    const unavailable = relationshipGraph().edges.find(edge => edge.id === 'rel-3');
    expect(unavailable).toBeDefined();
    expect(unavailable && 'target' in unavailable ? unavailable.target.id : 'x').toBeNull();
    expect(unavailable && 'target' in unavailable ? unavailable.target.label : null).toBe('关联内容不可用或无权访问');
  });

  it('rejects edges that are not attached to a declared node', () => {
    const value = { ...relationshipGraph(), edges: [{ id: 'rel-9', from: 'asset-ghost', type: 'REFERENCES',
      state: 'CURRENT', target: { kind: 'ASSET', id: 'asset-a', version: 3, digest: 'a'.repeat(64), label: 'x', deleted: false },
      expected: { kind: 'ASSET', id: 'asset-a', version: 3, digest: 'a'.repeat(64) },
      semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION' }] };
    expect(rejectionCode(() => assetBrowserRelationships(value)))
      .toBe(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid);
  });

  it('rejects a lineage edge that claims a non-asset target', () => {
    const graph = relationshipGraph() as unknown as Record<string, unknown>;
    const edges = (graph.edges as Record<string, unknown>[]).map(edge => edge.owner === 'ASSET_LINEAGE'
      ? { ...edge, target: { kind: 'CHAPTER', id: 'chapter-1', version: 1, digest: 'd'.repeat(64), label: 'x', deleted: false } }
      : edge);
    expect(rejectionCode(() => assetBrowserRelationships({ ...graph, edges })))
      .toBe(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid);
  });

  it('rejects tampered owner self-declarations', () => {
    expect(rejectionCode(() => assetBrowserRelationships({ ...relationshipGraph(), executable: true })))
      .toBe(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid);
    expect(rejectionCode(() => assetBrowserRelationships({ ...relationshipGraph(), graph_kind: 'KNOWLEDGE_GRAPH' })))
      .toBe(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid);
  });

  it('is idempotent: its own decoded projection re-decodes unchanged', () => {
    const decoded = relationshipGraph();
    const again = assetBrowserRelationships(JSON.parse(JSON.stringify(decoded)) as unknown);
    expect(again).toEqual(decoded);
  });

  it('rejects a forged semantics claim on a declared relationship', () => {
    // 服务端原文（声明关系不带 `owner`）被篡改成"这是版权授权"。
    const graph = relationshipGraphPayload();
    const edges = (graph.edges as Record<string, unknown>[]).map(edge => edge.owner === undefined
      ? { ...edge, semantics: 'DECLARED_LINK_IS_A_RIGHTS_GRANT' } : edge);
    expect(rejectionCode(() => assetBrowserRelationships({ ...graph, edges })))
      .toBe(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid);
  });
});
